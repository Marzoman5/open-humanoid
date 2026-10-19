"""profiles.yaml: load, validate and expand (mirror) the per-segment section stations that define the outer shape.

Frame: metres, z up, x forward, y left, origin on the ground under the body centre.
A station is a superellipse section |u/(w/2)|^n + |v/(d/2)|^n = 1 at one position along the segment axis.
Schema: schemas/design-profiles.schema.json
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml

from ..paths import schemas_dir

SCHEMA_ID = "design-profiles/0.1"


class ProfilesError(ValueError):
    pass


def _schema() -> dict:
    return json.loads((schemas_dir() / "design-profiles.schema.json").read_text(encoding="utf-8"))


def validate(data: dict) -> list[str]:
    """Return a list of human-readable problems (empty = valid)."""
    import jsonschema

    errs = [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in jsonschema.Draft202012Validator(_schema()).iter_errors(data)]
    if errs:
        return errs
    ids: set[str] = set()
    for seg in data["segments"]:
        axis = seg.get("axis", "z")
        if seg["id"] in ids:
            errs.append(f"duplicate segment id {seg['id']}")
        ids.add(seg["id"])
        vals = []
        for i, st in enumerate(seg["stations"]):
            if axis not in st:
                errs.append(f"segment {seg['id']} station {i}: axis {axis} needs '{axis}'")
            else:
                vals.append(st[axis])
        if vals != sorted(vals) or len(set(vals)) != len(vals):
            errs.append(f"segment {seg['id']}: stations must be strictly increasing in {axis}")
    return errs


def expand(data: dict) -> dict:
    """Return a copy with mirrored segments expanded to <id>_l / <id>_r and station defaults filled in."""
    out = copy.deepcopy(data)
    segs = []
    for seg in out["segments"]:
        axis = seg.get("axis", "z")
        base = {"role": seg.get("role", seg["id"]), "axis": axis, "k_m": seg.get("k_m")}
        for st in seg["stations"]:
            st.setdefault("n", 2.0)
            for k in ("cx", "cy", "cz"):
                st.setdefault(k, 0.0)
        if seg.get("mirror"):
            left = {**base, "id": seg["id"] + "_l", "stations": copy.deepcopy(seg["stations"])}
            right = {**base, "id": seg["id"] + "_r", "stations": copy.deepcopy(seg["stations"])}
            for st in right["stations"]:
                st["cy"] = -st["cy"]
            segs += [left, right]
        else:
            segs.append({**base, "id": seg["id"], "stations": seg["stations"]})
    out["segments"] = segs
    have = {j["id"] for j in out.get("joints", [])}
    for jt in list(out.get("joints", [])):
        if jt["id"].endswith("_l") and jt["id"][:-2] + "_r" not in have:
            x, y, z = jt["pos"]
            out["joints"].append({"id": jt["id"][:-2] + "_r", "pos": [x, -y, z]})
    hps = []
    for hp in out.get("hard_points", []):
        hps.append(hp)
        if hp["id"].endswith("_l"):
            c, seg = hp["center"], hp.get("segment")
            hps.append({**hp, "id": hp["id"][:-2] + "_r", "center": [c[0], -c[1], c[2]],
                        "segment": seg[:-2] + "_r" if seg and seg.endswith("_l") else seg})
    out["hard_points"] = hps
    return out


def load_profiles(path: str | Path) -> dict:
    """Load + validate + expand a profiles file. Raises ProfilesError listing every problem."""
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errs = validate(data)
    if errs:
        raise ProfilesError(f"{path}: " + "; ".join(errs))
    prof = expand(data)
    prof["_path"] = str(path)
    if "head_unit_m" not in prof:
        head = [s for s in prof["segments"] if s["role"] == "head"]
        if head:
            zs = [st[head[0]["axis"]] for st in head[0]["stations"]]
            prof["head_unit_m"] = max(zs) - min(zs)
    return prof


def default_path(variant_dir: str | Path) -> Path:
    return Path(variant_dir) / "design" / "profiles.yaml"
