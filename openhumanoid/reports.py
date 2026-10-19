"""Turn sizing results into generated/sizing.{json,md} and generated/bom.{csv,md}."""
from __future__ import annotations

import csv
import json
from collections import Counter

from . import catalog
from .paths import generated_header
from .sizing import capability, fixed_parts, material_cost
from .spec import generated_dir


def sizing_to_dict(spec: dict, res: dict) -> dict:
    b = res["best"]
    d = {
        "generated_by": "oh size", "variant": spec["id"],
        "feasible": b.feasible, "reason": b.reason, "height_m": b.height, "height_mode": res["mode"],
        "limiting_factor": res["limiting"], "joints_base": b.base_joints,
        "optional_added": res["optional_added"], "optional_dropped": res["optional_dropped"],
        "sweep": [{"height_m": e.height, "feasible": e.feasible, "reason": e.reason,
                   "cost": e.cost["total"] if e.cost else None} for e in res["sweep"]],
    }
    if b.body:
        d["mass"] = b.body.breakdown
        d["geometry_m"] = {k: round(v, 4) for k, v in b.body.geom.items()}
        d["segment_mass_kg"] = {k: round(v, 4) for k, v in b.body.seg_mass.items()}
    if b.selection:
        d["actuators"] = b.selection
        d["cost_usd"] = b.cost
        d["gaits"] = b.gait_checks
        d["joint_checks"] = {
            jn: {g: {"ok": c["ok"], "limit": c["limit"], "margins": {k: round(v, 2) for k, v in c["margins"].items()}}
                 for g, c in gc.items()} for jn, gc in b.checks.items()}
        d["requirements"] = {g: {jn: {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}
                                 for jn, r in rq.items()} for g, rq in b.reqs.items()}
    return d


def write_sizing(spec: dict, res: dict) -> dict:
    d = sizing_to_dict(spec, res)
    out = generated_dir(spec)
    (out / "sizing.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
    (out / "sizing.md").write_text(sizing_markdown(spec, d), encoding="utf-8")
    return d


def sizing_markdown(spec: dict, d: dict) -> str:
    L = [generated_header("size", "<!--").rstrip() + " -->", f"# Sizing report: {spec['name']}", ""]
    L.append(f"**Result:** {'✅ feasible' if d['feasible'] else '❌ infeasible'} ({d['reason']}) · "
             f"**height {d['height_m']:.2f} m** (mode: {d['height_mode']})")
    if d.get("limiting_factor"):
        L.append(f"\n**What stops it being taller:** {d['limiting_factor']}")
    if "mass" in d:
        m = d["mass"]
        L += ["", f"**Estimated mass:** {m['total_kg']:.2f} kg (structure {m['structure_kg']:.2f} · actuators "
              f"{m['actuators_kg']:.2f} · compute/power {m['compute_power_kg']:.2f} · electronics {m['electronics_kg']:.2f})"]
    if "cost_usd" in d:
        c = d["cost_usd"]
        L += [f"**Estimated cost:** ${c['total']:.2f} (actuators ${c['actuators']:.0f} · other parts ${c['fixed_parts']:.0f} · "
              f"filament {c['material_kg']:.2f} kg ${c['material']:.0f}) vs cap ${spec['goals']['budget_usd'].get('hard_cap', spec['goals']['budget_usd']['target'])}"]
        L += ["", f"Optional joints added: {', '.join(d['optional_added']) or 'none'} · dropped for budget/torque: "
              f"{', '.join(d['optional_dropped']) or 'none'}"]
        L += ["", "## Gaits", "", "| Gait | Required | Feasible | Worst joint | Margin | Limited by |", "|---|---|---|---|---|---|"]
        for g, gc in d["gaits"].items():
            L.append(f"| {g} | {'yes' if gc['required'] else 'stretch'} | {'✅' if gc['ok'] else '❌'} | {gc['worst_joint']} | "
                     f"{gc['worst_margin']}× | {gc['limit']} |")
        L += ["", "## Joints (required gaits)", "", "| Joint | Actuator | Cont. req N·m | Peak req N·m | Speed req rad/s | Margins (cont/peak/speed) |",
              "|---|---|---|---|---|---|"]
        g0 = next(iter(d["requirements"]))
        for jn, act in d["actuators"].items():
            r = d["requirements"][g0][jn]
            m = d["joint_checks"][jn][g0]["margins"]
            L.append(f"| {jn} | {act} | {r['continuous_nm']:.2f} | {r['peak_nm']:.2f} | {r['speed_rad_s']:.2f} | "
                     f"{m['continuous']} / {m['peak']} / {m['speed']} |")
    L += ["", "## Height sweep", "", "| h (m) | feasible | cost | reason |", "|---|---|---|---|"]
    for s in d["sweep"]:
        L.append(f"| {s['height_m']:.2f} | {'✅' if s['feasible'] else '—'} | {('$%.0f' % s['cost']) if s['cost'] else ''} | {s['reason']} |")
    L += ["", "## Assumptions", "",
          "- First-order quasi-static model × dynamic factors (see `openhumanoid/sizing.py`, spec `analysis:`).",
          "- Structure mass = `mass_model.structure_kg_at_1m × h³`. **Uncalibrated until CAD exists (P3).**",
          "- Catalog prices/specs marked `verified: false` are estimates. Run the sourcing prompt before buying.",
          "- Validate against `oh sim test` joint torques and hardware tests before trusting margins < 1.3×."]
    return "\n".join(L) + "\n"


def write_bom(spec: dict, sizing: dict) -> dict:
    lines = []
    for aid, qty in Counter(sizing["actuators"].values()).items():
        lines.append((catalog.get(aid), qty, "actuators: " + ", ".join(sorted(j for j, a in sizing["actuators"].items() if a == aid))))
    _, _, fixed = fixed_parts(spec)
    lines += [(p, q, "") for p, q in fixed]
    mat = catalog.get(spec["bom"].get("material", "pla-plus-1kg"))
    lines.append((mat, round(sizing["cost_usd"]["material_kg"], 2), "printed frame + shell incl. waste"))
    rows, tot = [], {"typical": 0.0, "low": 0.0, "high": 0.0}
    for p, qty, note in lines:
        row = {"part": p["id"], "name": p["name"], "category": p["category"], "qty": qty,
               "unit": p["price_usd"].get("unit", "each"), "unit_usd": catalog.price(p),
               "low_usd": catalog.price(p, "low"), "high_usd": catalog.price(p, "high"),
               "ext_usd": round(catalog.price(p) * qty, 2), "verified": p["verified"], "note": note}
        for k in tot:
            tot[k] += catalog.price(p, k) * qty
        rows.append(row)
    out = generated_dir(spec)
    with open(out / "bom.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    unverified = sum(1 for r in rows if not r["verified"])
    cap = spec["goals"]["budget_usd"].get("hard_cap", spec["goals"]["budget_usd"]["target"])
    md = [generated_header("bom", "<!--").rstrip() + " -->", f"# BOM: {spec['name']} (h = {sizing['height_m']:.2f} m)", "",
          f"**Total (typical): ${tot['typical']:.2f}** · range ${tot['low']:.0f}–${tot['high']:.0f} · cap ${cap}", "",
          f"⚠️ {unverified}/{len(rows)} lines unverified (estimates). Run `prompts/sourcing/part-sourcing.md` before buying." if unverified else "All lines verified.",
          "", "| Part | Qty | Unit $ | Ext $ | Verified | Note |", "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['name']} (`{r['part']}`) | {r['qty']} {r['unit'] if r['unit'] != 'each' else ''} | {r['unit_usd']:.2f} | "
                  f"{r['ext_usd']:.2f} | {'✅' if r['verified'] else '—'} | {r['note']} |")
    (out / "bom.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"rows": rows, "totals": tot, "unverified": unverified}


def capability_table(spec: dict) -> list[dict]:
    return [{"id": p["id"], **{k: round(v, 2) for k, v in capability(p, spec).items()}, "usd": catalog.price(p)}
            for p in catalog.actuators()]


__all__ = ["write_sizing", "write_bom", "capability_table", "material_cost"]
