"""Adam baseline v2 (T-20261019-4ab5): write variants/adam/design/profiles.yaml = the R2a B4 'Atlas-capsule' styling on the v2 hard points.

v2 hard points = R1 + longer arms (L9a). L5c is NOT in v2 (R2a-v2 review section 3: the real-CAD leg widens the upper thigh and calf and
the arm-gap rule cannot be met). So the B4 profile (variants/adam/design/silhouette/dir_B/profiles.yaml, hand-styled
by silhouette/directions.py) keeps its head, torso and legs; its arm segments, arm hard points and elbow joint are replaced by the ones the
packaging capsule rules (B4, parametric) fit around the longer-arm hard points (variants/adam/design/v2/look.py candidate V2a). The arm
display cant is re-derived with the R2a visible-gap rule against the B4 body.

Run:  .venv/Scripts/python variants/adam/design/v2/profiles_v2.py [--render]
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PK = HERE.parent / "packaging"
sys.path.insert(0, str(PK))
sys.path.insert(0, str(REPO))
import capsule as C  # noqa: E402
import study as ST  # noqa: E402

B4 = HERE.parent / "silhouette" / "dir_B" / "profiles.yaml"
OUT = HERE.parent / "profiles.yaml"
ARM = ("arm_core", "deltoid", "upper_arm", "forearm")
LV = ST.replace(ST.B, upper=0.20, fore=0.23)


def hybrid(cant: float) -> dict:
    b4 = yaml.safe_load(B4.read_text(encoding="utf-8"))
    v2 = C.build(LV, cant, name="adam-v2")
    L = v2.pop("_L")
    out = copy.deepcopy(b4)
    arm = {s["id"]: s for s in v2["segments"] if s["id"] in ARM}
    out["segments"] = [arm.get(s["id"], s) for s in b4["segments"]]
    out["hard_points"] = [h for h in b4["hard_points"] if h["segment"] != "arm_core_l"] + [h for h in v2["hard_points"] if h["segment"] == "arm_core_l"]
    out["joints"] = [next(j for j in v2["joints"] if j["id"] == "elbow_l") if j["id"] == "elbow_l" else j for j in b4["joints"]]
    out["name"] = "adam-v2"
    out["sources"] = list(b4.get("sources", [])) + ["variants/adam/design/v2/profiles_v2.py (T-20261019-4ab5): arm segments / hard points / elbow from "
                                                    "packaging capsule.py (B4 rules) around the L9a longer-arm hard points (upper arm 0.20 H, forearm 0.23 H)"]
    out["notes"] = (f"Adam baseline v2 (PROVISIONAL): R2a B4 Atlas-capsule styling (head, torso, legs unchanged) on the v2 hard points = R1 0.55 m + "
                    f"longer arms (L9a). Arm display cant {cant:.1f} deg (R2a visible-gap rule). L5c is not in v2 (R2a-v2 review section 3).")
    out["_L"] = L
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args(argv)
    gap = ST.baseline_gap()
    cant = 14.0
    while True:
        prof = hybrid(cant)
        if C.min_gap(prof) >= gap or cant >= 30:
            break
        cant += 0.5
    fails = C.hp_fails(prof)
    prof.pop("_L")
    print(f"v2 hybrid: cant {cant}  gap target {gap:.2f}  HP fails {fails}")
    OUT.write_text("# Adam baseline v2 (T-20261019-4ab5, PROVISIONAL): R2a B4 'Atlas-capsule' styling on the v2 hard points (R1 + longer arms).\n"
                   "# Written by variants/adam/design/v2/profiles_v2.py from silhouette/dir_B/profiles.yaml (B4) + packaging/capsule.py arms; re-run, do not edit.\n"
                   + yaml.safe_dump(prof, sort_keys=False, width=160), encoding="utf-8")
    from openhumanoid.design import metrics, studio
    from openhumanoid.design.meshio import load_subject
    d = HERE / "look" / "v2_profiles"
    d.mkdir(parents=True, exist_ok=True)
    rep = metrics.write_report(load_subject(OUT, "v2"), d / "design_metrics.json", ref_masks=dict(studio.reference_mask(r, "front") for r in ST.REFS))
    ev = rep["evaluation"]
    print("metrics", {k: (round(v["value"], 3) if isinstance(v["value"], float) else v["value"]) for k, v in ev["criteria"].items()}, ev["n_pass"], "/", ev["n_scored"], ev["failed"])
    if a.render and not fails:
        import render_pack as RP
        RP.OUT = REPO / "docs" / "design-method" / "R2a-v2"
        RP.render(OUT, "v2_B4_longarm", "design-v2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
