"""Table-height pickup of a light object (default 150 g, 40 mm cylinder) with the right hand.

Plan: squat just deep enough that the hand can reach, reach to a pre-grasp point (jaws open), advance, close the gripper
(torque-limited), lift 40 mm, stand back up holding the object. Arm joints come from damped-least-squares IK on the
MuJoCo model; the legs/pelvis from the double-support COM-balancing machinery. Without a wrist the finger direction is
whatever the 3-DOF arm gives; the lateral-jaw alignment error is reported rather than hidden.
"""
from __future__ import annotations

import math

import numpy as np

from .. import config
from ..kin import Reference, RobotKin, quat_from_yaw_pitch, smoothstep5
from .common import GRIP_CLOSED, knee_flex_from, rest_upper_body, set_col
from .posture import double_support, z_from_flex
from .smoothing import smooth_series

OBJ = {"mass_kg": 0.150, "radius_m": 0.020, "half_height_m": 0.025, "friction": 1.0}   # requirement R5: <= 150 g can/ball/small toy


def solve_ik(kin: RobotKin, Q_row: np.ndarray, pel: np.ndarray, quat: np.ndarray, site: str, target: np.ndarray,
             joints: list[str], iters: int = 120, damping: float = 2e-3, tol: float = 5e-4):
    """DLS position IK for `site` using the listed joints (names). Returns (Q_row, residual_m)."""
    mj, m, d = kin.mj, kin.model, kin.data
    cols = [int(kin.dadr[kin.index[j]]) for j in joints]
    ids = [kin.index[j] for j in joints]
    lim = []
    for j in joints:
        jd = next(x for x in kin.robot.joints if x["name"] == j)
        lim.append((math.radians(jd["range"][0]), math.radians(jd["range"][1])))
    Q = Q_row.copy()
    jac = np.zeros((3, m.nv))
    err = 1e9
    for _ in range(iters):
        kin.set_state(Q, pel, quat)
        mj.mj_kinematics(m, d)
        mj.mj_comPos(m, d)
        p = d.site(site).xpos.copy()
        e = target - p
        err = float(np.linalg.norm(e))
        if err < tol:
            break
        mj.mj_jacSite(m, d, jac, None, d.site(site).id)
        J = jac[:, cols]
        dq = J.T @ np.linalg.solve(J @ J.T + damping * np.eye(3), e)
        step = np.clip(dq, -0.15, 0.15)
        for k, i in enumerate(ids):
            Q[i] = np.clip(Q[i] + step[k], lim[k][0], lim[k][1])
    return Q, err


def pickup(kin: RobotKin, dt: float = 0.01, table_height_frac: float = 0.36, table_height_m: float | None = None,
           side: str = "r") -> Reference:
    robot = kin.robot
    notes: list[str] = []
    if not (kin.has(f"gripper_{side}") and kin.has(f"elbow_{side}") and kin.has(f"shoulder_pitch_{side}")):
        ref = double_support(kin, "pickup", dt, 101, notes=["no gripper/arm joints: pickup not possible"])
        ref.feasible = False
        return ref
    lg = kin.lg
    h = robot.height
    z_t = table_height_m if table_height_m else table_height_frac * h
    f0 = knee_flex_from(kin)
    arm = [f"shoulder_pitch_{side}", f"elbow_{side}"] + ([f"shoulder_roll_{side}"] if kin.has(f"shoulder_roll_{side}") else []) \
        + ([f"wrist_{side}"] if kin.has(f"wrist_{side}") else [])
    grip_site = f"grip_{side}"
    sy = 1.0 if side == "l" else -1.0
    q_open = 0.058
    r_o, hh = OBJ["radius_m"], OBJ["half_height_m"]
    z_obj = z_t + hh
    # reach of the arm from the shoulder (upper arm + forearm to the grip point)
    g = robot.geom
    hand = max(0.045, 0.09 * h)
    L_arm = g["upper_arm"] + (g["forearm"] - hand) + 0.62 * hand

    def pose_at_flex(K):
        r0 = double_support(kin, "tmp", dt, 2, flex=np.full(2, K))
        return r0.base_pos[0], r0.base_quat[0], r0.q[0]

    rest0 = rest_upper_body(kin, 1)[0]

    def object_for(sh, Kq):
        """Object placed ahead of the shoulder, its open-gap centre in the shoulder plane (so the arm needs no lateral reach)."""
        drop = max(sh[2] - (z_obj + 0.5 * hh), 0.0)
        reach_x = math.sqrt(max((0.85 * L_arm) ** 2 - drop ** 2, 0.0))
        return np.array([sh[0] + min(reach_x, 0.75 * L_arm), sh[1] + sy * q_open / 2, z_obj])

    # smallest squat from which the grasp pose is actually reachable by IK (checked, not guessed)
    chosen = None
    last = None
    for Kd in np.arange(math.degrees(f0), 121, 5):
        K = math.radians(Kd)
        pel, quat, Q = pose_at_flex(K)
        kin.set_state(Q, pel, quat)
        kin.mj.mj_kinematics(kin.model, kin.data)
        sh = kin.data.body(f"upper_arm_{side}").xpos.copy()
        last = (K, pel, quat, Q, sh)
        Qt = Q.copy()
        for a_ in arm:
            Qt[kin.index[a_]] = rest0[kin.index[a_]]
        tgt0 = object_for(sh, K) - np.array([0.0, sy * q_open / 2, 0.0])
        _, err0 = solve_ik(kin, Qt, pel, quat, grip_site, tgt0, arm)
        if err0 < 0.002 and sh[2] - (z_obj + 0.5 * hh) <= 0.70 * L_arm:
            chosen = last
            break
    if chosen is None:
        notes.append("arm too short / table too low: no squat up to 120 deg brings the hand within reach")
        chosen = last
    K, pel, quat, Q, sh = chosen
    obj = object_for(sh, K)

    # ---- timeline
    n = lambda s: int(round(s / dt))  # noqa: E731
    # gripper timing is set by the servo: 45 mm of jaw travel on a 12 mm/rad pinion is 3.75 rad, so the jaw takes 3 s to close and 3.5 s to open (peak servo speed below 3 rad/s)
    marks = {"stand": 0.8, "down": 3.0, "raise": 4.3, "pre": 6.0, "grasp": 7.4, "closed": 10.4, "lift": 11.4, "up": 13.6, "end": 14.6}
    T = n(marks["end"]) + 1
    t = np.arange(T) * dt

    def prof(a, b):
        return smoothstep5(np.clip((t - a) / max(b - a, 1e-9), 0, 1))

    flex = f0 + (K - f0) * prof(marks["stand"], marks["down"]) - (K - f0) * prof(marks["lift"], marks["up"])

    def upper_from(waypoints):
        """waypoints: list of (time, Q_arm dict) -> upper dict of series (smoothstep between consecutive waypoints)."""
        up = {}
        names = set()
        for _, qd in waypoints:
            names |= set(qd)
        for nme in names:
            ser = np.zeros(T)
            ts = [w[0] for w in waypoints]
            vs = [w[1].get(nme, 0.0) for w in waypoints]
            for k in range(len(ts) - 1):
                m = (t >= ts[k]) & (t <= ts[k + 1])
                s = smoothstep5((t[m] - ts[k]) / max(ts[k + 1] - ts[k], 1e-9))
                ser[m] = vs[k] + (vs[k + 1] - vs[k]) * s
            ser[t < ts[0]] = vs[0]
            ser[t > ts[-1]] = vs[-1]
            up[nme] = ser
        return up

    rest = rest_upper_body(kin, 1)[0]
    rest_arm = {a: float(rest[kin.index[a]]) for a in arm}
    grip_rest = GRIP_CLOSED
    obj_c = obj.copy()
    wp_world: dict[str, np.ndarray] = {}
    sol: dict[str, dict] = {}
    def pelvis_at(ref_pel, ref_quat, time_s):
        i = min(int(round(time_s / dt)), len(ref_pel) - 1)
        return ref_pel[i], ref_quat[i]

    ref_pel, ref_quat = None, None
    up_series = {}
    resid = {}
    for it in range(3):
        # pelvis trajectory for the current arm plan (first pass: arm at rest)
        base_ref = double_support(kin, "pickup", dt, T, flex=flex, upper=up_series or None)
        ref_pel, ref_quat = base_ref.base_pos, base_ref.base_quat
        Qs = base_ref.q.copy()
        pel_g, q_g = pelvis_at(ref_pel, ref_quat, marks["grasp"])
        Qg = Qs[int(marks["grasp"] / dt)].copy()
        for a in arm:
            Qg[kin.index[a]] = rest_arm[a]
        # grasp: object centre minus the half-opening offset along the hand's lateral axis (iterated)
        tgt = obj_c.copy()
        Qg, e = solve_ik(kin, Qg, pel_g, q_g, grip_site, tgt, arm)
        for _ in range(2):
            kin.set_state(Qg, pel_g, q_g)
            kin.mj.mj_kinematics(kin.model, kin.data)
            Rh = kin.data.body(f"hand_{side}").xmat.reshape(3, 3)
            ylat = Rh[:, 1]
            tgt = obj_c - ylat * sy * (q_open / 2)   # object centred in the open gap (8 mm clearance each side); closing slides it 8 mm to the fixed jaw
            Qg, e = solve_ik(kin, Qg, pel_g, q_g, grip_site, tgt, arm)
        kin.set_state(Qg, pel_g, q_g)
        kin.mj.mj_kinematics(kin.model, kin.data)
        Rh = kin.data.body(f"hand_{side}").xmat.reshape(3, 3)
        u = -Rh[:, 2]
        lateral_err = math.degrees(math.acos(min(1.0, abs(Rh[1, 1]))))
        pre_target = tgt - 0.05 * u
        Qp, e_p = solve_ik(kin, Qg, pel_g, q_g, grip_site, pre_target, arm)
        lift_target = tgt + np.array([0, 0, 0.04])
        Ql, e_l = solve_ik(kin, Qg, pel_g, q_g, grip_site, lift_target, arm)
        resid = {"grasp_ik_m": e, "pregrasp_ik_m": e_p, "lift_ik_m": e_l, "jaw_axis_off_horizontal_deg": lateral_err}
        # approach: come in high and behind, then follow the straight line along the finger direction (joint-space interpolation
        # between pre-grasp and grasp swings the fingers through the object)
        Qhi, _ = solve_ik(kin, Qp, pel_g, q_g, grip_site, pre_target + np.array([0, 0, 0.03]), arm)
        line, Qprev = [], Qp
        for sfrac in (0.25, 0.5, 0.75, 1.0):
            Qs, _ = solve_ik(kin, Qprev, pel_g, q_g, grip_site, tgt - 0.05 * u * (1 - sfrac), arm)
            line.append((marks["pre"] + sfrac * (marks["grasp"] - marks["pre"]), {a: float(Qs[kin.index[a]]) for a in arm}))
            Qprev = Qs
        # first raise the hand straight up from the rest position until it is clear of the table top, only then reach forward
        Qrest = Qg.copy()
        for a in arm:
            Qrest[kin.index[a]] = rest_arm[a]
        kin.set_state(Qrest, pel_g, q_g)
        kin.mj.mj_kinematics(kin.model, kin.data)
        g0 = kin.data.site(grip_site).xpos.copy()
        raise_target = np.array([g0[0], g0[1], max(z_t + 0.08, pre_target[2] + 0.03)])
        Qr, _ = solve_ik(kin, Qrest, pel_g, q_g, grip_site, raise_target, arm)
        wp = [(0.0, rest_arm), (marks["down"], rest_arm), (marks["raise"], {a: float(Qr[kin.index[a]]) for a in arm}),
              (marks["pre"] - 0.9, {a: float(Qhi[kin.index[a]]) for a in arm}),
              (marks["pre"], {a: float(Qp[kin.index[a]]) for a in arm}), *line,
              (marks["closed"], {a: float(Qg[kin.index[a]]) for a in arm}),
              (marks["lift"], {a: float(Ql[kin.index[a]]) for a in arm}), (marks["end"], {a: float(Ql[kin.index[a]]) for a in arm})]
        up_series = upper_from(wp)
        for a in arm:    # the arm may not ask for more speed than the shared limit (same 3 rad/s as the dance)
            jd = next(x for x in kin.robot.joints if x["name"] == a)
            up_series[a] = smooth_series(up_series[a], dt, config.motions()["dance"]["v_limit_rad_s"], math.radians(jd["range"][0]), math.radians(jd["range"][1]))
        g_ser = np.full(T, grip_rest)
        g_ser += (q_open - grip_rest) * prof(marks["stand"], marks["raise"])
        g_ser += (0.005 - q_open) * prof(marks["grasp"], marks["closed"])
        up_series[f"gripper_{side}"] = g_ser

    for k, v in resid.items():
        if k.endswith("_m") and v > 0.004:
            notes.append(f"{k} = {v * 1000:.1f} mm (target not reached with the available arm joints)")
    if resid["jaw_axis_off_horizontal_deg"] > 25:
        notes.append(f"jaw axis {resid['jaw_axis_off_horizontal_deg']:.0f} deg off horizontal: no wrist, the grasp may be unreliable")
    ref = double_support(kin, "pickup", dt, T, flex=flex, upper=up_series, notes=notes,
                         meta={"squat_deg": round(math.degrees(K), 1), "table_height_m": round(z_t, 4),
                               "object_m": OBJ["mass_kg"], "object_xyz": [round(float(x), 4) for x in obj],
                               "arm_reach_m": round(L_arm, 4), **{k: round(float(v), 4) for k, v in resid.items()},
                               "marks_s": marks})
    # scene: table + object
    tx_front = obj[0] - 0.07
    # the table is a thin slab on legs that stay outside the model: the feet and knees of a squatting robot pass under it
    scene_xml = f"""    <body name="table" pos="{obj[0] + 0.03:.4f} {obj[1]:.4f} {z_t - 0.01:.4f}">
      <geom name="table_top" type="box" size="0.06 0.09 0.01" class="contact" rgba="0.55 0.45 0.35 1"/>
    </body>
    <body name="obj" pos="{obj[0]:.4f} {obj[1]:.4f} {z_t + hh + 0.0005:.4f}">
      <freejoint name="obj_free"/>
      <geom name="obj_geom" type="cylinder" size="{r_o} {hh}" mass="{OBJ['mass_kg']}" class="contact" friction="{OBJ['friction']} 0.02 0.01" rgba="0.8 0.2 0.2 1"/>
    </body>"""
    tx_front = obj[0] - 0.03
    ref.scene = {"xml": scene_xml, "object": "obj", "object_z0": float(z_t + hh), "table_z": float(z_t), "table_front_x": float(tx_front)}
    ref.meta["lift_marks_s"] = [marks["lift"], marks["end"]]
    return ref
