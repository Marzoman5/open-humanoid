"""Double-support whole-body motions: stand, squat (any depth), wave, and the get-up stub.

The feet stay put; the pelvis moves so the whole-body COM follows a target over the support polygon; the legs follow by
analytic IK. Upper-body joints are free time series.
"""
from __future__ import annotations

import math

import numpy as np

from ..kin import Reference, RobotKin, compensate_com, quat_from_yaw_pitch, smoothstep5
from .common import fill_legs, finish, knee_flex_from, rest_upper_body, set_col, stand_geometry


def feet_world(kin: RobotKin, T: int):
    lg = kin.lg
    z = np.full(T, lg.ankle_h)
    l = np.stack([np.zeros(T), np.full(T, lg.hip_y), z], 1)
    r = np.stack([np.zeros(T), np.full(T, -lg.hip_y), z], 1)
    return l, r


def z_from_flex(kin: RobotKin, flex: np.ndarray, pel_xy: np.ndarray) -> np.ndarray:
    """Pelvis height for a symmetric knee flexion `flex` with the pelvis at `pel_xy` (feet fixed under the origin)."""
    lg = kin.lg
    l2 = lg.L1 ** 2 + lg.L2 ** 2 + 2 * lg.L1 * lg.L2 * np.cos(flex)
    rx = -pel_xy[:, 0]
    ry = np.zeros(len(flex))
    zh = lg.ankle_h + np.sqrt(np.maximum(l2 - rx ** 2 - ry ** 2, 1e-9))
    return zh - lg.hip_z


def double_support(kin: RobotKin, name: str, dt: float, T: int, *, flex=None, pelvis_z=None, com_xy=None, pitch=None,
                   yaw=None, upper: dict | None = None, notes=None, meta=None, iters: int = 5) -> Reference:
    """flex (T,) knee flexion profile OR pelvis_z (T,); com_xy (T,2) COM target (default: foot centre)."""
    lg = kin.lg
    ank_l, ank_r = feet_world(kin, T)
    zeros = np.zeros(T)
    pitch = zeros if pitch is None else pitch
    yaw = zeros if yaw is None else yaw
    foot_c = np.array([lg.foot_off, 0.0])
    com_t = np.tile(foot_c, (T, 1)) if com_xy is None else com_xy

    def build_q(pelvis):
        Q = rest_upper_body(kin, T)
        for n, v in (upper or {}).items():
            set_col(kin, Q, n, v)
        build_q.ok = fill_legs(kin, Q, pelvis, yaw, pitch, ank_l, ank_r, zeros, zeros)
        return Q

    if flex is not None:
        adjust = lambda p: np.concatenate([p[:, :2], z_from_flex(kin, flex, p[:, :2])[:, None]], 1)  # noqa: E731
    else:
        adjust = None
    z0 = pelvis_z if pelvis_z is not None else z_from_flex(kin, np.full(T, knee_flex_from(kin)), np.zeros((T, 2)))
    pelvis0 = np.stack([np.zeros(T), np.zeros(T), z0], 1)
    pelvis, Q, err = compensate_com(kin, build_q, pelvis0, yaw, pitch, com_t, iters=iters, adjust=adjust)
    ref = finish(kin, name, dt, Q, pelvis, yaw, pitch, ok=build_q.ok,
                 notes=(notes or []) + [f"COM tracking error {err * 1000:.2f} mm"], meta=meta)
    ref.stance = np.ones((T, 2), bool)
    return ref


def stand(kin: RobotKin, duration: float = 4.0, dt: float = 0.01) -> Reference:
    T = int(duration / dt) + 1
    return double_support(kin, "stand", dt, T, meta={"duration_s": duration})


def squat(kin: RobotKin, depth_deg: float, dt: float = 0.01, down_s: float = 2.5, hold_s: float = 1.0) -> Reference:
    f0 = knee_flex_from(kin)
    K = math.radians(depth_deg)
    n = lambda s: int(round(s / dt))  # noqa: E731
    pre, d, h = n(0.8), n(down_s), n(hold_s)
    prof = np.concatenate([np.zeros(pre), smoothstep5(np.arange(d) / d), np.ones(h), 1 - smoothstep5(np.arange(d) / d),
                           np.zeros(pre + 1)])
    flex = f0 + (K - f0) * prof
    T = len(flex)
    ref = double_support(kin, f"squat_{int(depth_deg)}", dt, T, flex=flex,
                         meta={"depth_deg": depth_deg, "hold_s": hold_s, "down_s": down_s})
    return ref


# ---------------------------------------------------------------------------------------------- wave
def arm_tip(kin: RobotKin, side: str, q_row, pelvis, quat) -> np.ndarray:
    kin.set_state(q_row, pelvis, quat)
    kin.mj.mj_kinematics(kin.model, kin.data)
    gname = f"grip_{side}"
    try:
        return kin.data.site(gname).xpos.copy()
    except Exception:  # noqa: BLE001
        b = kin.data.body(f"forearm_{side}")
        return b.xpos + b.xmat.reshape(3, 3) @ np.array([0, 0, -kin.robot.geom["forearm"]])


def wave_pose(kin: RobotKin, side: str):
    """Search shoulder pitch/roll/elbow for the arm abducted outward with the forearm raised as high as possible."""
    sgn = 1.0 if side == "l" else -1.0
    j = {b: next((x for x in kin.robot.joints if x["name"] == f"{b}_{side}"), None) for b in ("shoulder_pitch", "shoulder_roll", "elbow")}
    if not all(j.values()):
        return None
    rng = {b: [math.radians(v) for v in j[b]["range"]] for b in j}
    lg = kin.lg
    pel = np.array([0, 0, stand_geometry(kin, knee_flex_from(kin))["pelvis_z"]])
    quat = quat_from_yaw_pitch(0.0, 0.0)[0]
    q0 = rest_upper_body(kin, 1)[0]
    base = kin.stand_q(knee_flex_from(kin))
    q0 = np.where(q0 != 0, q0, base)
    sh_z = None
    best, best_val = None, -1e9
    for p in np.radians(np.arange(-120, 61, 10)):
        for r in np.radians(np.arange(70, 106, 5)):
            for e in np.radians(np.arange(-130, 1, 10)):
                rr, pp, ee = sgn * r, p, e
                if not (rng["shoulder_roll"][0] <= rr <= rng["shoulder_roll"][1] or rng["shoulder_roll"][0] <= rr <= rng["shoulder_roll"][1]):
                    continue
                if not (rng["shoulder_pitch"][0] <= pp <= rng["shoulder_pitch"][1] and rng["elbow"][0] <= ee <= rng["elbow"][1]):
                    continue
                q = q0.copy()
                q[kin.index[f"shoulder_pitch_{side}"]], q[kin.index[f"shoulder_roll_{side}"]], q[kin.index[f"elbow_{side}"]] = pp, rr, ee
                tip = arm_tip(kin, side, q, pel, quat)
                if sh_z is None:
                    sh_z = float(kin.data.body(f"upper_arm_{side}").xpos[2])
                elbow_h = float(kin.data.body(f"forearm_{side}").xpos[2])
                if elbow_h < sh_z - 0.25 * kin.robot.geom["upper_arm"]:      # upper arm must really be abducted/raised
                    continue
                sh = kin.data.body(f"upper_arm_{side}").xpos
                val = (tip[2] - sh[2]) + 0.6 * sgn * (tip[1] - sh[1]) - 0.8 * abs(tip[0] - sh[0])   # high, outward, not forward
                if val > best_val:
                    best, best_val = (pp, rr, ee), val
    return best


def wave(kin: RobotKin, side: str = "r", dt: float = 0.01, duration: float = 7.0, freq_hz: float = 1.25, amp_deg: float = 22.0) -> Reference:
    pose = wave_pose(kin, side)
    f0 = knee_flex_from(kin)
    T = int(duration / dt) + 1
    t = np.arange(T) * dt
    if pose is None:
        ref = double_support(kin, "wave", dt, T, notes=["no abducted-arm pose found: arm joints missing or ranges too small"])
        ref.feasible = False
        return ref
    pp, rr, ee = pose
    ramp = smoothstep5(np.clip((t - 0.6) / 1.2, 0, 1)) * smoothstep5(np.clip((duration - 0.6 - t) / 1.2, 0, 1))
    amp = math.radians(amp_deg)
    ej = next(x for x in kin.robot.joints if x["name"] == f"elbow_{side}")
    lo, hi = math.radians(ej["range"][0]), math.radians(ej["range"][1])
    e0 = float(np.clip(ee, lo + amp, hi - amp))
    osc = amp * np.sin(2 * math.pi * freq_hz * np.maximum(t - 0.6, 0)) * ramp
    rest = rest_upper_body(kin, 1)[0]
    up = {}
    for b_, v in (("shoulder_pitch", pp), ("shoulder_roll", rr)):
        if kin.has(f"{b_}_{side}"):
            r0 = float(rest[kin.index[f"{b_}_{side}"]])
            up[f"{b_}_{side}"] = r0 + (v - r0) * ramp
    up[f"elbow_{side}"] = ARM_E0 + (e0 - ARM_E0) * ramp + osc
    # head follows the hand a little, waist turns slightly towards the waving side (if present)
    if kin.has("neck_yaw"):
        up["neck_yaw"] = (1.0 if side == "l" else -1.0) * math.radians(20) * ramp
    if kin.has("waist_yaw"):
        up["waist_yaw"] = (1.0 if side == "l" else -1.0) * math.radians(10) * ramp
    return double_support(kin, "wave", dt, T, upper=up, meta={"side": side, "freq_hz": freq_hz, "amp_deg": amp_deg,
                                                               "pose_deg": [round(math.degrees(x), 1) for x in pose]})


ARM_E0 = math.radians(-20.0)


def getup_stub(kin: RobotKin, dt: float = 0.01) -> Reference:
    """Stand-up-from-fall is not designed yet (P5). Returns an infeasible placeholder so reports list it explicitly."""
    ref = stand(kin, 1.0, dt)
    ref.name = "getup"
    ref.feasible = False
    ref.notes.append("STUB: stand-up-from-fall is not modelled in the concept loop (needs contact-rich optimisation; P5)")
    ref.meta["stub"] = True
    return ref
