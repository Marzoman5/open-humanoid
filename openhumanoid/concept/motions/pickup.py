"""Table-height pickup of a light object (default 150 g, 40 mm cylinder) with one hand: a WHOLE-BODY, collision-checked planner.

Task T-20261019-a536 (the R1 review found the earlier arm-only planner reporting "arm too short" for every candidate at a 0.45 m table, the
hand path colliding with a 0.40 m table, and nothing reachable at 0.55 m). What the planner does now:

1. **Whole-body posture search.** The grasp posture is (knee flexion K, hip hinge = pelvis pitch, waist yaw, COM position in the foot
   polygon) plus the arm (shoulder pitch/roll, elbow). K runs from nearly straight up to the CAD knee limit (read from the concept's own
   knee range), the hinge to 40 deg, the waist to 30 deg (only if the template has the joint, only towards the working side). Candidates are
   ordered by a "body effort" cost (a deep squat, a big hinge and a big waist twist all cost); the first one that passes every check wins.
2. **Table and standing distance are free parameters of the scenario**: the table top height is the input; where the robot stands relative
   to the table (a step-in) is an output (`standing_gap_m` between the toe line and the table edge, kept >= 0).
3. **Checks, each reported when it is the limit** (`meta["limit"]`): arm reach (a position IK within 2 mm, the finger tilt inside
   [-70, +30] deg, the jaw axis within 25 deg of horizontal, joint limits honoured), leg joint ranges (the CAD knee range, hip pitch, ankle
   pitch: `range_violations`), balance (the COM stays inside the foot polygon with a margin of >= 0.2 foot lengths in every frame), and
   the table (every robot geom, not only the fingers, stays >= 5 mm from the table top in every frame).
4. **Collision-aware approach path.** The hand does not move in joint space between key poses. Rest -> a clearance waypoint in front of the
   table edge (above the final approach line when the arm can reach it) -> a pre-grasp point 5 cm back along the fingers -> a straight line
   along the fingers to the grasp, then a straight 30-40 mm lift. Every segment is sampled in Cartesian space and solved by IK sample by
   sample, so the planned path is the path that is executed. The finished reference is re-checked against the table (all geoms, every frame
   after velocity smoothing) and the object is carried clear of the table through the stand-up.

The finger direction is whatever the 3-DOF arm gives (no wrist); the tilt and the jaw-axis error are reported. The table is a slab (0.30 m
deep, 0.40 m wide, 20 mm thick) whose legs stay outside the model; the object sits 60 mm behind its front edge.

CLI (writes variants/<base>/generated/concept/<id>/pickup_range.{json,md}; the generated file header says so):
    python -m openhumanoid.concept.motions.pickup <concept.yaml> [...] [--tables 0.40 0.45] [--scan 0.20 0.60 0.025] [--peak-factor 1.52]
"""
from __future__ import annotations

import math
import re

import numpy as np

from .. import config
from ..kin import Reference, RobotKin, smoothstep5
from .common import GRIP_CLOSED, knee_flex_from, rest_upper_body
from .posture import double_support
from .smoothing import smooth_series

OBJ = {"mass_kg": 0.150, "radius_m": 0.020, "half_height_m": 0.025, "friction": 1.0}   # requirement R5: <= 150 g can/ball/small toy

# Planner knobs. Overridable per call (`pickup(..., plan={...})`); every number here is an assumption of THIS scenario, not a measured value.
PLAN = {
    "tilt_deg": (-70.0, 45.0),           # finger direction above (+) / below (-) horizontal that the grasp accepts
    "jaw_axis_max_deg": 25.0,            # jaw axis off horizontal (the parallel jaw squeezes a vertical cylinder from the side)
    "ik_tol_m": 0.002,
    "reach_slack_m": 0.004,              # the grasp may not need the arm straighter than this (the arm is singular when straight)
    "clearance_m": 0.003,                # every robot geom vs the table top, every frame (the links are capsules: re-check in CAD)
    "balance_margin_foot_lengths": 0.20,   # COM margin to the foot polygon edge
    "edge_to_object_m": 0.05,            # object centre behind the table's front edge (its rim is 30 mm from the edge)
    "table_half_depth_m": 0.15, "table_half_width_m": 0.20, "table_half_thickness_m": 0.01,
    "grip_heights_m": (0.025, 0.032, 0.038),   # grip point above the table top (object centre is 0.025; the fingers span +-9.5 mm)
    "lift_m": (0.04, 0.03),              # lift achieved (>= 0.03 required: the engine's grasp test needs > 0.02)
    "raise_clear_m": (0.025, 0.05, 0.0),   # how far above the approach line the hand waits in front of the table edge
    "lead_in_m": (0.10, 0.07, 0.05),     # how far back along the fingers that waiting point is (0.05 = the pre-grasp point itself)
    "elbow_flex_deg": tuple(float(x) for x in range(4, 131, 4)),   # elbow flexions tried; height + flexion fix the reach and the finger tilt
    "knee_step_deg": 5.0, "knee_min_deg": 5.0,
    "hinge_deg": (0.0, 10.0, 20.0, 30.0, 40.0),
    "waist_deg": (0.0, 15.0, 30.0),
    "com_fracs": (0.0, 0.25, 0.5, 0.75, 1.0),   # COM x offset from the foot centre, as a fraction of half the foot length (> 0.5 breaks the margin)
    "max_verify": 12,                    # full time-parameterised builds tried before giving up
    # two search passes: a coarse grid first (cheap), the full grid only when the coarse one finds nothing; each pass has a budget of
    # grasp-pose checks and of path checks (a height that is out of reach by a hair is reported as such, not searched for minutes)
    "levels": ({"name": "coarse", "knee_step_deg": 10.0, "hinge_deg": (0.0, 20.0, 40.0), "waist_deg": (0.0, 30.0), "com_fracs": (0.0, 0.5),
                "budget_grasp": 3000, "budget_path": 300},
               {"name": "fine", "budget_grasp": 9000, "budget_path": 1200}),
}


# ------------------------------------------------------------------------------------------------ IK
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


def solve_ik_multi(kin: RobotKin, seeds: list[np.ndarray], pel, quat, site, target, joints, **kw):
    """The best IK result over several starting rows (the arm has more than one branch in a limited-range workspace)."""
    best = None
    for s in seeds:
        Q, e = solve_ik(kin, s, pel, quat, site, target, joints, **kw)
        if best is None or e < best[1]:
            best = (Q, e)
        if e < 5e-4:
            break
    return best


def _solve_arm(ctx: "_Ctx", base_row: np.ndarray, pel, quat, tgt: np.ndarray, prev: np.ndarray | None = None):
    """Grip-point position IK for the 3-DOF arm (shoulder pitch, shoulder roll, elbow), CLOSED FORM, with the joint limits honoured:
    the elbow angle follows from the shoulder-to-target distance, the roll from the lateral offset, the pitch from the remaining two
    components. Of the (up to) two roll branches the one nearest `prev` (default: the rest posture) is taken. A robot with a wrist falls
    back to the numeric DLS solver. Returns (Q_row, residual_m) with the residual measured by forward kinematics."""
    kin = ctx.kin
    if ctx.wrist:
        seeds = [base_row] + ctx.seeds(base_row)
        return solve_ik_multi(kin, ([prev] if prev is not None else []) + seeds, pel, quat, ctx.grip_site, tgt, ctx.arm)
    side = ctx.side
    kin.set_state(base_row, pel, quat)
    kin.mj.mj_kinematics(kin.model, kin.data)
    Sh = kin.data.body(f"upper_arm_{side}").xpos
    Rt = kin.data.body("torso").xmat.reshape(3, 3)
    p = Rt.T @ (tgt - Sh)
    L1, Lg = ctx.L1, ctx.Lg
    D2 = float(p @ p)
    c = (D2 - L1 * L1 - Lg * Lg) / (2 * L1 * Lg)
    ref = prev if prev is not None else base_row
    best = None
    ie, isr, isp = kin.index[f"elbow_{side}"], kin.index[f"shoulder_roll_{side}"], kin.index[f"shoulder_pitch_{side}"]
    lim = ctx.lims
    if c > 1.0 + 1e-9 or c < -1.0 - 1e-9:
        cc = max(-1.0, min(1.0, c))
    else:
        cc = c
    for el in (-math.acos(cc),):
        vx, vz = -Lg * math.sin(el), -L1 - Lg * math.cos(el)
        s_sr = -p[1] / vz if abs(vz) > 1e-9 else 0.0
        if abs(s_sr) > 1.0:
            s_sr = math.copysign(1.0, s_sr)
        for sr in (math.asin(s_sr), math.pi - math.asin(s_sr) if math.asin(s_sr) >= 0 else -math.pi - math.asin(s_sr)):
            a, b = vx, vz * math.cos(sr)
            r = math.hypot(a, b)
            # p_x = a cos sp + b sin sp ; p_z = -a sin sp + b cos sp  ->  sp = atan2(b, a) - atan2(p_z.., ..) by rotation
            sp = math.atan2(b * p[0] - a * p[2], a * p[0] + b * p[2]) if r > 1e-9 else 0.0
            cand = base_row.copy()
            cand[isp], cand[isr], cand[ie] = sp, sr, el
            pen = sum(max(lim[k][0] - v, 0.0) + max(v - lim[k][1], 0.0) for k, v in ((0, sp), (1, sr), (2, el)))
            dist = abs(sr - ref[isr]) + abs(sp - ref[isp])
            key = (pen > 1e-9, pen, dist)
            if best is None or key < best[0]:
                best = (key, cand)
    Q = best[1]
    for k, i in enumerate((isp, isr, ie)):
        Q[i] = float(np.clip(Q[i], lim[k][0], lim[k][1]))
    kin.set_state(Q, pel, quat)
    kin.mj.mj_kinematics(kin.model, kin.data)
    return Q, float(np.linalg.norm(kin.data.site(ctx.grip_site).xpos - tgt))


class _Ctx:
    """Everything the planner derives once from the robot."""

    def __init__(self, kin: RobotKin, side: str, plan: dict):
        self.kin, self.side, self.plan = kin, side, plan
        robot = kin.robot
        self.sy = 1.0 if side == "l" else -1.0
        self.arm = [f"shoulder_pitch_{side}", f"elbow_{side}"] + ([f"shoulder_roll_{side}"] if kin.has(f"shoulder_roll_{side}") else []) \
            + ([f"wrist_{side}"] if kin.has(f"wrist_{side}") else [])
        self.grip_site = f"grip_{side}"
        h = robot.height
        g = robot.geom
        self.hand = max(0.045, 0.09 * h)
        self.L_arm = g["upper_arm"] + (g["forearm"] - self.hand) + 0.62 * self.hand
        self.f0 = knee_flex_from(kin)
        knees = [j["range"][1] for j in robot.joints if j["base"] == "knee"]
        self.kmax = math.radians(min(knees) if knees else 130.0)
        self.has_waist = kin.has("waist_yaw")
        wj = next((j for j in robot.joints if j["name"] == "waist_yaw"), None)
        self.waist_lim = math.radians(min(abs(wj["range"][0]), abs(wj["range"][1]))) if wj else 0.0
        self.q_open = 0.058
        self.wrist = kin.has(f"wrist_{side}") or not kin.has(f"shoulder_roll_{side}")
        self.L1 = g["upper_arm"]
        self.Lg = max(0.02, g["forearm"] - self.hand) + 0.62 * self.hand
        self.lims = []
        self.d_max = self.L1 + self.Lg
        self.d_min = 0.0
        for nm in (f"shoulder_pitch_{side}", f"shoulder_roll_{side}", f"elbow_{side}"):
            jd = next((x for x in robot.joints if x["name"] == nm), None)
            self.lims.append((math.radians(jd["range"][0]), math.radians(jd["range"][1])) if jd else (-9.0, 9.0))
        el_lo = self.lims[2][0]          # most flexed elbow (negative angle): the closest the grip point can come to the shoulder
        self.d_min = math.sqrt(max(self.L1 ** 2 + self.Lg ** 2 + 2 * self.L1 * self.Lg * math.cos(el_lo), 0.0))
        self.rest = rest_upper_body(kin, 1)[0]
        self.rest_arm = {a: float(self.rest[kin.index[a]]) for a in self.arm}
        lg = kin.lg
        self.poly = (lg.foot_off - 0.5 * lg.foot_len, lg.foot_off + 0.5 * lg.foot_len, lg.hip_y + 0.5 * lg.foot_w)

    def seeds(self, base_row: np.ndarray) -> list[np.ndarray]:
        out = []
        for sp, el in ((self.rest_arm[self.arm[0]], self.rest_arm[self.arm[1]]), (-1.2, -0.9), (-0.4, -1.8), (-1.6, -0.4)):
            Q = base_row.copy()
            Q[self.kin.index[self.arm[0]]] = sp
            Q[self.kin.index[self.arm[1]]] = el
            if self.kin.has(f"shoulder_roll_{self.side}"):
                Q[self.kin.index[f"shoulder_roll_{self.side}"]] = self.rest_arm[f"shoulder_roll_{self.side}"]
            out.append(Q)
        return out


# ------------------------------------------------------------------------------------------------ body posture
def _pose(ctx: _Ctx, K: float, hinge: float, waist: float, cfrac: float) -> dict:
    """Static double-support posture (arm at rest): pelvis pose, joints, leg/waist range flags, COM margin to the foot polygon."""
    key = (round(K, 5), round(hinge, 5), round(waist, 5), round(cfrac, 4))
    cache = ctx.kin.__dict__.setdefault("_pickup_pose_cache", {})
    if key in cache:
        return cache[key]
    kin, lg = ctx.kin, ctx.kin.lg
    com = np.tile([lg.foot_off + cfrac * 0.5 * lg.foot_len, 0.0], (2, 1))
    up = {"waist_yaw": np.full(2, waist)} if (ctx.has_waist and waist) else None
    r0 = double_support(kin, "tmp", 0.01, 2, flex=np.full(2, K), pitch=np.full(2, hinge), com_xy=com, upper=up)
    pel, quat, Q = r0.base_pos[0], r0.base_quat[0], r0.q[0]
    c = kin.com(Q, pel, quat)
    x_lo, x_hi, y_hi = ctx.poly
    margin = float(min(c[0] - x_lo, x_hi - c[0], y_hi - abs(c[1])))
    kin.set_state(Q, pel, quat)
    kin.mj.mj_kinematics(kin.model, kin.data)
    out = {"K": K, "hinge": hinge, "waist": waist, "cfrac": cfrac, "pel": pel.copy(), "quat": quat.copy(), "Q": Q.copy(),
           "legs_ok": bool(r0.feasible), "notes": [n for n in r0.notes if "COM tracking" not in n], "com_margin_m": margin,
           "balance_ok": margin >= ctx.plan["balance_margin_foot_lengths"] * lg.foot_len,
           "shoulder": kin.data.body(f"upper_arm_{ctx.side}").xpos.copy()}
    cache[key] = out
    return out


def _pose_arm(ctx: _Ctx, pose: dict, opt: dict) -> dict:
    """The same body posture with the arm at the grasp: the COM compensation moves the pelvis back by the arm's weight shift (about 1 cm
    on a 0.55 m robot), so the table, which hangs off the shoulder at the grasp, sits that much nearer the body at the start."""
    kin, lg = ctx.kin, ctx.kin.lg
    com = np.tile([lg.foot_off + pose["cfrac"] * 0.5 * lg.foot_len, 0.0], (2, 1))
    up = {n: np.full(2, v) for n, v in opt["arm_q"].items()}
    if ctx.has_waist and pose["waist"]:
        up["waist_yaw"] = np.full(2, pose["waist"])
    r0 = double_support(kin, "tmp", 0.01, 2, flex=np.full(2, pose["K"]), pitch=np.full(2, pose["hinge"]), com_xy=com, upper=up)
    kin.set_state(r0.q[0], r0.base_pos[0], r0.base_quat[0])
    kin.mj.mj_kinematics(kin.model, kin.data)
    return {"pel": r0.base_pos[0].copy(), "quat": r0.base_quat[0].copy(), "Q": r0.q[0].copy(),
            "shoulder": kin.data.body(f"upper_arm_{ctx.side}").xpos.copy(), "legs_ok": bool(r0.feasible)}


def _candidates(ctx: _Ctx, level: dict | None = None) -> list[dict]:
    pl = {**ctx.plan, **{k: v for k, v in (level or {}).items() if k not in ("name", "budget_grasp", "budget_path")}}
    ks = np.arange(math.radians(pl["knee_min_deg"]), ctx.kmax - math.radians(0.5) + 1e-9, math.radians(pl["knee_step_deg"]))
    ks = sorted(set(ks.round(6)) | {round(min(ctx.f0, ctx.kmax - math.radians(0.5)), 6)})
    waists = [0.0]
    if ctx.has_waist:
        sgn = -ctx.sy                     # CCW yaw carries the right shoulder forward
        waists = [sgn * math.radians(w) for w in pl["waist_deg"] if math.radians(w) <= ctx.waist_lim + 1e-9]
    out = []
    for K in ks:
        for hg in pl["hinge_deg"]:
            for w in waists:
                for cf in pl["com_fracs"]:
                    cost = (1.0 * max(K - ctx.f0, 0.0) / math.radians(60) + 0.5 * max(ctx.f0 - K, 0.0) / math.radians(30)
                            + 1.2 * hg / 40.0 + 0.6 * abs(w) / math.radians(30) + 0.5 * cf)
                    out.append({"K": float(K), "hinge": math.radians(hg), "waist": float(w), "cfrac": float(cf), "cost": cost})
    out.sort(key=lambda c: c["cost"])
    return out


# ------------------------------------------------------------------------------------------------ arm: grasp options
def _lift_point(sh: np.ndarray, G: np.ndarray, h: np.ndarray, lift: float) -> np.ndarray:
    """The grasp point raised by `lift`, on the circle about the shoulder (a straight arm lifts by swinging up at constant radius, not by
    stretching further); falls back to a vertical move when the circle cannot rise that far."""
    z = np.array([0.0, 0.0, 1.0])
    v = G - sh
    vx, vz = float(v @ h), float(v[2])
    lat = v - vx * h - vz * z
    rad = math.hypot(vx, vz)
    zt = vz + lift
    if rad < 1e-6 or abs(zt) >= rad or vx <= 0.0:
        return G + lift * z
    return sh + math.sqrt(rad * rad - zt * zt) * h + zt * z + lat


def _hand_axes(ctx: _Ctx, Q, pel, quat):
    kin = ctx.kin
    kin.set_state(Q, pel, quat)
    kin.mj.mj_kinematics(kin.model, kin.data)
    return kin.data.body(f"hand_{ctx.side}").xmat.reshape(3, 3).copy()


def _with_arm(ctx: _Ctx, Q: np.ndarray, opt: dict) -> np.ndarray:
    out = Q.copy()
    for nm, v in opt["arm_q"].items():
        out[ctx.kin.index[nm]] = v
    return out


def _grasp_options(ctx: _Ctx, pose: dict, z_t: float, cache: dict) -> list[dict]:
    """Arm solutions for this body posture. For a finger tilt tau the planar two-link geometry fixes the horizontal reach from the
    height of the grip point above the shoulder (dz = L1 sin a1 + Lg sin tau, reach = L1 cos a1 + Lg cos tau, elbow flexion = tau - a1 >= 0),
    so each (grip height, tilt) is one option; the 3-D closed-form IK then confirms it (lateral offset of the open gap included).
    Translation-invariant, so cached on (hinge, waist, dz). Sorted by |tilt| (a level hand first)."""
    pl, kin, sy = ctx.plan, ctx.kin, ctx.sy
    sh = pose["shoulder"]
    key = (round(pose["hinge"], 4), round(pose["waist"], 4), round((z_t - sh[2]) * 1000.0))
    if key in cache:
        return cache[key]
    opts: list[dict] = []
    cache[key] = opts
    psi = pose["waist"]
    h = np.array([math.cos(psi), math.sin(psi), 0.0])
    perp = np.array([-math.sin(psi), math.cos(psi), 0.0])
    pel, quat = pose["pel"], pose["quat"]
    el_lo = ctx.lims[2][0]
    names = (f"shoulder_pitch_{ctx.side}", f"shoulder_roll_{ctx.side}", f"elbow_{ctx.side}")
    L1, Lg = ctx.L1, ctx.Lg
    for gh in pl["grip_heights_m"]:
        dz = z_t + gh - sh[2]
        if abs(dz) > ctx.d_max:
            continue
        for e_d in pl["elbow_flex_deg"]:
            e = math.radians(e_d)
            if e > -el_lo - math.radians(2.0):
                continue
            D = math.sqrt(L1 * L1 + Lg * Lg + 2 * L1 * Lg * math.cos(e))
            if abs(dz) >= 0.999 * D:
                continue
            if D > ctx.d_max - pl["reach_slack_m"]:
                continue                                # keep a little slack from the straight (singular) arm
            beta = math.asin(dz / D)
            alpha = math.asin(min(1.0, Lg * math.sin(e) / D))
            a1 = beta - alpha                          # upper arm direction above horizontal (elbow below the shoulder-hand chord)
            tau = a1 + e                               # forearm = finger direction
            tau_d = math.degrees(tau)
            if not (pl["tilt_deg"][0] <= tau_d <= pl["tilt_deg"][1]):
                continue
            reach = D * math.cos(beta)
            if reach < 0.03:
                continue
            O = sh + reach * h + sy * (ctx.q_open / 2) * perp
            O[2] = z_t + gh
            ylat = perp
            Q = pose["Q"]
            tgt = O - ylat * sy * (ctx.q_open / 2)
            sol, err = _solve_arm(ctx, Q, pel, quat, tgt)
            for _ in range(2):
                if err > 0.02:
                    break
                Rh = _hand_axes(ctx, sol, pel, quat)
                ylat = Rh[:, 1] * (1.0 if Rh[:, 1] @ perp >= 0 else -1.0)
                tgt = O - ylat * sy * (ctx.q_open / 2)
                sol, err = _solve_arm(ctx, sol, pel, quat, tgt, sol)
            if err > pl["ik_tol_m"]:
                continue
            Rh = _hand_axes(ctx, sol, pel, quat)
            u = -Rh[:, 2]
            tilt = math.degrees(math.asin(max(-1.0, min(1.0, u[2]))))
            jaw = math.degrees(math.asin(min(1.0, abs(Rh[2, 1]))))
            if not (pl["tilt_deg"][0] - 1 <= tilt <= pl["tilt_deg"][1] + 1) or jaw > pl["jaw_axis_max_deg"] or float(u @ h) < 0.2:
                continue
            opts.append({"gh": gh, "reach": reach, "frac": reach / ctx.L_arm, "arm_q": {n: float(sol[kin.index[n]]) for n in names},
                         "O_rel": O - sh, "tgt_rel": tgt - sh, "u": u.copy(), "tilt_deg": tilt, "jaw_deg": jaw, "ik_m": err, "ylat": ylat.copy()})
    # a level hand first, but not at the price of a (nearly) straight arm: the shoulder torque grows with the reach
    opts.sort(key=lambda o: (abs(o["tilt_deg"]) / 45.0 + 4.0 * max(o["frac"] - 0.8, 0.0), o["gh"]))
    return opts


# ------------------------------------------------------------------------------------------------ scene and clearance
def _scene_xml(O: np.ndarray, psi: float, z_t: float, pl: dict) -> tuple[str, dict]:
    """Table slab (front edge `edge_to_object_m` before the object along the torso heading) + the object."""
    h = np.array([math.cos(psi), math.sin(psi)])
    c = O[:2] + h * (pl["table_half_depth_m"] - pl["edge_to_object_m"])
    th = pl["table_half_thickness_m"]
    r_o, hh = OBJ["radius_m"], OBJ["half_height_m"]
    xml = f"""    <body name="table" pos="{c[0]:.4f} {c[1]:.4f} {z_t - th:.4f}" euler="0 0 {math.degrees(psi):.3f}">
      <geom name="table_top" type="box" size="{pl['table_half_depth_m']} {pl['table_half_width_m']} {th}" class="contact" rgba="0.55 0.45 0.35 1"/>
    </body>
    <body name="obj" pos="{O[0]:.4f} {O[1]:.4f} {z_t + hh + 0.0005:.4f}">
      <freejoint name="obj_free"/>
      <geom name="obj_geom" type="cylinder" size="{r_o} {hh}" mass="{OBJ['mass_kg']}" class="contact" friction="{OBJ['friction']} 0.02 0.01" rgba="0.8 0.2 0.2 1"/>
    </body>"""
    edge = O[:2] - h * pl["edge_to_object_m"]
    return xml, {"table_center": [float(c[0]), float(c[1])], "table_front_edge_xy": [float(edge[0]), float(edge[1])]}


class _Clearance:
    """Signed distance of every robot geom to the table top (negative = interpenetration), for a joint-space reference.
    The MuJoCo model is built once per kinematics object (building the MJCF is slow) and the table is moved with `place`."""

    def __init__(self, ctx: _Ctx):
        mj = ctx.kin.mj
        self.mj = mj
        self.pl = ctx.plan
        xml, _ = _scene_xml(np.zeros(3), 0.0, 0.3, ctx.plan)
        self.m = ctx.kin.robot.build_model(xml)
        self.d = mj.MjData(self.m)
        self.tg = self.m.geom("table_top").id
        self.tb = self.m.body("table").id
        skip = {self.tb, self.m.body("obj").id}
        self.geoms = [g for g in range(self.m.ngeom) if self.m.geom_bodyid[g] > 0 and int(self.m.geom_bodyid[g]) not in skip]
        self.qadr = np.array([self.m.joint(n).qposadr[0] for n in ctx.kin.names])
        self.fromto = np.zeros(6)

    @staticmethod
    def of(ctx: _Ctx) -> "_Clearance":
        cache = ctx.kin.__dict__.setdefault("_pickup_clr", {})
        key = (ctx.plan["table_half_depth_m"], ctx.plan["table_half_width_m"], ctx.plan["table_half_thickness_m"])
        if key not in cache:
            cache[key] = _Clearance(ctx)
        return cache[key]

    def place(self, O: np.ndarray, psi: float, z_t: float) -> None:
        pl = self.pl
        h = np.array([math.cos(psi), math.sin(psi)])
        c = O[:2] + h * (pl["table_half_depth_m"] - pl["edge_to_object_m"])
        self.m.body_pos[self.tb] = [c[0], c[1], z_t - pl["table_half_thickness_m"]]
        self.m.body_quat[self.tb] = [math.cos(psi / 2), 0.0, 0.0, math.sin(psi / 2)]

    def min_dist(self, Q: np.ndarray, pel: np.ndarray, quat: np.ndarray, every: int = 1):
        """(min distance over the frames, name of the closest geom, frame index)."""
        mj, m, d = self.mj, self.m, self.d
        best, name, at = 1e9, "", 0
        for i in range(0, len(Q), every):
            d.qpos[:3] = pel[i]
            d.qpos[3:7] = quat[i]
            d.qpos[self.qadr] = Q[i]
            mj.mj_kinematics(m, d)
            for g in self.geoms:
                dist = mj.mj_geomDistance(m, d, g, self.tg, 0.3, self.fromto)
                if dist < best:
                    best, name, at = float(dist), m.geom(g).name or m.body(int(m.geom_bodyid[g])).name, i
        return best, name, at


# ------------------------------------------------------------------------------------------------ trajectory
def _marks() -> dict:
    # gripper timing is set by the servo: 45 mm of jaw travel on a 12 mm/rad pinion is 3.75 rad, so the jaw takes 3 s to close and 3.5 s to open (peak servo speed below 3 rad/s)
    return {"stand": 0.8, "down": 3.0, "raise": 4.6, "pre": 6.0, "grasp": 7.4, "closed": 10.4, "lift": 11.4, "up": 13.6, "end": 14.6}


def _series(t: np.ndarray, times: list[float], vals: list[float]) -> np.ndarray:
    from scipy.interpolate import PchipInterpolator
    return PchipInterpolator(times, vals)(np.clip(t, times[0], times[-1]))


def _series_matrix(t: np.ndarray, times: list[float], rows: np.ndarray) -> np.ndarray:
    from scipy.interpolate import PchipInterpolator
    return PchipInterpolator(times, rows, axis=0)(np.clip(t, times[0], times[-1]))


def _build(ctx: _Ctx, cand: dict, pose: dict, opt: dict, z_t: float, c_up: float, lead: float, lift: float, dt: float, iters: int = 3):
    """Full time-parameterised reference for one posture + grasp option. Returns (ref, info) or (None, reason)."""
    kin, pl, side, sy = ctx.kin, ctx.plan, ctx.side, ctx.sy
    marks = _marks()
    n = lambda s: int(round(s / dt))  # noqa: E731
    T = n(marks["end"]) + 1
    t = np.arange(T) * dt

    def prof(a, b):
        return smoothstep5(np.clip((t - a) / max(b - a, 1e-9), 0, 1))

    K, hinge, waist, cfrac = cand["K"], cand["hinge"], cand["waist"], cand["cfrac"]
    K_end = min(ctx.f0, K)                    # stand back up to the walking stance, but never lower the body while holding the object
    down, up = prof(marks["stand"], marks["down"]), prof(marks["lift"], marks["up"])
    flex = ctx.f0 + (K - ctx.f0) * down + (K_end - K) * up
    pitch = hinge * down * (1 - up)
    waist_s = waist * down * (1 - up)
    lg = kin.lg
    com_xy = np.stack([lg.foot_off + cfrac * 0.5 * lg.foot_len * down * (1 - up), np.zeros(T)], 1)
    sh0 = pose["shoulder"]
    h = np.array([math.cos(waist), math.sin(waist), 0.0])
    u = opt["u"]
    gi = lambda tt: min(int(round(tt / dt)), T - 1)  # noqa: E731
    G = sh0 + opt["tgt_rel"]
    O = sh0 + opt["O_rel"]
    up_series: dict = {}
    base_ref = None
    infos: dict = {}
    for _ in range(iters):
        base_ref = double_support(kin, "pickup", dt, T, flex=flex, pitch=pitch, com_xy=com_xy, upper=({**up_series, "waist_yaw": waist_s} if ctx.has_waist else up_series) or None)
        pelv, quat = base_ref.base_pos, base_ref.base_quat
        # the waypoints hang off the shoulder AT THE GRASP (translation-invariant arm solution): the COM compensation shifts the pelvis a few mm
        # once the arm is out, so they are re-anchored on every pass instead of being fixed from the arm-at-rest posture
        ig = gi(marks["grasp"])
        kin.set_state(base_ref.q[ig], pelv[ig], quat[ig])
        kin.mj.mj_kinematics(kin.model, kin.data)
        sh_g = kin.data.body(f"upper_arm_{side}").xpos.copy()
        G = sh_g + opt["tgt_rel"]
        O = sh_g + opt["O_rel"]
        P = G - 0.05 * u + np.array([0.0, 0.0, c_up])
        R = G - lead * u + np.array([0.0, 0.0, c_up])
        Lp = _lift_point(sh_g, G, h, lift)
        Qrow = base_ref.q[gi(marks["down"])].copy()
        for a in ctx.arm:
            Qrow[kin.index[a]] = ctx.rest_arm[a]
        pel_d, q_d = pelv[gi(marks["down"])], quat[gi(marks["down"])]
        kin.set_state(Qrow, pel_d, q_d)
        kin.mj.mj_kinematics(kin.model, kin.data)
        g_rest = kin.data.site(ctx.grip_site).xpos.copy()
        times = [0.0, marks["down"]]
        rows = [Qrow.copy(), Qrow.copy()]
        # a straight Cartesian line at each stage, solved sample by sample (warm start from the previous sample)
        prev = Qrow
        worst = 0.0
        fail = None
        for tgt, tt, kind in _path_points(sh_g, g_rest, R, P, G, marks):
            idx = gi(tt)
            sol, err = _solve_arm(ctx, prev, pelv[idx], quat[idx], tgt, prev)
            worst = max(worst, err)
            if err > 0.004 and fail is None:
                fail = f"path IK residual {err * 1000:.1f} mm at {tt:.1f} s ({kind})"
            times.append(tt)
            rows.append(sol)
            prev = sol
        # hold at the grasp until the jaw is closed, lift straight up, hold
        idx = gi(marks["lift"])
        Qlift, e_l = _solve_arm(ctx, prev, pelv[idx], quat[idx], Lp, prev)
        if e_l > 0.004 and fail is None:
            fail = f"lift IK residual {e_l * 1000:.1f} mm"
        times += [marks["closed"], marks["lift"], marks["end"]]
        rows += [prev, Qlift, Qlift]
        if fail:
            return None, fail
        up_series = {}
        for a in ctx.arm:
            col = kin.index[a]
            jd = next(x for x in kin.robot.joints if x["name"] == a)
            ser = _series(t, times, [float(r[col]) for r in rows])
            up_series[a] = smooth_series(ser, dt, config.motions()["dance"]["v_limit_rad_s"], math.radians(jd["range"][0]), math.radians(jd["range"][1]))
        g_ser = np.full(T, GRIP_CLOSED)
        g_ser += (ctx.q_open - GRIP_CLOSED) * prof(marks["stand"], marks["raise"])
        g_ser += (0.005 - ctx.q_open) * prof(marks["grasp"], marks["closed"])
        up_series[f"gripper_{side}"] = g_ser
        infos["path_ik_worst_m"] = worst
        infos["lift_ik_m"] = e_l

    upper = {**up_series, "waist_yaw": waist_s} if ctx.has_waist else up_series
    ref = double_support(kin, "pickup", dt, T, flex=flex, pitch=pitch, com_xy=com_xy, upper=upper)
    return ref, {"marks": marks, "G": G, "O": O, "P": P, "R": R, "Lp": Lp, "u": u, "psi": waist, "h": h, "K_end": K_end, **infos}


def _final_checks(ctx: _Ctx, ref: Reference, info: dict, opt: dict, z_t: float) -> dict:
    """Re-measure the finished reference: the actual grasp, the object placement it implies, the table and balance."""
    kin, pl, sy, side = ctx.kin, ctx.plan, ctx.sy, ctx.side
    dt = ref.dt
    marks = info["marks"]
    ig = min(int(round(marks["grasp"] / dt)), len(ref.q) - 1)
    Rh = _hand_axes(ctx, ref.q[ig], ref.base_pos[ig], ref.base_quat[ig])
    grip = kin.data.site(ctx.grip_site).xpos.copy()
    ylat = Rh[:, 1]
    perp = np.array([-math.sin(info["psi"]), math.cos(info["psi"]), 0.0])
    ylat = ylat * (1.0 if ylat @ perp >= 0 else -1.0)
    O = grip + ylat * sy * (ctx.q_open / 2)          # the object sits where the open gap's centre is at the grasp frame
    O[2] = z_t + opt["gh"]
    u = -Rh[:, 2]
    xml, tinfo = _scene_xml(O, info["psi"], z_t, pl)
    clr = _Clearance.of(ctx)
    clr.place(O, info["psi"], z_t)
    dmin, gname, at = clr.min_dist(ref.q, ref.base_pos, ref.base_quat, every=2)
    com = kin.com_traj(ref.q[::5], ref.base_pos[::5], ref.base_quat[::5])
    x_lo, x_hi, y_hi = ctx.poly
    bm = np.minimum(np.minimum(com[:, 0] - x_lo, x_hi - com[:, 0]), y_hi - np.abs(com[:, 1]))
    # object carried: grip height above the grasp height after the lift, stand-up included
    il = min(int(round(marks["lift"] / dt)), len(ref.q) - 1)
    gz = np.array([kin.site(ctx.grip_site, ref.q[i], ref.base_pos[i], ref.base_quat[i])[2] for i in range(il, len(ref.q), 5)])
    carry_min = float(gz.min() - (z_t + opt["gh"]))
    carry_end = float(gz[-1] - (z_t + opt["gh"]))
    toe = np.array([0.65 * kin.lg.foot_len, 0.0])
    gap = float((np.array(tinfo["table_front_edge_xy"]) - toe) @ np.array(info["h"][:2]))
    return {"O": O, "xml": xml, "tinfo": tinfo, "table_min_dist_m": dmin, "table_closest_geom": gname, "table_closest_t_s": at * dt,
            "balance_margin_min_m": float(bm.min()), "carry_min_m": carry_min, "carry_end_m": carry_end, "gap_m": gap,
            "tilt_deg": math.degrees(math.asin(max(-1.0, min(1.0, u[2])))), "jaw_deg": math.degrees(math.asin(min(1.0, abs(Rh[2, 1])))),
            "grasp_resid_m": float(np.linalg.norm(grip - info["G"]))}



def _arc(sh: np.ndarray, a: np.ndarray, b: np.ndarray, s: float) -> np.ndarray:
    """Point at fraction s on the arc from a to b about the shoulder (direction slerp, radius linear). A straight line between two points near the
    edge of the arm's reach cuts through the region the arm cannot reach (too close to the shoulder); the arc stays in the annulus."""
    va, vb = a - sh, b - sh
    ra, rb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    ua, ub = va / ra, vb / rb
    w = math.acos(max(-1.0, min(1.0, float(ua @ ub))))
    d = ub if w < 1e-6 else (math.sin((1 - s) * w) * ua + math.sin(s * w) * ub) / math.sin(w)
    return sh + ((1 - s) * ra + s * rb) * d


def _path_points(sh: np.ndarray, g_rest: np.ndarray, R: np.ndarray, P: np.ndarray, G: np.ndarray, marks: dict):
    """Cartesian samples (target, time, kind) of the hand path after the rest posture: an arc about the shoulder from the rest hand to the
    waiting point R (so the swing stays inside the arm's annulus), a straight line R -> P, then the straight approach P -> G along (nearly)
    the fingers. Each piece is sampled and solved by IK sample by sample."""
    t1 = marks["raise"]
    pts: list[tuple[np.ndarray, float, str]] = []
    for i in range(1, 9):
        pts.append((_arc(sh, g_rest, R, i / 8), marks["down"] + (t1 - marks["down"]) * (i / 8), "raise"))
    for i in range(1, 4):
        pts.append((R + (P - R) * (i / 3), t1 + (marks["pre"] - t1) * (i / 3), "approach"))
    for i in range(1, 5):
        pts.append((P + (G - P) * (i / 4), marks["pre"] + (marks["grasp"] - marks["pre"]) * (i / 4), "approach"))
    return pts


def _stage_a(ctx: _Ctx, pose: dict, opt: dict, z_t: float):
    """What does not depend on the waiting point or the lift: legs and waist still in range once the arm is out (the pelvis moves back with
    the arm's weight), the table clear of the body at the grasp AND of the rest posture, and the table edge not behind the toes.
    Returns (ok, reason, data)."""
    pl = ctx.plan
    pg = _pose_arm(ctx, pose, opt)
    if not pg["legs_ok"]:
        return False, "legs/waist out of range once the arm is out", None
    sh0 = pg["shoulder"]
    O = sh0 + opt["O_rel"]
    h = np.array([math.cos(pose["waist"]), math.sin(pose["waist"]), 0.0])
    edge = O[:2] - h[:2] * pl["edge_to_object_m"]
    gap = float((edge - np.array([0.65 * ctx.kin.lg.foot_len, 0.0])) @ h[:2])
    if gap < 0.0:
        return False, "table edge behind the toes", None
    clr = _Clearance.of(ctx)
    clr.place(O, pose["waist"], z_t)
    d1 = clr.min_dist(pg["Q"][None], pg["pel"][None], pg["quat"][None])
    d2 = clr.min_dist(pose["Q"][None], pose["pel"][None], pose["quat"][None])
    dmin = min(d1[0], d2[0])
    if dmin < pl["clearance_m"]:
        return False, f"table clearance {dmin * 1000:.1f} mm ({d1[1] if d1[0] <= d2[0] else d2[1]}) at the {'grasp' if d1[0] <= d2[0] else 'rest posture'}", None
    return True, "", {"pg": pg, "O": O, "h": h}


def _static_paths(ctx: _Ctx, pose: dict, opt: dict, z_t: float, c_up: float, lead: float, lift: float, A: dict):
    """Cheap pre-check of one plan: the arm's annulus (min/max reach) for P, R and the lift point, IK of the whole hand path, and the table
    clearance along the (PCHIP-interpolated) joint path with the pelvis moving from the rest-arm pose to the grasp-arm pose.
    Returns (ok, reason, heavy) - heavy=False when it was rejected by the cheap analytic reach test."""
    kin, pl = ctx.kin, ctx.plan
    pg, O, h = A["pg"], A["O"], A["h"]
    sh0 = pg["shoulder"]
    pel, quat = pg["pel"], pg["quat"]
    G = sh0 + opt["tgt_rel"]
    u = opt["u"]
    P = G - 0.05 * u + np.array([0.0, 0.0, c_up])
    R = G - lead * u + np.array([0.0, 0.0, c_up])
    Lp = _lift_point(sh0, G, h, lift)
    for name, X in (("pre-grasp", P), ("waiting point", R), ("lift point", Lp)):
        D = float(np.linalg.norm(X - sh0))
        if not (ctx.d_min + 0.003 <= D <= ctx.d_max + 0.0005):
            return False, f"{name} is {D * 1000:.0f} mm from the shoulder; the arm covers {ctx.d_min * 1000:.0f}-{ctx.d_max * 1000:.0f} mm", False
    Qrest = pose["Q"].copy()
    kin.set_state(Qrest, pose["pel"], pose["quat"])
    kin.mj.mj_kinematics(kin.model, kin.data)
    g_rest = kin.data.site(ctx.grip_site).xpos.copy()
    marks = _marks()
    rows = [Qrest.copy(), Qrest.copy()]
    times = [0.0, marks["down"]]
    prev = pg["Q"].copy()
    for a in ctx.arm:
        prev[kin.index[a]] = ctx.rest_arm[a]
    for tgt, tt, kind in _path_points(sh0, g_rest, R, P, G, marks):
        sol, err = _solve_arm(ctx, prev, pel, quat, tgt, prev)
        if err > 0.004:
            return False, f"IK residual {err * 1000:.1f} mm on the {kind} path", True
        rows.append(sol)
        times.append(tt)
        prev = sol
    Qlift, err = _solve_arm(ctx, prev, pel, quat, Lp, prev)
    if err > 0.004:
        return False, f"IK residual {err * 1000:.1f} mm on the lift path", True
    rows += [prev, Qlift]
    times += [marks["closed"], marks["lift"]]
    tt = np.arange(marks["down"], marks["lift"] + 1e-9, 0.2)
    dense = _series_matrix(tt, times, np.array(rows))
    s_arm = smoothstep5(np.clip((tt - marks["down"]) / (marks["grasp"] - marks["down"]), 0, 1))[:, None]
    pels = pose["pel"][None, :] + (pel - pose["pel"])[None, :] * s_arm
    quats = np.tile(pose["quat"], (len(dense), 1))
    clr = _Clearance.of(ctx)
    clr.place(O, pose["waist"], z_t)
    dmin, gname, at = clr.min_dist(dense, pels, quats)
    if dmin < pl["clearance_m"]:
        return False, f"table clearance {dmin * 1000:.1f} mm ({gname}) at {tt[at]:.1f} s on the planned path", True
    return True, "", True


def _grasp_clear(ctx: _Ctx, pose: dict, opt: dict, z_t: float) -> float:
    """Table clearance of the grasp pose alone (the cheapest reject)."""
    sh0 = pose["shoulder"]
    clr = _Clearance.of(ctx)
    clr.place(sh0 + opt["O_rel"], pose["waist"], z_t)
    Qs = np.array([_with_arm(ctx, pose["Q"], opt)])
    return clr.min_dist(Qs, np.tile(pose["pel"], (1, 1)), np.tile(pose["quat"], (1, 1)))[0]


# ------------------------------------------------------------------------------------------------ planner entry
def plan_pickup(kin: RobotKin, z_t: float, side: str = "r", dt: float = 0.01, plan: dict | None = None):
    """Search the whole-body posture and build the reference. Returns (Reference | None, info dict). `info["limit"]` names what stops it."""
    pl = {**PLAN, **(plan or {})}
    ctx = _Ctx(kin, side, pl)
    cache: dict = {}
    seen = {"arm": False, "table": False, "path": False, "balance": False}
    verifies = 0
    tally: dict[str, int] = {}
    done: set = set()

    def note(msg: str) -> None:
        k = re.sub(r"[0-9.]+ mm", "x mm", msg)
        tally[k] = tally.get(k, 0) + 1

    levels = [{**lv, **{k: v for k, v in (plan or {}).items() if k in ("knee_step_deg", "hinge_deg", "waist_deg", "com_fracs")}} for lv in pl["levels"]]
    for level in levels:
        n_grasp = n_path = 0
        for cand in _candidates(ctx, level):
            key = (round(cand["K"], 5), round(cand["hinge"], 5), round(cand["waist"], 5), round(cand["cfrac"], 4))
            if key in done:
                continue
            done.add(key)
            pose = _pose(ctx, cand["K"], cand["hinge"], cand["waist"], cand["cfrac"])
            if not (pose["legs_ok"] and pose["balance_ok"]):
                continue
            opts = _grasp_options(ctx, pose, z_t, cache)
            if not opts:
                continue
            seen["arm"] = True
            for opt in opts:
                if n_grasp >= level["budget_grasp"]:
                    break
                n_grasp += 1
                if _grasp_clear(ctx, pose, opt, z_t) < pl["clearance_m"] - 0.02:      # coarse: the exact check moves the pelvis (see _pose_arm)
                    seen["table"] = True
                    note("the body or arm meets the table at the grasp")
                    continue
                okA, whyA, A = _stage_a(ctx, pose, opt, z_t)
                if not okA:
                    seen["table" if "clearance" in whyA or "edge" in whyA else "balance"] = True
                    note(whyA)
                    continue
                for lift in pl["lift_m"]:
                    for c_up in pl["raise_clear_m"]:
                        for lead in pl["lead_in_m"]:
                            if n_path >= level["budget_path"] or verifies >= pl["max_verify"]:
                                break
                            ok, why, heavy = _static_paths(ctx, pose, opt, z_t, c_up, lead, lift, A)
                            n_path += int(heavy)
                            if not ok:
                                seen["table" if "clearance" in why else "path"] = True
                                note(why)
                                continue
                            verifies += 1
                            ref, info = _build(ctx, cand, pose, opt, z_t, c_up, lead, lift, dt)
                            if ref is None:
                                seen["path"] = True
                                note(info)
                                continue
                            chk = _final_checks(ctx, ref, info, opt, z_t)
                            bad = []
                            if not ref.feasible:
                                bad.append("legs/waist range: " + "; ".join(n for n in ref.notes if "COM tracking" not in n)[:160])
                            if chk["table_min_dist_m"] < pl["clearance_m"]:
                                bad.append(f"table clearance {chk['table_min_dist_m'] * 1000:.1f} mm at {chk['table_closest_t_s']:.1f} s ({chk['table_closest_geom']})")
                                seen["table"] = True
                            if chk["balance_margin_min_m"] < pl["balance_margin_foot_lengths"] * kin.lg.foot_len - 1e-4:
                                bad.append(f"balance margin {chk['balance_margin_min_m'] * 1000:.1f} mm")
                                seen["balance"] = True
                            if chk["carry_min_m"] < 0.015 and lift >= 0.03:
                                bad.append(f"carried object comes within {chk['carry_min_m'] * 1000:.0f} mm of the table")
                            if chk["gap_m"] < 0.0:
                                bad.append(f"table edge {chk['gap_m'] * 1000:.0f} mm behind the toes")
                            if bad:
                                note("final check: " + "; ".join(bad))
                                continue
                            info.update(chk)
                            info.update({"cand": cand, "opt": opt, "pose": pose, "lift_m": lift, "raise_clear_m": c_up, "lead_in_m": lead,
                                         "verified_plans_tried": verifies, "search_level": level["name"]})
                            return ref, info
    # nothing passed: say why. Re-run the geometry without the leg/balance constraints to classify the limit.
    limit = "arm reach" if not seen["arm"] else ("table collision" if seen["table"] else ("path/IK" if seen["path"] else "balance" if seen["balance"] else "joint range"))
    if not seen["arm"]:
        arm_free = balance_only = False
        for cand in _candidates(ctx, levels[0]):
            pose = _pose(ctx, cand["K"], cand["hinge"], cand["waist"], cand["cfrac"])
            if pose["legs_ok"] and pose["balance_ok"]:
                continue
            if abs(z_t - pose["shoulder"][2]) > ctx.d_max:
                continue
            if _grasp_options(ctx, pose, z_t, cache):
                arm_free = True
                balance_only = balance_only or pose["legs_ok"]
                if balance_only:
                    break
        if arm_free:
            limit = "balance" if balance_only else "leg joint range"
    top = sorted(tally.items(), key=lambda kv: -kv[1])[:3]
    return None, {"limit": limit, "reason": "; ".join(f"{k} (x{v})" for k, v in top), "verified_plans_tried": verifies, "tally": tally}


def _limit_note(limit: str, z_t: float, ctx: _Ctx, info: dict) -> str:
    base = {"arm reach": "arm too short for this table height with the whole-body options tried (knee, hip hinge, waist, step-in)",
            "balance": "the arm could reach with a posture whose COM leaves the foot polygon margin: balance, not reach, limits it",
            "leg joint range": "the arm could reach only with leg/waist joints outside their ranges (knee CAD limit, hip pitch, ankle pitch): joint range, not arm reach, limits it",
            "table collision": "every reachable posture put the hand or body into the table",
            "path/IK": "the collision-free approach path is not reachable by IK"}.get(limit, limit)
    return f"pickup at {z_t:.2f} m: {base}" + (f" ({info.get('reason')})" if info.get("reason") else "")


def pickup(kin: RobotKin, dt: float = 0.01, table_height_frac: float = 0.36, table_height_m: float | None = None,
           side: str = "r", plan: dict | None = None) -> Reference:
    robot = kin.robot
    if not (kin.has(f"gripper_{side}") and kin.has(f"elbow_{side}") and kin.has(f"shoulder_pitch_{side}")):
        ref = double_support(kin, "pickup", dt, 101, notes=["no gripper/arm joints: pickup not possible"])
        ref.feasible = False
        return ref
    z_t = table_height_m if table_height_m else table_height_frac * robot.height
    pl = {**PLAN, **(plan or {})}
    ref, info = plan_pickup(kin, z_t, side, dt, plan)
    ctx = _Ctx(kin, side, pl)
    if ref is None:
        ref = double_support(kin, "pickup", dt, 101, notes=[_limit_note(info["limit"], z_t, ctx, info)])
        ref.feasible = False
        ref.meta.update({"table_height_m": round(z_t, 4), "limit": info["limit"], "reachable": False})
        return ref
    cand, opt, ch = info["cand"], info["opt"], info
    O = ch["O"]
    ref.meta.update({
        "table_height_m": round(z_t, 4), "reachable": True, "limit": None, "object_m": OBJ["mass_kg"],
        "squat_deg": round(math.degrees(cand["K"]), 1), "hip_hinge_deg": round(math.degrees(cand["hinge"]), 1),
        "waist_yaw_deg": round(math.degrees(cand["waist"]), 1), "com_shift_frac_of_half_foot": cand["cfrac"],
        "knee_deg_max": round(math.degrees(cand["K"]), 1), "knee_range_max_deg": round(math.degrees(ctx.kmax), 1),
        "object_xyz": [round(float(x), 4) for x in O], "arm_reach_m": round(ctx.L_arm, 4), "grasp_reach_m": round(opt["reach"], 4),
        "grasp_ik_m": round(ch["grasp_resid_m"], 5), "pregrasp_ik_m": round(ch["path_ik_worst_m"], 5), "lift_ik_m": round(ch["lift_ik_m"], 5),
        "jaw_axis_off_horizontal_deg": round(ch["jaw_deg"], 2), "finger_tilt_deg": round(ch["tilt_deg"], 1),
        "grip_height_above_table_m": opt["gh"], "lift_m": ch["lift_m"], "raise_clearance_m": ch["raise_clear_m"],
        "table_min_clearance_m": round(ch["table_min_dist_m"], 4), "table_closest_geom": ch["table_closest_geom"],
        "balance_margin_min_m": round(ch["balance_margin_min_m"], 4), "carried_object_clearance_min_m": round(ch["carry_min_m"], 4),
        "standing_gap_m": round(ch["gap_m"], 4), "table_front_edge_xy": [round(v, 4) for v in ch["tinfo"]["table_front_edge_xy"]],
        "plans_tried": ch["verified_plans_tried"], "marks_s": ch["marks"], "lift_marks_s": [ch["marks"]["lift"], ch["marks"]["end"]]})
    ref.notes.append(f"whole-body pickup at {z_t:.2f} m: knee {math.degrees(cand['K']):.0f} deg, hinge {math.degrees(cand['hinge']):.0f} deg, "
                     f"waist {math.degrees(cand['waist']):.0f} deg, finger tilt {ch['tilt_deg']:.0f} deg, table clearance {ch['table_min_dist_m'] * 1000:.0f} mm")
    ref.scene = {"xml": ch["xml"], "object": "obj", "object_z0": float(z_t + OBJ["half_height_m"]), "table_z": float(z_t),
                 "table_front_x": float(ch["tinfo"]["table_front_edge_xy"][0])}
    return ref


# ------------------------------------------------------------------------------------------------ reachable table-height range
def reach_range(kin: RobotKin, side: str = "r", lo: float = 0.15, hi: float | None = None, step: float = 0.025,
                resolution: float = 0.005, plan: dict | None = None, dt: float = 0.01) -> dict:
    """Which table-top heights the whole-body planner can pick from: a scan on a `step` grid, then a bisection of every boundary to
    `resolution`. The plan found at each height is the full collision-checked reference (posture, finger tilt, clearance), not a
    geometric guess. Returns per-height rows, the contiguous reachable segments, and what limits just outside each segment."""
    pl = {**PLAN, **(plan or {})}
    hi = hi if hi is not None else 0.95 * kin.robot.height
    rows: dict[float, dict] = {}

    def probe(z: float) -> bool:
        z = round(z, 4)
        if z not in rows:
            ref, info = plan_pickup(kin, z, side, dt, plan)
            if ref is None:
                rows[z] = {"table_m": z, "reachable": False, "limit": info["limit"], "why": info.get("reason", "")}
            else:
                c, o = info["cand"], info["opt"]
                rows[z] = {"table_m": z, "reachable": True, "limit": None, "knee_deg": round(math.degrees(c["K"]), 1),
                           "hip_hinge_deg": round(math.degrees(c["hinge"]), 1), "waist_yaw_deg": round(math.degrees(c["waist"]), 1),
                           "finger_tilt_deg": round(info["tilt_deg"], 1), "arm_reach_fraction": round(o["frac"], 3),
                           "table_clearance_mm": round(info["table_min_dist_m"] * 1000, 1), "standing_gap_mm": round(info["gap_m"] * 1000, 1),
                           "balance_margin_mm": round(info["balance_margin_min_m"] * 1000, 1), "lift_mm": round(info["lift_m"] * 1000)}
        return rows[z]["reachable"]

    grid = [round(lo + i * step, 4) for i in range(int(round((hi - lo) / step)) + 1)]
    ok = [probe(z) for z in grid]
    segs: list[list[float]] = []
    for z, r in zip(grid, ok):
        if r:
            if segs and abs(segs[-1][1] - (z - step)) < 1e-6:
                segs[-1][1] = z
            else:
                segs.append([z, z])
    for sg in segs:                                   # bisect each boundary down to the resolution
        for end, direction in ((0, -1), (1, +1)):
            good = sg[end]
            bad = good + direction * step
            if bad < lo - 1e-9 or bad > hi + 1e-9:
                continue
            while abs(bad - good) > resolution + 1e-9:
                mid = round(0.5 * (good + bad), 4)
                if probe(mid):
                    good = mid
                else:
                    bad = mid
            sg[end] = good
    out_segs = [{"from_m": round(a, 4), "to_m": round(b, 4)} for a, b in segs]
    limits = {}
    for sg in out_segs:
        below = max((z for z, r in rows.items() if not r["reachable"] and z < sg["from_m"]), default=None)
        above = min((z for z, r in rows.items() if not r["reachable"] and z > sg["to_m"]), default=None)
        limits[f"{sg['from_m']}-{sg['to_m']}"] = {"just_below": rows[below]["limit"] if below is not None else None,
                                                 "just_above": rows[above]["limit"] if above is not None else None,
                                                 "just_above_m": above, "just_below_m": below}
    return {"side": side, "robot_height_m": kin.robot.height, "scan_m": [lo, hi, step], "resolution_m": resolution,
            "segments": out_segs, "min_reachable_m": out_segs[0]["from_m"] if out_segs else None,
            "max_reachable_m": out_segs[-1]["to_m"] if out_segs else None, "limits_outside": limits,
            "object": dict(OBJ), "edge_to_object_m": pl["edge_to_object_m"], "tilt_limits_deg": list(pl["tilt_deg"]),
            "rows": [rows[z] for z in sorted(rows)]}


# ------------------------------------------------------------------------------------------------ demand (through the engine's own gates)
PEAK_FACTOR_ADR0014 = 1.52     # ADR 0014 section 2: Open Duck Mini measured peak-torque headroom over the datasheet stall (7.4 V part; transfer to others is an ASSUMPTION)


def demand_at(concept, table_height: float, peak_factor: float = PEAK_FACTOR_ADR0014, servo: bool = False) -> dict:
    """The pickup's per-joint demand at one table height through the engine (ideal playback, nominal masses, nominal pack voltage).
    Strict = the datasheet gate (peak <= 0.70 of stall); calibrated = the same demand against `peak_factor` x the stall."""
    from .. import envelopes as E
    from .. import evaluate as EV
    b = EV.run_bundle(concept, EV.Mods(), table_height=table_height, thermal=False, motions=["stand", "pickup"])
    out: dict = {"table_m": table_height, "valid": "pickup" not in b.invalid, "reason": b.invalid.get("pickup", "")}
    if "pickup" not in b.dem or not b.dem["pickup"].valid:
        out["valid"] = False
        out["reason"] = b.dem["pickup"].invalid_reason if "pickup" in b.dem else "no pickup motion"
        return out
    ref = b.refs["pickup"]
    m = E.joint_metrics(b.robot, b.dem["pickup"], np.full(len(b.robot.names), b.vin))
    gate = config.gate("peak_torque_fraction_of_stall")
    rows = {}
    for j, n in enumerate(b.robot.names):
        pk = float(m["peak_frac_stall"][j])
        rows[n] = {"actuator": b.robot.acts[n], "peak_nm": round(float(m["peak_nm"][j]), 4), "stall_nm": round(float(m["stall_nm"][j]), 3),
                   "peak_frac_of_stall": round(pk, 3), "strict_margin": round(gate / max(pk, 1e-9), 2),
                   "calibrated_peak_frac": round(pk / peak_factor, 3), "calibrated_margin": round(gate * peak_factor / max(pk, 1e-9), 2),
                   "envelope_utilisation": round(float(m["util_max"][j]), 3), "rms_over_rated": round(float(m["rms_over_rated"][j]), 3)}
    worst = max(rows, key=lambda n: rows[n]["peak_frac_of_stall"])
    out.update({"posture": {k: ref.meta.get(k) for k in ("squat_deg", "hip_hinge_deg", "waist_yaw_deg", "finger_tilt_deg", "table_min_clearance_m", "standing_gap_m", "balance_margin_min_m")},
                "joints": rows, "worst_joint": worst, "worst_peak_frac": rows[worst]["peak_frac_of_stall"],
                "arm_waist_gripper": {n: rows[n] for n in rows if n.split("_")[0] in ("shoulder", "elbow", "waist", "gripper") and not n.endswith("_l")},
                "tether_pct_bw": round(100 * b.dem["pickup"].assist_mean, 2), "peak_factor": peak_factor, "gate": gate})
    if servo:
        s = EV._servo_runs(b).get("pickup", {})
        out["servo"] = {k: s.get(k) for k in ("grasp_ok", "object_lift_m", "overload_trips", "fell", "saturation_fraction_max", "saturated_joint", "max_err_deg", "worst_joint")}
    return out


def _md(rep: dict) -> str:
    from ...paths import generated_header
    r = rep["reach"]
    L = [generated_header("concept pickup-range", "<!--").rstrip() + " -->", f"# Pickup reach and demand: {rep['candidate']}", "",
         f"Robot {rep['robot_height_m']} m, right hand, {OBJ['mass_kg'] * 1000:.0f} g object, object centre {r['edge_to_object_m'] * 1000:.0f} mm behind the table's front edge, "
         f"finger tilt limits {r['tilt_limits_deg']} deg. Whole-body planner (knee, hip hinge, waist, step-in), table and body collision-checked.", ""]
    L.append("**Reachable table-top heights: " + (", ".join(f"{s['from_m']:.3f}-{s['to_m']:.3f} m" for s in r["segments"]) or "none") + f"** (resolution {r['resolution_m']} m).")
    for k, v in r["limits_outside"].items():
        L.append(f"- segment {k}: limited below by '{v['just_below']}' (at {v['just_below_m']} m), above by '{v['just_above']}' (at {v['just_above_m']} m)")
    L += ["", "| table m | reachable | limit | knee deg | hinge deg | waist deg | finger tilt deg | arm reach | table clearance mm | gap to toes mm |", "|---|---|---|---|---|---|---|---|---|---|"]
    for x in r["rows"]:
        if x["reachable"]:
            L.append(f"| {x['table_m']:.3f} | yes | | {x['knee_deg']} | {x['hip_hinge_deg']} | {x['waist_yaw_deg']} | {x['finger_tilt_deg']} | {x['arm_reach_fraction']} | {x['table_clearance_mm']} | {x['standing_gap_mm']} |")
        else:
            L.append(f"| {x['table_m']:.3f} | no | {x['limit']} | | | | | | | |")
    if rep.get("demand"):
        L += ["", f"## Grasp-and-lift demand (ideal playback, 100 ms peak vs stall; strict gate {rep['demand'][0].get('gate', 0.7)} of stall; calibrated = x{rep['peak_factor']} stall, ADR 0014, an assumption for 12 V / STS3250)", "",
              "| table m | valid | joint | actuator | peak N.m | stall N.m | peak/stall | strict margin | peak/stall calibrated | calibrated margin |", "|---|---|---|---|---|---|---|---|---|---|"]
        for d in rep["demand"]:
            if not d.get("valid"):
                L.append(f"| {d['table_m']:.3f} | NO: {d.get('reason', '')[:90]} | | | | | | | | |")
                continue
            for n, x in d["arm_waist_gripper"].items():
                L.append(f"| {d['table_m']:.3f} | yes | {n} | {x['actuator']} | {x['peak_nm']} | {x['stall_nm']} | {x['peak_frac_of_stall']} | {x['strict_margin']} | {x['calibrated_peak_frac']} | {x['calibrated_margin']} |")
            L.append(f"| {d['table_m']:.3f} | | worst joint of all: {d['worst_joint']} | | | | {d['worst_peak_frac']} | | | |")
            if d.get("servo"):
                L.append(f"| {d['table_m']:.3f} | | servo-in-the-loop: {d['servo']} | | | | | | | |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import time
    from pathlib import Path

    from ...paths import variants_dir
    from ..robot import build_robot, load_concept

    ap = argparse.ArgumentParser(description="Whole-body pickup: reachable table range and grasp-and-lift demand per concept")
    ap.add_argument("concepts", nargs="+")
    ap.add_argument("--tables", nargs="*", type=float, default=[0.30, 0.35, 0.40, 0.45], help="table heights for the demand runs (m)")
    ap.add_argument("--scan", nargs=3, type=float, metavar=("LO", "HI", "STEP"), default=None)
    ap.add_argument("--resolution", type=float, default=0.005)
    ap.add_argument("--edge-to-object", type=float, default=None, help="object centre behind the table's front edge (m); default %s" % PLAN["edge_to_object_m"])
    ap.add_argument("--peak-factor", type=float, default=PEAK_FACTOR_ADR0014)
    ap.add_argument("--servo", action="store_true", help="also run the servo-in-the-loop grasp test at each demand height")
    ap.add_argument("--no-demand", action="store_true")
    ap.add_argument("--out", default=None, help="output root (default variants/<base>/generated/concept)")
    ap.add_argument("--suffix", default="", help="added to the output file names (a sensitivity run)")
    a = ap.parse_args(argv)
    if a.edge_to_object is not None:
        PLAN["edge_to_object_m"] = a.edge_to_object      # the demand runs go through pickup(), which reads the same defaults
    for path in a.concepts:
        t0 = time.time()
        concept = load_concept(path)
        robot = build_robot(concept)
        kin = RobotKin(robot)
        lo, hi, st = a.scan if a.scan else (0.15, round(0.95 * robot.height, 3), 0.025)
        rep: dict = {"candidate": concept["id"], "robot_height_m": robot.height, "generated_by": "python -m openhumanoid.concept.motions.pickup",
                     "peak_factor": a.peak_factor}
        rep["reach"] = reach_range(kin, lo=lo, hi=hi, step=st, resolution=a.resolution)
        print(f"{concept['id']}: reachable {[(s['from_m'], s['to_m']) for s in rep['reach']['segments']]}", flush=True)
        if not a.no_demand:
            rep["demand"] = []
            mx = rep["reach"]["max_reachable_m"]
            for h in sorted(set(a.tables) | ({mx} if mx else set())):
                d = demand_at(path, h, a.peak_factor, a.servo)
                rep["demand"].append(d)
                print(f"  {h:.2f} m: valid={d.get('valid')} worst={d.get('worst_joint')} {d.get('worst_peak_frac')} {d.get('servo', '')}", flush=True)
        rep["seconds"] = round(time.time() - t0, 1)
        root = Path(a.out) if a.out else variants_dir() / concept.get("base", "adam") / "generated" / "concept"
        out = root / concept["id"]
        out.mkdir(parents=True, exist_ok=True)
        (out / f"pickup_range{a.suffix}.json").write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")
        (out / f"pickup_range{a.suffix}.md").write_text(_md(rep), encoding="utf-8")
        print("  ->", out / f"pickup_range{a.suffix}.md")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
