"""M1: build123d section lofts. Superellipse sections from the profile stations -> loft -> outer - inner wall -> panels.

B-rep all the way (OCCT), so the result exports STEP. Hollowing is `outer - inner loft` (never `offset`, which gave a
false-valid solid in research/ai-engineering/prototypes/README.md). The knee pocket is the thigh-swept cutter polygon
extruded and subtracted from the shank twice: gap `band` for the outside, `band + wall` for the inside, so the pocket
keeps a full wall.
"""
from __future__ import annotations

import numpy as np

from .meshutil import ShellSet, Timer, name_panels
from .spec import LegSpec, SegProfile, knee_cutter_polygon


DENSIFY = 2     # extra sections between neighbouring stations (found necessary: 0 gave a wavy calf)


def _bd():
    import build123d as bd
    return bd


def section_wire(prof: SegProfile, z: float, shrink: float = 0.0, k: int = 40, zshift: float = 0.0):
    bd = _bd()
    pts = [bd.Vector(float(x), float(y), z + zshift) for x, y in prof.xy(z, k, shrink)]
    return bd.Wire([bd.Edge.make_spline(pts, periodic=True)])


def loft(stations: list[tuple], shrink: float = 0.0, end_shift: float = 0.0):
    """Loft through one superellipse section per station. `shrink` pulls every section in by that many mm (inner wall);
    `end_shift` moves the first/last section inwards along z so the cavity closes `end_shift` inside the end faces."""
    bd = _bd()
    prof = SegProfile(stations)
    zs = [s[0] for s in prof.stations]
    if DENSIFY:       # OCC's loft is a global B-spline through the sections and rings between sparse ones; extra sections taken from the PCHIP profile pin it
        zs = sorted(set(zs) | {round(a + (b - a) * t / (DENSIFY + 1), 3) for a, b in zip(zs, zs[1:]) for t in range(1, DENSIFY + 1)})
    wires = []
    for i, z in enumerate(zs):
        dz = end_shift if i == 0 else (-end_shift if i == len(zs) - 1 else 0.0)
        wires.append(section_wire(prof, z, shrink, zshift=dz))
    return bd.Solid.make_loft(wires)


def prism(poly: np.ndarray, half_y: float = 80.0):
    """(x, z) polygon extruded along y over [-half_y, half_y]."""
    bd = _bd()
    wire = bd.Wire.make_polygon([bd.Vector(float(x), -half_y, float(z)) for x, z in poly], close=True)
    return bd.extrude(bd.Face(wire), amount=2 * half_y, dir=(0, 1, 0))


def keepout_solid(k, inflate: float):
    bd = _bd()
    if k.kind == "box":
        s = [v + 2 * inflate for v in k.size]
        return bd.Pos(*k.center) * bd.Box(*s)
    r = k.radius + inflate
    z0, z1 = sorted((k.p0[2], k.p1[2]))
    cyl = bd.Pos(k.p0[0], k.p0[1], (z0 + z1) / 2) * bd.Cylinder(r, z1 - z0)
    return cyl + bd.Pos(k.p0[0], k.p0[1], z0) * bd.Sphere(r) + bd.Pos(k.p0[0], k.p0[1], z1) * bd.Sphere(r)


def shell_solid(stations, wall, pocket_outer=None, pocket_wall=None):
    """Outer loft - inner loft, with the optional knee pocket cut from both (the inner cut is wider by one wall)."""
    outer = loft(stations)
    inner = loft(stations, shrink=wall, end_shift=wall)
    if pocket_outer is not None:
        outer = outer - pocket_outer
        inner = inner - pocket_wall
    return outer - inner


def tessellate(shape, tol: float = 0.02, ang: float = 0.15):
    import trimesh

    v, t = shape.tessellate(tol, ang)
    m = trimesh.Trimesh(np.array([[p.X, p.Y, p.Z] for p in v]), np.array(t), process=True)   # process merges the duplicate seam vertices
    m.merge_vertices()
    return m


def build(spec: LegSpec | None = None, step_path: str | None = None) -> ShellSet:
    bd = _bd()
    spec = spec or LegSpec()
    with Timer() as T:
        pocket_o = prism(knee_cutter_polygon(spec, spec.band))
        pocket_w = prism(knee_cutter_polygon(spec, spec.band + spec.wall))
        shells = {
            "thigh": shell_solid(spec.thigh_stations(), spec.wall),
            "shank": shell_solid(spec.shank_stations(), spec.wall, pocket_o, pocket_w),
        }
        slab = bd.Pos(spec.seam_x, 0, 0) * bd.Box(spec.seam_gap, 400, 600)
        panels: dict = {}
        for seg, sh in shells.items():
            for k in (k for k in spec.keepouts() if k.host == seg):
                sh = sh - keepout_solid(k, spec.clearance)       # keep-outs subtracted: never let the wall touch a servo
            sh = sh - slab                                      # reveal gap at the panel line -> front / rear panels
            panels[seg] = list(sh.solids())
        solids = name_panels({seg: [(p.center().X, p) for p in ps] for seg, ps in panels.items()}, spec)
        parts = {k: tessellate(s) for k, s in solids.items()}
        if step_path:
            bd.export_step(bd.Compound(list(solids.values())), step_path)
    ss = ShellSet("M1_build123d", spec, parts, step_path, T.seconds)
    ss.notes["brep_valid"] = {k: bool(s.is_valid) for k, s in solids.items()}
    ss.notes["brep_volume_mm3"] = {k: round(float(s.volume), 1) for k, s in solids.items()}
    ss.solids = solids   # not serialised; lets callers inspect the B-rep
    return ss
