"""Motion clips: the concept engine's motion library (wave, dance, pickup, crouch) compiled to joint-space arrays and cached on disk.

The onboard computer (R8) loads cached clips; it does not need casadi or the planners. `ClipStore.get(name, **params)` returns a
`concept.kin.Reference`-like object (q, dt, base trajectory, scene) so the same player drives sim and hardware. Cache: npz files keyed by
concept id, clip name and parameters, in `cache_dir` (default: the OS temp dir; set it to a persistent folder on the robot).
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np

from ..concept.kin import Reference
from .model import RobotModel


class ClipStore:
    def __init__(self, model: RobotModel, cache_dir: str | Path | None = None):
        self.m = model
        self.dir = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "openhumanoid_clips"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict = {}

    def _key(self, name: str, params: dict) -> str:
        h = hashlib.sha1(json.dumps([self.m.concept_id, name, params, round(self.m.robot.height, 4)], sort_keys=True, default=str).encode()).hexdigest()[:12]
        return f"{name}-{h}"

    def build(self, name: str, **params) -> Reference:
        k = self.m.kin
        if name == "wave":
            from ..concept.motions.posture import wave
            return wave(k, params.get("side", "r"))
        if name == "dance":
            from ..concept.motions.dance import dance
            return dance(k, n_phrases=params.get("n_phrases", 6), bpm=params.get("bpm", 80.0))
        if name == "pickup":
            from ..concept.motions.pickup import pickup
            return pickup(k, table_height_m=params.get("table_height_m", 0.30))
        if name == "crouch":
            from ..concept.motions.posture import squat
            return squat(k, 100.0, down_s=3.0, hold_s=0.5)
        if name == "stand":
            from ..concept.motions.posture import stand
            return stand(k, params.get("duration", 4.0))
        raise KeyError(name)

    def __call__(self, name: str, **params) -> Reference:
        key = self._key(name, params)
        if key in self._mem:
            return self._mem[key]
        f = self.dir / f"{key}.npz"
        if f.exists():
            z = np.load(f, allow_pickle=True)
            ref = Reference(name, float(z["dt"]), z["q"], z["base_pos"], z["base_quat"], bool(z["feasible"]), list(z["notes"]),
                            json.loads(str(z["meta"])), scene=json.loads(str(z["scene"])) if str(z["scene"]) != "null" else None)
        else:
            ref = self.build(name, **params)
            np.savez(f, dt=ref.dt, q=ref.q, base_pos=ref.base_pos, base_quat=ref.base_quat, feasible=ref.feasible, notes=np.array(ref.notes, dtype=object),
                     meta=json.dumps(ref.meta, default=lambda o: float(o) if np.isscalar(o) else str(o)),
                     scene=json.dumps(ref.scene, default=str) if ref.scene else "null")
        self._mem[key] = ref
        return ref
