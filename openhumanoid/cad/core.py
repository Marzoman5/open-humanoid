"""Core types and guarded boolean operations for the CAD foundation.

LLM-written CAD fails mostly by *silent* booleans (a union drops a tangent cylinder, a cut does nothing, `offset()` reports
valid on a broken shell: research/ai-engineering/01-ai-cad.md). Everything in the helper library therefore goes through
`safe_cut` / `safe_union`, which check validity, solid count and that the volume moved the way the operation says it must,
and raise `CadOpError` instead of returning a quietly wrong part.

Units: mm. Frames: x forward, y left, z up (sim convention). A `Location` is a placement; shapes are built in a local frame
and moved with `loc * shape`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

import build123d as bd

# --------------------------------------------------------------------------- errors / small utilities


class CadOpError(RuntimeError):
    """A boolean or feature operation did not do what it claims. Never swallowed by the helpers."""


def vec(v) -> bd.Vector:
    return v if isinstance(v, bd.Vector) else bd.Vector(*v)


def loc_from(origin=(0, 0, 0), z_dir=(0, 0, 1), x_dir=None) -> bd.Location:
    """Location whose origin is `origin`, local +z along `z_dir`, local +x along `x_dir` (or any perpendicular)."""
    z = vec(z_dir).normalized()
    if x_dir is None:
        ref = bd.Vector(1, 0, 0) if abs(z.X) < 0.9 else bd.Vector(0, 1, 0)
        x = (ref - z * ref.dot(z)).normalized()
    else:
        x = vec(x_dir)
        x = (x - z * x.dot(z)).normalized()
    return bd.Location(bd.Plane(origin=tuple(origin), x_dir=(x.X, x.Y, x.Z), z_dir=(z.X, z.Y, z.Z)))


def axis_of(loc: bd.Location) -> tuple[bd.Vector, bd.Vector]:
    """(origin, unit z direction) of a Location."""
    p = loc.position
    z = (loc * bd.Vector(0, 0, 1)) - (loc * bd.Vector(0, 0, 0))
    return bd.Vector(p.X, p.Y, p.Z), z.normalized()


def volume(s: bd.Shape | None) -> float:
    return 0.0 if s is None else float(s.volume)


def solids_of(s: bd.Shape) -> list[bd.Solid]:
    return list(s.solids())


def bbox_tuple(s: bd.Shape) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    bb = s.bounding_box()
    return (bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z)


def bboxes_overlap(a: bd.Shape, b: bd.Shape, pad: float = 0.0) -> bool:
    (a0, a1), (b0, b1) = bbox_tuple(a), bbox_tuple(b)
    return all(a0[i] - pad <= b1[i] and b0[i] - pad <= a1[i] for i in range(3))


def union_all(shapes: Iterable[bd.Shape]) -> bd.Shape | None:
    shapes = [s for s in shapes if s is not None]
    if not shapes:
        return None
    out = shapes[0]
    for s in shapes[1:]:
        out = safe_union(out, s, "union_all")
    return out


# --------------------------------------------------------------------------- guarded booleans


def check_solid(s: bd.Shape, name: str = "shape", single: bool = True, min_volume: float = 1e-3) -> bd.Shape:
    """Validity + (optionally) exactly one solid with positive volume. Returns `s` or raises."""
    if s is None:
        raise CadOpError(f"{name}: operation returned None")
    if not s.is_valid:
        raise CadOpError(f"{name}: shape is not valid (OCC check)")
    n = len(solids_of(s))
    if n == 0 or s.volume < min_volume:
        raise CadOpError(f"{name}: empty result (volume {s.volume:.4g} mm3, {n} solids)")
    if single and n != 1:
        raise CadOpError(f"{name}: expected one solid, got {n} (a feature floats free or a boolean split the part)")
    return s


def overlap_volume(a: bd.Shape, b: bd.Shape) -> float:
    """Common volume in mm3 (0 when bounding boxes do not touch). OCC first; mesh booleans (manifold3d) if OCC fails."""
    if not bboxes_overlap(a, b):
        return 0.0
    try:
        c = a & b
        v = float(c.volume) if c is not None else 0.0
        if v == v:
            return v
    except Exception:  # noqa: BLE001
        pass
    return mesh_overlap_volume(a, b)


def mesh_of(s: bd.Shape, tol: float = 0.05, ang: float = 0.2):
    """Merged, watertight-if-possible trimesh of a shape (mm)."""
    import numpy as np
    import trimesh

    verts, tris = s.tessellate(tol, ang)
    m = trimesh.Trimesh(np.array([(v.X, v.Y, v.Z) for v in verts], float), np.array(tris, int), process=True)
    m.merge_vertices()
    return m


def mesh_overlap_volume(a: bd.Shape, b: bd.Shape) -> float:
    """Fallback interference volume via manifold3d on tessellations (robust where OCC booleans fail)."""
    import manifold3d as m3d
    import numpy as np

    def man(sh):
        m = mesh_of(sh)
        return m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(m.vertices, dtype=np.float32),
                                     tri_verts=np.asarray(m.faces, dtype=np.uint32)))
    try:
        return float((man(a) ^ man(b)).volume())
    except Exception:  # noqa: BLE001
        return -1.0


def min_distance(a: bd.Shape, b: bd.Shape) -> float:
    """Exact minimum distance between two shapes in mm (0 when they touch or overlap)."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    d = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    d.Perform()
    if not d.IsDone():
        return float("nan")
    return float(d.Value())


def safe_cut(base: bd.Shape, cutter: bd.Shape, name: str = "cut", must_remove: float = 0.0, single: bool = True) -> bd.Shape:
    """base - cutter, verified. `must_remove`: minimum volume (mm3) the cut has to take away. When the cutter's volume
    inside `base` is non-trivial (checked with an independent intersection) the result must lose about that much."""
    if cutter is None:
        return base
    v0 = volume(base)
    out = base - cutter
    check_solid(out, name, single=single)
    removed = v0 - volume(out)
    if removed < -1e-6 * v0:
        raise CadOpError(f"{name}: cut ADDED volume ({-removed:.3g} mm3)")
    if bboxes_overlap(base, cutter):
        expect = overlap_volume(base, cutter)
        if expect > 0.5 and removed < 0.5 * expect:
            raise CadOpError(f"{name}: cut silently failed (expected to remove ~{expect:.3g} mm3, removed {removed:.3g})")
    if removed < must_remove:
        raise CadOpError(f"{name}: cut removed {removed:.3g} mm3, required at least {must_remove:.3g}")
    return out


def safe_union(base: bd.Shape, add: bd.Shape, name: str = "union", single: bool = True) -> bd.Shape:
    """base + add, verified: valid, one solid (unless single=False), volume is at least that of the larger input and no
    more than the sum. Catches tangent-union drops where a feature silently disappears."""
    if add is None:
        return base
    v0, v1 = volume(base), volume(add)
    out = base + add
    check_solid(out, name, single=single)
    vo = volume(out)
    if vo < max(v0, v1) - 1e-4 * max(v0, v1):
        raise CadOpError(f"{name}: union lost volume ({vo:.4g} < max({v0:.4g}, {v1:.4g}))")
    if vo > v0 + v1 + 1e-4 * (v0 + v1):
        raise CadOpError(f"{name}: union gained volume ({vo:.4g} > {v0 + v1:.4g})")
    # a feature that contributes nothing although it should add material is the classic silent drop
    shared = overlap_volume(base, add) if bboxes_overlap(base, add) else 0.0
    if shared >= 0 and (v1 - shared) > 0.5 and (vo - v0) < 0.5 * (v1 - shared):
        raise CadOpError(f"{name}: union silently dropped the added feature (+{vo - v0:.3g} mm3 vs {v1 - shared:.3g} expected)")
    return out


# --------------------------------------------------------------------------- features


@dataclass
class Site:
    """A fastener or insert location on a part. `frame` origin is on the surface the screw head (or insert opening) sits on,
    local +z points OUT of the material along the tool-approach axis (the screw travels in -z)."""
    id: str
    kind: str                     # screw | insert | magnet
    part: str                     # part id this site belongs to
    frame: bd.Location
    thread: str = "M3"
    length_mm: float = 8.0        # screw length / insert length
    mates: str | None = None      # id of the part this fastener clamps (None = unknown/free)
    tool_d: float = 8.0           # diameter of the free tool corridor
    tool_len: float = 40.0        # corridor length (key + hand room)
    needs_access: bool = True     # magnets/inserts pressed in at print time still list for assembly order but need no corridor

    def corridor(self) -> bd.Shape:
        """Cylinder along +z of the site frame, starting 0.2 mm above the seat surface."""
        return self.frame * (bd.Pos(0, 0, 0.2 + self.tool_len / 2) * bd.Cylinder(self.tool_d / 2, self.tool_len))


@dataclass
class FeatureResult:
    """What a helper hands back: material to add, material to cut, fastener sites, keep-out volumes and notes.
    Use `apply(base, feat, ...)` to execute (adds first, then cuts), so features compose in any order."""
    add: list[bd.Shape] = field(default_factory=list)
    cut: list[bd.Shape] = field(default_factory=list)
    sites: list[Site] = field(default_factory=list)
    keepouts: list[bd.Shape] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    name: str = "feature"

    def merged(self, other: "FeatureResult") -> "FeatureResult":
        return FeatureResult(self.add + other.add, self.cut + other.cut, self.sites + other.sites,
                             self.keepouts + other.keepouts, self.notes + other.notes, self.name)

    def placed(self, loc: bd.Location) -> "FeatureResult":
        """The same feature moved by `loc` (helpers build in a local frame)."""
        return FeatureResult([loc * s for s in self.add], [loc * s for s in self.cut],
                             [Site(**{**s.__dict__, "frame": loc * s.frame}) for s in self.sites],
                             [loc * s for s in self.keepouts], list(self.notes), self.name)


def apply(base: bd.Shape, *feats: FeatureResult, name: str = "part", single: bool = True) -> tuple[bd.Shape, list[Site]]:
    """Add all material first, then make all cuts, each through the guarded booleans. Returns (shape, sites)."""
    sites: list[Site] = []
    out = base
    for f in feats:
        sites += f.sites
        for a in f.add:
            out = safe_union(out, a, f"{name}:{f.name}+", single=single)
    for f in feats:
        for c in f.cut:
            out = safe_cut(out, c, f"{name}:{f.name}-", single=single)
    return out, sites


def cyl_along(loc: bd.Location, d: float, h: float, z0: float = 0.0) -> bd.Shape:
    """Cylinder of diameter d, height h, standing on the local z = z0 plane of `loc` (extends toward +z)."""
    return loc * (bd.Pos(0, 0, z0 + h / 2) * bd.Cylinder(d / 2, h))


def box_at(loc: bd.Location, size, center=(0, 0, 0)) -> bd.Shape:
    return loc * (bd.Pos(*center) * bd.Box(*size))


def deg(rad: float) -> float:
    return math.degrees(rad)
