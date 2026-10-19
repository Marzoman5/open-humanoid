"""CLI for the design tooling. Standalone so it can be wired into `oh` without touching cli.py in this task:

    python -m openhumanoid.design <command> ...        (works today)
    oh design <command> ...                            (after the commander wires `register` into openhumanoid/cli.py)

Commands: render, massing, metrics, calibrate, verdict.  See docs/design-method.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..paths import repo_root, variants_dir


def _variant_dir(v: str) -> Path:
    p = variants_dir() / v
    if not p.exists():
        raise SystemExit(f"unknown variant '{v}' (looked in {p})")
    return p


def resolve_source(target: str, source: str | None = None) -> tuple[str, Path, Path]:
    """target = variant id | path to profiles.yaml | mesh file | mesh dir | robot.xml. Returns (name, source path, out base dir)."""
    p = Path(target)
    if p.exists():
        base = p if p.is_dir() else p.parent
        return p.stem, p, base / "generated" if (base / "generated").exists() else base
    vdir = _variant_dir(target)
    if source:
        sp = Path(source)
        if not sp.is_absolute():
            sp = vdir / source
    else:
        prof = vdir / "design" / "profiles.yaml"
        sp = prof if prof.exists() else vdir / "cad" / "export" / "robot.xml"
    if not sp.exists():
        raise SystemExit(f"no design source for '{target}': expected {vdir / 'design' / 'profiles.yaml'} or {vdir / 'cad/export/robot.xml'}")
    return target, sp, vdir / "generated"


def cmd_render(a) -> int:
    from .meshio import load_subject
    from .studio import render_studio

    name, src, gen = resolve_source(a.target, a.source)
    subj = load_subject(src, name, a.voxel)
    out = Path(a.out) if a.out else gen / "renders" / "studio"
    r = render_studio(subj, out, refs=a.ref, zebra=a.zebra, clay=not a.no_clay, color_by_class=a.color_by_class)
    print(f"{name}: studio rig -> {out}  (review sheet: {r['sheet']})")
    return 0


def cmd_massing(a) -> int:
    from .massing import build_massing
    from .profiles import load_profiles

    prof = load_profiles(a.profiles)
    mesh, _ = build_massing(prof, a.voxel)
    out = Path(a.out or Path(a.profiles).with_suffix(".massing.stl"))
    mesh.export(out)
    print(f"massing: {len(mesh.faces)} faces, watertight={mesh.is_watertight}, volume={mesh.volume * 1e6:.1f} cm3 -> {out}")
    return 0


def cmd_metrics(a) -> int:
    from . import metrics, studio
    from .meshio import load_subject

    name, src, gen = resolve_source(a.target, a.source)
    subj = load_subject(src, name)
    refs = dict(studio.reference_mask(r, "front") for r in (a.ref or []))
    approved = load_subject(a.approved, "approved") if a.approved else None
    out = Path(a.out) if a.out else gen / "design_metrics.json"
    rep = metrics.write_report(subj, out, ref_masks=refs or None, approved=approved)
    ev = rep["evaluation"]
    print(f"{name}: {ev['n_pass']}/{ev['n_scored']} numeric criteria pass -> {out}")
    for i, c in ev["criteria"].items():
        if c["verdict"] == "FAIL":
            print(f"  FAIL {i:4s} {c['name']}: {c['value']}  (band {c['band']})")
    return 0 if not a.strict or not ev["failed"] else 1


def cmd_calibrate(a) -> int:
    from . import calibrate

    root = repo_root()
    rep = calibrate.run(root, Path(a.out) if a.out else root / "docs" / "design-method" / "calibration.json")
    print(calibrate.table(rep))
    g = rep["gap"]
    print(f"\nlowest reference pass fraction {g['lowest_reference_pass_fraction']}, highest counter-example {g['highest_counter_example_pass_fraction']}"
          f" -> separates: {g['separates']}")
    return 0 if g["separates"] else 1


def cmd_verdict(a) -> int:
    from . import critic

    rep = critic.combine([json.loads(Path(p).read_text(encoding="utf-8")) if p.endswith(".json") else critic.extract_json(Path(p).read_text(encoding="utf-8")) for p in a.reports],
                         step=a.step, state_path=Path(a.state) if a.state else None,
                         metrics_path=Path(a.metrics) if a.metrics else None)
    print(json.dumps(rep, indent=2))
    return 0 if rep["pass"] else 1


def register(sub) -> None:
    """Attach `design` (and nothing else) to an argparse subparsers object from openhumanoid/cli.py."""
    d = sub.add_parser("design", help="agent design tooling (ADR 0010): render | massing | metrics | calibrate | verdict")
    build_parser(d.add_subparsers(dest="design_cmd", required=True))
    d.set_defaults(f=lambda a: a.design_f(a))


def build_parser(sp) -> None:
    s = sp.add_parser("render", help="studio render set + review sheet (clay/SSAO, silhouettes, head-unit grid, ref overlays)")
    s.add_argument("target", help="variant id, or a profiles.yaml / mesh / dir / robot.xml path")
    s.add_argument("--source", help="path relative to the variant dir (default design/profiles.yaml, else cad/export/robot.xml)")
    s.add_argument("--ref", action="append", help="reference outline slot: name=path (profiles.yaml, mesh, or silhouette png); repeatable")
    s.add_argument("--zebra", action="store_true"); s.add_argument("--no-clay", action="store_true")
    s.add_argument("--color-by-class", action="store_true", help="tint servo/frame parts dark in the clay views")
    s.add_argument("--voxel", type=float); s.add_argument("--out"); s.set_defaults(design_f=cmd_render)
    s = sp.add_parser("massing", help="profiles.yaml -> smooth massing STL")
    s.add_argument("profiles"); s.add_argument("--voxel", type=float); s.add_argument("--out"); s.set_defaults(design_f=cmd_massing)
    s = sp.add_parser("metrics", help="code-measured rubric numbers -> generated/design_metrics.json")
    s.add_argument("target"); s.add_argument("--source"); s.add_argument("--ref", action="append")
    s.add_argument("--approved", help="approved D1 profiles/mesh for the S1 IoU"); s.add_argument("--out")
    s.add_argument("--strict", action="store_true", help="exit 1 if any numeric criterion fails")
    s.set_defaults(design_f=cmd_metrics)
    s = sp.add_parser("calibrate", help="run metrics over the reference set; check sleek vs toy separation")
    s.add_argument("--out"); s.set_defaults(design_f=cmd_calibrate)
    s = sp.add_parser("verdict", help="combine design-critic reports (both presentation orders) into a pass/no-pass; tracks the 3-round cap")
    s.add_argument("reports", nargs="+"); s.add_argument("--step", default="D1"); s.add_argument("--state"); s.add_argument("--metrics", help="design_metrics.json: hard-gate failures override the critic")
    s.set_defaults(design_f=cmd_verdict)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    ap = argparse.ArgumentParser(prog="python -m openhumanoid.design", description="Open Humanoid design tooling (ADR 0010)")
    build_parser(ap.add_subparsers(dest="design_cmd", required=True))
    a = ap.parse_args(argv)
    return a.design_f(a)


if __name__ == "__main__":
    raise SystemExit(main())
