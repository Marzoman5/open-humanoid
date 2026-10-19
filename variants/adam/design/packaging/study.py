"""Packaging-for-look study (T-20261019-c1aa): LOOK side of every lever.

For each lever variant: layout.py hard points -> capsule.py (B4 rules) at the gap-rule display cant -> HP check -> profiles.yaml ->
`openhumanoid.design.metrics` (same code as `oh design metrics`, refs optimus_like + atlas_like). Writes
variants/adam/design/packaging/variants/<key>/{profiles.yaml,design_metrics.json} and results/look.{json,md}.

Run:  .venv/Scripts/python variants/adam/design/packaging/study.py [--only KEY ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import capsule as C  # noqa: E402
import layout as LY  # noqa: E402

OUT = HERE / "variants"
RES = HERE / "results"
REFS = [f"optimus_like={REPO / 'openhumanoid/design/references/optimus_like.yaml'}",
        f"atlas_like={REPO / 'openhumanoid/design/references/atlas_like.yaml'}"]
B = LY.Levers()
SM = "sts3045m"
VARIANTS = {   # key: (levers, what it tests)
    "V0": (B, "baseline: R1 hardware, B4 rules (B4-generic)"),
    "L1a": (replace(B, arm=SM), "shoulder-roll + elbow servos -> STS3045M (6 V rail)"),
    "L1b": (replace(B, pitch=SM), "shoulder-pitch servos -> STS3045M (narrower chest pair, lower chest top)"),
    "L1c": (replace(B, grip="scs0009"), "gripper servo -> SCS0009"),
    "L1d": (replace(B, arm=SM, pitch=SM, grip="scs0009"), "whole arm small: roll, elbow, pitch STS3045M; gripper SCS0009"),
    "L2": (replace(B, waist=False), "no waist-yaw servo"),
    "L3a": (replace(B, pack="chest_flat1300"), "pack -> Tattu 3S 1300 laid flat across the upper back (22 mm)"),
    "L3b": (replace(B, pack="lumbar_gnb", waist=False), "pack -> GNB 1850 low in the lumbar back (waist yaw removed to free the space)"),
    "L4": (replace(B, arm=SM, pitch=SM, grip="scs0009", pack="lumbar_gnb", waist=False), "shoulder layout with the chest emptied: small arm + no pack in the upper chest"),
    "L5a": (replace(B, knee_up=True), "knee servo up into the thigh, 1:1 parallelogram"),
    "L5b": (replace(B, ankle_up=True), "ankle-pitch servo up into the calf, 1:1 parallelogram"),
    "L5c": (replace(B, knee_up=True, ankle_up=True), "both: knee servo in the thigh, ankle servo in the calf"),
    "L6a": (replace(B, neck="scs0009"), "neck pitch + yaw -> SCS0009 (pitch in a slimmer head, yaw in the chest slot)"),
    "L6b": (replace(B, neck="scs0009", neck_yaw_at="neck"), "neck pitch + yaw -> SCS0009, yaw servo standing in the neck (chest front slot freed)"),
    "L7": (replace(B, legs="5dof"), "5-DOF legs (no ankle roll; heel and foot at 0.17 H)"),
    "L8": (replace(B, H=600.0), "height 0.60 m, R1 hardware"),
}
KEYS = ["P1", "P2a", "P2b", "P3", "P4", "P5", "P6", "P7", "P8a", "P8b", "P9a", "P9b", "P10a", "P10b", "S3a", "S3b", "S4a", "S4b", "HP"]


def baseline_gap() -> float:
    return C.min_gap(C.build(B, 21.0))


def run_variant(key: str, lv, label: str, gap: float, cant: float | None = None, style: dict | None = None, out_dir: Path | None = None,
                metrics_on: bool = True) -> dict:
    from openhumanoid.design import metrics, studio
    from openhumanoid.design.meshio import load_subject
    if cant is None:
        cant = 21.0 if key == "V0" else C.gap_rule_cant(lv, gap)
    prof = C.build(lv, cant, style, name=f"adam-pack-{key}")
    fails = C.hp_fails(prof)
    L = prof.pop("_L")
    d = out_dir or (OUT / key)
    d.mkdir(parents=True, exist_ok=True)
    pp = d / "profiles.yaml"
    pp.write_text(f"# Packaging-for-look variant {key} (T-20261019-c1aa, PROVISIONAL): {label}\n# levers: {lv.tag()}\n"
                  "# Written by variants/adam/design/packaging/study.py (capsule.py + layout.py); re-run, do not edit.\n"
                  + yaml.safe_dump(prof, sort_keys=False, width=160), encoding="utf-8")
    row = {"key": key, "label": label, "levers": asdict(lv), "cant_deg": cant, "hp_fails": fails, "ya_mm": round(L["ya"], 2),
           "Tf_mm": round(L["Tf"], 2), "chest_top_mm": round(L["chest_top"], 2), "pack_z_mm": round(L["pack_z"], 1), "notes": L["notes"]}
    for k in ("knee_rod_mm", "ankle_rod_mm", "ankle_gap_mm"):
        if k in L:
            row[k] = round(L[k], 1)
    if metrics_on:
        subj = load_subject(pp, key)
        refs = dict(studio.reference_mask(r, "front") for r in REFS)
        rep = metrics.write_report(subj, d / "design_metrics.json", ref_masks=refs)
        crit = rep["evaluation"]["criteria"]
        row["metrics"] = {k: (round(crit[k]["value"], 3) if isinstance(crit[k]["value"], (int, float)) else crit[k]["value"]) for k in crit}
        row["verdicts"] = {k: crit[k]["verdict"] for k in crit}
        row["n_pass"], row["n_scored"] = rep["evaluation"]["n_pass"], rep["evaluation"]["n_scored"]
        row["failed"] = rep["evaluation"]["failed"]
        m = rep["measured"]
        row["side_depth"] = {k: m.get(k) for k in m if "depth" in k.lower()}
    print(f"{key}: cant {cant:.1f}  HP fails {len(fails)}  {row.get('n_pass')}/{row.get('n_scored')}  P3 {row.get('metrics', {}).get('P3')}  "
          f"P8a {row.get('metrics', {}).get('P8a')}  P8b {row.get('metrics', {}).get('P8b')}  P10a {row.get('metrics', {}).get('P10a')}  "
          f"P2a {row.get('metrics', {}).get('P2a')}  failed {row.get('failed')}", flush=True)
    return row


def to_md(rows: list[dict], b4: dict | None) -> str:
    L = ["<!-- written by variants/adam/design/packaging/study.py (T-20261019-c1aa); re-run, do not edit -->",
         "# Packaging-for-look study: look metrics per lever (PROVISIONAL)", "",
         "Every variant: same B4 rules (capsule.py), cant by the R2a visible-gap rule, `oh design metrics` code. ✗ = outside the band.", "",
         "| key | lever | cant ° | HP | " + " | ".join(KEYS[:-1]) + " | pass |", "|" + "---|" * (len(KEYS) + 4)]
    allrows = ([b4] if b4 else []) + rows
    for r in allrows:
        m, v = r.get("metrics", {}), r.get("verdicts", {})
        cells = []
        for k in KEYS[:-1]:
            x = m.get(k)
            cells.append("-" if x is None else f"{x}{' ✗' if v.get(k) == 'FAIL' else ''}")
        L.append(f"| {r['key']} | {r['label']} | {r.get('cant_deg', '')} | {'pass' if not r.get('hp_fails') else len(r['hp_fails'])} | " + " | ".join(cells) + f" | {r.get('n_pass')}/{r.get('n_scored')} |")
    return "\n".join(L) + "\n"


def b4_row() -> dict:
    p = REPO / "docs/design-method/R2a/B_atlas_capsule/design_metrics.json"
    rep = json.loads(p.read_text(encoding="utf-8"))
    crit = rep["evaluation"]["criteria"]
    return {"key": "B4", "label": "R2a B4 as signed-provisional (hand-styled)", "cant_deg": 21.0, "hp_fails": [],
            "metrics": {k: (round(crit[k]["value"], 3) if isinstance(crit[k]["value"], (int, float)) else crit[k]["value"]) for k in crit},
            "verdicts": {k: crit[k]["verdict"] for k in crit}, "n_pass": rep["evaluation"]["n_pass"], "n_scored": rep["evaluation"]["n_scored"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    RES.mkdir(parents=True, exist_ok=True)
    gap = baseline_gap()
    print(f"target front-view arm gap (B4 rules at 21 deg): {gap:.2f} mm")
    prev = {}
    pj = RES / "look.json"
    if pj.exists():
        prev = {r["key"]: r for r in json.loads(pj.read_text(encoding="utf-8"))["rows"]}
    for key, (lv, label) in VARIANTS.items():
        if a.only and key not in a.only:
            continue
        prev[key] = run_variant(key, lv, label, gap)
    rows = [prev[k] for k in VARIANTS if k in prev] + [r for k, r in prev.items() if k not in VARIANTS]
    pj.write_text(json.dumps({"target_gap_mm": gap, "rows": rows}, indent=1, default=str), encoding="utf-8")
    (RES / "look.md").write_text(to_md(rows, b4_row()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
