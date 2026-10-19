"""Push recovery (requirement R10: balance recovery / fall prevention is a MUST), redefined after challenge #2.

THE REQUIREMENT IS AN ABSOLUTE IMPULSE. Every candidate must survive the same push `J` (N.s, thresholds.yaml
`motions.push.required_impulse_Ns`, PROVISIONAL pending the maintainer), recovered by ANY combination of strategies:

  ankle strategy   the centre of pressure (COP) moves inside the support polygon (double support: the hull of both feet)
  hip strategy     the trunk pitches about the hips (flywheel term on the effective COP). Forward pushes only. Treated as
                   UNAVAILABLE beyond the trunk speed the hip servos can deliver; it is never a blocker by itself
  steps            up to two capture steps to the capture point, swing time swept over 0.15-0.35 s; a stepping leg that cannot
                   reach crouches the stance leg (knee flexion up to a cap)

in these scenarios (a push is a velocity change of the whole body, dv = J / M, applied to the free base):
  stand_fwd / stand_lat      standing in double support. Lateral: ankle / hip-roll load shifting inside the double-support polygon
                             FIRST, a step only for what lies beyond the polygon
  walk_fwd / walk_lat_out / walk_lat_in    at mid single support of `walk_forward` (the third step of the frozen gait); the swing
                             foot is already in flight and is re-targeted; lat_out pushes the body past the stance foot (the swing
                             foot must cross-step), lat_in pushes it towards the swing foot

THE GATE is one number per scenario: the largest recoverable impulse must be >= the requirement. `largest_recoverable()` bisects on
J (plan, then actuator demand) and reports it in N.s and m/s so the maintainer can choose the requirement with numbers.

MODEL. LIPM in the horizontal plane with the exact constant-COP update, COP = xi + K (xi - xi_ref) clipped to the support polygon
(foot rectangles shrunk to `cop_margin_frac`), reaction delay = servo command delay + control tick + sensing, the COM falling freely
until then. The COP is referenced to the FOOT CENTRE (challenge-2 row 9): the old plan referenced it to the initial COM, which sat
7 mm behind the foot centre. The landing point is the capture point at touchdown (+ a margin). Plan caveats, all optimistic: perfect
state estimate, instant unloading of the stepping foot, no foot rotation, no collision between feet / legs (a cross-step is placed
behind or ahead of the stance foot by a foot length so the swept foot clears it), COM height changes only through the planned crouch.
Backward pushes are not run (kinematically similar to forward, but hip extension is CAD-limited to 40 deg: a known gap).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .. import config
from ..kin import Reference, RobotKin, compensate_com, quat_from_yaw_pitch, smoothstep5
from .common import fill_legs, finish, knee_flex_from, rest_upper_body, stand_geometry

G = 9.81
DT = 0.01
SCENARIOS = ("stand_fwd", "stand_lat", "walk_fwd", "walk_lat_out", "walk_lat_in")
KINDS = SCENARIOS                      # the evaluator iterates `push_mod.KINDS`


# ------------------------------------------------------------------------------------------------ small geometry helpers
def _box(cx: float, cy: float, mx: float, my: float):
    return [(cx - mx, cy - my), (cx + mx, cy - my), (cx + mx, cy + my), (cx - mx, cy + my)]


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def _closest_on_segment(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return (ax + t * dx, ay + t * dy)


def _clip_to_polygon(p, poly):
    """Closest point of a convex polygon (counter-clockwise hull) to p."""
    n = len(poly)
    inside = True
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) < 0:
            inside = False
            break
    if inside:
        return p
    best, bd = poly[0], 1e18
    for i in range(n):
        q = _closest_on_segment(p, poly[i], poly[(i + 1) % n])
        d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2
        if d < bd:
            best, bd = q, d
    return best


def _inside_shrunk(p, poly, shrink: float):
    cx = sum(q[0] for q in poly) / len(poly)
    cy = sum(q[1] for q in poly) / len(poly)
    sp = [(cx + shrink * (q[0] - cx), cy + shrink * (q[1] - cy)) for q in poly]
    c = _clip_to_polygon(p, sp)
    return (c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2 < 1e-12


def _lipm_step(c, v, p, w, dt):
    ch, sh = math.cosh(w * dt), math.sinh(w * dt)
    return ((p[0] + (c[0] - p[0]) * ch + v[0] / w * sh, p[1] + (c[1] - p[1]) * ch + v[1] / w * sh),
            (w * (c[0] - p[0]) * sh + v[0] * ch, w * (c[1] - p[1]) * sh + v[1] * ch))


def _reach(dh: float, l0: float, dz_max: float, rmax: float):
    """(crouch dz, horizontal distance actually reached). The swing hip is l0 - dz above the ankle plane; the leg reaches rmax."""
    if dh * dh + l0 * l0 <= rmax * rmax:
        return 0.0, dh
    vmin = l0 - dz_max
    if vmin >= rmax:
        return dz_max, 0.0
    r_h = math.sqrt(rmax * rmax - vmin * vmin)
    if dh <= r_h:
        return l0 - math.sqrt(rmax * rmax - dh * dh), dh
    return dz_max, r_h


# ------------------------------------------------------------------------------------------------ options and plans
@dataclass(frozen=True)
class Option:
    """A combination of strategies. steps = how many capture steps are ALLOWED (a second is taken only if still needed);
    swing_s = swing time of a step; hip = trunk (hip) strategy."""
    steps: int = 0
    swing_s: float | None = None
    hip: bool = False

    @property
    def label(self) -> str:
        if self.steps == 0:
            return "ankle+hip" if self.hip else "ankle"
        return f"ankle+{self.steps}step@{self.swing_s * 1000:.0f}ms"


def options_for(scenario: str, allow_hip: bool = True) -> list[Option]:
    """Every combination tried for a scenario, simplest first."""
    cfg = config.motions()["push"]
    out = [Option(0)]
    if scenario == "stand_fwd" and allow_hip:
        out.append(Option(0, None, True))
    for n in range(1, int(cfg["max_steps"]) + 1):
        for t in cfg["swing_times_s"]:
            out.append(Option(n, float(t)))
    return out


@dataclass
class Plan:
    scenario: str
    option: Option
    impulse_Ns: float
    ok: bool = False                     # the LIPM plan recovers
    reason: str = ""
    c: np.ndarray | None = None
    v: np.ndarray | None = None
    p: np.ndarray | None = None
    th: np.ndarray | None = None
    dz: np.ndarray | None = None
    foot: dict | None = None             # {"l": (T,3) ankle x, y, lift ; "r": ...}
    k_push: int = 0
    k_react: int = 0
    meta: dict = field(default_factory=dict)


def reaction_delay_s(kin: RobotKin) -> float:
    cfg = config.motions()["push"]
    servo = max(s.delay_s for s in kin.robot.servo.values())
    return servo + cfg["control_period_s"] + cfg["sensing_latency_s"]


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


# ------------------------------------------------------------------------------------------------ scenario set-up
@dataclass
class Setup:
    """Everything about a scenario that does not depend on the impulse or the strategy."""
    scenario: str
    kin: RobotKin
    dt: float
    T: int
    k_push: int
    zc: float
    M: float
    off0: np.ndarray
    I_tr: float
    pelvis_z: float
    leg_len0: float
    c0: np.ndarray                       # COM xy just before the push
    v0: np.ndarray
    foot0: dict                          # ankle xy + lift of both feet at the push
    pre: dict                            # per-sample arrays up to the push: c, zmp, foot l / r (x, y, lift)
    dir: np.ndarray                      # unit push direction (xy)
    stance: str | None                   # walk: the stance foot at the push (None: double support)
    nominal: dict | None                 # walk: the nominal swing continuation and its landing sample
    zmp_full: object                     # k -> nominal COP at sample k
    walk_ref: Reference | None = None


def _stand_setup(kin: RobotKin, scenario: str) -> Setup:
    cfg = config.motions()["push"]
    lg = kin.lg
    sg = stand_geometry(kin, knee_flex_from(kin))
    ones = np.ones(1)
    Q0 = rest_upper_body(kin, 1)
    pel0 = np.array([[0.0, 0.0, sg["pelvis_z"]]])
    ank0 = {"l": np.array([[0.0, lg.hip_y, lg.ankle_h]]), "r": np.array([[0.0, -lg.hip_y, lg.ankle_h]])}
    fill_legs(kin, Q0, pel0, 0 * ones, 0 * ones, ank0["l"], ank0["r"], 0 * ones, 0 * ones)
    quat0 = quat_from_yaw_pitch(0 * ones, 0 * ones)[0]
    com0 = kin.com(Q0[0], pel0[0], quat0)
    off0 = com0[:2] - pel0[0, :2]
    M = float(sum(kin.model.body_mass))
    I_tr = trunk_inertia_about_hip(kin, Q0[0], pel0[0], quat0)
    k_push = int(round(cfg["push_time_s"] / DT))
    T = k_push + int(round(cfg["horizon_s"] / DT)) + 1
    # the COM stands over the FOOT CENTRE (the stand reference does the same): the COP limits are referenced to the foot centre
    c0 = np.array([lg.foot_off, 0.0])
    foot0 = {"l": np.array([0.0, lg.hip_y, 0.0]), "r": np.array([0.0, -lg.hip_y, 0.0])}
    pre = {"c": np.tile(c0, (k_push + 1, 1)), "zmp": np.tile(c0, (k_push + 1, 1)),
           "l": np.tile(foot0["l"], (k_push + 1, 1)), "r": np.tile(foot0["r"], (k_push + 1, 1))}
    d = np.array([1.0, 0.0]) if scenario == "stand_fwd" else np.array([0.0, 1.0])
    return Setup(scenario, kin, DT, T, k_push, float(com0[2]), M, off0, I_tr, sg["pelvis_z"], sg["leg_len"], c0, np.zeros(2), foot0, pre, d, None, None,
                 lambda k: c0)


def _walk_setup(kin: RobotKin, scenario: str) -> Setup:
    from . import walk as walk_mod
    cfg = config.motions()["push"]
    ref = walk_mod.walk(kin, "forward", n_steps=int(cfg["walk_steps_built"]))
    a = ref.aux
    dt = a["dt"]
    n_p = int(cfg["walk_push_step_index"])
    k0 = a["n_init"] + n_p * a["n_step"]
    k_push = k0 + a["n_ss"] // 2                    # mid single support
    sup = a["support"][n_p]
    sw = "r" if sup == "l" else "l"
    com = a["com"]
    v0 = (com[k_push + 1] - com[k_push - 1]) / (2 * dt)
    foot = a["foot"]
    sgn_st = 1.0 if sup == "l" else -1.0
    if scenario == "walk_fwd":
        d = np.array([1.0, 0.0])
    elif scenario == "walk_lat_out":
        d = np.array([0.0, sgn_st])                 # past the stance foot: the swing foot has to cross
    else:
        d = np.array([0.0, -sgn_st])                # towards the swing foot
    n_sw_nom = max(4, min(a["n_ss"], a["n_step"] - 1))
    nominal = {"sw": sw, "k_land": k0 + n_sw_nom, "foot": {s: foot[s][:, :3].copy() for s in "lr"}}
    T = k_push + int(round(cfg["horizon_s"] / dt)) + 1
    pre = {"c": com[:k_push + 1].copy(), "zmp": a["zmp"][:k_push + 1].copy(), "l": foot["l"][:k_push + 1, :3].copy(), "r": foot["r"][:k_push + 1, :3].copy()}
    foot0 = {s: foot[s][k_push, :3].copy() for s in "lr"}
    M = float(sum(kin.model.body_mass))
    sg = stand_geometry(kin, knee_flex_from(kin))
    zm = a["zmp"]
    return Setup(scenario, kin, dt, T, k_push, a["zc"], M, a["off0"], 0.0, a["pelvis_z"], sg["leg_len"], com[k_push].copy(), v0, foot0, pre, d, sup, nominal,
                 lambda k: zm[min(k, len(zm) - 1)], ref)


def make_setup(kin: RobotKin, scenario: str) -> Setup:
    assert scenario in SCENARIOS, scenario
    return _stand_setup(kin, scenario) if scenario.startswith("stand") else _walk_setup(kin, scenario)


def _crouch_cap(S: Setup) -> float:
    """Largest pelvis drop (m) the stance leg may use: knee flexion up to `crouch_knee_max_deg` and never past the knee range."""
    cfg = config.motions()["push"]
    lg = S.kin.lg
    kmax = math.radians(cfg["crouch_knee_max_deg"])
    for j in S.kin.robot.joints:
        if j["base"] == "knee":
            kmax = min(kmax, math.radians(j["range"][1]) - math.radians(5.0))
    if kmax <= knee_flex_from(S.kin):
        return 0.0
    l_min = math.sqrt(lg.L1 ** 2 + lg.L2 ** 2 + 2 * lg.L1 * lg.L2 * math.cos(kmax))
    return max(S.leg_len0 - l_min, 0.0)


# ------------------------------------------------------------------------------------------------ the LIPM plan
def simulate(S: Setup, impulse_Ns: float, opt: Option, hip_speed_cap: float | None = None) -> Plan:
    """LIPM recovery plan for one impulse and one combination of strategies. Pure Python floats: a few ms."""
    cfg = config.motions()["push"]
    kin, lg = S.kin, S.kin.lg
    dt, T, kp = S.dt, S.T, S.k_push
    K = cfg["dcm_gain"]
    cf = cfg["cop_margin_frac"]
    mx, my = cf * lg.foot_len / 2, cf * lg.foot_w / 2
    foff = lg.foot_off
    d_r = reaction_delay_s(kin)
    n_react = kp + max(1, int(math.ceil(d_r / dt - 1e-9)))
    dvv = impulse_Ns / S.M
    dv = (dvv * float(S.dir[0]), dvv * float(S.dir[1]))
    plan = Plan(S.scenario, opt, impulse_Ns, k_push=kp, k_react=n_react)
    c = np.zeros((T, 2)); v = np.zeros((T, 2)); pp = np.zeros((T, 2)); th = np.zeros(T); dz = np.zeros(T)
    foot = {s: np.zeros((T, 3)) for s in "lr"}
    for s in "lr":
        foot[s][:kp + 1] = S.pre[s]
        foot[s][kp + 1:] = S.foot0[s]
    c[:kp + 1] = S.pre["c"]
    pp[:kp + 1] = S.pre["zmp"]
    cur_c = (float(S.c0[0]), float(S.c0[1]))
    cur_v = (float(S.v0[0]) + dv[0], float(S.v0[1]) + dv[1])
    v[kp] = S.v0 + np.array(dv)
    alpha_max, th_max = cfg["trunk_alpha_max_rad_s2"], math.radians(cfg["trunk_pitch_max_deg"])
    thv = 0.0
    walk = S.nominal is not None
    loaded = {S.stance} if walk else {"l", "r"}
    sw_foot = S.nominal["sw"] if walk else None
    clearance, land_margin = cfg["capture_clearance_m"], cfg["land_margin_m"]
    dz_max = _crouch_cap(S)
    l0 = S.leg_len0
    rmax = cfg["reach_frac"] * (lg.L1 + lg.L2)
    zc0 = S.zc
    landings, st = [], None
    steps_done, clipped_any = 0, False
    phase = "pre"

    def centre(f, k):
        return (float(foot[f][k, 0]) + foff, float(foot[f][k, 1]))

    def polygon(k, loaded_set):
        pts = []
        for f in loaded_set:
            cx, cy = centre(f, k)
            pts += _box(cx, cy, mx, my)
        return _hull(pts)

    def xi_ref_of(k, loaded_set):
        cs = [centre(f, k) for f in loaded_set]
        return (sum(x for x, _ in cs) / len(cs), sum(y for _, y in cs) / len(cs))

    def w_of(zdrop):
        return math.sqrt(G / max(zc0 - zdrop, 0.05))

    def predict_capture(k, st_foot, n_sw, dz_final, c_in, v_in):
        ctr = centre(st_foot, k)
        poly = _hull(_box(ctr[0], ctr[1], mx, my))
        cc, vv = c_in, v_in
        for j in range(n_sw):
            w = w_of(dz_final * float(smoothstep5((j + 1) / n_sw)))
            xi = (cc[0] + vv[0] / w, cc[1] + vv[1] / w)
            pd = (xi[0] + K * (xi[0] - ctr[0]), xi[1] + K * (xi[1] - ctr[1]))
            cc, vv = _lipm_step(cc, vv, _clip_to_polygon(pd, poly), w, dt)
        w = w_of(dz_final)
        return (cc[0] + vv[0] / w, cc[1] + vv[1] / w), cc

    def plan_step(k, swing_f, c_in, v_in, first=True):
        """Landing point (swing-foot ankle xy), crouch and timing for a step that starts at sample k."""
        stf = "r" if swing_f == "l" else "l"
        n_sw = max(3, int(round(opt.swing_s / dt)))
        sx, sy = centre(swing_f, k)
        stx, sty = centre(stf, k)
        dzs, clipped, xi_l, tx, ty = 0.0, False, None, sx, sy
        for _it in range(3):
            xi_l, c_l = predict_capture(k, stf, n_sw, dzs, c_in, v_in)
            # the foot lands ON the capture point (plus a margin along the push), but never narrower than its nominal stance width
            # and never closer than a foot width to the stance foot; a lateral drift during the swing therefore widens the step
            side = 1.0 if sy >= sty else -1.0
            tx = max(xi_l[0] + land_margin * float(S.dir[0]), sx)
            ty = sty + side * max(side * (xi_l[1] + land_margin * float(S.dir[1]) - sty), abs(sy - sty), lg.foot_w + 0.01)
            if first and S.scenario == "walk_lat_out":
                ahead = 1.0 if sx >= stx else -1.0
                tx = stx + ahead * (lg.foot_len + 0.01)          # cross-step: clears the stance foot by a foot length
                side_out = 1.0 if S.dir[1] > 0 else -1.0
                ty = sty + side_out * max(side_out * (xi_l[1] + land_margin * float(S.dir[1]) - sty), lg.foot_w + 0.01)
            elif S.scenario == "stand_lat":
                tx = sx
                ty = sty + side * max(side * (xi_l[1] + land_margin * float(S.dir[1]) - sty), abs(sy - sty))
            hip_sgn = 1.0 if swing_f == "l" else -1.0
            hx, hy = c_l[0] - float(S.off0[0]), c_l[1] - float(S.off0[1]) + hip_sgn * lg.hip_y
            ax, ay = tx - foff, ty
            dh = math.hypot(ax - hx, ay - hy)
            need, dh_ok = _reach(dh, l0, dz_max, rmax)
            if dh_ok < dh - 1e-9:
                f = dh_ok / dh
                ax, ay = hx + (ax - hx) * f, hy + (ay - hy) * f
                tx, ty = ax + foff, ay
                clipped = True
            dzs = min(need * 1.02, dz_max) if need > 0 else 0.0
        return {"swing": swing_f, "stance": stf, "n_sw": n_sw, "k0": k, "k_land": k + n_sw, "target": (tx - foff, ty), "dz": dzs, "clipped": clipped, "capture": xi_l}

    for k in range(kp, T - 1):
        # ---------------- events at the start of sample k
        if k == n_react:
            if walk:
                phase = "ss_nominal" if opt.steps == 0 else "step"
                if opt.steps >= 1:
                    st = plan_step(k, sw_foot, cur_c, cur_v)
                    loaded = {st["stance"]}
            else:
                phase = "ds"
                if opt.steps >= 1:
                    swf = "r" if S.scenario == "stand_fwd" else ("l" if S.dir[1] > 0 else "r")
                    st = plan_step(k, swf, cur_c, cur_v)
                    phase, loaded = "step", {st["stance"]}
        if phase == "step" and k == st["k_land"]:
            foot[st["swing"]][k, 2] = 0.0
            steps_done += 1
            clipped_any = clipped_any or st["clipped"]
            landings.append({"t_s": float(k * dt), "ankle_xy": [float(st["target"][0]), float(st["target"][1])], "foot": st["swing"],
                             "capture_point_xy": [float(st["capture"][0]), float(st["capture"][1])], "crouch_m": float(st["dz"]), "clipped": bool(st["clipped"])})
            prev_stance, prev_swing = st["stance"], st["swing"]
            loaded, phase, st = {"l", "r"}, "ds", None
            if steps_done < opt.steps:
                w1 = w_of(float(dz[k]))
                xi1 = (cur_c[0] + cur_v[0] / w1, cur_c[1] + cur_v[1] / w1)
                if not _inside_shrunk(xi1, polygon(k, loaded), cfg["second_step_trigger_shrink"]):
                    # the foot nearer the COM (laterally) carries the body, the other steps: unloading the foot the COM is over is not possible
                    sup_f = "l" if abs(cur_c[1] - centre("l", k)[1]) <= abs(cur_c[1] - centre("r", k)[1]) else "r"
                    swf2 = "r" if sup_f == "l" else "l"
                    st = plan_step(k, swf2, cur_c, cur_v, first=False)
                    phase, loaded = "step", {sup_f}
        if walk and phase == "ss_nominal" and k == S.nominal["k_land"]:
            landings.append({"t_s": float(k * dt), "ankle_xy": [float(foot[sw_foot][k, 0]), float(foot[sw_foot][k, 1])], "foot": sw_foot,
                             "capture_point_xy": None, "crouch_m": 0.0, "clipped": False, "nominal": True})
            loaded, phase = {"l", "r"}, "ds"
        # ---------------- COP
        w = w_of(float(dz[k]))
        if k < n_react:
            zk = S.zmp_full(k)
            p = (float(zk[0]), float(zk[1]))
        else:
            xi = (cur_c[0] + cur_v[0] / w, cur_c[1] + cur_v[1] / w)
            poly = polygon(k, loaded)
            ref = xi_ref_of(k, loaded)
            pd = (xi[0] + K * (xi[0] - ref[0]), xi[1] + K * (xi[1] - ref[1]))
            p = _clip_to_polygon(pd, poly)
            if opt.hip and phase == "ds":
                extra = pd[0] - p[0]
                if abs(extra) > 1e-9:
                    ang = max(-alpha_max, min(alpha_max, extra * S.M * G / S.I_tr))
                else:
                    ang = -2 * 0.9 * 10.0 * thv - 100.0 * th[k]
                if (th[k] >= th_max and ang > 0) or (th[k] <= -th_max and ang < 0):
                    ang = 0.0
                    thv *= 0.9
                thv += ang * dt
                th[k + 1] = th[k] + thv * dt
                if abs(th[k + 1]) > th_max:
                    th[k + 1] = math.copysign(th_max, th[k + 1])
                    thv = 0.0
                p = (p[0] + S.I_tr * ang / (S.M * G), p[1])      # the flywheel acts as an extra COP shift along x
        pp[k] = p
        # ---------------- feet and crouch for sample k+1
        dz[k + 1] = dz[k]
        for f in "lr":
            foot[f][k + 1] = foot[f][k]
        if phase == "step":
            j = k + 1 - st["k0"]
            s_ = float(smoothstep5(j / st["n_sw"]))
            a0 = foot[st["swing"]][st["k0"]]
            foot[st["swing"]][k + 1, 0] = a0[0] + (st["target"][0] - a0[0]) * s_
            foot[st["swing"]][k + 1, 1] = a0[1] + (st["target"][1] - a0[1]) * s_
            foot[st["swing"]][k + 1, 2] = float(a0[2]) * (1 - s_) + clearance * math.sin(math.pi * min(j / st["n_sw"], 1.0))
            dz[k + 1] = max(float(dz[st["k0"]]), st["dz"] * s_)
        elif walk and phase in ("pre", "ss_nominal"):
            for f in "lr":
                foot[f][k + 1] = S.nominal["foot"][f][min(k + 1, len(S.nominal["foot"][f]) - 1)]
            if phase == "ss_nominal" and k + 1 >= S.nominal["k_land"]:
                foot[sw_foot][k + 1, 2] = 0.0
        cur_c, cur_v = _lipm_step(cur_c, cur_v, p, w, dt)
        c[k + 1], v[k + 1] = cur_c, cur_v
    pp[-1] = pp[-2]
    # ---------------- outcome
    w_end = w_of(float(dz[-1]))
    xi_end = (c[-1, 0] + v[-1, 0] / w_end, c[-1, 1] + v[-1, 1] / w_end)
    ref_end = xi_ref_of(T - 1, {"l", "r"})
    dist = math.hypot(xi_end[0] - ref_end[0], xi_end[1] - ref_end[1])
    settled = dist < cfg["settle_tol_frac"] * min(mx, my) and math.hypot(float(v[-1, 0]), float(v[-1, 1])) < cfg["settle_speed_mps"]
    sane = float(np.abs(c - c[kp]).max()) < cfg["max_com_excursion_m"]
    trunk_speed = float(np.abs(np.gradient(th, dt)).max()) if opt.hip else 0.0
    speed_ok = not (opt.hip and hip_speed_cap is not None and trunk_speed > hip_speed_cap)
    plan.ok = bool(settled and sane and speed_ok and phase not in ("step", "ss_nominal", "pre"))
    if not plan.ok:
        plan.reason = ("hip strategy needs a trunk pitch speed of %.1f rad/s, the hip servos give %.1f rad/s" % (trunk_speed, hip_speed_cap or 0.0)) if (settled and not speed_ok) else \
                      ("COM left the sane region" if not sane else "capture point left the support polygon: no recovery with this strategy")
    plan.c, plan.v, plan.p, plan.th, plan.dz, plan.foot = c, v, pp, th, dz, foot
    plan.meta = {"landings": landings, "steps_taken": steps_done, "clipped": bool(clipped_any), "trunk_pitch_peak_deg": float(np.degrees(np.abs(th).max())),
                 "trunk_speed_peak_rad_s": trunk_speed, "reaction_delay_s": d_r, "dv_mps": dvv, "dv": [dv[0], dv[1]],
                 "cop_peak_offset_m": float(np.abs(pp - pp[0]).max()), "com_peak_offset_m": float(np.abs(c - c[kp]).max()),
                 "capture_offset_m": dvv / math.sqrt(G / S.zc), "crouch_peak_m": float(dz.max()), "xi_end_dist_m": dist}
    return plan


# ------------------------------------------------------------------------------------------------ Reference from a plan
def build_reference(S: Setup, plan: Plan, name: str | None = None) -> Reference:
    kin, lg = S.kin, S.kin.lg
    T, dt = S.T, S.dt
    c, th, dz = plan.c, plan.th, plan.dz
    yaw = np.zeros(T)
    ank = {s: np.stack([plan.foot[s][:, 0], plan.foot[s][:, 1], lg.ankle_h + plan.foot[s][:, 2]], 1) for s in "lr"}

    def build_q(pelvis):
        Q = rest_upper_body(kin, T)
        build_q.ok = fill_legs(kin, Q, pelvis, yaw, th, ank["l"], ank["r"], np.zeros(T), np.zeros(T))
        return Q

    pelvis0 = np.stack([c[:, 0] - S.off0[0], c[:, 1] - S.off0[1], S.pelvis_z - dz], 1)
    pelvis, Q, err = compensate_com(kin, build_q, pelvis0, yaw, th, c, iters=4)
    m = plan.meta
    notes = [f"push {plan.impulse_Ns:.2f} N.s = dv {m['dv_mps']:.3f} m/s ({S.scenario}), strategy {plan.option.label}; reaction delay {m['reaction_delay_s'] * 1000:.0f} ms; "
             f"initial capture-point offset {m['capture_offset_m'] * 1000:.0f} mm", f"COM tracking error {err * 1000:.2f} mm"]
    if m["landings"]:
        notes.append("steps: " + "; ".join(f"{l['foot']} at t={l['t_s']:.2f} s ankle xy {np.round(l['ankle_xy'], 3).tolist()} crouch {l['crouch_m'] * 1000:.0f} mm"
                                           + (" (reach-clipped)" if l["clipped"] else "") for l in m["landings"]))
    t_push = S.k_push * dt
    meta = dict(m)
    meta.update({"push": {"t": t_push, "dv": [m["dv"][0], m["dv"][1], 0.0]}, "kind": S.scenario, "scenario": S.scenario, "option": plan.option.label,
                 "impulse_Ns": plan.impulse_Ns, "mass_kg": S.M, "zc_m": S.zc, "omega0": math.sqrt(G / S.zc),
                 "walk_window": [t_push, (T - 1) * dt], "recovered_plan": plan.ok})
    ref = finish(kin, name or f"push_{S.scenario}", dt, Q, pelvis, yaw, th, ok=build_q.ok, notes=notes, meta=meta)
    if not plan.ok:
        ref.feasible = False
        ref.notes.append("PLAN NOT RECOVERED: " + plan.reason)
    ref.stance = np.stack([plan.foot["l"][:, 2] < 1e-4, plan.foot["r"][:, 2] < 1e-4], 1)
    return ref


# ------------------------------------------------------------------------------------------------ search over strategies
def vnom(kin: RobotKin) -> float:
    from .. import tradestudy as TS
    return TS.v_nominal(TS.pack_of(kin.robot))


def hip_speed_cap(kin: RobotKin, vin: float | None = None) -> float:
    """The hip strategy is UNAVAILABLE beyond what the hip pitch servos can swing: 90% of the lowest hip-pitch no-load speed."""
    vin = vin if vin is not None else vnom(kin)
    sp = [float(kin.robot.servo[n].noload(vin)) for n in kin.robot.names if n.startswith("hip_pitch")]
    return 0.9 * (min(sp) if sp else 5.0)


def plan_feasible(S: Setup, J: float, opt: Option, cap: float | None, full: bool = True):
    """(ok, plan, ref|None): the LIPM plan recovers and (full) the Reference is kinematically feasible (leg reach, joint ranges)."""
    plan = simulate(S, J, opt, cap)
    if not plan.ok:
        return False, plan, None
    if not full:
        return True, plan, None
    ref = build_reference(S, plan)
    return bool(ref.feasible), plan, ref


def j_search(pred, j_hi: float, step: float = 0.1, iters: int = 6) -> float:
    """Largest J in (0, j_hi] with pred(J) true, scanning down from j_hi (a step option can fail for a tiny push that does not need
    it, so a bisection from below would be wrong) and refining between the first success and the grid point above it."""
    j = j_hi
    while j >= step * 0.99:
        if pred(j):
            if j >= j_hi - 1e-9:
                return j_hi
            lo, hi = j, min(j + step, j_hi)
            for _ in range(iters):
                mid = 0.5 * (lo + hi)
                if pred(mid):
                    lo = mid
                else:
                    hi = mid
            return lo
        j -= step
    return 0.0


def plan_bisect(S: Setup, opt: Option, cap: float | None, j_hi: float, iters: int = 6, full: bool = False) -> float:
    """Largest J (N.s) at which `opt` recovers (plan level; full=True also requires a kinematically feasible Reference)."""
    return j_search(lambda J: plan_feasible(S, J, opt, cap, full)[0], j_hi, iters=iters)


def required_impulse() -> float:
    return float(config.motions()["push"]["required_impulse_Ns"])


def push_case(kin: RobotKin, scenario: str, impulse_Ns: float | None = None, option: Option | None = None, setup: Setup | None = None) -> Reference:
    """The Reference for one scenario at one impulse (default: the requirement). With `option` that strategy; otherwise the simplest
    strategy whose plan recovers, or - when none does - the ankle-strategy plan marked as not recovered."""
    S = setup or make_setup(kin, scenario)
    J = impulse_Ns if impulse_Ns is not None else required_impulse()
    cap = hip_speed_cap(kin)
    if option is not None:
        _, plan, ref = plan_feasible(S, J, option, cap, full=True)
        return ref if ref is not None else build_reference(S, plan)
    for opt in options_for(scenario):
        ok, plan, ref = plan_feasible(S, J, opt, cap, full=True)
        if ok:
            return ref
    return build_reference(S, simulate(S, J, Option(0), cap))
