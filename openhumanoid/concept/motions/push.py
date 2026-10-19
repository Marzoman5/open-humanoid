"""Push recovery (requirement R10: balance recovery / fall prevention is a MUST).

Four reference cases, each a LIPM-based recovery plan after a defined velocity impulse, replayed in MuJoCo with the push applied
to the free base:

  ankle_fwd     small forward push, answered by shifting the centre of pressure (COP) inside the foot ("ankle strategy")
  hip_fwd       larger forward push; the COP saturates at the toe edge and the trunk pitches about the hips to add the missing
                moment ("hip strategy", a flywheel term  I*theta_ddot / (M g)  on the effective COP)
  capture_fwd   forward push beyond what the stance foot plus the trunk can absorb: one capture step to the capture point
  capture_lat   lateral push: one lateral capture step with the foot on the pushed side

DEFINED PUSH. The impulse is a velocity change of the whole body, dv, so the impulse is J = M_total * dv. It is expressed in
capture-point units so the SAME non-dimensional push applies to any height or mass:  dv = k * margin * w0  with
w0 = sqrt(g / z_com), margin = half the foot length (forward) or the stance half-width (lateral), and k = 0.5 (ankle),
1.2 (hip), 2.5 (capture forward), 2.0 (capture lateral) (thresholds.yaml `motions.push`). For a 0.45 m robot that is
roughly 0.14 / 0.34 / 0.7 / 0.5 m/s. Precedent in research/methods/domain_randomization_ranges.yaml: Open Duck Mini adds
0.1-1.0 m/s to the base velocity, MuJoCo Playground G1 / Berkeley / T1 0.1-2.0 m/s, ToddlerBot pushes of 1-3 N for 0.2 s.

LATENCY. The controller reacts d_r = servo command delay + one control period + sensing latency after the push; until then the
COM falls freely (COP at the nominal point). This delay is what the capture-step landing point and the strategy margins are
computed with.

The plan assumes an ideal state estimate and COM-height LIPM dynamics; it is a feasibility/demand calculation for the actuators,
not a controller.
"""
from __future__ import annotations

import math

import numpy as np

from .. import config
from ..kin import Reference, RobotKin, compensate_com, quat_from_yaw_pitch, smoothstep5
from .common import fill_legs, finish, knee_flex_from, rest_upper_body, stand_geometry

G = 9.81
KINDS = ("ankle_fwd", "hip_fwd", "capture_fwd", "capture_lat")


def trunk_inertia_about_hip(kin: RobotKin, Q0, pel0, quat0) -> float:
    """Inertia (kg m^2) of everything above the legs about the pelvis y axis (what the hip strategy swings)."""
    kin.set_state(Q0, pel0, quat0)
    kin.mj.mj_kinematics(kin.model, kin.data)
    kin.mj.mj_comPos(kin.model, kin.data)
    m, d = kin.model, kin.data
    axis = d.body("pelvis").xpos.copy()
    total = 0.0
    for i in range(m.nbody):
        nm = m.body(i).name
        if nm.startswith(("thigh", "shank", "foot")) or nm == "world":
            continue
        r = d.xipos[i] - axis
        total += m.body_mass[i] * (r[0] ** 2 + r[2] ** 2) + float(np.mean(m.body_inertia[i]))
    return total


def reaction_delay_s(kin: RobotKin) -> float:
    cfg = config.motions()["push"]
    servo = max(s.delay_s for s in kin.robot.servo.values())
    return servo + cfg["control_period_s"] + cfg["sensing_latency_s"]


def push_vector(kin: RobotKin, kind: str, zc: float) -> np.ndarray:
    cfg = config.motions()["push"]
    w0 = math.sqrt(G / zc)
    lg = kin.lg
    if kind == "capture_lat":
        return np.array([0.0, cfg["capture_lat_k"] * (lg.foot_w / 2 + 0.5 * lg.hip_y) * w0, 0.0])
    k = {"ankle_fwd": cfg["ankle_k"], "hip_fwd": cfg["hip_k"], "capture_fwd": cfg["capture_fwd_k"]}[kind]
    return np.array([k * (lg.foot_len / 2) * w0, 0.0, 0.0])


def push_case(kin: RobotKin, kind: str, dt: float = 0.005, push_scale: float = 1.0) -> Reference:
    assert kind in KINDS
    cfg = config.motions()["push"]
    lg = kin.lg
    flex = knee_flex_from(kin)
    sg = stand_geometry(kin, flex)
    t_push = 1.0
    T_total = 1.0 + (4.5 if kind.startswith("capture") else 4.0)
    T = int(round(T_total / dt)) + 1
    t = np.arange(T) * dt
    i_push = int(round(t_push / dt))

    # nominal stand, COM height, mass, trunk inertia
    ones = np.ones(1)
    Q0 = rest_upper_body(kin, 1)
    ank0 = {"l": np.array([[0.0, lg.hip_y, lg.ankle_h]]), "r": np.array([[0.0, -lg.hip_y, lg.ankle_h]])}
    pel0 = np.array([[0.0, 0.0, sg["pelvis_z"]]])
    fill_legs(kin, Q0, pel0, 0 * ones, 0 * ones, ank0["l"], ank0["r"], 0 * ones, 0 * ones)
    quat0 = quat_from_yaw_pitch(0 * ones, 0 * ones)[0]
    com0 = kin.com(Q0[0], pel0[0], quat0)
    zc = float(com0[2])
    off0 = com0[:2] - pel0[0, :2]
    M = float(sum(kin.model.body_mass))
    I_tr = trunk_inertia_about_hip(kin, Q0[0], pel0[0], quat0)
    w0 = math.sqrt(G / zc)
    n_pt = com0[:2].copy()                                   # nominal COM = foot-centre line
    fc = {"l": np.array([lg.foot_off, lg.hip_y]), "r": np.array([lg.foot_off, -lg.hip_y])}
    cf = cfg["cop_margin_frac"]
    mx, my = cf * lg.foot_len / 2, cf * lg.foot_w / 2
    dv = push_vector(kin, kind, zc) * push_scale
    d_r = reaction_delay_s(kin)
    K = cfg["dcm_gain"]
    th_max = math.radians(cfg["trunk_pitch_max_deg"])
    alpha_max = cfg["trunk_alpha_max_rad_s2"]

    c = np.zeros((T, 2)); v = np.zeros((T, 2)); p = np.zeros((T, 2)); th = np.zeros(T)
    c[0] = n_pt
    thv = 0.0
    foot = {s: np.tile(np.array([0.0, fc[s][1], 0.0]), (T, 1)) for s in "lr"}     # ankle x, y, lift (feet centre = ankle + foot_off in x)
    foot["l"][:, 1], foot["r"][:, 1] = lg.hip_y, -lg.hip_y
    notes, meta = [], {}
    swing = support = None
    land = None
    t_land = None
    ds_poly = None
    if kind.startswith("capture"):
        swing, support = ("r", "l") if kind == "capture_fwd" else ("l", "r")
    n_react = i_push + int(round(d_r / dt))
    n_land = None
    for k in range(T - 1):
        ck, vk = c[k], v[k]
        if k == i_push:
            vk = vk + dv[:2]
            v[k] = vk
        xi = ck + vk / w0
        pk = n_pt.copy()
        ang = 0.0
        if k >= n_react:
            if kind in ("ankle_fwd", "hip_fwd"):
                pd = n_pt + (1 + K) * (xi - n_pt)
                pc = np.array([np.clip(pd[0], n_pt[0] - mx, n_pt[0] + mx), np.clip(pd[1], -lg.hip_y - my, lg.hip_y + my)])
                pk = pc
                if kind == "hip_fwd":
                    extra = pd[0] - pc[0]
                    if abs(extra) > 1e-9:
                        ang = float(np.clip(extra * M * G / I_tr, -alpha_max, alpha_max))
                    else:
                        ang = -2 * 0.9 * 10.0 * thv - 100.0 * th[k]
                    if (th[k] >= th_max and ang > 0) or (th[k] <= -th_max and ang < 0):
                        ang = 0.0
                        thv *= 0.9
            else:
                if n_land is None:
                    n_land = k + int(round(cfg["capture_swing_s"] / dt))
                    # simulate the single-support phase forward to find the capture point at landing
                    cc, vv = ck.copy(), vk.copy()
                    sf = fc[support]
                    for j in range(k, n_land):
                        pp = _ss_cop(kind, sf, mx, my, cc, vv, w0, K, n_pt)
                        acc = w0 ** 2 * (cc - pp)
                        vv = vv + acc * dt
                        cc = cc + vv * dt
                    xi_land = cc + vv / w0
                    tgt_center = xi_land + (np.array([cfg["land_margin_m"], 0.0]) if kind == "capture_fwd" else np.array([0.0, math.copysign(cfg["land_margin_m"], dv[1])]))
                    if kind == "capture_fwd":
                        tgt_center[1] = fc[swing][1]
                    else:
                        tgt_center[0] = fc[swing][0]
                    land = np.array([tgt_center[0] - lg.foot_off, tgt_center[1]])
                    k_start = k
                    a0 = foot[swing][k_start, :2].copy()
                    meta.update({"t_step_start_s": float(t[k_start]), "t_land_s": float(t[n_land]), "landing_ankle_xy": [float(land[0]), float(land[1])],
                                 "capture_point_xy": [float(xi_land[0]), float(xi_land[1])]})
                if k < n_land:
                    pk = _ss_cop(kind, fc[support], mx, my, ck, vk, w0, K, n_pt)
                else:
                    if ds_poly is None:
                        fcs = {support: fc[support], swing: land + np.array([lg.foot_off, 0.0])}
                        xs = [fcs["l"][0], fcs["r"][0]]; ys = [fcs["l"][1], fcs["r"][1]]
                        ds_poly = (min(xs) - mx, max(xs) + mx, min(ys) - my, max(ys) + my)
                        ds_center = np.array([np.mean(xs), np.mean(ys)])
                    pd = ds_center + (1 + K) * (xi - ds_center)
                    pk = np.array([np.clip(pd[0], ds_poly[0], ds_poly[1]), np.clip(pd[1], ds_poly[2], ds_poly[3])])
        p[k] = pk
        a = w0 ** 2 * (ck - pk) - np.array([I_tr * ang / (M * zc), 0.0])
        v[k + 1] = vk + a * dt
        c[k + 1] = ck + v[k + 1] * dt
        thv = thv + ang * dt
        th[k + 1] = th[k] + thv * dt
        if abs(th[k + 1]) > th_max:
            th[k + 1] = math.copysign(th_max, th[k + 1]); thv = 0.0
    p[-1] = p[-2]
    # swing foot trajectory
    if kind.startswith("capture") and n_land is not None:
        k0 = n_react
        n_sw = n_land - k0
        s = smoothstep5(np.arange(n_sw + 1) / n_sw)
        a0 = np.array([0.0, fc[swing][1]])
        foot[swing][k0:n_land + 1, 0] = a0[0] + (land[0] - a0[0]) * s
        foot[swing][k0:n_land + 1, 1] = a0[1] + (land[1] - a0[1]) * s
        foot[swing][k0:n_land + 1, 2] = cfg["capture_clearance_m"] * 0.5 * (1 - np.cos(2 * math.pi * np.arange(n_sw + 1) / n_sw))
        foot[swing][n_land + 1:, 0], foot[swing][n_land + 1:, 1], foot[swing][n_land + 1:, 2] = land[0], land[1], 0.0

    # outcome of the plan
    xi_end = c[-1] + v[-1] / w0
    ctr = ds_center if ds_poly is not None else n_pt
    recovered = bool(np.linalg.norm(xi_end - ctr) < 0.35 * lg.foot_len / 2 and np.abs(c - n_pt).max() < 0.25 and np.abs(c[:, 0] - n_pt[0]).max() < 0.5)
    margin_x = lg.foot_len / 2
    notes.append(f"push dv = {np.round(dv[:2], 3).tolist()} m/s, J = {M * np.linalg.norm(dv):.2f} N.s; reaction delay {d_r * 1000:.0f} ms; "
                 f"initial capture-point offset {np.linalg.norm(dv[:2]) / w0 * 1000:.0f} mm vs foot half-length {margin_x * 1000:.0f} mm")
    if not recovered:
        notes.append("PLAN NOT RECOVERED: the COM / capture point ran away (push beyond this strategy or reach)")
    meta.update({"push": {"t": t_push, "dv": [float(dv[0]), float(dv[1]), 0.0]}, "kind": kind, "impulse_Ns": float(M * np.linalg.norm(dv)),
                 "dv_mps": float(np.linalg.norm(dv)), "mass_kg": M, "zc_m": zc, "omega0": w0, "reaction_delay_s": d_r,
                 "capture_offset_m": float(np.linalg.norm(dv[:2]) / w0), "foot_margin_m": float(margin_x), "trunk_inertia_kgm2": I_tr,
                 "trunk_pitch_peak_deg": float(np.degrees(np.abs(th).max())), "trunk_speed_peak_rad_s": float(np.abs(np.gradient(th, dt)).max()), "recovered_plan": recovered,
                 "cop_peak_offset_m": float(np.abs(p - n_pt).max()), "com_peak_offset_m": float(np.abs(c - n_pt).max()),
                 "free_fall_time_to_edge_s": float(math.log(max(margin_x / max(np.linalg.norm(dv[:2]) / w0, 1e-6), 1.0 + 1e-9)) / w0)})

    yaw = np.zeros(T)
    pitch = th.copy()

    def build_q(pelvis):
        Q = rest_upper_body(kin, T)
        ank_l = np.stack([foot["l"][:, 0], foot["l"][:, 1], lg.ankle_h + foot["l"][:, 2]], 1)
        ank_r = np.stack([foot["r"][:, 0], foot["r"][:, 1], lg.ankle_h + foot["r"][:, 2]], 1)
        build_q.ok = fill_legs(kin, Q, pelvis, yaw, pitch, ank_l, ank_r, np.zeros(T), np.zeros(T))
        return Q

    pelvis0 = np.stack([c[:, 0] - off0[0], c[:, 1] - off0[1], np.full(T, sg["pelvis_z"])], 1)
    pelvis, Q, err = compensate_com(kin, build_q, pelvis0, yaw, pitch, c, iters=4)
    notes.append(f"COM tracking error {err * 1000:.2f} mm")
    ref = finish(kin, f"push_{kind}", dt, Q, pelvis, yaw, pitch, ok=build_q.ok, notes=notes, meta=meta)
    if not recovered:
        ref.feasible = False
    ref.stance = np.stack([foot["l"][:, 2] < 1e-4, foot["r"][:, 2] < 1e-4], 1)
    return ref


def _ss_cop(kind, sf, mx, my, cc, vv, w0, K, n_pt):
    """COP command in single support on foot centre `sf`: push towards the foot edge in the direction of the fall (ankle strategy)."""
    xi = cc + vv / w0
    pd = sf + (1 + K) * (xi - sf)
    if kind == "capture_fwd":
        pd[0] = sf[0] + mx
    elif kind == "capture_lat":
        pd[1] = sf[1] + math.copysign(my, xi[1] - sf[1])
    return np.array([np.clip(pd[0], sf[0] - mx, sf[0] + mx), np.clip(pd[1], sf[1] - my, sf[1] + my)])


def max_recoverable_scale(kin: RobotKin, kind: str, hi: float = 4.0, iters: int = 7, speed_cap: float | None = None) -> dict:
    """Largest multiple of the DEFINED push whose recovery plan is geometrically feasible (COM recovered, leg IK reachable, joint
    ranges respected and, for the hip strategy, trunk pitch speed <= speed_cap). Plan-level only: it ignores torque. Bisection."""
    def ok(scale: float) -> bool:
        ref = push_case(kin, kind, push_scale=scale)
        if not ref.feasible:
            return False
        return speed_cap is None or ref.meta["trunk_speed_peak_rad_s"] <= speed_cap

    lo, top = 0.0, hi
    if not ok(0.05):
        return {"scale": 0.0, "dv_mps": 0.0, "impulse_Ns": 0.0}
    lo = 0.05
    if ok(hi):
        lo = hi
    else:
        for _ in range(iters):
            mid = 0.5 * (lo + top)
            if ok(mid):
                lo = mid
            else:
                top = mid
    ref = push_case(kin, kind, push_scale=max(lo, 0.05))
    return {"scale": round(lo, 3), "dv_mps": round(ref.meta["dv_mps"], 3), "impulse_Ns": round(ref.meta["impulse_Ns"], 3)}
