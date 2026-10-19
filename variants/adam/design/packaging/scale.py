"""Packaging-for-look study (T-20261019-c1aa): at what HEIGHT does a toy-free silhouette become feasible with a given actuator class?

For each limb feature, the reference robots' front-view width as a fraction of height (optimus_like, atlas_like: approximate, low-confidence
profiles in openhumanoid/design/references/) is compared with the narrowest section the actuator packaging allows:
servo dimension across the limb + 2 x housing (2.65 mm) + 2 x shell gap and wall (3.1 mm). H_min = floor_mm / reference_fraction is the
height at which that feature can be as slim as the reference. The feature with the largest H_min sets the scale. A blind critic tolerates
some excess, so this is a FLOOR on the answer, not a prediction of a pass.

Run:  .venv/Scripts/python variants/adam/design/packaging/scale.py   -> results/scale.{json,md}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REFS = {k: REPO / f"openhumanoid/design/references/{k}.yaml" for k in ("optimus_like", "atlas_like")}
WRAP = 2 * 2.65 + 2 * 3.1     # housing + shell gap/wall, both sides


def width_at(seg: dict, z: float) -> float:
    st = seg["stations"]
    zs = np.array([s["z"] for s in st])
    ws = np.array([s["w"] for s in st])
    return float(np.interp(z, zs, ws))


def ref_fractions(path: Path) -> dict:
    p = yaml.safe_load(path.read_text(encoding="utf-8"))
    H = p["height_m"]
    seg = {s["id"]: s for s in p["segments"]}
    j = {x["id"]: x["pos"][2] for x in p["joints"]}
    hip, knee, ankle, sh = j["hip_l"], j["knee_l"], j["ankle_l"], j["shoulder_l"]
    arm_z = [s["z"] for s in seg["arm"]["stations"]]
    wrist = min(arm_z) + 0.03 * H
    elbow = sh - 0.19 * H
    leg, arm, head = seg["leg"], seg["arm"], seg["head"]
    return {"thigh_upper": width_at(leg, hip - 0.25 * (hip - knee)) / H, "knee": width_at(leg, knee) / H,
            "calf_max": max(width_at(leg, z) for z in np.linspace(ankle, knee, 40)) / H, "ankle": width_at(leg, ankle + 0.03 * H) / H,
            "upper_arm": width_at(arm, (sh + elbow) / 2) / H, "elbow": width_at(arm, elbow) / H, "forearm": width_at(arm, (elbow + wrist) / 2) / H,
            "head_w": max(s["w"] for s in head["stations"]) / H,
            "shoulder_P3": None}


# narrowest front-view section per feature (mm) for each packaging: servo dimension across the limb + WRAP
FLOORS = {
    "STS3215 direct (R1 layout)": {"thigh_upper": 52 + 6.2, "knee": 52 + 6.2, "calf_max": 52 + 6.2, "ankle": 52 + 6.2,
                                   "upper_arm": 24.7 + WRAP, "elbow": 35 + 2 + WRAP, "forearm": 24.7 + WRAP, "head_w": 35 + 2 + WRAP},
    "STS3215 legs relocated (slim knee/ankle) + STS3045M arm + SCS0009 neck/gripper": {
        "thigh_upper": 52 + 6.2, "knee": 32 + 6.2, "calf_max": 52 + 6.2, "ankle": 32 + 6.2,
        "upper_arm": 15 + WRAP, "elbow": 29.2 + 2 + WRAP, "forearm": 12.1 + WRAP, "head_w": 25.25 + 2 + WRAP},
}


def main() -> int:
    refs = {k: ref_fractions(p) for k, p in REFS.items()}
    feats = [f for f in FLOORS["STS3215 direct (R1 layout)"]]
    out = {"refs": refs, "floors_mm": FLOORS, "h_min_m": {}}
    md = ["<!-- written by variants/adam/design/packaging/scale.py (T-20261019-c1aa); re-run, do not edit -->",
          "# Height at which each limb section can be as slim as the references (PROVISIONAL)", "",
          "Reference width / H from the approximate reference profiles (optimus_like, atlas_like; low confidence). Floor = servo dimension "
          "across the limb + housing + shell (11.5 mm). H_min = floor / (reference width / H). The largest H_min sets the scale.", "",
          "| feature | optimus W/H | atlas W/H | " + " | ".join(f"{k}: floor mm / H_min m (optimus, atlas)" for k in FLOORS) + " |",
          "|---|---|---|" + "---|" * len(FLOORS)]
    for f in feats:
        row = f"| {f} | {refs['optimus_like'][f]:.3f} | {refs['atlas_like'][f]:.3f} |"
        for k, fl in FLOORS.items():
            hm = [fl[f] / 1000 / refs[r][f] for r in REFS]
            out["h_min_m"].setdefault(k, {})[f] = [round(x, 2) for x in hm]
            row += f" {fl[f]:.1f} / {hm[0]:.2f}, {hm[1]:.2f} |"
        md.append(row)
    md.append("")
    for k in FLOORS:
        worst = max(out["h_min_m"][k].items(), key=lambda kv: min(kv[1]))
        out.setdefault("binding", {})[k] = {"feature": worst[0], "h_min_m": worst[1]}
        md.append(f"- **{k}:** binding feature `{worst[0]}`, H_min {worst[1][0]:.2f} m (optimus) / {worst[1][1]:.2f} m (atlas).")
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "scale.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (HERE / "results" / "scale.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
