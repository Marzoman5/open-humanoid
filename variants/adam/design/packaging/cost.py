"""Packaging-for-look study (T-20261019-c1aa): R1-accounting cost of each lever and of the combined package.

Uses variants/adam/design/r1_cost.py (config/total: sticker + ~13% spares + 7.53% tax + shipping, x1.10 contingency) on the R1 recommended
Path 1 line list. New lines come from parts.yaml (vendor listings read 2026-10-19, verified: false) plus one ESTIMATE (linkage hardware).

Run:  .venv/Scripts/python variants/adam/design/packaging/cost.py      -> results/cost.{json,md}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import r1_cost as RC  # noqa: E402

PARTS = yaml.safe_load((HERE / "parts.yaml").read_text(encoding="utf-8"))
RC.P["sts3045m"] = (PARTS["servos"]["sts3045m"]["price"],) * 2
RC.P["scs0009"] = (PARTS["servos"]["scs0009"]["price"],) * 2
RC.P["buck6"] = (PARTS["rail"]["buck-pololu-d36v50f6"]["price"],) * 2
# ESTIMATE (not quoted): per relocated joint 2 M3 ball links + 1 M3 threaded rod + 2 MR105 bearings ~ $3; 4 joints -> $12
RC.P["linkage_kit"] = (12.0, 12.0)
RC.EST = set(RC.EST) | {"linkage_kit"}
RC.P["lipo3s_1300"] = (26.99, 26.99)


def cfg(name, *, small_arm=False, small_neck=False, waist=True, links=False, five_dof=False, pack="lipo3s_1850", h=0.55, knees_3250=True):
    n12 = 19 if knees_3250 else 21
    n3250 = 4 if knees_3250 else 2
    kw = dict(RC.BASE_P1, n_servo=n12, n_sts3250=n3250, pack=pack, pla_kg=RC.PLA_060 if h > 0.57 else RC.PLA_055)
    c = RC.config(name, **kw)
    L, sp = c["lines"], dict(c["spares"])
    if small_arm:     # 6 STS3215 (2 pitch, 2 roll, 2 elbow) -> STS3045M; 2 gripper STS3215 -> SCS0009
        L["servo12"] -= 8
        L["sts3045m"] = 6
        L["scs0009"] = 2
        sp["sts3045m"] = 1
    if small_neck:
        L["servo12"] -= 2
        L["scs0009"] = L.get("scs0009", 0) + 2
        sp["scs0009"] = 1
    if small_arm or small_neck:
        L["buck6"] = 1
    if not waist:
        L["servo12"] -= 1
    if five_dof:
        L["servo12"] -= 2
    if links:
        L["linkage_kit"] = 1
    c["spares"] = sp
    return c


ROWS = [
    ("R1 recommended (baseline)", {}),
    ("L1d small arm (6x STS3045M + 2x SCS0009 + 6 V buck)", dict(small_arm=True)),
    ("L2 no waist yaw", dict(waist=False)),
    ("L3a flat Tattu 1300 pack", dict(pack="lipo3s_1300")),
    ("L3b lumbar pack (needs no waist yaw)", dict(waist=False)),
    ("L5 knee + ankle linkages (est. hardware)", dict(links=True)),
    ("L6 small neck (2x SCS0009 + 6 V buck)", dict(small_neck=True)),
    ("L7 5-DOF legs", dict(five_dof=True)),
    ("L8 0.60 m", dict(h=0.60)),
    ("C1 package (L1d + L6 + L2/L3b + L5, 6-DOF)", dict(small_arm=True, small_neck=True, waist=False, links=True)),
    ("C1 with 5-DOF legs", dict(small_arm=True, small_neck=True, waist=False, links=True, five_dof=True)),
]


def main() -> int:
    base = RC.total(cfg("base"))["r1_total"]
    out = []
    for name, kw in ROWS:
        c = cfg(name, **kw)
        t = RC.total(c)
        out.append({"config": name, "lines": c["lines"], "spares": c["spares"], "r1_total": t["r1_total"], "delta_r1": round(t["r1_total"] - base, 2),
                    "sticker": t["parts_sticker"], "estimate_lines": t["estimate_lines"]})
    md = ["<!-- written by variants/adam/design/packaging/cost.py (T-20261019-c1aa); re-run, do not edit -->",
          "# Packaging-for-look levers: R1-accounting cost (CHEAP scenario)", "",
          "New prices are vendor listings read 2026-10-19 (parts.yaml, verified: false): STS3045M $40.00 (aifitlab, backordered; Core Electronics "
          "A$57.93 in stock), SCS0009/SC09 $8.99 (Waveshare), Pololu D36V50F6 $39.95. Linkage hardware $12 is an ESTIMATE.", "",
          "| configuration | sticker | R1 total | change vs R1 |", "|---|---|---|---|"]
    for r in out:
        md.append(f"| {r['config']} | ${r['sticker']:.0f} | ${r['r1_total']:.0f} | {r['delta_r1']:+.0f} $ |")
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "cost.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (HERE / "results" / "cost.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
