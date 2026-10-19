"""M3: Blender `bpy` subdivision surface. Low-poly cage driven by the profile stations -> Catmull-Clark -> Solidify -> Boolean
keep-outs. Mesh only. Blender runs as a module in its own virtualenv (bpy 5.0.1 pins numpy 1.26, the main venv has numpy 2),
as a subprocess on a JSON spec: `m3_bpy_worker.py`. Set OH_BPY_PYTHON to that venv's python (default: <repo>/.venv-bpy).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .meshutil import ShellSet, Timer, decimate, name_panels
from .spec import LegSpec

WORKER = Path(__file__).with_name("m3_bpy_worker.py")


def bpy_python() -> Path | None:
    env = os.environ.get("OH_BPY_PYTHON")
    cands = [Path(env)] if env else []
    root = Path(__file__).resolve().parents[3]
    cands += [root / ".venv-bpy" / "Scripts" / "python.exe", root / ".venv-bpy" / "bin" / "python"]
    return next((c for c in cands if c.exists()), None)


def available() -> bool:
    py = bpy_python()
    if not py:
        return False
    return subprocess.run([str(py), "-c", "import bpy"], capture_output=True).returncode == 0


def _run(spec_json: Path, out: Path, comp: Path | None, outer_only: bool = False):
    py = bpy_python()
    cmd = [str(py), str(WORKER), str(spec_json), str(out)] + ([str(comp)] if comp else []) + (["--outer-only"] if outer_only else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f"bpy worker failed ({r.returncode}):\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")


def _measure(mesh, z, centre_x):
    sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec is None:
        return None
    v = np.vstack([e for e in sec.discrete])
    return v[:, 1].max() - v[:, 1].min(), v[:, 0].max() - v[:, 0].min()


def calibrate(spec: LegSpec, spec_json: Path, work: Path, passes: int = 2) -> dict:
    """Subdivision shrinks the cage, so scale each interior station's width/depth by target / measured (a few passes)."""
    import trimesh

    comp = {s: [(1.0, 1.0)] * len(st) for s, st in (("thigh", spec.thigh_stations()), ("shank", spec.shank_stations()))}
    hist = []
    for _ in range(passes):
        cj = work / "comp.json"
        cj.write_text(json.dumps(comp))
        _run(spec_json, work, cj, outer_only=True)
        worst = 0.0
        for seg, st in (("thigh", spec.thigh_stations()), ("shank", spec.shank_stations())):
            m = trimesh.load(work / f"{seg}_outer.stl")
            for i, (z, w, d, n, cx) in enumerate(st):
                if i in (0, len(st) - 1):
                    continue
                got = _measure(m, z, cx)
                if got is None:
                    continue
                cw, cd = comp[seg][i]
                worst = max(worst, abs(got[0] - w), abs(got[1] - d))
                comp[seg][i] = (cw * w / got[0], cd * d / got[1])
        hist.append(round(float(worst), 3))
    return {"comp": comp, "max_error_mm_per_pass": hist}


def build(spec: LegSpec | None = None, calibrate_passes: int = 2) -> ShellSet:
    import trimesh

    spec = spec or LegSpec()
    if not available():
        raise RuntimeError("bpy is not importable from the M3 virtualenv (see OH_BPY_PYTHON / .venv-bpy)")
    with Timer() as T, tempfile.TemporaryDirectory() as td:
        work = Path(td)
        sj = work / "spec.json"
        spec.to_json(sj)
        cal = calibrate(spec, sj, work, calibrate_passes) if calibrate_passes else {"comp": None, "max_error_mm_per_pass": []}
        cj = None
        if cal["comp"]:
            cj = work / "comp.json"
            cj.write_text(json.dumps(cal["comp"]))
        _run(sj, work, cj)
        items = {}
        for seg in ("thigh", "shank"):
            m = trimesh.load(work / f"{seg}.stl")
            m.merge_vertices()
            comps = [c for c in m.split(only_watertight=False) if len(c.faces) > 200]
            items[seg] = [(float(c.centroid[0]), decimate(c, 0.03)) for c in comps]
        parts = name_panels(items, spec)
    ss = ShellSet("M3_bpy", spec, parts, None, T.seconds)
    ss.notes["calibration_max_error_mm_per_pass"] = cal["max_error_mm_per_pass"]
    return ss
