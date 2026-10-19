"""Sizing: joint torque/speed requirements -> actuator selection -> cost -> (optionally) max height for budget.

Model (first-order, documented in docs/tools.md; constants live in spec `analysis:`):
  * Static loads: single-support stance in the gait's crouch posture.
  * Peak loads: static x gait dynamic factor (ground-reaction peaks) x safety factor.
  * Continuous check: static x safety factor <= continuous torque (or stall x continuous_fraction).
  * Speed check: swing-phase peak joint speed (pi*f*A) <= no-load speed on a linear torque-speed
    curve at the swing load, with a speed margin.
Validate these numbers against sim joint torques (`oh sim test`) and hardware before trusting them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import catalog
from .body import Body, build_body
from .spec import expand_joints, resolve_height

G = 9.81


# ---------------------------------------------------------------- requirements
def joint_loads(spec: dict, body: Body, gait: dict) -> dict[str, dict]:
    """Return per *base* joint: static torque (N·m), peak speed required (rad/s), swing load (N·m)."""
    g, m = body.geom, body.seg_mass
    M = body.total
    flex = math.radians(gait.get("stance_knee_flex_deg", 30))
    f, A = gait.get("step_freq_hz", 1.5), gait.get("knee_amplitude_rad", 0.6)
    w_swing = math.pi * f * A                     # peak of a sinusoid with peak-to-peak A at freq f
    m_shank_foot = m["shank"] + m["foot"]
    knee_offset = g["thigh"] * math.sin(flex / 2)
    swing_load = m_shank_foot * G * g["shank"] / 2

    stance = (M - m_shank_foot) * G * knee_offset
    hip_swing = body.leg * G * (g["thigh"] + g["shank"]) / 2 * math.sin(math.radians(30))
    loads = {
        "knee": (stance, w_swing),
        "hip_pitch": (max(stance, hip_swing), w_swing * 0.8),
        "ankle_pitch": ((M - m["foot"]) * G * g["foot_length"] * 0.4, w_swing * 0.6),
        "hip_roll": ((M - body.leg) * G * g["hip_width"] / 2, w_swing * 0.3),
        "ankle_roll": ((M - m["foot"]) * G * g["foot_width"] / 2, w_swing * 0.3),
    }
    loads["hip_yaw"] = (0.25 * loads["hip_roll"][0], w_swing * 0.2)
    arm_len = g["upper_arm"] + g["forearm"]
    loads["shoulder_pitch"] = (body.arm * G * arm_len / 2, 4.0)
    loads["shoulder_roll"] = (body.arm * G * arm_len / 2, 3.0)
    loads["elbow"] = (m["forearm"] * G * g["forearm"] / 2, 4.0)
    loads["neck_yaw"] = (m["head"] * (g["head"] / 2) ** 2 * 50 + 0.01, 4.0)
    loads["neck_pitch"] = (m["head"] * G * g["head"] * 0.2, 3.0)
    return {k: {"static_nm": v[0], "speed_rad_s": v[1], "swing_load_nm": swing_load} for k, v in loads.items()}


def _limb_fallback(j: dict, loads: dict) -> dict:
    return loads.get(j["base"]) or loads[{"leg": "knee", "arm": "shoulder_pitch", "head": "neck_yaw"}.get(j["limb"], "shoulder_pitch")]


def requirements(spec: dict, body: Body, joints: list[dict], gait_name: str) -> dict[str, dict]:
    a = spec["analysis"]
    gait = spec["locomotion"][gait_name]
    loads = joint_loads(spec, body, gait)
    sf = a["safety_factor"]
    out = {}
    for j in joints:
        L = _limb_fallback(j, loads)
        dyn = a["dynamic_factor"].get(gait_name, 1.5) if j["limb"] == "leg" else a.get("arm_dynamic_factor", 1.5)
        out[j["name"]] = {
            "base": j["base"], "limb": j["limb"],
            "continuous_nm": L["static_nm"] * sf,
            "peak_nm": L["static_nm"] * dyn * sf,
            "speed_rad_s": L["speed_rad_s"] * a.get("speed_margin", 1.1),
            "swing_load_nm": L["swing_load_nm"] if j["limb"] == "leg" else L["static_nm"],
        }
    return out


# ---------------------------------------------------------------- actuator checks
def capability(act: dict, spec: dict) -> dict:
    a, s = act["actuator"], spec["analysis"]
    stall = a["stall_torque_nm"]
    return {
        "continuous_nm": a.get("continuous_torque_nm", stall * s["continuous_fraction_default"]),
        "peak_nm": stall * s["peak_fraction"],
        "stall_nm": stall,
        "no_load_speed_rad_s": a["no_load_speed_rad_s"],
    }


def check(act: dict, req: dict, spec: dict) -> dict:
    c = capability(act, spec)
    w_avail = c["no_load_speed_rad_s"] * max(0.0, 1 - req["swing_load_nm"] / c["stall_nm"])
    margins = {
        "continuous": c["continuous_nm"] / max(req["continuous_nm"], 1e-9),
        "peak": c["peak_nm"] / max(req["peak_nm"], 1e-9),
        "speed": w_avail / max(req["speed_rad_s"], 1e-9),
    }
    worst = min(margins, key=margins.get)
    return {"ok": all(v >= 1.0 for v in margins.values()), "margins": margins, "limit": worst}


def candidates(spec: dict) -> tuple[list[dict], dict[str, str]]:
    act_spec = spec["actuation"]
    need = catalog.FEEDBACK_LEVEL[act_spec.get("require_feedback", "position")]
    vlo, vhi = act_spec.get("supply_voltage_v", [0, 1e9])
    fams = act_spec.get("allowed_families")
    keep, rejected = [], {}
    for p in sorted(catalog.actuators(), key=catalog.price):
        a = p["actuator"]
        if catalog.FEEDBACK_LEVEL[a["feedback"]] < need:
            rejected[p["id"]] = f"feedback '{a['feedback']}' < required '{act_spec.get('require_feedback')}'"
        elif not (a["voltage_v"][0] <= vlo and vhi <= a["voltage_v"][1]):
            rejected[p["id"]] = f"voltage {a['voltage_v']} does not cover supply {[vlo, vhi]}"
        elif fams and a.get("family") not in fams:
            rejected[p["id"]] = "family not allowed"
        else:
            keep.append(p)
    return keep, rejected


# ---------------------------------------------------------------- evaluation
@dataclass
class Evaluation:
    height: float
    base_joints: list[str]
    feasible: bool
    reason: str
    body: Body | None = None
    selection: dict | None = None           # joint -> actuator id
    checks: dict | None = None               # joint -> check (required gaits)
    gait_checks: dict | None = None          # gait -> {ok, worst joint, ...}
    reqs: dict | None = None
    cost: dict | None = None


def fixed_parts(spec: dict) -> tuple[float, float, list]:
    cost, mass, lines = 0.0, 0.0, []
    for item in spec["bom"].get("fixed", []):
        p = catalog.get(item["part"])
        cost += catalog.price(p) * item["qty"]
        mass += p.get("mass_kg", 0.0) * item["qty"]
        lines.append((p, item["qty"]))
    return cost, mass, lines


def material_cost(spec: dict, body: Body) -> tuple[float, float]:
    p = catalog.get(spec["bom"].get("material", "pla-plus-1kg"))
    kg = body.breakdown["structure_kg"] * spec["mass_model"]["waste_factor"]
    return kg, kg * catalog.price(p)


def evaluate(spec: dict, height: float, base_joints: list[str]) -> Evaluation:
    joints = expand_joints(spec, base_joints)
    cands, _ = candidates(spec)
    overrides = dict(spec["actuation"].get("overrides") or {})
    overrides.update({j["name"]: j["actuator"] for j in spec["kinematics"]["joints"] if j.get("actuator")})
    if not cands and not overrides:
        return Evaluation(height, base_joints, False, "no catalog actuator passes the constraints (feedback/voltage/family)")
    fixed_cost, fixed_mass, _ = fixed_parts(spec)
    required_gaits = [g for g, v in spec["locomotion"].items() if v.get("required")]
    if not required_gaits:
        required_gaits = list(spec["locomotion"])[:1]

    def pinned(j):
        return overrides.get(j["name"]) or overrides.get(j["base"])

    # Fixed-point iteration: mass depends on chosen actuators, requirements depend on mass.
    sel = {j["name"]: (pinned(j) or (cands[0]["id"] if cands else None)) for j in joints}
    for _ in range(8):
        body = build_body(spec, height, joints, {n: catalog.get(a).get("mass_kg", 0) for n, a in sel.items()}, fixed_mass)
        reqs = {g: requirements(spec, body, joints, g) for g in required_gaits}

        def passes(act, jn):
            return all(check(act, reqs[g][jn], spec)["ok"] for g in required_gaits)

        new = {}
        if spec["actuation"].get("uniform") and not any(pinned(j) for j in joints):
            ok = [c for c in cands if all(passes(c, j["name"]) for j in joints)]
            if not ok:
                new = None
            else:
                new = {j["name"]: ok[0]["id"] for j in joints}
        else:
            for j in joints:
                if pinned(j):
                    new[j["name"]] = pinned(j)
                    continue
                ok = [c for c in cands if passes(c, j["name"])]
                if not ok:
                    new = None
                    break
                new[j["name"]] = ok[0]["id"]
        if new is None:
            worst = _worst_joint(spec, joints, reqs, required_gaits, cands)
            return Evaluation(height, base_joints, False, f"torque/speed: no actuator meets '{worst}'", body=body, reqs=reqs)
        if new == sel:
            break
        sel = new

    checks = {j["name"]: {g: check(catalog.get(sel[j["name"]]), reqs[g][j["name"]], spec) for g in required_gaits} for j in joints}
    # Non-required gaits: feasibility report only.
    gait_checks = {}
    for g, gv in spec["locomotion"].items():
        r = requirements(spec, body, joints, g)
        cs = {j["name"]: check(catalog.get(sel[j["name"]]), r[j["name"]], spec) for j in joints}
        bad = {n: c for n, c in cs.items() if not c["ok"]}
        worst = min(cs, key=lambda n: min(cs[n]["margins"].values()))
        gait_checks[g] = {"required": bool(gv.get("required")), "ok": not bad, "worst_joint": worst,
                          "worst_margin": round(min(cs[worst]["margins"].values()), 2), "limit": cs[worst]["limit"],
                          "failing": sorted(bad)}

    act_cost = sum(catalog.price(catalog.get(a)) for a in sel.values())
    mat_kg, mat_cost = material_cost(spec, body)
    total = act_cost + fixed_cost + mat_cost
    cost = {"actuators": round(act_cost, 2), "fixed_parts": round(fixed_cost, 2), "material": round(mat_cost, 2),
            "material_kg": round(mat_kg, 3), "total": round(total, 2)}
    cap = spec["goals"]["budget_usd"].get("hard_cap", spec["goals"]["budget_usd"]["target"])
    feasible = total <= cap + 1e-6
    reason = "ok" if feasible else f"over budget: ${total:.0f} > ${cap:.0f}"
    return Evaluation(height, base_joints, feasible, reason, body, sel, checks, gait_checks, reqs, cost)


def _worst_joint(spec, joints, reqs, gaits, cands) -> str:
    best = cands[-1] if cands else None
    if not best:
        return joints[0]["name"]
    worst, wm = joints[0]["name"], 1e9
    for j in joints:
        m = min(min(check(best, reqs[g][j["name"]], spec)["margins"].values()) for g in gaits)
        if m < wm:
            worst, wm = j["name"], m
    return worst


# ---------------------------------------------------------------- driver
def size(spec: dict) -> dict:
    h = resolve_height(spec)
    required = [j["name"] for j in spec["kinematics"]["joints"] if j.get("priority", "required") == "required"]
    optional = [j["name"] for j in spec["kinematics"]["joints"] if j.get("priority") == "optional"]
    sweep = []
    if h["mode"] == "fixed":
        best = evaluate(spec, h["target"], required)
        sweep.append(best)
    else:
        n = int(round((h["max"] - h["min"]) / h["step"]))
        heights = [round(h["min"] + i * h["step"], 4) for i in range(n + 1)]
        if h["mode"] == "minimize":
            heights.reverse()
        best = None
        for H in heights:
            ev = evaluate(spec, H, required)
            sweep.append(ev)
            if ev.feasible:
                best = ev
        if best is None:
            best = sweep[0]
    limiting = None
    if h["mode"] == "maximize" and best.feasible:
        nxt = [e for e in sweep if e.height > best.height]
        limiting = nxt[0].reason if nxt else "reached max search height"
    added = []
    if best.feasible:
        for name in optional:
            trial = evaluate(spec, best.height, best.base_joints + [name])
            if trial.feasible:
                best, added = trial, added + [name]
    return {"best": best, "sweep": sweep, "mode": h["mode"], "limiting": limiting,
            "optional_added": added, "optional_dropped": [o for o in optional if o not in added]}
