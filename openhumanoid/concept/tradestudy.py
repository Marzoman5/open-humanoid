"""Power and voltage trade study (ADR 0012 decision 2): bus voltage vs pack vs actuator mix.

One bus voltage serves every servo, so a mix (STS3250 knees on a 3S pack, say) is judged on that single voltage:
each servo's stall and speed scale with the bus (datasheet figures scaled linearly), the model quality of the extrapolated
cases is reported, and the voltage rating of every part is checked against the pack's full-charge voltage.

Reported per candidate: torque/speed margins (from the gate table), peak current, runtime, pack mass, regulator needs,
cost with low/high price bands, time over voltage rating plus its mitigation, peak current per bus branch, minimum voltage
at the farthest servo, fuse sizing and actuator-model quality.
"""
from __future__ import annotations

import math

import numpy as np

from .. import catalog
from . import config
from .power import CUTOFF_V_CELL, Pack, _SOC, _VOC, compute_power_w, pack_from_catalog, regulator_efficiency
from .robot import Robot

FUSE_STEPS_A = [3, 5, 7.5, 10, 15, 20, 25, 30, 40, 50]
BRANCHES = {"leg_l": lambda n: n.endswith("_l") and n.split("_")[0] in ("hip", "knee", "ankle"),
            "leg_r": lambda n: n.endswith("_r") and n.split("_")[0] in ("hip", "knee", "ankle"),
            "arm_l": lambda n: n.endswith("_l") and n.split("_")[0] in ("shoulder", "elbow", "wrist", "gripper"),
            "arm_r": lambda n: n.endswith("_r") and n.split("_")[0] in ("shoulder", "elbow", "wrist", "gripper")}


def branch_of(name: str) -> str:
    for b, f in BRANCHES.items():
        if f(name):
            return b
    return "torso_head"


def onboard_load_w(robot: Robot) -> dict:
    """Electrical load of on-board non-servo parts (W at the regulated rail): catalog specs.power_w_typical (or power_w), or the
    concept's per-part power_w override. Parts without data count as 0 and are listed."""
    items, missing = [], []
    for it in robot.concept.get("parts", {}).get("onboard", []):
        p = catalog.get(it["part"])
        s = p.get("specs", {})
        w = it.get("power_w", s.get("power_w_typical", s.get("power_w")))
        if w is None:
            if p["category"] in ("compute", "sensor"):
                missing.append(it["part"])
            continue
        items.append({"part": it["part"], "qty": it.get("qty", 1), "watts": float(w) * it.get("qty", 1)})
    return {"items": items, "total_w": sum(i["watts"] for i in items), "no_power_data": missing}


def pack_of(robot: Robot, soc: float = 1.0, r_scale: float = 1.0) -> Pack:
    pk = pack_from_catalog(robot.concept["power"]["pack"], soc)
    pk.r_cell *= r_scale
    return pk


def v_nominal(pack: Pack) -> float:
    return pack.cells * config.value("power.cell_nominal_v")


def regulator_for(robot: Robot) -> dict:
    reg = robot.concept.get("power", {}).get("regulator")
    if not reg:
        return {"part": None, "efficiency": config.value("power.regulator_efficiency")}
    p = catalog.get(reg)
    s = p.get("specs", {})
    return {"part": reg, "efficiency": float(s.get("efficiency", config.value("power.regulator_efficiency"))),
            "max_current_a": s.get("max_current_a", 5.0), "input_v": s.get("input_v")}


def compute_check(robot: Robot, load: dict) -> dict:
    """Does the regulator carry the on-board 5 V load (compute + camera + logic) at its rated current?"""
    reg = regulator_for(robot)
    amps = load["total_w"] / 5.0
    ok = amps <= reg.get("max_current_a", 5.0) * 0.8
    pk = catalog.get(robot.concept["power"].get("compute", "rpi-zero-2w"))
    peak_w = pk.get("specs", {}).get("power_w_peak", load["total_w"])
    return {"regulator": reg["part"], "rail_current_typical_a": round(amps, 2), "rail_current_peak_a": round(peak_w / 5.0, 2),
            "regulator_rating_a": reg.get("max_current_a"), "ok_at_typical": ok,
            "ok_at_peak": peak_w / 5.0 <= reg.get("max_current_a", 5.0) * 0.95}


def voltage_rating_report(robot: Robot, pack: Pack) -> dict:
    """Share of the discharge (and minutes) the open-circuit pack voltage sits above each actuator's maximum rating."""
    out = {}
    cells = pack.cells
    for aid in sorted(set(robot.acts.values())):
        spec = next(s for n, s in robot.servo.items() if robot.acts[n] == aid)
        vmax = spec.voltage_rating_v[1]
        v_full = cells * float(_VOC[-1])
        soc_over = 0.0
        if v_full > vmax:
            v_cell = vmax / cells
            soc_cross = float(np.interp(v_cell, _VOC, _SOC)) if v_cell > _VOC[0] else 0.0
            soc_over = 1.0 - soc_cross
        # energy share above the crossing (approximation: energy proportional to SoC span)
        out[aid] = {"rating_v": list(spec.voltage_rating_v), "pack_full_v": round(v_full, 2), "over_rating_at_full_v": round(max(v_full - vmax, 0), 2),
                    "soc_share_over": round(soc_over, 3), "mitigation": None}
        if soc_over > 0:
            cap_v_cell = vmax / cells
            lost = float(np.interp(cap_v_cell, _VOC, _SOC))
            out[aid]["mitigation"] = {
                "action": f"charge only to {cap_v_cell:.2f} V/cell ({cells * cap_v_cell:.1f} V) -- most chargers allow it; costs about {100 * soc_over:.0f}% of the capacity",
                "cost_usd": 0.0, "capacity_lost_fraction": round(soc_over, 3),
                "alternative": "a regulator rated for the full pack current (tens of amps) is not a hobby part; not costed"}
    return out


def bus_analysis(robot: Robot, ms: dict, dem_batt_branch: dict, pack: Pack, load_w: float, transient: dict | None = None) -> dict:
    """Branch currents, sag and fuse sizing. The peak legitimate draw is the larger of the worst frozen motion and the R10 push transient
    (challenge-2 row 15: a fuse sized from the walk alone would blow on the push it exists to survive); the all-leg stall current is reported
    as the fault case (what a fuse would have to carry to ride through a stalled leg, not a design draw)."""
    v = v_nominal(pack)
    r_branch = config.value("power.wire_resistance_ohm_per_branch")
    motion_w = ms["batt_total_peak_w"] + load_w
    r10_w = (transient["total_w"] + load_w) if transient and transient.get("total_w") else 0.0
    total_peak_w = max(motion_w, r10_w)
    i_total = total_peak_w / v
    v_sag = pack.voltage(i_total, soc=0.2)
    i_total = total_peak_w / max(v_sag, 1.0)
    i_motion = motion_w / max(pack.voltage(motion_w / v, soc=0.2), 1.0)
    i_r10 = r10_w / max(pack.voltage(r10_w / v, soc=0.2), 1.0) if r10_w else 0.0
    branches = {}
    min_v = 1e9
    br_w = dict(dem_batt_branch)
    if transient:
        for k, w in transient["branch_w"].items():
            br_w[k] = max(br_w.get(k, 0.0), w)
    for b_, w in br_w.items():
        i_b = w / v_sag
        v_far = v_sag - i_b * r_branch
        min_v = min(min_v, v_far)
        branches[b_] = {"peak_w": round(w, 1), "peak_a": round(i_b, 2), "voltage_at_far_servo_v": round(v_far, 2)}
    low_rating = min(s.voltage_rating_v[0] for s in robot.servo.values())
    margin = config.value("power.fuse_margin")
    nxt = lambda a: next((f for f in FUSE_STEPS_A if f >= margin * a), None)   # noqa: E731
    leg_stall = sum(s.stall_current_a * (v / s.vin_ref) for n, s in robot.servo.items() if n.split("_")[0] in ("hip", "knee", "ankle"))
    stall_total = sum(s.stall_current_a for s in robot.servo.values())
    return {"pack_nominal_v": round(v, 2), "peak_total_a": round(i_total, 2), "peak_total_w": round(total_peak_w, 1),
            "peak_from_frozen_motions_a": round(i_motion, 2), "peak_from_r10_transient_a": round(i_r10, 2),
            "r10_transient_scenario": (transient or {}).get("scenario"),
            "sag_at_peak_v": round(v - v_sag, 2), "v_at_peak_v": round(v_sag, 2), "branches": branches,
            "min_voltage_at_far_servo_v": round(min_v, 2), "servo_min_operating_v": low_rating,
            "min_voltage_ok": bool(min_v >= low_rating),
            "fuse_a": nxt(i_total), "fuse_a_if_sized_from_motions_only": nxt(i_motion),
            "fuse_blows_on_r10_if_sized_from_motions_only": bool(i_r10 > (nxt(i_motion) or 0)),
            "fuse_rule": f"{margin} x peak legitimate draw (larger of the frozen motions and the R10 push transient), next standard value",
            "all_leg_servos_stalled_a": round(leg_stall, 1), "fuse_a_to_ride_through_all_leg_stall": nxt(leg_stall),
            "all_servos_stalled_a": round(stall_total, 1),
            "pack_limit_a": round(pack.max_discharge_a, 1),
            "pack_c_ok": bool(i_total <= config.gate("pack_peak_current_fraction_of_c") * pack.max_discharge_a),
            "connector_rating_note": "STS3215 connector current rating is unknown (research/methods/e); the fuse must also stay below the wiring/connector limit"}


def cost_report(robot: Robot) -> dict:
    """BOM cost with low/typical/high price bands from the catalog (all prices unverified unless the catalog says so)."""
    from ..sizing import material_cost
    rows = []
    totals = {"low": 0.0, "typical": 0.0, "high": 0.0}
    unverified = 0

    def add(part_id, qty, label):
        nonlocal unverified
        p = catalog.get(part_id)
        pr = p["price_usd"]
        row = {"part": part_id, "qty": qty, "label": label, "typical": pr["typical"] * qty, "low": pr.get("low", pr["typical"]) * qty,
               "high": pr.get("high", pr["typical"]) * qty, "verified": bool(p["verified"])}
        unverified += not p["verified"]
        for k in totals:
            totals[k] += row[k]
        rows.append(row)

    for aid in sorted(set(robot.acts.values())):
        add(aid, sum(1 for a in robot.acts.values() if a == aid), "actuators")
    for it in robot.concept.get("parts", {}).get("onboard", []):
        add(it["part"], it.get("qty", 1), "on-board")
    for it in robot.concept.get("parts", {}).get("offboard", []):
        add(it["part"], it.get("qty", 1), "off-board (charger etc., counts toward the budget)")
    kg = robot.body.breakdown["structure_kg"] * robot.spec["mass_model"]["waste_factor"]
    mat = catalog.get(robot.spec["bom"].get("material", "pla-plus-1kg"))
    pr = mat["price_usd"]
    mrow = {"part": mat["id"], "qty": round(kg, 3), "label": "printed structure (kg incl. waste)", "typical": pr["typical"] * kg,
            "low": pr.get("low", pr["typical"]) * kg, "high": pr.get("high", pr["typical"]) * kg, "verified": bool(mat["verified"])}
    for k in totals:
        totals[k] += mrow[k]
    rows.append(mrow)
    cap = robot.spec["goals"]["budget_usd"].get("hard_cap", robot.spec["goals"]["budget_usd"]["target"])
    return {"rows": rows, "total_usd": {k: round(v, 2) for k, v in totals.items()}, "budget_cap_usd": cap,
            "within_cap_typical": totals["typical"] <= cap, "within_cap_at_high": totals["high"] <= cap,
            "unverified_lines": unverified, "note": "every price in the catalog is an estimate unless verified: true; the decision needs a pass at the high price"}


def model_quality(robot: Robot, v_op: float) -> dict:
    out = {}
    for n, s in robot.servo.items():
        aid = robot.acts[n]
        if aid in out:
            continue
        ratio = v_op / s.vin_ref
        flag = "voltage-extrapolated" if abs(ratio - 1.0) > 0.10 else "at the model voltage"
        out[aid] = {"quality": s.quality, "score": s.quality_score, "vin_ref": s.vin_ref, "bus_v": round(v_op, 2),
                    "voltage_ratio": round(ratio, 2), "voltage_note": flag, "uncertainty": s.uncertainty, "notes": list(s.notes)}
    return out
