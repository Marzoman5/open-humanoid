"""Height sweep of one candidate (challenge-2 task step 11): the SAME robot at 0.40-0.65 m with the packaging floors of the T-0004 lessons PLUS
the CAD-foundation facts (ankle height 66 mm, knee range <= 115 deg, hip pitch -110/+40, ankle pitch -60/+25; the height they add is taken pro rata
from the other vertical proportions so the label is the standing height), the frozen gait-sweep choice (stance knee flex x step time) made per
height, the nominal joint gates, and the R10 push gate (largest recoverable impulse per scenario against the requirement).

Per height: feasible = every frozen motion valid, every nominal joint gate met, every R10 scenario recoverable at the required impulse.
Binding constraint = the gate with the largest violation factor (1 / margin for a joint gate, required / recoverable for a push), reported with the joint.
Nominal gates only (no bounds sweep / Monte Carlo): the answer for 'how tall can it be' is a ceiling, the robust answer is lower.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import numpy as np

from . import config, pushcheck as PC
from .evaluate import Mods, apply_gait, gait_sweep, run_bundle
from .robot import load_concept

DEFAULT_HEIGHTS = (0.40, 0.45, 0.50, 0.55, 0.60, 0.65)


def _violations(b, push: dict) -> list[dict]:
    out = []
    for r in b.rows.values():
        for key, nm in (("margin_peak", "peak torque"), ("margin_rms", "RMS vs rated"), ("margin_util", "torque-speed envelope"), ("margin_overload", "overload time")):
            if r[key] < 1.0:
                out.append({"constraint": f"{nm} @ {r['joint']}", "factor": round(1.0 / max(r[key], 1e-9), 2), "kind": "joint gate"})
    for k, why in b.invalid.items():
        out.append({"constraint": f"motion {k} invalid: {why[:90]}", "factor": 99.0, "kind": "invalid motion"})
    req = config.motions()["push"]["required_impulse_Ns"]
    for sc, c in push.items():
        if not c["recoverable_at_required"]:
            jm = c.get("largest_recoverable", {}).get("largest_recoverable_Ns")
            f = (req / jm) if jm else 99.0
            out.append({"constraint": f"R10 {sc} ({c.get('strategy') or 'no strategy'}; largest {jm} N.s vs {req})", "factor": round(min(f, 99.0), 2), "kind": "R10"})
    return sorted(out, key=lambda v: -v["factor"])


def sweep_height(concept: dict, h: float, *, packaging=("t0004", "cad_foundation"), push_max: bool = True, table_height=None) -> dict:
    t0 = time.time()
    c = copy.deepcopy(concept)
    c["height_m"] = float(h)
    c["packaging"] = list(packaging)
    best, rows = gait_sweep(c, table_height)
    c = apply_gait(c, best)
    b = run_bundle(c, Mods(), table_height=table_height, thermal=False, pushes=True)
    cfgp = config.motions()["push"]
    push = {}
    for nm, row in b.push_rows.items():
        sc = nm[len("push_"):]
        d = {"valid": row["valid"], "demand_ok": bool(row.get("ok")), "strategy": row.get("strategy"), "recoverable_at_required": bool(row["valid"] and row.get("ok")),
             "peak_frac_of_stall": row.get("peak_frac_of_stall"), "why": row.get("why", []), "reason": row.get("reason", "")[:120]}
        if push_max:
            d["largest_recoverable"] = PC.largest_recoverable(b.robot, b.kin, b.vin, sc, demand_iters=3)
        push[sc] = d
    w, j = b.worst
    viol = _violations(b, push)
    lr = {sc: d["largest_recoverable"]["largest_recoverable_Ns"] for sc, d in push.items() if "largest_recoverable" in d}
    row = {"height_m": h, "mass_kg": round(b.robot.total_mass, 3), "packaging_notes": b.robot.spec.get("_floor_notes", []),
           "gait": {"stance_knee_flex_deg": best["stance_knee_flex_deg"], "step_time_s": best["step_time_s"], "worst_margin": best["worst_margin"]},
           "joint_gates_pass": b.passes, "worst_margin": round(w, 3), "worst_joint": j, "invalid_motions": dict(b.invalid),
           "rom_clamps": [n for n, r in b.refs.items() if r.meta.get("rom_clamped_from_deg")],
           "push": push, "largest_recoverable_Ns": lr, "required_impulse_Ns": cfgp["required_impulse_Ns"],
           "largest_recoverable_min_Ns": (min(lr.values()) if lr else None), "largest_recoverable_min_dv_mps": (round(min(lr.values()) / b.robot.total_mass, 3) if lr else None),
           "feasible": bool(b.passes and not b.invalid and all(d["recoverable_at_required"] for d in push.values())),
           "feasible_ignoring_the_high_table_pickup": bool(all(not r["fails"] for r in b.rows.values()) and all(k.startswith("pickup_") for k in b.invalid) and all(d["recoverable_at_required"] for d in push.values())),
           "violations": viol[:6], "binding": viol[0]["constraint"] if viol else None,
           "binding_ignoring_the_high_table_pickup": next((v["constraint"] for v in viol if not v["constraint"].startswith("motion pickup_")), None), "seconds": round(time.time() - t0, 1)}
    return row


def run_sweep(concept_path, heights=DEFAULT_HEIGHTS, *, out_root: Path | None = None, packaging=("t0004", "cad_foundation"), push_max: bool = True, verbose: bool = True) -> dict:
    concept = load_concept(concept_path)
    rows = []
    for h in heights:
        r = sweep_height(concept, h, packaging=packaging, push_max=push_max)
        rows.append(r)
        if verbose:
            lr = r["largest_recoverable_Ns"]
            print(f"{h:.2f} m  {r['mass_kg']:.2f} kg  gait {r['gait']['stance_knee_flex_deg']:.0f} deg/{r['gait']['step_time_s']} s  joints {'PASS' if r['joint_gates_pass'] else 'FAIL'} "
                  f"({r['worst_margin']} {r['worst_joint']})  R10 min {r['largest_recoverable_min_Ns']} N.s  {'FEASIBLE' if r['feasible'] else 'infeasible'}  binding: {r['binding']}  [{r['seconds']} s]", flush=True)
    feas = [r["height_m"] for r in rows if r["feasible"]]
    feas2 = [r["height_m"] for r in rows if r["feasible_ignoring_the_high_table_pickup"]]
    res = {"candidate": concept["id"], "packaging": list(packaging), "heights": rows, "feasible_heights_m": feas, "max_feasible_height_m": max(feas) if feas else None,
           "min_feasible_height_m": min(feas) if feas else None,
           "feasible_heights_ignoring_the_high_table_pickup_m": feas2, "max_feasible_height_ignoring_the_high_table_pickup_m": max(feas2) if feas2 else None,
           "binding_by_height": {f"{r['height_m']:.2f}": r["binding"] for r in rows},
           "binding_by_height_ignoring_the_high_table_pickup": {f"{r['height_m']:.2f}": r["binding_ignoring_the_high_table_pickup"] for r in rows},
           "note": "nominal gates only (no bounds sweep / Monte Carlo / servo-in-the-loop), gait chosen per height from the frozen set, CAD-foundation floors applied; a ceiling, not a robust answer"}
    if out_root is not None:
        out = Path(out_root)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{concept['id']}.json").write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
        (out / f"{concept['id']}.md").write_text(to_markdown(res), encoding="utf-8")
    return res


def to_markdown(r: dict) -> str:
    L = [f"<!-- generated by python -m openhumanoid.concept sweep; tool-written -->", f"# Height sweep: {r['candidate']}", "",
         f"Packaging: {r['packaging']}. {r['note']}.", "",
         f"**Maximum feasible height: {r['max_feasible_height_m']} m** (feasible heights: {r['feasible_heights_m']}). Ignoring the 0.45 m-table pickup: {r['max_feasible_height_ignoring_the_high_table_pickup_m']} m (feasible: {r['feasible_heights_ignoring_the_high_table_pickup_m']}).", "",
         "| height m | mass kg | gait (flex deg / step s) | joint gates (worst margin) | R10 largest recoverable N.s (m/s) per scenario | feasible | binding constraint | binding without the 0.45 m-table pickup |", "|---|---|---|---|---|---|---|---|"]
    for x in r["heights"]:
        lr = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in x["largest_recoverable_Ns"].items())
        L.append(f"| {x['height_m']:.2f} | {x['mass_kg']} | {x['gait']['stance_knee_flex_deg']:.0f} / {x['gait']['step_time_s']} | {'PASS' if x['joint_gates_pass'] else 'FAIL'} ({x['worst_margin']} {x['worst_joint']}) | "
                 f"{lr} (min {x['largest_recoverable_min_Ns']} = {x['largest_recoverable_min_dv_mps']} m/s; need {x['required_impulse_Ns']}) | {x['feasible']} | {x['binding']} | {x['binding_ignoring_the_high_table_pickup']} |")
    L += ["", "## Violations per height (largest factor first)"]
    for x in r["heights"]:
        L.append(f"- {x['height_m']:.2f} m: " + ("; ".join(f"{v['constraint']} x{v['factor']}" for v in x["violations"][:4]) or "none"))
    return "\n".join(L) + "\n"


def relaxed_feasibility(res: dict, factors: dict) -> dict:
    """INDICATIVE, not applied anywhere: which heights of a sweep would be feasible if the joint gates were looser by `factors` (e.g. the factors the
    frozen gait needs on Open Duck Mini's own model, `calibration/odm_calibration.json` b_frozen_on_odm), with R10 and invalid motions (except the
    high-table pickup) unchanged. `factors`: {"peak torque": f, "RMS vs rated": f, "torque-speed envelope": f, "overload time": f}.
    Uses the top violations stored per height, which is complete for every category above the smallest factor."""
    out = {}
    for x in res["heights"]:
        ok, why = True, []
        for v in x["violations"]:
            if v["kind"] == "joint gate":
                cat = v["constraint"].split(" @ ")[0]
                if v["factor"] > factors.get(cat, 1.0):
                    ok = False
                    why.append(f"{v['constraint']} x{v['factor']} > {factors.get(cat, 1.0):.2f}")
            elif v["kind"] == "R10" or (v["kind"] == "invalid motion" and not v["constraint"].startswith("motion pickup_")):
                ok = False
                why.append(v["constraint"][:80])
        out[f"{x['height_m']:.2f}"] = {"feasible": ok, "why_not": why[:3]}
    return out
