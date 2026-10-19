"""Adam baseline v2 (T-20261019-4ab5): cost of the v2 candidates in the R1 accounting (variants/adam/design/r1_cost.py: parts + ~13% spares
+ 7.53% tax + shipping, x 1.10 contingency), against the locked R1 budget (requirements R1: <= $1,600 delivered).

New lines (2026-10-19; listed prices read today, `verified` = the price was seen on a vendor page, not a catalog part):
* bus_adapter_2: a second Waveshare bus servo adapter, $4.99 (catalog/.../waveshare-bus-servo-adapter.yaml). SIL finding (T-20261019-2adc):
  23 servos on one adapter take ~9-10 ms per cycle, so 100 Hz control needs two buses.
* L5c CAD bill (variants/adam/cad/linkages/l5c.py; per leg: 6 pin/axle joints x 2 = 12 623ZZ; 2 couplers; 4 M3x16 12.9 low-head pins,
  2 M3x45 axles, thin nuts, washers, 3x6 spacers):
    - 623ZZ x 24: budget 50-pack $10.39 + $4.85 shipping (eBay, ships from China; budget-grade C0r may be ~180 N, not NSK's 218 N),
      or quality VXB 10-pack $29.99 x 3 (C0r 230 N);
    - 6061-T6 1/8" x 3" x 12" bar $5.31 (Speedy Metals) + ~$8 shipping (ESTIMATE), cut into four 10 mm strips;
    - M3 12.9 screws, DIN 439 thin nuts, washers, spacers: $10 (ESTIMATE);
    - minus R1's 4 MR105ZZ fork idler bearings at the knees and ankles (the parallelogram joints use 623ZZ): -$3 (ESTIMATE).
Run:  .venv/Scripts/python variants/adam/design/v2/cost.py      Out: variants/adam/design/v2/results/cost.{json,md}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "packaging"))
import r1_cost as RC  # noqa: E402
import cost as PKC  # noqa: E402  (packaging cost.py: cfg() with the R1 Path 1 line list; its linkage_kit ESTIMATE is not used here)

RC.P["bus_adapter_2"] = (4.99, 4.99)
RC.P["l5c_budget"] = (10.39 + 4.85 + 5.31 + 8.0 + 10.0 - 3.0,) * 2
RC.P["l5c_quality"] = (3 * 29.99 + 5.31 + 8.0 + 10.0 - 3.0,) * 2
RC.EST = set(RC.EST) | {"l5c_budget", "l5c_quality"}
REQ_CAP = 1600.0
CATALOG_ADDITIONS = 25.0     # requirements R1: catalog additions ~ $25 (post-sign-off findings: 4 WAGO, Lumenier/GNB swap, wire)


def row(name, **kw):
    extra = kw.pop("extra", {})
    c = PKC.cfg(name, **kw)
    for k, q in extra.items():
        c["lines"][k] = c["lines"].get(k, 0) + q
    t = RC.total(c)
    return {"name": name, "sticker": t["parts_sticker"], "r1_total": t["r1_total"], "with_catalog_additions": round(t["r1_total"] + CATALOG_ADDITIONS, 2),
            "estimate_lines": t["estimate_lines"]}


def main() -> int:
    rows = [row("R1 Path 1 (0.55 m), engine accounting", ),
            row("V2a: R1 + longer arms + 2nd bus adapter", extra={"bus_adapter_2": 1}),
            row("V2b: V2a + L5c, budget 623ZZ", extra={"bus_adapter_2": 1, "l5c_budget": 1}),
            row("V2b: V2a + L5c, quality 623ZZ (VXB)", extra={"bus_adapter_2": 1, "l5c_quality": 1}),
            row("V2a at 0.60 m (bench-conditional)", h=0.60, extra={"bus_adapter_2": 1}),
            row("V2a lean (STS3215 knees, after the bench + Q3)", knees_3250=False, extra={"bus_adapter_2": 1})]
    base = rows[0]["with_catalog_additions"]
    for r in rows:
        r["delta_vs_R1"] = round(r["with_catalog_additions"] - base, 2)
        r["under_1600"] = r["with_catalog_additions"] <= REQ_CAP
    out = HERE / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cost.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    L = ["<!-- written by variants/adam/design/v2/cost.py (T-20261019-4ab5); re-run, do not edit -->", "# Adam v2 cost (R1 accounting, CHEAP scenario)", "",
         f"R1 total = (parts + ~13% spares) x 1.0753 tax + shipping, x 1.10 contingency; + ${CATALOG_ADDITIONS:.0f} catalog additions (requirements R1). Cap ${REQ_CAP:.0f}.", "",
         "| configuration | sticker | R1 total | + catalog additions | vs R1 | <= $1,600 |", "|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['name']} | ${r['sticker']:.0f} | ${r['r1_total']:.0f} | ${r['with_catalog_additions']:.0f} | {r['delta_vs_R1']:+.0f} | {'yes' if r['under_1600'] else 'NO'} |")
    (out / "cost.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
