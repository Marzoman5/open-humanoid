"""Load, resolve (extends + defaults), validate and expand variant specs."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

from .paths import schemas_dir, variants_dir

# Defaults applied under every spec. Variant values win. Keep these scale-neutral:
# proportions are fractions of height, everything else is a ratio or a model constant.
DEFAULTS: dict[str, Any] = {
    "status": "concept",
    "body": {
        "architecture": {"style": "modular", "shell": True},
        "proportions": {
            "ankle_height": 0.045, "shank": 0.225, "thigh": 0.225, "pelvis": 0.06, "torso": 0.25,
            "neck": 0.035, "head": 0.14, "hip_width": 0.15, "shoulder_width": 0.30,
            "upper_arm": 0.17, "forearm": 0.17, "foot_length": 0.17, "foot_width": 0.075,
        },
    },
    "kinematics": {"template": "biped_v1", "mirror": True},
    "locomotion": {"walk": {"required": True, "step_freq_hz": 1.5, "knee_amplitude_rad": 0.6, "stance_knee_flex_deg": 30}},
    "actuation": {"selection": "auto", "uniform": False, "require_feedback": "position", "overrides": {}},
    "bom": {"fixed": [], "material": "pla-plus-1kg"},
    "mass_model": {"structure_kg_at_1m": 6.4, "electronics_kg": 0.12, "waste_factor": 1.3},
    "analysis": {
        "safety_factor": 1.25, "dynamic_factor": {"walk": 1.6, "run": 2.8},
        "arm_dynamic_factor": 1.5, "speed_margin": 1.1,
        "continuous_fraction_default": 0.40, "peak_fraction": 0.85,
    },
    "cad": {"backend": "build123d"},
    "sim": {"engine": "mujoco", "timestep_s": 0.002},
    "software": {"hal": "sim", "plugins": []},
}

LIMB_SIDES = {"leg": ("l", "r"), "arm": ("l", "r"), "hand": ("l", "r")}


def deep_merge(base: dict, over: dict) -> dict:
    """Recursively merge `over` onto `base`. Dicts merge; everything else (incl. lists) is replaced."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def spec_path(ref: str | Path) -> Path:
    p = Path(ref)
    if p.suffix in (".yaml", ".yml") and p.exists():
        return p.resolve()
    if p.is_dir() and (p / "spec.yaml").exists():
        return (p / "spec.yaml").resolve()
    cand = variants_dir() / str(ref) / "spec.yaml"
    if cand.exists():
        return cand
    raise FileNotFoundError(f"No variant '{ref}' (looked for {cand})")


def load_raw(ref: str | Path, _seen: tuple = ()) -> dict:
    path = spec_path(ref)
    if path in _seen:
        raise ValueError(f"extends cycle: {' -> '.join(map(str, _seen + (path,)))}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    parent = data.get("extends")
    if parent:
        base = load_raw(parent if not str(parent).startswith(".") else (path.parent / parent), _seen + (path,))
        base.pop("extends", None)
        data = deep_merge(base, data)
    return data


def load_spec(ref: str | Path, validate_spec: bool = True) -> dict:
    raw = load_raw(ref)
    if validate_spec:
        errs = validate(raw)
        if errs:
            raise ValueError("Spec invalid:\n  " + "\n  ".join(errs))
    spec = deep_merge(DEFAULTS, raw)
    spec["_dir"] = str(spec_path(ref).parent)
    return spec


def validate(raw: dict) -> list[str]:
    import jsonschema

    schema = json.loads((schemas_dir() / "spec.schema.json").read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema)
    errs = [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in v.iter_errors(raw)]
    names = [j.get("name") for j in raw.get("kinematics", {}).get("joints", [])]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        errs.append(f"kinematics/joints: duplicate names {sorted(dupes)}")
    for j in raw.get("kinematics", {}).get("joints", []):
        r = j.get("range", [0, 0])
        if len(r) == 2 and r[0] >= r[1]:
            errs.append(f"kinematics/joints/{j.get('name')}: range min must be < max")
    return errs


def variant_dir(spec: dict) -> Path:
    return Path(spec["_dir"])


def generated_dir(spec: dict) -> Path:
    d = variant_dir(spec) / "generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def expand_joints(spec: dict, names: list[str] | None = None) -> list[dict]:
    """Expand spec joints into concrete per-side joints (hip_pitch -> hip_pitch_l, hip_pitch_r).

    `names` restricts to a subset of *base* joint names (used by sizing to drop optional joints).
    Right-side ranges of roll/yaw (x/z) joints are mirrored so positive always means 'outward' on the left.
    """
    out = []
    mirror = spec["kinematics"].get("mirror", True)
    for j in spec["kinematics"]["joints"]:
        if names is not None and j["name"] not in names:
            continue
        sides = LIMB_SIDES.get(j["limb"]) if mirror else None
        if not sides:
            out.append({**j, "base": j["name"], "side": None})
            continue
        for s in sides:
            lo, hi = j["range"]
            rng = [-hi, -lo] if (s == "r" and j["axis"] in ("x", "z")) else [lo, hi]
            out.append({**j, "name": f"{j['name']}_{s}", "base": j["name"], "side": s, "range": rng})
    return out


def resolve_height(spec: dict) -> dict:
    """Normalize body.height_m to {mode, target, min, max, step}."""
    h = spec["body"]["height_m"]
    if isinstance(h, (int, float)):
        return {"mode": "fixed", "target": float(h), "min": float(h), "max": float(h), "step": 0.01}
    target = h.get("target", h.get("min", 0.5))
    return {"mode": h["mode"], "target": target, "min": h.get("min", target), "max": h.get("max", target), "step": h.get("step", 0.01)}
