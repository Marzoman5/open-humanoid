"""`python -m openhumanoid.cad <command>`: the CAD foundation's own entry point (the commander wires `oh cad ...` and gate ids later).

  components                       list the component library
  dfm                              print the DFM rules summary
  interfaces <variant> [--layout]  generate variants/<id>/generated/interfaces.yaml (before any part geometry)
  gauge [--out DIR]                write the printable fit gauge (STEP, STL, key)
  gate    <builder.py>             geometry gate on the assembly a builder file returns
  rom     <builder.py>             range-of-motion sweep (+ coupled poses)
  access  <builder.py>             assembly access / order check
  check   <builder.py>             all three, JSON report to --out
  render  <builder.py>             clay views of the assembly

A builder file defines  build(ctx) -> openhumanoid.cad.assembly.Assembly  where ctx has .spec, .interfaces, .variant_dir.
Exit status is non-zero when a check fails, so the same command works as a gate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_builder(path: str, variant: str):
    from ..spec import load_spec
    from . import interfaces

    spec = load_spec(variant)
    ifp = Path(spec["_dir"]) / "generated" / "interfaces.yaml"
    ifs = interfaces.load(ifp) if ifp.exists() else None
    ctx = SimpleNamespace(spec=spec, interfaces=ifs, variant_dir=Path(spec["_dir"]))
    p = Path(path).resolve()
    sp = importlib.util.spec_from_file_location(p.stem, p)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[p.stem] = mod
    sp.loader.exec_module(mod)
    return mod.build(ctx), ctx


def _write(out: Path | None, name: str, data) -> None:
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / name).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def cmd_components(a) -> int:
    from .components import get, list_components

    for cid in list_components():
        c = get(cid.replace("x<len>", "x8"))
        est = c.estimates()
        print(f"{cid:34s} {c.kind:10s} bbox {tuple(round(v, 1) for v in c.bbox_mm())}  estimates: {len(est)}")
    return 0


def cmd_dfm(a) -> int:
    from . import dfm

    d = dfm.load_dfm()
    print(f"DFM rules v{d['version']} (nozzle {d['nozzle_mm']} mm, layer {d['layer_mm']} mm)")
    for k, v in d["clearance"].items():
        print(f"  clearance {k:9s} {v['per_side_mm']:.2f} mm/side{'  [tune with gauge]' if v.get('tune') else ''}")
    print(f"  hole compensation: {[(r['max_d_mm'], r['add_mm']) for r in d['hole_compensation']]}")
    print(f"  min wall: {({k: v['v'] for k, v in d['min_wall'].items() if isinstance(v, dict)})}")
    print(f"  usable bed for 220x220x250: {dfm.bed_usable([220, 220, 250])}")
    print(f"  tunable rules: {dfm.tuned_rules()}")
    return 0


def cmd_interfaces(a) -> int:
    from ..spec import load_spec
    from . import interfaces

    spec = load_spec(a.variant)
    lay = interfaces.load_layout(spec, a.layout)
    try:
        from ..simgen import load_sizing

        sizing = load_sizing(spec)
    except Exception:  # noqa: BLE001
        sizing = None
    p = interfaces.write(spec, lay, sizing)
    d = interfaces.load(p).d
    print(f"{spec['id']}: {len(d['joints'])} joints, {len(d['links'])} links -> {p}")
    for pr in d["problems"]:
        print("  PROBLEM:", pr)
    if d["estimates_to_confirm"]:
        print(f"  {len(d['estimates_to_confirm'])} servo dimensions are estimates (confirm with the fit gauge): "
              f"{', '.join(d['estimates_to_confirm'][:6])}...")
    return 1 if d["problems"] else 0


def cmd_gauge(a) -> int:
    from . import gauge

    out = Path(a.out)
    info = gauge.write(out, a.actuator, a.bearing)
    print(f"gauge -> {out}  ({info['volume_cm3']} cm3, ~{info['est_print_min']:.0f} min)")
    for t in info["tiles"]:
        print(f"  {t['id']}: {t['what']}")
    return 0


def _asm(a):
    asm, ctx = _load_builder(a.builder, a.variant)
    return asm, ctx


def cmd_gate(a) -> int:
    from . import geometry_gate as gg

    asm, ctx = _asm(a)
    rep = gg.run_gate(asm, fast=a.fast, stl_dir=Path(a.out) / "stl" if a.out else None)
    print(gg.summarize(rep))
    _write(Path(a.out) if a.out else None, "geometry_gate.json", rep)
    return 0 if rep["ok"] else 1


def cmd_rom(a) -> int:
    from . import rom

    asm, ctx = _asm(a)
    res = rom.sweep_all(asm, step_deg=a.step, gap_check=a.gap)
    poses = [rom.check_pose(asm, p, side=a.side, gap_check=a.gap) for p in (a.pose or ["squat", "step_forward", "split_stance"])]
    print(rom.summarize(res, poses))
    _write(Path(a.out) if a.out else None, "rom.json", {"sweep": res, "poses": poses})
    return 0 if res["ok"] and all(p["ok"] for p in poses) else 1


def cmd_access(a) -> int:
    from . import access

    asm, ctx = _asm(a)
    plan = access.analyse(asm)
    print(access.summarize(plan))
    _write(Path(a.out) if a.out else None, "access.json", plan)
    return 0 if plan["ok"] else 1


def cmd_check(a) -> int:
    from . import access, rom
    from . import geometry_gate as gg

    asm, ctx = _asm(a)
    out = Path(a.out) if a.out else None
    g = gg.run_gate(asm, fast=a.fast)
    print(gg.summarize(g))
    r = rom.sweep_all(asm, step_deg=a.step, gap_check=True)           # also enforces dfm moving_gap_min_mm
    poses = [rom.check_pose(asm, p, side=a.side, gap_check=True) for p in ("squat", "step_forward", "split_stance")]
    print(rom.summarize(r, poses))
    ac = access.analyse(asm)
    print(access.summarize(ac))
    _write(out, "cad_check.json", {"gate": g, "rom": {"sweep": r, "poses": poses}, "access": ac, "bom": asm.bom()})
    ok = g["ok"] and r["ok"] and all(p["ok"] for p in poses) and ac["ok"]
    print("CAD FOUNDATION CHECK:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def cmd_render(a) -> int:
    from . import render

    asm, ctx = _asm(a)
    files = render.render_views(asm, Path(a.out), pose=a.pose[0] if a.pose else None, side=a.side)
    print("\n".join(str(f) for f in files))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openhumanoid.cad", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("components").set_defaults(fn=cmd_components)
    sp.add_parser("dfm").set_defaults(fn=cmd_dfm)
    s = sp.add_parser("interfaces")
    s.add_argument("variant")
    s.add_argument("--layout")
    s.set_defaults(fn=cmd_interfaces)
    s = sp.add_parser("gauge")
    s.add_argument("--out", default="gauge")
    s.add_argument("--actuator", default="sts3215-12v")
    s.add_argument("--bearing", default="MR105ZZ")
    s.set_defaults(fn=cmd_gauge)
    for name, fn in (("gate", cmd_gate), ("rom", cmd_rom), ("access", cmd_access), ("check", cmd_check), ("render", cmd_render)):
        s = sp.add_parser(name)
        s.add_argument("builder")
        s.add_argument("--variant", default="adam")
        s.add_argument("--out")
        s.add_argument("--fast", action="store_true", help="skip the voxel wall check")
        s.add_argument("--step", type=float, default=5.0, help="ROM step (deg)")
        s.add_argument("--pose", action="append")
        s.add_argument("--side", default="l")
        s.add_argument("--gap", action="store_true", help="ROM: also report moving-gap violations")
        s.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
