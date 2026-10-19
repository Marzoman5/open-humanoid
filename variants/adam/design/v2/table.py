"""Collect the v2 engine results into one comparison table (T-20261019-4ab5): calibrated/strict/half margins, bounds, R10, largest push
(results/cal_*.json, this task's engine.py) and the 64-sample engine reports (generated/concept/<id>/report.json: MC p95, runtime,
current, mass). Writes results/compare.{json,md}.

Run:  .venv/Scripts/python variants/adam/design/v2/table.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GEN = REPO / "variants/adam/generated/concept"
IDS = {"R1": "R1-P1r-0p55-3s-sts3250-knee-hiproll", "V2a": "V2a-0p55-longarm", "V2b": "V2b-0p55-l5c-longarm"}
MC = {"R1 0.55": "R1-P1r-0p55-3s-sts3250-knee-hiproll", "V2a 0.55": "V2a-0p55-longarm", "V2b 0.55": "V2b-0p55-l5c-longarm", "V2a 0.60": "V2a-0p60-longarm",
      "R1 0.60": "R1-P1-0p60-3s-sts3250-knee-hiproll"}


def find(d, *keys):
    """First value found under any of the dotted key paths."""
    for k in keys:
        cur = d
        ok = True
        for p in k.split("."):
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                ok = False
                break
        if ok:
            return cur
    return None


def main() -> int:
    rows = []
    for tag, cid in IDS.items():
        p = HERE / "results" / f"cal_{cid}.json"
        if not p.exists():
            continue
        for r in json.loads(p.read_text(encoding="utf-8")):
            n = r["nominal"]
            lr = r.get("largest_recoverable_Ns") or {}
            rows.append({"cand": tag, "h": r["height_m"], "mass": n["mass_kg"], "gait": f"{r['gait']['stance_knee_flex_deg']:.0f}/{r['gait']['step_time_s']}",
                         "strict": f"{n['strict_worst']} ({n['strict_worst_joint']})", "half": n["half_worst"], "cal": f"{n['cal_worst']} ({n['cal_worst_joint']})",
                         "bounds s/h/c": "{strict_pass}/{half_pass}/{cal_pass} of {n_bounds}".format(**r["counts"]) if r.get("counts") else "-",
                         "failing_cal": r.get("bounds_failing_cal"), "failing_strict": r.get("bounds_failing_strict"),
                         "R10 all": n["r10_pass"], "R10 min Ns": min((v["Ns"] for v in lr.values() if v.get("Ns") is not None), default=None),
                         "invalid": list(n["invalid"])})
    mc = {}
    for tag, cid in MC.items():
        p = GEN / cid / "report.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        mc[tag] = {"mtime": p.stat().st_mtime,
                   "verdict": find(d, "verdict", "summary.verdict"),
                   "mc": find(d, "uncertainty.monte_carlo", "monte_carlo"),
                   "runtime_min": find(d, "power.runtime_min"), "avg_w": find(d, "power.average_power_w"),
                   "bus": find(d, "power.bus"), "mass": find(d, "robot.mass_kg", "mass.total_kg", "robot.mass_breakdown.total_kg"),
                   "cost": find(d, "cost", "bom.total")}
    (HERE / "results" / "compare.json").write_text(json.dumps({"cal": rows, "reports": mc}, indent=1, default=str), encoding="utf-8")
    for r in rows:
        print(r)
    for k, v in mc.items():
        print(k, {kk: (str(vv)[:300] if kk in ("mc", "bus", "cost") else vv) for kk, vv in v.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
