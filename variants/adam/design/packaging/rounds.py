"""Packaging-for-look study (T-20261019-c1aa): critic rounds on the combined package C2 (styling only; hard points untouched).

Each round = the C2 levers + a REFINE set (capsule.py) that applies the previous round's critic top changes that are feasible inside
the hard points. The display cant stays the gap-rule value of C2 unless the refined shells close the gap (then it is raised).
Writes variants/adam/design/packaging/variants/<tag>/profiles.yaml and the compact render set docs/design-method/R2a-packaging/<tag>/.

Run:  .venv/Scripts/python variants/adam/design/packaging/rounds.py r2 [--no-render]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capsule as C  # noqa: E402
import render_pack as RP  # noqa: E402
import study as ST  # noqa: E402

C2_CANT = 20.5
ROUNDS = {
    # round 2: critic r1 (C2_r1 vs B4, both orders) top changes that the hard points allow
    "r2": dict(head_ovoid=True, chest_blend=True, low_roll=True, chest_n=2.3, back_n=2.3, pelvis_n=3.0, arm_bands="joints", leg_smooth=True),
}


def run(tag: str, refine: dict, render: bool = True) -> dict:
    gap = ST.baseline_gap()
    cant = C2_CANT
    while True:
        prof = C.build(ST.C2, cant, name=f"adam-pack-C2-{tag}", refine=refine)
        if C.min_gap(prof) >= gap or cant >= 30:
            break
        cant += 0.5
    fails = C.hp_fails(prof)
    prof.pop("_L")
    d = HERE / "variants" / f"C2_{tag}"
    d.mkdir(parents=True, exist_ok=True)
    pp = d / "profiles.yaml"
    pp.write_text(f"# Packaging-for-look C2, critic round {tag} (T-20261019-c1aa, PROVISIONAL). levers: {ST.C2.tag()}; refine: {refine}\n"
                  "# Written by variants/adam/design/packaging/rounds.py; re-run, do not edit.\n" + yaml.safe_dump(prof, sort_keys=False, width=160),
                  encoding="utf-8")
    print(f"C2 {tag}: cant {cant}  HP fails {fails}", flush=True)
    if render and not fails:
        RP.render(pp, f"C2_{tag}", "design-7")
    return {"cant": cant, "hp_fails": fails}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    run(a.tag, ROUNDS[a.tag], not a.no_render)
