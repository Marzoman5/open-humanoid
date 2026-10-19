"""Spec-driven CAD (build123d). `oh cad build|check <variant>`.

- geom.py:   generic helpers (servo envelopes, lofted superellipse shells, mass properties, checks)
- biped.py:  the `biped_v1` template (frame + shell link tree from spec + sizing + catalog + style.yaml)
- export.py: link tree -> cad/EXPORT_CONTRACT.md files (STEP/STL, meshes, mass properties, MJCF, manifest)

Variants whose CAD lives in another tool (Onshape, SolidWorks...) skip `build` and just commit their
export; `check` still works on any link tree a template produces.
"""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATES = {"biped_v1": "biped"}


def _template(spec: dict):
    import importlib

    name = spec["kinematics"].get("template", "biped_v1")
    if name not in TEMPLATES:
        raise ValueError(f"No CAD template for kinematics.template '{name}'. Available: {sorted(TEMPLATES)}")
    return importlib.import_module(f".{TEMPLATES[name]}", __name__)


def build_links(spec: dict):
    from ..simgen import load_sizing

    sizing = load_sizing(spec)
    if not sizing.get("actuators"):
        raise ValueError("Sizing is infeasible (no actuator selection). Fix the spec before CAD.")
    t = _template(spec)
    style = t.load_style(spec)
    links, notes = t.build(spec, sizing, style)
    return sizing, style, links, notes


def build_variant(spec: dict) -> dict:
    """Generate the variant's CAD from its spec and write the export contract to <variant>/cad/export/."""
    from . import export

    backend = spec.get("cad", {}).get("backend", "build123d")
    if backend != "build123d":
        raise ValueError(f"cad.backend is '{backend}': export from that tool per cad/EXPORT_CONTRACT.md instead of `oh cad build`.")
    sizing, style, links, notes = build_links(spec)
    out = Path(spec["_dir"]) / "cad" / "export"
    r = export.export(spec, sizing, links, style, out, notes)
    r["notes"] = notes
    return r


def check_variant(spec: dict, min_mm3: float = 20.0) -> dict:
    """Interference at the stand pose + printer-bed fit. Writes generated/cad_check.json."""
    from .. import simgen
    from ..spec import expand_joints, generated_dir
    from . import export

    sizing, style, links, notes = build_links(spec)
    q = simgen.stand_pose(spec, expand_joints(spec, sizing["joints_base"]))
    bed = spec.get("manufacturing", {}).get("printer_bed_mm")
    r = export.check(links, q, min_mm3=min_mm3, bed_mm=bed)
    r["notes"] = notes
    r["pose"] = "stand"
    p = generated_dir(spec) / "cad_check.json"
    p.write_text(json.dumps({"generated_by": "oh cad check", **r}, indent=2), encoding="utf-8")
    r["file"] = str(p)
    return r
