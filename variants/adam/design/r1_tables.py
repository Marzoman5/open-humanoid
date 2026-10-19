"""R5 table-height check for the R1 concepts (T-20261019-36f9): the frozen 150 g pickup at the provisional coffee-table heights
0.40 / 0.45 / 0.50 m (challenge-1 provisional answer 1) through the concept engine's own planner, nominal gates only (`run_bundle`).

Run:  .venv/Scripts/python variants/adam/design/r1_tables.py variants/adam/concepts/R1-P1-0p60-3s-sts3250-knee-hiproll.yaml [--tables 0.30 0.35 0.40 0.45 0.50]
Out:  variants/adam/design/r1_results/tables_<candidate>.json and a printed table.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openhumanoid.concept import evaluate as EV
from openhumanoid.concept.robot import load_concept

OUT = Path(__file__).resolve().parent / "r1_results"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("concept")
    ap.add_argument("--tables", nargs="+", type=float, default=[0.30, 0.35, 0.40, 0.45, 0.50])
    a = ap.parse_args(argv)
    c = load_concept(a.concept)
    rows = []
    for t in a.tables:
        b = EV.run_bundle(c, EV.Mods(), table_height=t, thermal=False, motions=["stand", "pickup"])
        inv = {k: v[:140] for k, v in b.invalid.items() if k.startswith("pickup")}
        r = b.rows
        worst = min(((x["worst_margin"], x["joint"]) for x in r.values()), default=(None, None))
        rows.append({"table_m": t, "pickup_valid": not inv, "invalid": inv, "strict_worst_margin": round(worst[0], 3) if worst[0] is not None else None,
                     "worst_joint": worst[1], "motions_run": sorted(b.dem)})
        print(f"table {t:.2f} m: valid {not inv}  {inv or ''}  strict worst {rows[-1]['strict_worst_margin']} {worst[1]}", flush=True)
    OUT.mkdir(exist_ok=True)
    (OUT / f"tables_{c['id']}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
