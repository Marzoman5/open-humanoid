"""Runtime configuration from YAML (software/configs/adam.yaml): which concept/spec to run, gait and safety overrides, sim noise, front ends.

Every key is optional and maps onto a dataclass field (GaitConfig, StabiliserConfig, SafetyConfig, SimConfig). Unknown keys raise, so a typo
cannot silently leave a safety threshold at its default.
"""
from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path

import yaml

from .control import StabiliserConfig
from .hal.sim import SimConfig
from .locomotion import GaitConfig
from .model import DEFAULT_CONCEPT
from .runtime import RuntimeConfig
from .safety import SafetyConfig


def _apply(obj, over: dict | None, what: str):
    if not over:
        return obj
    names = {f.name for f in fields(obj)}
    bad = set(over) - names
    if bad:
        raise KeyError(f"unknown {what} keys {sorted(bad)}; valid: {sorted(names)}")
    return replace(obj, **{k: (tuple(v) if isinstance(v, list) else v) for k, v in over.items()})


def load_config(path: str | Path) -> dict:
    """-> {"concept": str, "runtime": RuntimeConfig, "sim": SimConfig, "frontends": dict}"""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    known = {"concept", "gait", "stabiliser", "safety", "sim", "frontends", "control_hz", "clip_dir"}
    bad = set(raw) - known
    if bad:
        raise KeyError(f"unknown top-level keys {sorted(bad)}; valid: {sorted(known)}")
    rt = RuntimeConfig(gait=_apply(GaitConfig(), raw.get("gait"), "gait"), stab=_apply(StabiliserConfig(), raw.get("stabiliser"), "stabiliser"),
                       safety=_apply(SafetyConfig(), raw.get("safety"), "safety"), clip_dir=raw.get("clip_dir"))
    sim = _apply(SimConfig(), raw.get("sim"), "sim")
    if "control_hz" in raw:
        sim = replace(sim, control_hz=float(raw["control_hz"]))
    return {"concept": raw.get("concept", DEFAULT_CONCEPT), "runtime": rt, "sim": sim, "frontends": raw.get("frontends", {})}
