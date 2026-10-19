"""Load cases for the strength check, derived from data with provenance.

Every case is a `chain.Scenario` (pose, external contact forces, inertial field) plus a provenance record: which numbers are SOURCED
(concept-engine report, catalog), DERIVED (energy method, torque / lever) or ASSUMED (policy `strength.yaml`, flagged with the physical
test that would replace it). Cases:

  (a) walking and dance peaks:   `walk_*`   ground reaction at a centre of pressure limited by the ACTUAL peak ankle torque of the concept
                                 report; `stall_*`  each joint pushing its STALL torque against a blocked foot (a servo can always push stall).
  (b) R10 push recovery:         `push_*`   absolute impulse over a short time, centre of pressure at the stall-limited foot edge.
  (c) falls:                     `fall_pivot_*`, `landing_*`, `fall_contact_*` (energy / stopping-distance, protected and rigid bounds),
                                 `fall_inertial_*` (equivalent g-load on the whole leg).
  (d) handling:                  `handling_*` and the fastener-level assembly checks in checks.py.

The robot mass, height and the concept report path come from the variant file `variants/<id>/cad/strength.yaml`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import yaml

from ...paths import repo_root
from .chain import G, Contact, Scenario, apply_scale, scale_to_cap
from .model import Model
from .policy import policy, pv

SIDE_SIGN = {"l": 1.0, "r": -1.0}


# ------------------------------------------------------------------------------------------------------------------ config
def load_config(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def base_name(j: str) -> str:
    return j[:-2] if j.endswith(("_l", "_r")) else j


def concept_peaks(cfg: dict) -> dict[str, dict]:
    """joint -> {peak_nm, stall_nm, peak_frac, motion} from the concept report (SOURCED)."""
    rp = cfg.get("concept", {}).get("report")
    if not rp:
        return {}
    path = Path(rp)
    if not path.is_absolute():
        path = repo_root() / rp
    rep = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for r in rep["joints_ranked_by_margin"]:
        out[r["joint"]] = {"peak_nm": float(r["peak_frac_of_stall"]) * float(r["stall_nm"]), "stall_nm": float(r["stall_nm"]),
                           "peak_frac": float(r["peak_frac_of_stall"]), "motion": r["peak_motion"], "actuator": r["actuator"]}
    out["_meta"] = {"candidate": rep.get("candidate"), "mass_kg": rep["mass"]["total_kg"], "height_m": rep["design"]["height_m"],
                    "report": str(rp), "gait": rep.get("gait", {}).get("chosen"), "push": rep.get("push_recovery", {}).get("required_impulse_Ns")}
    return out


def joint_stall(model: Model, cfg: dict) -> dict[str, float]:
    """Stall torque (N.m) per model joint: the DESIGN actuator (cfg `actuators`, base-joint -> catalog id) else the CAD actuator."""
    from ... import catalog

    over = cfg.get("actuators", {}) or {}
    out = {}
    for jn, j in model.joints.items():
        aid = over.get(base_name(jn), j.actuator)
        out[jn] = float(catalog.get(aid)["actuator"]["stall_torque_nm"])
    return out


def actuator_masses(model: Model, cfg: dict) -> dict[str, float]:
    """part-id -> mass override (kg) for servos whose design actuator differs from the CAD placeholder."""
    from ... import catalog

    over = cfg.get("actuators", {}) or {}
    out = {}
    for jn, j in model.joints.items():
        aid = over.get(base_name(jn), j.actuator)
        if aid != j.actuator:
            out[f"servo_{jn}"] = float(catalog.get(aid).get("mass_kg", 0.0))
    return out


# ---------------------------------------------------------------------------------------------------------------- geometry
def _leg_joint(model: Model, base: str, side: str) -> str:
    n = f"{base}_{side}"
    if n in model.joints:
        return n
    raise KeyError(f"leg joint '{n}' not in the model: {sorted(model.joints)}")


def stance_pose(model: Model, side: str, flex_deg: float) -> dict[str, float]:
    k = math.radians(flex_deg)
    return {_leg_joint(model, "hip_pitch", side): -k / 2, _leg_joint(model, "knee", side): k, _leg_joint(model, "ankle_pitch", side): -k / 2}


def foot_geometry(model: Model, cfg: dict, q: dict[str, float]) -> dict:
    """Sole rectangle in the foot link frame and the world transform of the foot at pose q."""
    fcfg = cfg["leg"]["foot"]
    part = model.parts[fcfg["part"]]
    V = np.asarray(part.mesh.vertices)
    z0 = float(V[:, 2].min())
    sole = V[V[:, 2] < z0 + 0.6]
    fk = model.fk(q)
    R, t = fk[fcfg["link"]]
    return {"link": fcfg["link"], "part": fcfg["part"], "z0": z0, "x0": float(sole[:, 0].min()), "x1": float(sole[:, 0].max()),
            "y0": float(sole[:, 1].min()), "y1": float(sole[:, 1].max()), "R": R, "t": t,
            "ankle_x": 0.0, "ankle_pitch_axis_z": float(-model.links[fcfg["link"]].pos[2])}


def _sole_force(foot: dict, x: float, y: float, F_local: np.ndarray, label: str) -> Contact:
    """Ground reaction at the foot-frame sole point (x, y); F_local is given in the WORLD axes (flat foot: world-aligned)."""
    p = foot["R"] @ np.array([x, y, foot["z0"]]) + foot["t"]
    return Contact(foot["link"], p, F_local, label)



def _fit_tangential(model, q, foot, x, y, Fn, tdir, joint, target_nmm, mu) -> float:
    """Tangential-to-normal ratio t in [0, mu] along `tdir` such that |torque of `joint`| equals target (linear in t); 0 when the vertical force alone is above."""
    from .chain import joint_wrenches

    def tau(t):
        sc = Scenario("fit", "walk", "", q, contacts=[_sole_force(foot, x, y, np.array([0, 0, Fn]) + tdir * t * Fn, "fit")])
        return joint_wrenches(model, sc, only_joints=[joint])[joint]["tau"]

    t0, t1 = tau(0.0), tau(0.1)
    slope = (t1 - t0) / 0.1
    if abs(slope) < 1e-9 or target_nmm <= 0:
        return 0.0
    cands = [((sgn * target_nmm) - t0) / slope for sgn in (1.0, -1.0)]
    cands = [c for c in cands if 0.0 <= c <= mu]
    return float(min(cands)) if cands else (0.0 if abs(t0) >= target_nmm else mu)


# ------------------------------------------------------------------------------------------------------------------- builder
def build(model: Model, cfg: dict, only: list[str] | None = None) -> tuple[list[Scenario], dict]:
    """Returns (scenarios, context) where context documents every number used (for the report)."""
    pol = policy()
    side = cfg["leg"].get("side", "l")
    sgn = SIDE_SIGN[side]
    rob = cfg["robot"]
    M = float(rob["mass_kg"])
    H = float(rob["height_m"])
    peaks = concept_peaks(cfg)
    stall = joint_stall(model, cfg)
    W = M * G
    flex = float(cfg.get("walking", {}).get("stance_knee_flexion_deg", pv(pol, "walking", "stance_knee_flexion_deg")))
    k_walk = float(pv(pol, "walking", "grf_peak_over_weight"))
    mu = float(pv(pol, "walking", "friction_tangential_over_normal"))
    ctx: dict = {"robot": rob, "concept": peaks.get("_meta"), "stall_nm": stall, "peaks_nm": {k: v["peak_nm"] for k, v in peaks.items() if k != "_meta"},
                 "weight_n": W, "k_walk": k_walk, "mu": mu, "stance_knee_flexion_deg": flex}
    q0: dict[str, float] = {}
    qs = stance_pose(model, side, flex)
    foot_q = foot_geometry(model, cfg, qs)
    foot_0 = foot_geometry(model, cfg, q0)
    ctx["foot"] = {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in foot_q.items() if k not in ("R", "t")}
    scs: list[Scenario] = []
    ank_p = _leg_joint(model, "ankle_pitch", side)
    ank_r = _leg_joint(model, "ankle_roll", side)
    tau_ap = peaks.get(ank_p, {}).get("peak_nm", 0.0)
    tau_ar = peaks.get(ank_r, {}).get("peak_nm", 0.0)
    stall_ap = stall[ank_p]
    stall_ar = stall[ank_r]
    ax_z = foot_q["ankle_pitch_axis_z"]

    def clip(v, lo, hi):
        return min(max(v, lo), hi)

    # ---------------------------------------------------------------- (a) walking: centre of pressure from the concept ankle peak torque
    Fn = k_walk * W
    prov_w = (f"F_n = {k_walk} x weight ({W:.1f} N) ASSUMPTION; centre of pressure offset = peak ankle torque / F_n, with the peak torque from the "
              f"concept report ({peaks.get('_meta', {}).get('candidate')}): ankle pitch {tau_ap:.2f} N.m, roll {tau_ar:.2f} N.m (SOURCED)")
    xp = clip(tau_ap * 1000.0 / Fn, 0, foot_q["x1"])
    yp = clip(tau_ar * 1000.0 / Fn, 0, foot_q["y1"])
    hip_p = _leg_joint(model, "hip_pitch", side)
    hip_r = _leg_joint(model, "hip_roll", side)
    tau_hp = peaks.get(hip_p, {}).get("peak_nm", 0.0)
    tau_hr = peaks.get(hip_r, {}).get("peak_nm", 0.0)
    for tag, x, y, tdir, hj, hpk in (("toe", xp, 0.0, np.array([1.0, 0, 0]), hip_p, tau_hp), ("heel", -xp, 0.0, np.array([-1.0, 0, 0]), hip_p, tau_hp),
                                      ("lat", 0.0, sgn * yp, np.array([0, sgn, 0.0]), hip_r, tau_hr), ("med", 0.0, -sgn * yp, np.array([0, -sgn, 0.0]), hip_r, tau_hr)):
        t_fit = _fit_tangential(model, qs, foot_q, x, y, Fn, tdir, hj, hpk * 1000.0, mu)
        F = np.array([0.0, 0.0, Fn]) + tdir * t_fit * Fn
        scs.append(Scenario(f"walk_{tag}", "walk", f"single-support peak, centre of pressure {tag} ({x:+.1f}, {y:+.1f}) mm of the ankle, tangential {t_fit:.2f} F_n", qs,
                            contacts=[_sole_force(foot_q, x, y, F, f"walk_{tag}")], kind="assumption",
                            prov=prov_w + f"; tangential force fitted so the {base_name(hj)} torque equals its concept peak {hpk:.2f} N.m (SOURCED), limit mu {mu}",
                            info={"cop_mm": [x, y], "F_n": Fn, "tangential_over_normal": t_fit}))
    scs.append(Scenario("stand", "walk", "standing on one foot, centre of pressure at the foot centre", q0,
                        contacts=[_sole_force(foot_0, 0.5 * (foot_0["x0"] + foot_0["x1"]), 0.5 * (foot_0["y0"] + foot_0["y1"]), np.array([0, 0, W]), "stand")],
                        kind="derived", prov=f"weight {W:.1f} N from the R1 shelled mass {M} kg"))

    # ---------------------------------------------------------------- (a2) stall bound: each joint pushing stall against the foot
    for jn, j in model.joints.items():
        if j.child_link not in model.subtree(model.joints[_leg_joint(model, "hip_yaw", side)].child_link):
            continue
        tau = stall[jn] * 1000.0
        fk0 = model.fk(q0)
        O, a = model.world_axis(jn, fk0)
        R_f, t_f = fk0[foot_0["link"]]
        x0, x1, y0, y1, z0 = foot_0["x0"], foot_0["x1"], foot_0["y0"], foot_0["y1"], foot_0["z0"]
        pts = {"toe": (x1, 0.5 * (y0 + y1)), "heel": (x0, 0.5 * (y0 + y1)), "lat": (0.5 * (x0 + x1), y1 if sgn > 0 else y0),
               "med": (0.5 * (x0 + x1), y0 if sgn > 0 else y1)}
        for ptag, (px, py) in pts.items():
            P = R_f @ np.array([px, py, z0]) + t_f
            r = P - O
            rperp = r - a * float(r @ a)
            if np.linalg.norm(rperp) < 5.0:
                continue
            d = np.cross(a, rperp)
            d /= np.linalg.norm(d)
            Fmag = tau / np.linalg.norm(rperp)
            scs.append(Scenario(f"stall_{jn}_{ptag}", "stall", f"{jn} at stall ({stall[jn]:.2f} N.m) against a blocked foot at the {ptag}: {Fmag:.0f} N",
                                q0, contacts=[Contact(foot_0["link"], P, d * Fmag, f"stall_{jn}_{ptag}")], kind="derived",
                                prov=f"stall torque {stall[jn]:.3f} N.m (catalog) / lever {np.linalg.norm(rperp):.1f} mm",
                                info={"joint": jn, "force_n": float(Fmag), "point": ptag}))

    # ---------------------------------------------------------------- (b) R10 push recovery
    I = float(peaks.get("_meta", {}).get("push") or pv(pol, "walking", "push_impulse_ns"))
    dt = float(pv(pol, "walking", "push_duration_s"))
    Fh = I / dt
    Fn = 1.2 * W
    xs = clip(stall_ap * 1000.0 / Fn, 0, foot_q["x1"])
    ys = clip(stall_ar * 1000.0 / Fn, 0, foot_q["y1"])
    for tag, x, y, tx, ty in (("fwd", xs, 0.0, -Fh / Fn, 0.0), ("back", -xs, 0.0, Fh / Fn, 0.0), ("lat", 0.0, sgn * ys, 0.0, -sgn * Fh / Fn)):
        scs.append(Scenario(f"push_{tag}", "push", f"R10 push ({I} N.s over {dt} s = {Fh:.0f} N), ankle at stall: centre of pressure ({x:+.1f}, {y:+.1f}) mm",
                            qs, contacts=[_sole_force(foot_q, x, y, np.array([tx * Fn, ty * Fn, Fn]), f"push_{tag}")], kind="derived",
                            prov=f"impulse {I} N.s (R10, SOURCED provisional); duration {dt} s ASSUMED; F_n = 1.2 x weight ASSUMED",
                            info={"cop_mm": [x, y]}))

    # ---------------------------------------------------------------- (c) falls
    f = pol["fall"]
    com_h = float(rob.get("com_height_m") or pv(f, "com_height_fraction") * H)
    dh = max(0.0, com_h - float(pv(f, "lying_com_height_m")))
    E = M * G * dh
    phi = float(pv(f, "energy_fraction_leg_contact"))
    kpk = float(pv(f, "peak_over_average"))
    d_prot = float(pv(f, "stop_distance_protected_mm")) * 1e-3
    d_rig = float(pv(f, "stop_distance_rigid_mm")) * 1e-3
    ctx["fall"] = {"energy_j": E, "com_height_m": com_h, "drop_m": dh, "phi": phi, "k_peak": kpk,
                   "F_protected_n": phi * E / d_prot * kpk, "F_rigid_n": phi * E / d_rig * kpk, "n_g_protected": dh / d_prot, "n_g_rigid": dh / d_rig}
    pf = float(pv(f, "pivot_load_factor"))
    lf = float(pv(f, "landing_load_factor"))
    prov_f = f"E = m g dh = {M} x 9.81 x {dh:.3f} = {E:.1f} J (dh from the CoM height {com_h:.3f} m, SOURCED fraction); phi, d, k_peak ASSUMED (drop-test)"
    # pivot reactions at the foot edge the robot topples over
    fwd = np.array([1.0, 0, 0])
    for tag, (x, y) in (("fwd", (foot_0["x1"], 0.5 * (foot_0["y0"] + foot_0["y1"]))), ("back", (foot_0["x0"], 0.5 * (foot_0["y0"] + foot_0["y1"]))),
                        ("side", (0.5 * (foot_0["x0"] + foot_0["x1"]), foot_0["y1"] if sgn > 0 else foot_0["y0"]))):
        scs.append(Scenario(f"fall_pivot_{tag}", "fall", f"toppling {tag}: ground reaction {pf} x weight on the foot edge it pivots on",
                            q0, contacts=[_sole_force(foot_0, x, y, np.array([0, 0, pf * W]), f"pivot_{tag}")], kind="assumption",
                            prov=f"pivot_load_factor {pf} ASSUMED (drop test)"))
    for tag, (x, y) in (("heel", (foot_0["x0"], 0.5 * (foot_0["y0"] + foot_0["y1"]))), ("toe", (foot_0["x1"], 0.5 * (foot_0["y0"] + foot_0["y1"]))),
                        ("flat", (0.5 * (foot_0["x0"] + foot_0["x1"]), 0.5 * (foot_0["y0"] + foot_0["y1"])))):
        scs.append(Scenario(f"landing_{tag}", "fall", f"stumble / step-down landing on one foot ({lf} x weight) on the {tag}",
                            q0, contacts=[_sole_force(foot_0, x, y, np.array([0, 0, lf * W]), f"landing_{tag}")], kind="assumption",
                            prov=f"landing_load_factor {lf} ASSUMED (drop test)"))
    # contact impacts on the extreme point of every leg link
    fk0 = model.fk(q0)
    leg_root = model.joints[_leg_joint(model, "hip_yaw", side)].child_link
    leg_links = [l for l in model.subtree(leg_root)]
    dirs = {"fwd": np.array([1.0, 0, 0]), "back": np.array([-1.0, 0, 0]), "side": np.array([0, sgn, 0])}
    for dtag, dvec in dirs.items():
        exposed = cfg.get("fall", {}).get("exposed_links")
        for ln in leg_links:
            if exposed is not None and ln not in exposed:
                continue            # inside the pelvis / torso shell: the floor cannot touch it directly (forces still reach it through the chain)
            pts = []
            for p in model.parts_in(ln, True):
                if p.id in cfg.get("exclude_parts", []):
                    continue
                Rn, tn = fk0[ln]
                pts.append((np.asarray(p.mesh.vertices) @ Rn.T + tn))
            if not pts:
                continue
            V = np.vstack(pts)
            proj = V @ dvec
            sel = V[proj > proj.max() - 1.5]
            P = sel.mean(axis=0)
            for prot, dd, cl in (("protected", d_prot, "fall"), ("rigid", d_rig, "fall_rigid")):
                Fm = phi * E / dd * kpk
                scs.append(Scenario(f"fall_contact_{dtag}_{ln}_{prot}", cl,
                                    f"{dtag} fall, floor contact on {ln} at {P.round(0).tolist()}: {Fm:.0f} N ({prot}, stop {dd * 1e3:.0f} mm)",
                                    q0, contacts=[Contact(ln, P, -dvec * Fm, f"fall_{dtag}_{ln}")], kind="assumption", prov=prov_f,
                                    info={"force_n": Fm, "dir": dtag, "link": ln, "prot": prot}))
    for dtag, dvec in {"x+": np.array([1.0, 0, 0]), "x-": np.array([-1.0, 0, 0]), "y+": np.array([0, 1.0, 0]), "y-": np.array([0, -1.0, 0]),
                       "z-": np.array([0, 0, -1.0]), "z+": np.array([0, 0, 1.0])}.items():
        for prot, dd, cl in (("protected", d_prot, "fall"), ("rigid", d_rig, "fall_rigid")):
            n = dh / dd
            scs.append(Scenario(f"fall_inertial_{dtag}_{prot}", cl, f"leg inertia: {n:.0f} g equivalent along {dtag} ({prot}); supported at the hip",
                                q0, g_eff=dvec * n * G, contacts=[], kind="assumption", prov=prov_f + f"; n = dh/d = {n:.0f} g (research/methods/d section 3)",
                                info={"n_g": n, "dir": dtag}))
    # ---------------------------------------------------------------- (d) handling
    hl = float(pv(pol, "handling", "lift_by_leg_over_weight"))
    scs.append(Scenario("handling_lift_by_foot", "handling", "robot picked up by one foot / ankle: whole weight through that leg, plus 50% jerk",
                        q0, contacts=[_sole_force(foot_0, 0.5 * (foot_0["x0"] + foot_0["x1"]), 0.5 * (foot_0["y0"] + foot_0["y1"]),
                                                  np.array([0, 0, 1.5 * hl * W]), "lift")], kind="assumption", prov="lift_by_leg_over_weight ASSUMED"))
    # ---------------------------------------------------------------- cap the loading to what the servos can transmit
    bd = float(pv(pol, "joint_torque", "back_drive_over_stall"))
    for sc in scs:
        if sc.cls in ("walk", "push", "stall"):
            sc.cap_factor = float(pv(pol, "joint_torque", "stall_bound_factor"))
            if sc.cls == "walk" and peaks:
                # walking: no joint torque above its concept-engine peak (plus headroom for what the open-loop replay does not see), never above stall
                head = float(pv(pol, "walking", "concept_headroom"))
                sc.cap_nm = {j: min(max(head * peaks[j]["peak_nm"], 0.2 * stall[j]), stall[j]) for j in stall if j in peaks}
        elif sc.cls == "fall":
            sc.cap_factor = bd
            sc.cap_mode = "field" if sc.name.startswith("fall_inertial") else "contacts"
        if sc.cap_factor is not None:
            s_ = scale_to_cap(model, sc, stall, actuator_masses(model, cfg))
            sc.info["servo_cap_scale"] = s_
            apply_scale(sc, s_)
            if s_ < 0.999:
                sc.desc += f" [servo-limited x{s_:.2f}: no joint transmits more than {sc.cap_factor:g} x stall]"
    if only:
        scs = [s for s in scs if any(o in s.name for o in only)]
    return scs, ctx
