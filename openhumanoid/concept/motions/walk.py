"""Walking reference: footstep plan -> ZMP reference -> LIPM preview control -> COM-compensated pelvis -> leg IK.

Forward, backward and turn-in-place share one generator (a unicycle footstep plan). Everything is parameterised by the
robot's own geometry (leg lengths, foot size, hip width, COM height) and a Froude-scaled step time.
"""
from __future__ import annotations

import math

import numpy as np

from .. import config
from ..kin import RobotKin, smoothstep5
from .common import fill_legs, finish, knee_flex_from, rest_upper_body, set_col, stand_geometry
from .lipm import PreviewController


def frozen_gait(step_time_s: float | None = None) -> dict:
    """Walk spec shared by every candidate (thresholds.yaml `motions.walk`): absolute speed, step time, turn rate, clearance.
    `step_time_s` picks another member of the frozen step-time SET (gait_sweep.step_time_s): speed and turn rate stay, so the
    step length and the yaw per step scale with it, and the number of steps keeps the walk about as long as the default."""
    w = config.walk_spec()
    st = float(step_time_s) if step_time_s else float(w["step_time_s"])
    n = max(int(round(w["n_steps"] * w["step_time_s"] / st)), 4)
    return {"step_len": w["speed_mps"] * st, "step_time": st, "clearance": w["clearance_m"],
            "ds_fraction": w["ds_fraction"], "turn_per_step": w["turn_rate_rad_s"] * st,
            "arm_swing": w["arm_swing"], "n_steps": n}


def chosen_step_time(kin: RobotKin) -> float | None:
    """The step time this robot's concept selected from the frozen set (None: the default)."""
    return (kin.robot.concept.get("gait") or {}).get("step_time_s")


def walk(kin: RobotKin, mode: str = "forward", n_steps: int | None = None, dt: float = 0.01, *, landing_shift: int = 0,
         capture_n: int | None = None, capture_m: float = 0.0, **over) -> Reference:
    """mode: forward | backward | turn. `over` overrides frozen gait keys (stress variants and the diagnostic ladder).
    landing_shift: swing foot lands this many samples (10 ms each) later (+) or earlier (-) than the ZMP plan assumes.
    capture_n / capture_m: swing foot of step `capture_n` lands `capture_m` further out sideways (one lateral capture step)."""
    st_over = over.get("step_time")
    gait = {**frozen_gait(st_over if st_over is not None else chosen_step_time(kin)), **{k: v for k, v in over.items() if v is not None}}
    n_steps = n_steps or int(gait["n_steps"])
    lg = kin.lg
    L = {"forward": 1.0, "backward": -1.0, "turn": 0.0}[mode] * gait["step_len"]
    dpsi = gait["turn_per_step"] if mode == "turn" else 0.0
    flex = knee_flex_from(kin)
    sg = stand_geometry(kin, flex)
    n_step = int(round(gait["step_time"] / dt))
    n_ds = max(2, int(round(gait["ds_fraction"] * n_step)))
    n_ss = n_step - n_ds
    n_init, n_end = int(0.9 / dt), int(1.0 / dt)
    S = n_steps
    T = n_init + S * n_step + n_end
    hy = lg.hip_y
    side_sign = {"l": 1.0, "r": -1.0}

    def pose(c, psi, side):
        return np.array([c[0] - side_sign[side] * hy * math.sin(psi), c[1] + side_sign[side] * hy * math.cos(psi), psi])

    # landings: step n swings the foot opposite to support n (support 0 = left)
    support = ["l" if n % 2 == 0 else "r" for n in range(S)]
    land = []
    c, psi = np.zeros(2), 0.0
    for n in range(S):
        if n == 0:
            c = c + np.array([math.cos(psi), math.sin(psi)]) * L / 2
        elif n < S - 1:
            c = c + np.array([math.cos(psi), math.sin(psi)]) * L
        if n < S - 1:
            psi = psi + dpsi
        lp = pose(c.copy(), psi, "r" if support[n] == "l" else "l")
        if capture_n is not None and n == capture_n:
            sw = "r" if support[n] == "l" else "l"
            lp = lp + np.array([-side_sign[sw] * capture_m * math.sin(psi), side_sign[sw] * capture_m * math.cos(psi), 0.0])
        land.append(lp)
    init = {"l": pose(np.zeros(2), 0.0, "l"), "r": pose(np.zeros(2), 0.0, "r")}

    # foot trajectories (x, y, z, yaw) at dt
    foot = {s: np.tile(np.array([init[s][0], init[s][1], 0.0, 0.0]), (T, 1)) for s in "lr"}
    cur = {s: init[s].copy() for s in "lr"}
    stance_pose = []                                   # pose of the support foot during support n
    for n in range(S):
        sup = support[n]
        swing = "r" if sup == "l" else "l"
        t0 = n_init + n * n_step
        stance_pose.append(cur[sup].copy())
        a, b = cur[swing], land[n]
        n_sw = max(4, min(n_ss + landing_shift, n_step - 1))
        s = smoothstep5(np.arange(n_sw) / max(n_sw - 1, 1))
        xs = a[0] + (b[0] - a[0]) * s
        ys = a[1] + (b[1] - a[1]) * s
        ps = a[2] + (b[2] - a[2]) * s
        zs = gait["clearance"] * 0.5 * (1 - np.cos(2 * math.pi * np.arange(n_sw) / max(n_sw - 1, 1)))
        foot[swing][t0:t0 + n_sw] = np.stack([xs, ys, zs, ps], 1)
        foot[swing][t0 + n_sw:] = [b[0], b[1], 0.0, b[2]]
        cur[swing] = b.copy()
    final_mid = 0.5 * (cur["l"][:2] + cur["r"][:2])

    inboard = float(gait.get("zmp_inboard", 0.0))          # ZMP target this far towards the midline from the foot centre (0 for the frozen gait; a wide, knock-kneed stance like Open Duck Mini's needs it)

    def centre(p):
        c = p[:2] + lg.foot_off * np.array([math.cos(p[2]), math.sin(p[2])])
        if inboard:
            c = c - inboard * math.copysign(1.0, p[1]) * np.array([-math.sin(p[2]), math.cos(p[2])])
        return c

    zmp = np.zeros((T, 2))
    mid0 = 0.5 * (centre(init["l"]) + centre(init["r"]))
    z_seq = [centre(p) for p in stance_pose]
    z_end = 0.5 * (centre(cur["l"]) + centre(cur["r"]))
    zmp[:] = mid0
    ramp = int(0.4 / dt)
    for i in range(ramp):
        zmp[n_init - ramp + i] = mid0 + (z_seq[0] - mid0) * smoothstep5((i + 1) / ramp)
    for n in range(S):
        t0 = n_init + n * n_step
        zmp[t0:t0 + n_ss] = z_seq[n]
        nxt = z_seq[n + 1] if n + 1 < S else z_end
        for i in range(n_ds):
            zmp[t0 + n_ss + i] = z_seq[n] + (nxt - z_seq[n]) * smoothstep5((i + 1) / n_ds)
    zmp[n_init + S * n_step:] = z_end

    # whole-body COM height from the stand pose
    Q0 = rest_upper_body(kin, 1)
    ones = np.ones(1)
    ank0 = {s: np.array([[init[s][0], init[s][1], lg.ankle_h]]) for s in "lr"}
    pel0 = np.array([[0.0, 0.0, sg["pelvis_z"]]])
    fill_legs(kin, Q0, pel0, 0 * ones, 0 * ones, ank0["l"], ank0["r"], 0 * ones, 0 * ones)
    from ..kin import quat_from_yaw_pitch
    com0 = kin.com(Q0[0], pel0[0], quat_from_yaw_pitch(0 * ones, 0 * ones)[0])
    zc = float(com0[2])
    off0 = com0[:2] - pel0[0, :2]
    pc = PreviewController(zc, dt)
    cx, _ = pc.run(zmp[:, 0], (com0[0], 0, 0))
    cy, _ = pc.run(zmp[:, 1], (com0[1], 0, 0))
    com_t = np.stack([cx, cy], 1)

    yaw = 0.5 * (foot["l"][:, 3] + foot["r"][:, 3])
    pitch = np.zeros(T)
    t = np.arange(T) * dt
    arm = np.zeros((T, 1))
    swing_amp = gait["arm_swing"] * 1.0
    arm_sig = (foot["l"][:, 0] - foot["r"][:, 0]) / max(abs(L), 1e-6) if L else np.zeros(T)

    def build_q(pelvis):
        Q = rest_upper_body(kin, T)
        ank_l = np.stack([foot["l"][:, 0], foot["l"][:, 1], lg.ankle_h + foot["l"][:, 2]], 1)
        ank_r = np.stack([foot["r"][:, 0], foot["r"][:, 1], lg.ankle_h + foot["r"][:, 2]], 1)
        build_q.ok = fill_legs(kin, Q, pelvis, yaw, pitch, ank_l, ank_r, foot["l"][:, 3], foot["r"][:, 3])
        if L:
            set_col(kin, Q, "shoulder_pitch_l", np.clip(swing_amp * arm_sig * 0.4, -0.5, 0.5))
            set_col(kin, Q, "shoulder_pitch_r", np.clip(-swing_amp * arm_sig * 0.4, -0.5, 0.5))
        return Q

    pelvis0 = np.stack([com_t[:, 0] - off0[0], com_t[:, 1] - off0[1], np.full(T, sg["pelvis_z"])], 1)
    from ..kin import compensate_com
    pelvis, Q, err = compensate_com(kin, build_q, pelvis0, yaw, pitch, com_t, iters=4)
    ref = finish(kin, f"walk_{mode}", dt, Q, pelvis, yaw, pitch, ok=build_q.ok,
                 notes=[f"COM tracking error after compensation {err * 1000:.2f} mm"],
                 meta={"mode": mode, "steps": S, "step_len_m": L, "step_time_s": gait["step_time"], "zc_m": zc,
                       "speed_mps": abs(L) / gait["step_time"], "turn_rate_rad_s": dpsi / gait["step_time"],
                       "clearance_m": gait["clearance"], "gait": {k: float(v) for k, v in gait.items()}})
    ref.stance = np.stack([foot["l"][:, 2] < 1e-4, foot["r"][:, 2] < 1e-4], 1)
    ref.meta["walk_window"] = [n_init * dt, (n_init + S * n_step) * dt]
    ref.aux = {"foot": foot, "com": com_t, "zmp": zmp, "support": support, "land": land, "init": init, "dt": dt, "n_init": n_init,
               "n_step": n_step, "n_ss": n_ss, "n_ds": n_ds, "zc": zc, "off0": off0, "pelvis_z": sg["pelvis_z"], "gait": gait, "n_steps": S}
    return ref
