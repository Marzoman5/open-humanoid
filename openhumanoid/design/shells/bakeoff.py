"""Run the shell-method bake-off: build each method on the same LegSpec, evaluate, render, test +-10 % regeneration and
determinism, and write everything under docs/design-method/bakeoff/ (per-stage JSON, so an interrupted run resumes).

    python -m openhumanoid.design.shells.bakeoff [--out DIR] [--methods M1 M2 M3] [--force] [--skip-variants]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np

from . import evaluate as ev
from .meshutil import ShellSet
from .spec import LegSpec

HERE = Path(__file__).parent


def builders():
    from . import m1_build123d, m2_sdf, m3_bpy

    return {"M1": lambda spec, out: m1_build123d.build(spec, step_path=str(out / "shells.step") if out else None),
            "M2": lambda spec, out: m2_sdf.build(spec),
            "M3": lambda spec, out: m3_bpy.build(spec)}


FILES = {"M1": ["m1_build123d.py"], "M2": ["m2_sdf.py"], "M3": ["m3_bpy.py", "m3_bpy_worker.py"]}
SHARED = ["spec.py", "meshutil.py"]
VARIANTS = [LegSpec(length_scale=0.9), LegSpec(length_scale=1.1), LegSpec(width_scale=0.9), LegSpec(width_scale=1.1)]


def loc(files) -> int:
    n = 0
    for f in files:
        for line in (HERE / f).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                n += 1
    return n


def digest(ss: ShellSet) -> str:
    h = hashlib.sha256()
    for k in sorted(ss.parts):
        m = ss.parts[k]
        h.update(k.encode())
        h.update(np.round(np.asarray(m.vertices), 2).tobytes())
        h.update(str(len(m.faces)).encode())
    return h.hexdigest()[:16]


def _json(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=_json), encoding="utf-8")


def quick_eval(parts: dict, spec: LegSpec) -> dict:
    """Regeneration check: fit + ROM + printability basics + silhouette fidelity (no wall rays, coarse ROM)."""
    look = ev.look_metrics(parts, spec)
    fit = ev.fit_keepouts(parts, spec)
    rom = ev.rom_sweep(parts, spec, 10.0)
    pr = ev.printability(parts, spec, with_wall=False)
    return {"iou_front": look["T1_iou_front"], "iou_side": look["T1_iou_side"], "keepouts_ok": fit["all_ok"],
            "keepouts_failed": [k for k, v in fit.items() if isinstance(v, dict) and not v["ok"]],
            "rom_collision_free": rom["collision_free"], "rom_min_gap_mm": rom["min_gap_mm"],
            "watertight": pr["all_watertight"], "fits_bed": pr["all_fit_bed"], "parts": pr["part_count"]}


def run_method(name: str, out: Path, force: bool, variants: bool) -> dict:
    res_path = out / "results" / f"{name}.json"
    if res_path.exists() and not force:
        return json.loads(res_path.read_text(encoding="utf-8"))
    build = builders()[name]
    spec = LegSpec()
    parts_dir = out / "parts" / name
    parts_dir.mkdir(parents=True, exist_ok=True)
    res: dict = {"method": name, "loc": {"method_files": loc(FILES[name]), "shared_spec_meshutil": loc(SHARED)}}
    ss = build(spec, parts_dir)
    ss.save(parts_dir)
    res["build_seconds"] = round(ss.seconds, 2)
    res["notes"] = ss.notes
    res["step_exported"] = bool(ss.step_path and Path(ss.step_path).exists())
    save_json(res_path, res)
    res["eval"] = ev.evaluate(ss.parts, spec, with_wall=True, rom_step=5.0)
    save_json(res_path, res)
    ss2 = build(spec, None)
    res["determinism"] = {"hash_run1": digest(ss), "hash_run2": digest(ss2), "identical": digest(ss) == digest(ss2),
                          "seconds_run2": round(ss2.seconds, 2)}
    save_json(res_path, res)
    if variants:
        res["variants"] = {}
        for v in VARIANTS:
            t0 = time.perf_counter()
            try:
                sv = build(v, None)
                q = quick_eval(sv.parts, v)
                q["build_seconds"] = round(sv.seconds, 2)
                q["status"] = "built"
            except Exception as e:  # a failed regeneration is a result, not a crash
                q = {"status": "FAILED", "error": f"{type(e).__name__}: {str(e)[:300]}", "build_seconds": round(time.perf_counter() - t0, 2)}
                traceback.print_exc()
            res["variants"][v.label()] = q
            save_json(res_path, res)
    return res


def criteria(res: dict) -> dict:
    """Rubric-style numeric criteria (same JSON shape as `oh design metrics`: evaluation.criteria) for the critic."""
    L, F, P = res["eval"]["look"], res["eval"]["fit"], res["eval"]["print"]
    rows = [
        ("T1a", "Front silhouette IoU vs target", L["T1_iou_front"], [0.95, None]),
        ("T1b", "Side silhouette IoU vs target", L["T1_iou_side"], [0.95, None]),
        ("P8a", "Thigh taper: distal / proximal section area", L["P8a_thigh_taper_area"], [None, 0.65]),
        ("P8b", "Shank taper: ankle / calf section area", L["P8b_shank_taper_area"], [None, 0.60]),
        ("P9a", "Thigh widest point, fraction from the top", L["P9a_thigh_widest_from_top"], [None, 0.33]),
        ("P9b", "Calf widest point, fraction from the top", L["P9b_calf_widest_from_top"], [None, 0.33]),
        ("S3a", "Silhouette ledges (front + side)", L["S3_ledges_front"] + L["S3_ledges_side"], [None, 6]),
        ("S4a", "Share of surface in flat patches", L["S4_flat_area_fraction"], [None, 0.30]),
        ("HP", "Every keep-out enclosed with >= 1.5 mm", int(F["keepouts"]["all_ok"]), [1, 1]),
        ("ROM", "No shell-shell collision over 0-130 deg", int(F["rom"]["collision_free"]), [1, 1]),
        ("M1", "All panels watertight + manifold", int(P["all_watertight"]), [1, 1]),
        ("W1", "Interior wall >= 1.6 mm (sampled)", int(P["wall_ok"]), [1, 1]),
    ]
    crit = {}
    for i, name, v, (lo, hi) in rows:
        ok = (v is not None) and (lo is None or v >= lo) and (hi is None or v <= hi)
        crit[i] = {"name": name, "value": v, "band": [lo, hi], "verdict": "PASS" if ok else "FAIL"}
    failed = [i for i, c in crit.items() if c["verdict"] == "FAIL"]
    return {"evaluation": {"criteria": crit, "failed": failed, "n_pass": len(crit) - len(failed), "n_scored": len(crit)}}


def render_method(name: str, out: Path, force: bool) -> None:
    from . import render
    import trimesh

    d = out / "renders" / name
    if (d / "sheet.png").exists() and not force:
        return
    parts = {p.stem: trimesh.load(p) for p in sorted((out / "parts" / name).glob("*.stl"))}
    render.render_set(parts, LegSpec(), d, name="design")        # neutral label: the critic must not see the method


def blind_copies(out: Path, methods: list[str], seed: int = 20261019) -> dict:
    order = list(methods)
    random.Random(seed).shuffle(order)
    mapping = {f"design-{i + 1}": m for i, m in enumerate(order)}
    cd = out / "critic"
    cd.mkdir(parents=True, exist_ok=True)
    for label, m in mapping.items():
        res = json.loads((out / "results" / f"{m}.json").read_text(encoding="utf-8"))
        shutil.copy(out / "renders" / m / "sheet.png", cd / f"{label}_sheet.png")
        save_json(cd / f"{label}_metrics.json", criteria(res))
    save_json(cd / "blind_map.json", mapping)
    return mapping


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[3] / "docs" / "design-method" / "bakeoff"))
    ap.add_argument("--methods", nargs="*", default=["M1", "M2", "M3"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-variants", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out)
    for m in a.methods:
        t0 = time.time()
        run_method(m, out, a.force, not a.skip_variants)
        if not a.no_render:
            render_method(m, out, a.force)
        print(f"{m}: done in {time.time() - t0:.0f}s", flush=True)
    if not a.no_render and all((out / "results" / f"{m}.json").exists() for m in a.methods):
        print("blind map:", blind_copies(out, a.methods))
    return 0


if __name__ == "__main__":
    sys.exit(main())
