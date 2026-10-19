"""R2a silhouette builder (library) for Adam (task T-20261019-d955, ADR 0010 step D1). The station tables live in
directions.py, which imports this module.

Each *direction* is a list of segments whose stations are written in millimetres. A station width or depth may be
`fit(extra)`: the smallest value that encloses every hard point of that segment spanning the station height with its
margin (3.1 mm wall + gap), plus `extra`. Everything else is a styling number chosen by the author. The result is a
`profiles.yaml` (the source of truth for the outer shape, schema design-profiles/0.1), checked with the framework's own
hard-point test (openhumanoid.design.massing.hard_point_margins).

Two segment families (frame + shell, design-language rule 5):
  role "dark"  - the graphite under-structure: joint cores, neck, waist/pelvis band (direction-dependent), heel, hands, visor
  role "shell" - the matte warm-white covers
Union = outer shape, so a dark core shows only where no shell covers it: those are the recessed joint bands.

Run (via the tables):
  .venv/Scripts/python variants/adam/design/silhouette/directions.py            # all directions + the recommended profiles.yaml
  .venv/Scripts/python variants/adam/design/silhouette/directions.py --only B   # one direction
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import hardpoints as HPM  # noqa: E402
from openhumanoid.design.massing import superellipse_sd, hard_point_margins  # noqa: E402
from openhumanoid.design.profiles import expand, validate  # noqa: E402

H = 550.0


class fit:  # noqa: N801  (reads like a keyword in the station tables)
    def __init__(self, extra: float = 0.0, of: str | None = None, win: float = 8.0):
        self.extra = extra
        self.of = of          # fit the hard points of another segment (a shell sized over its dark core)
        self.win = win        # include boxes within margin + win of the station height (conservative between stations)


def S(z, w, d, n=3.0, cx=0.0, cy=None):
    return {"z": z, "w": w, "d": d, "n": n, "cx": cx, "cy": cy}


def F(x, w, d, n=3.0, cy=None, cz=0.0):
    return {"x": x, "w": w, "d": d, "n": n, "cy": cy, "cz": cz}


# ------------------------------------------------------------------------------------------------------------ fitting
def _pts(b):
    xs = (b["x"][0], (b["x"][0] + b["x"][1]) / 2, b["x"][1])
    ys = (b["y"][0], (b["y"][0] + b["y"][1]) / 2, b["y"][1])
    return np.array([(x, y) for x in xs for y in ys])


def _fit_dim(boxes, z, cx, cy, n, w=None, d=None, win=8.0):
    """Smallest w (if w is fit) or d (if d is fit) so every box spanning z has sd <= -(margin + 0.25 mm)."""
    act = [b for b in boxes if b["z"][0] - b["m"] - win <= z <= b["z"][1] + b["m"] + win]
    if not act:
        return None
    lo, hi = 1.0, 400.0
    for _ in range(40):
        mid = (lo + hi) / 2
        ww, dd = (mid, d) if w is None else (w, mid)
        ok = True
        for b in act:
            p = _pts(b)
            sd = superellipse_sd(p[:, 1] - cy, p[:, 0] - cx, ww / 2, dd / 2, n)
            if np.max(sd) > -(b["m"] + 0.25):
                ok = False
                break
        lo, hi = (lo, mid) if ok else (mid, hi)
    return hi


def resolve(seg: dict, boxes: list[dict], cant: float) -> list[dict]:
    axis = seg.get("axis", "z")
    out = []
    sb = [b for b in boxes if b["segment"] == seg["id"] + ("_l" if seg.get("mirror") else "")]
    for st in seg["stations"]:
        st = dict(st)
        if axis == "z" and st.get("cy") is None:
            st["cy"] = HPM.arm_centre_y(st["z"], cant) if seg.get("arm") else seg.get("cy", 0.0)
        if axis == "x" and st.get("cy") is None:
            st["cy"] = seg.get("cy", 0.0)
        for key in ("w", "d"):
            v = st[key]
            if isinstance(v, fit):
                other = st["d"] if key == "w" else st["w"]
                if isinstance(other, fit):
                    raise ValueError(f"{seg['id']} z={st.get('z')}: fit both w and d")
                bb = sb if v.of is None else [b for b in boxes if b["segment"] == v.of + ("_l" if seg.get("mirror") else "")]
                sc = getattr(v, "scale", 1.0)           # an end-roll station: fit at the station it copies, then scale
                zf = getattr(v, "at_z", st["z"])
                cyf = HPM.arm_centre_y(zf, cant) if (seg.get("arm") and axis == "z") else st["cy"]
                other = other / sc
                r = _fit_dim(bb, zf, st["cx"], cyf, st["n"], win=v.win, **({"d": other} if key == "w" else {"w": other}))
                if r is None:
                    raise ValueError(f"{seg['id']} z={st.get('z')}: fit() but no hard point spans this height")
                st[key] = (r + v.extra) * getattr(v, "scale", 1.0)
        out.append(st)
    return out


def to_profile(dirn: dict) -> dict:
    cant = dirn["cant_deg"]
    hps = HPM.hard_points(cant, dirn["seg_map"])
    boxes = HPM.boxes_mm(hps)
    segs = []
    for seg in dirn["segments"]:
        sts = resolve(seg, boxes, cant)
        axis = seg.get("axis", "z")
        o = {"id": seg["id"], "role": seg["role"]}
        if axis != "z":
            o["axis"] = axis
        if seg.get("mirror"):
            o["mirror"] = True
        if seg.get("k") is not None:
            o["k_m"] = round(seg["k"] / 1000, 5)
        o["stations"] = []
        for st in sts:
            q = {axis: round(st[axis] / 1000, 5), "w": round(st["w"] / 1000, 5), "d": round(st["d"] / 1000, 5), "n": round(st["n"], 3)}
            for k in ("cx", "cy", "cz"):
                if st.get(k):
                    q[k] = round(st[k] / 1000, 5)
            o["stations"].append(q)
        segs.append(o)
    joints = [{"id": "hip_l", "pos": [0.0, 0.035, 0.275]}, {"id": "knee_l", "pos": [0.0, 0.035, 0.1485]},
              {"id": "ankle_l", "pos": [0.0, 0.035, 0.066]}, {"id": "shoulder_l", "pos": [0.0, 0.06515, 0.4393]},
              {"id": "elbow_l", "pos": [0.0, round(HPM.arm_centre_y(334.8, cant) / 1000, 5), 0.3348]}]
    prof = {"schema": "design-profiles/0.1", "name": dirn["name"], "kind": "design", "confidence": "approximate",
            "height_m": H / 1000, "head_unit_m": dirn["head_unit"] / 1000,
            "sources": ["variants/adam/design/silhouette/build.py (T-20261019-d955): R2a silhouette direction "
                        f"'{dirn['title']}' around the R1 0.55 m hard points (variants/adam/design/silhouette/hardpoints.py)"],
            "blend": {"k_m": dirn.get("k_default", 4.0) / 1000, "voxel_m": 0.0015},
            "notes": dirn["notes"] + f" Arm display cant {cant:.1f} deg (R1 minimum {HPM.R1_CANT_DEG} deg).",
            "segments": segs, "joints": joints, "hard_points": hps}
    errs = validate(prof)
    if errs:
        raise ValueError("; ".join(errs))
    return prof


def check(prof: dict) -> list[dict]:
    return [r for r in hard_point_margins(expand(prof)) if not r["pass"]]


