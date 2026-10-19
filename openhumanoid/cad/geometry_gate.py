"""Geometry gate (research C3): the checks every part and assembly must pass before anyone looks at a render.

Per part (`check_part`):
  1. executes to ONE valid solid with positive volume
  2. STEP export -> re-import -> valid, one solid, volume and bbox unchanged   (catches silent boolean/export damage)
  3. watertight STL (tessellated with trimesh): watertight, winding consistent, volume agrees with the B-rep
  4. bounding box and key dimensions / features against `interfaces.yaml` (declared on the part as `meta["expect"]`)
  5. minimum wall against dfm.yaml (voxel opening) and the printer bed fit (usable volume, any axis-aligned orientation)
Per assembly (`check_assembly`) at the stand pose:
  6. pairwise interference (OCC common, manifold3d mesh fallback) and minimum clearance. Pairs that mate by design go in
     `Assembly.allowed_pairs`; everything else that overlaps is a clash.
  7. keep-out volumes (cable channels, plug room) vs other parts.

Each check returns plain dicts so results go straight into JSON. `run_gate` runs everything and returns {"ok", "parts", "assembly"}.

Part expectations (`Part.meta["expect"]`, a list of dicts, all in the LINK frame, mm):
  {"kind": "bbox", "axis": "x"|"y"|"z", "min": a, "max": b, "tol": 0.2}          the part's extent along axis
  {"kind": "size", "axis": "z", "value": 12.0, "tol": 0.2}                      its extent
  {"kind": "void_cylinder", "origin": [x,y,z], "dir": [dx,dy,dz], "d": 3.4, "length": 8, "tol": 0.15, "label": "..."}
        a hole: a probe cylinder of d - 2 tol is fully void and one of d + 2 tol + 0.3 touches material
  {"kind": "contains_bbox", "min": [x,y,z], "max": [x,y,z], "tol": 0.2}          the part's bounding box encloses this box (e.g. the servo envelope)
  {"kind": "solid_point", "point": [x,y,z], "label": "..."} / {"kind": "void_point", ...}
  {"kind": "interface", "joint": "hip_yaw_l", "key": "axis.origin", "value": [..], "tol": 0.05}   recorded value must equal interfaces.yaml
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import build123d as bd

from . import dfm
from .assembly import Assembly, Placed, candidates, pair_key
from .core import loc_from, mesh_of, min_distance, overlap_volume, volume
from .geom import Part, fits_bed

CLASH_MM3 = 2.0          # overlaps below this are numerical contact, not clashes


# --------------------------------------------------------------------------- per-part checks


def _fail(name: str, msg: str, **kw) -> dict:
    return {"check": name, "ok": False, "msg": msg, **kw}


def _ok(name: str, msg: str = "", **kw) -> dict:
    return {"check": name, "ok": True, "msg": msg, **kw}


def check_solid(shape: bd.Shape) -> dict:
    n = len(shape.solids())
    if not shape.is_valid:
        return _fail("solid", "shape is not valid (OCC)")
    if n != 1:
        return _fail("solid", f"expected exactly one solid, found {n}", solids=n)
    if shape.volume <= 0:
        return _fail("solid", "non-positive volume")
    return _ok("solid", f"valid single solid, {shape.volume:.1f} mm3", volume=float(shape.volume))


def check_step_roundtrip(shape: bd.Shape, workdir: Path | None = None, rel_tol: float = 1e-3) -> dict:
    """Export STEP, re-import, re-check validity, solid count, volume and bbox (silent boolean damage shows up here)."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(workdir or td) / "roundtrip.step"
        try:
            bd.export_step(shape, str(p))
            back = bd.import_step(str(p))
        except Exception as e:  # noqa: BLE001
            return _fail("step_roundtrip", f"STEP export/import raised {type(e).__name__}: {e}")
    if not back.is_valid:
        return _fail("step_roundtrip", "re-imported STEP is not valid")
    n = len(back.solids())
    if n != 1:
        return _fail("step_roundtrip", f"re-imported STEP has {n} solids")
    dv = abs(back.volume - shape.volume) / max(shape.volume, 1e-9)
    b0, b1 = shape.bounding_box(), back.bounding_box()
    dbb = max(abs(a - b) for a, b in zip((b0.min.X, b0.min.Y, b0.min.Z, b0.max.X, b0.max.Y, b0.max.Z),
                                         (b1.min.X, b1.min.Y, b1.min.Z, b1.max.X, b1.max.Y, b1.max.Z)))
    if dv > rel_tol or dbb > 0.01:
        return _fail("step_roundtrip", f"volume changed {dv:.2e} (rel), bbox moved {dbb:.3f} mm", dv=dv, dbbox=dbb)
    return _ok("step_roundtrip", f"volume drift {dv:.1e}, bbox drift {dbb:.1e} mm", dv=dv, dbbox=dbb)


def check_stl(shape: bd.Shape, rel_tol: float = 0.01, out: Path | None = None) -> dict:
    """Tessellate (trimesh): watertight, consistent winding, positive volume matching the B-rep within rel_tol."""
    m = mesh_of(shape)
    if out is not None:
        m.export(str(out))
    if not m.is_watertight:
        return _fail("stl", "tessellation is not watertight", faces=len(m.faces))
    if not m.is_winding_consistent:
        return _fail("stl", "inconsistent face winding")
    dv = abs(m.volume - shape.volume) / max(shape.volume, 1e-9)
    if m.volume <= 0 or dv > rel_tol:
        return _fail("stl", f"mesh volume {m.volume:.1f} vs B-rep {shape.volume:.1f} (rel {dv:.3f})", dv=dv)
    return _ok("stl", f"watertight, {len(m.faces)} faces, volume agrees to {dv:.1e}", faces=len(m.faces), dv=dv)


def check_bed(shape: bd.Shape, bed_mm=None) -> dict:
    usable = dfm.bed_usable(bed_mm)
    ok, ext = fits_bed(shape, usable)
    msg = f"extents {[round(e, 1) for e in ext]} vs usable {[round(u, 1) for u in sorted(usable, reverse=True)]}"
    return (_ok if ok else _fail)("bed", msg, extents=[round(e, 1) for e in ext], usable=[round(u, 1) for u in usable])


def check_min_wall(shape: bd.Shape, wall_class: str | None = None, pitch: float | None = None) -> dict:
    need = dfm.min_wall(wall_class)
    r = dfm.thin_wall_report(shape, need, pitch=pitch)
    msg = (f"no material thinner than {need} mm (grid {r['pitch_mm']:.2f} mm)" if r["ok"]
           else f"{r['thin_volume_mm3']:.0f} mm3 thinner than {need} mm near {None if not r['worst_location'] else [round(v, 1) for v in r['worst_location']]}")
    return (_ok if r["ok"] else _fail)("min_wall", msg, **{k: r[k] for k in ("thin_volume_mm3", "thin_fraction", "worst_location", "pitch_mm")})


def _probe(origin, direction, d, length) -> bd.Shape:
    loc = loc_from(origin, direction)
    return loc * (bd.Pos(0, 0, length / 2) * bd.Cylinder(d / 2, length))


def check_expect(shape: bd.Shape, exp: dict, interfaces: dict | None = None) -> dict:
    """One declared expectation against the shape (see module docstring)."""
    k = exp["kind"]
    tol = float(exp.get("tol", 0.2))
    label = exp.get("label", k)
    if k in ("bbox", "size"):
        ax = "xyz".index(exp["axis"])
        bb = shape.bounding_box()
        lo, hi = [bb.min.X, bb.min.Y, bb.min.Z][ax], [bb.max.X, bb.max.Y, bb.max.Z][ax]
        if k == "size":
            got, want = hi - lo, float(exp["value"])
            ok = abs(got - want) <= tol
            return (_ok if ok else _fail)(f"expect:{label}", f"size {exp['axis']} = {got:.2f}, want {want:.2f} +-{tol}")
        ok = lo >= float(exp["min"]) - tol and hi <= float(exp["max"]) + tol
        return (_ok if ok else _fail)(f"expect:{label}", f"extent {exp['axis']} [{lo:.2f}, {hi:.2f}] in [{exp['min']}, {exp['max']}] +-{tol}")
    if k == "void_cylinder":
        d, L = float(exp["d"]), float(exp["length"])
        inner = _probe(exp["origin"], exp["dir"], d - 2 * tol, L)
        outer = _probe(exp["origin"], exp["dir"], d + 2 * tol + 0.3, L)
        clash = overlap_volume(shape, inner)
        touch = overlap_volume(shape, outer)
        if clash > CLASH_MM3:
            return _fail(f"expect:{label}", f"hole d{d} at {exp['origin']} is blocked ({clash:.1f} mm3 of material in the probe)")
        if touch <= 0.01:
            return _fail(f"expect:{label}", f"hole d{d} at {exp['origin']} is far larger than specified or missing material around it")
        return _ok(f"expect:{label}", f"hole d{d} present and clear")
    if k == "contains_bbox":
        bb = shape.bounding_box()
        lo, hi = (bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z)
        ok = all(lo[i] <= exp["min"][i] + tol and hi[i] >= exp["max"][i] - tol for i in range(3))
        return (_ok if ok else _fail)(f"expect:{label}", f"bbox [{[round(v, 1) for v in lo]}, {[round(v, 1) for v in hi]}] "
                                                          f"{'encloses' if ok else 'does NOT enclose'} [{exp['min']}, {exp['max']}]")
    if k in ("solid_point", "void_point"):
        inside = bool(shape.is_inside(bd.Vector(*exp["point"])))
        ok = inside if k == "solid_point" else not inside
        return (_ok if ok else _fail)(f"expect:{label}", f"point {exp['point']} is {'inside' if inside else 'outside'} material")
    if k == "interface":
        if not interfaces:
            return _fail(f"expect:{label}", "no interfaces.yaml loaded")
        node = interfaces["joints"][exp["joint"]]
        for part_ in exp["key"].split("."):
            node = node[part_]
        want = node
        got = exp["value"]
        try:
            diff = max(abs(float(a) - float(b)) for a, b in zip(_flat(want), _flat(got)))
        except Exception:  # noqa: BLE001
            return _fail(f"expect:{label}", f"cannot compare {got} with interfaces {want}")
        return (_ok if diff <= tol else _fail)(f"expect:{label}", f"{exp['joint']}.{exp['key']}: part {got} vs interfaces {want} (max diff {diff:.3f})")
    return _fail(f"expect:{label}", f"unknown expectation kind '{k}'")


def _flat(x):
    if isinstance(x, (list, tuple)):
        for v in x:
            yield from _flat(v)
    else:
        yield x


def check_part(part: Part, *, bed_mm=None, interfaces: dict | None = None, wall_class: str | None = None, fast: bool = False,
               stl_dir: Path | None = None, wall: bool = True) -> dict:
    """All per-part checks. `fast=True` skips the voxel wall check (use in tight loops)."""
    shape = part.shape
    res = [check_solid(shape)]
    if res[0]["ok"]:
        res.append(check_step_roundtrip(shape))
        res.append(check_stl(shape, out=(stl_dir / f"{part.id}.stl") if stl_dir else None))
        for e in part.meta.get("expect", []):
            res.append(check_expect(shape, e, interfaces))
        if part.process == "fdm" and not part.keepout:
            res.append(check_bed(shape, bed_mm))
            if wall and not fast:
                res.append(check_min_wall(shape, part.meta.get("wall_class", wall_class)))
    return {"part": part.id, "ok": all(r["ok"] for r in res), "checks": res,
            "volume_mm3": float(shape.volume) if res[0]["ok"] else None}


# --------------------------------------------------------------------------- assembly checks


def check_assembly(asm: Assembly, q: dict[str, float] | None = None, *, min_gap: float | None = None, pad_clearance: bool = True) -> dict:
    """Pairwise interference and minimum clearance at pose q (default: the assembly's stand pose).
    Returns {"clashes": [...], "tight": [...], "keepout": [...], "unknown": [...], "checked_pairs": n}.
    * clashes: overlap volume > CLASH_MM3 between parts that are not in `allowed_pairs` (hardware ignored);
    * tight: pairs on DIFFERENT links closer than dfm moving_gap_min (they move relative to each other) or on the same link closer
      than dfm static_gap_min without being an allowed contact;
    * keepout: a keep-out volume (cable channel, plug room) overlapped by a part it does not belong to."""
    gap = float(dfm.load_dfm()["moving_gap_min_mm"]["v"] if min_gap is None else min_gap)
    static_gap = float(dfm.load_dfm()["static_gap_min_mm"]["v"])
    pl = [p for p in asm.placed(q) if not p.part.hardware]
    solids = [p for p in pl if not p.part.keepout]
    kos = [p for p in pl if p.part.keepout]
    clashes, tight, unknown, keep = [], [], [], []
    pairs = candidates(solids, pad=max(gap, static_gap) if pad_clearance else 0.0)
    for i, k in pairs:
        a, b = solids[i], solids[k]
        key = pair_key(a.part.id, b.part.id)
        allowed = key in asm.allowed_pairs
        v = overlap_volume(a.shape, b.shape)
        if v < 0:
            unknown.append((a.part.id, b.part.id))
            continue
        if v > CLASH_MM3:
            if not allowed:
                clashes.append({"a": a.part.id, "b": b.part.id, "mm3": round(v, 1), "links": [a.link, b.link]})
            continue
        if allowed:
            continue
        d = min_distance(a.shape, b.shape)
        lim = asm.fits.get(key, gap if a.link != b.link else static_gap)
        if d < lim - 1e-6:
            tight.append({"a": a.part.id, "b": b.part.id, "dist_mm": round(d, 3), "limit_mm": lim, "links": [a.link, b.link]})
    for ko in kos:
        owner = ko.part.meta.get("owner")
        for s in solids:
            if s.part.id == owner or pair_key(ko.part.id, s.part.id) in asm.allowed_pairs:
                continue
            v = overlap_volume(ko.shape, s.shape)
            if v > CLASH_MM3:
                keep.append({"keepout": ko.part.id, "part": s.part.id, "mm3": round(v, 1)})
    return {"ok": not clashes and not keep and not unknown, "clashes": clashes, "tight": tight, "keepout": keep, "unknown": unknown,
            "checked_pairs": len(pairs), "pose": q or asm.stand_pose, "gap_limits_mm": {"moving": gap, "static": static_gap}}


def run_gate(asm: Assembly, *, fast: bool = False, only_parts: list[str] | None = None, stl_dir: Path | None = None) -> dict:
    """Full geometry gate for an assembly: every printed/purchased part plus the assembly pairwise checks."""
    parts = []
    if stl_dir is not None:
        Path(stl_dir).mkdir(parents=True, exist_ok=True)
    for ln, p in asm.parts(include_hardware=False):
        if only_parts and p.id not in only_parts:
            continue
        parts.append(check_part(p, bed_mm=asm.bed_mm, interfaces=asm.interfaces, fast=fast or p.process == "purchased",
                                stl_dir=stl_dir, wall=p.process == "fdm"))
    ar = check_assembly(asm)
    ok = all(r["ok"] for r in parts) and ar["ok"]
    return {"assembly": asm.name, "ok": ok, "parts": parts, "assembly_check": ar,
            "failed_parts": [r["part"] for r in parts if not r["ok"]]}


def summarize(report: dict) -> str:
    lines = [f"geometry gate: {report['assembly']}  ->  {'PASS' if report['ok'] else 'FAIL'}"]
    for r in report["parts"]:
        bad = [c for c in r["checks"] if not c["ok"]]
        lines.append(f"  {'ok  ' if r['ok'] else 'FAIL'} {r['part']}" + ("" if r["ok"] else ": " + "; ".join(f"{c['check']}: {c['msg']}" for c in bad)))
    a = report["assembly_check"]
    lines.append(f"  assembly: {len(a['clashes'])} clashes, {len(a['tight'])} tight gaps, {len(a['keepout'])} keep-out hits "
                 f"({a['checked_pairs']} candidate pairs)")
    for c in a["clashes"][:40]:
        lines.append(f"    CLASH {c['a']} x {c['b']}: {c['mm3']} mm3")
    for c in a["tight"][:40]:
        lines.append(f"    tight {c['a']} x {c['b']}: {c['dist_mm']} mm < {c['limit_mm']}")
    for c in a["keepout"][:20]:
        lines.append(f"    KEEPOUT {c['keepout']} hit by {c['part']}: {c['mm3']} mm3")
    return "\n".join(lines)
