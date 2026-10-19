"""Print a compact summary of results/{widths,rom}.json (written by check.py)."""
import json
from pathlib import Path

R = Path(__file__).resolve().parent / "results"


def f(ps):
    return [(p["a"], p["b"], p["kind"], p["mm3"]) for p in ps[:6]]


if (R / "widths.json").exists():
    w = json.loads((R / "widths.json").read_text())
    for k, v in w.items():
        if k not in ("sections", "R1_leg_v2"):
            print(k, v)
    r1 = w.get("R1_leg_v2", {})
    print("R1:", {k: v for k, v in r1.items() if k != "sections"})
if (R / "rom.json").exists():
    r = json.loads((R / "rom.json").read_text())
    print("zero", f(r["zero_pose"]))
    for j in ("hip_pitch_l", "knee_l", "ankle_pitch_l", "ankle_at_knee_90"):
        v = r[j]
        print(j, v["limit_neg"], v["limit_pos"], v["within_spec"])
        for e in v["events"]:
            print("   ", e["angle_deg"], f(e["pairs"]))
    for k, v in r["poses"].items():
        print(k, v["ok"], v["q_deg"], f(v["pairs"]))
    print("ROM ok:", r["ok"])
