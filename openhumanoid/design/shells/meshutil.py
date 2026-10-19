"""Mesh helpers shared by the bake-off methods: ShellSet container, trimesh <-> manifold3d, the knee-cutter prism,
keep-out solids, the seam slab. Millimetres, knee-axis frame (see spec.py)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .spec import KeepOut, LegSpec


@dataclass
class ShellSet:
    """What every method returns: printable panels as triangle meshes (mm), optional B-rep STEP, timing and notes."""
    method: str
    spec: LegSpec
    parts: dict = field(default_factory=dict)      # name -> trimesh.Trimesh, watertight if the method is sound
    step_path: str | None = None
    seconds: float = 0.0
    notes: dict = field(default_factory=dict)

    def save(self, out_dir: str | Path) -> Path:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        for k, m in self.parts.items():
            m.export(out / f"{k}.stl")
        (out / "shellset.json").write_text(json.dumps({"method": self.method, "spec": self.spec.label(), "seconds": round(self.seconds, 2),
                                                        "parts": sorted(self.parts), "step": self.step_path, "notes": self.notes}, indent=1),
                                           encoding="utf-8")
        return out


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.seconds = time.perf_counter() - self.t0


# ------------------------------------------------------------------------------------------------------ manifold
def _mf():
    import manifold3d as mf
    return mf


def to_manifold(mesh):
    mf = _mf()
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(mesh.vertices, np.float32), tri_verts=np.asarray(mesh.faces, np.uint32)))


def from_manifold(m):
    import trimesh

    me = m.to_mesh()
    return trimesh.Trimesh(np.asarray(me.vert_properties)[:, :3].astype(float), np.asarray(me.tri_verts, int), process=False)


def decimate(mesh, tol: float = 0.03):
    """Merge near-coplanar triangles within `tol` mm (manifold3d simplify): marching-cubes meshes drop ~5x with no visible change."""
    return from_manifold(to_manifold(mesh).simplify(tol))


def prism_from_xz(poly: np.ndarray, half_y: float = 80.0):
    """Manifold prism: the (x, z) polygon extruded along y over [-half_y, +half_y]."""
    mf = _mf()
    cs = mf.CrossSection([np.asarray(poly, float)])
    sol = mf.Manifold.extrude(cs, 2 * half_y)              # polygon in the xy plane, extruded along z
    return sol.rotate((90.0, 0.0, 0.0)).translate((0.0, half_y, 0.0))   # (x,y,z)->(x,-z,y) then centre in y


def keepout_manifold(k: KeepOut, inflate: float = 0.0):
    mf = _mf()
    if k.kind == "box":
        s = np.array(k.size) + 2 * inflate
        return mf.Manifold.cube(tuple(s), True).translate(tuple(k.center))
    assert abs(k.p0[0] - k.p1[0]) < 1e-9 and abs(k.p0[1] - k.p1[1]) < 1e-9, "capsule keep-outs are z-aligned"
    r = k.radius + inflate
    z0, z1 = sorted((k.p0[2], k.p1[2]))
    cyl = mf.Manifold.cylinder(z1 - z0, r, r, 48).translate((k.p0[0], k.p0[1], z0))
    return cyl + mf.Manifold.sphere(r, 48).translate((k.p0[0], k.p0[1], z0)) + mf.Manifold.sphere(r, 48).translate((k.p0[0], k.p0[1], z1))


def seam_slab_manifold(spec: LegSpec):
    mf = _mf()
    return mf.Manifold.cube((spec.seam_gap, 400.0, 600.0), True).translate((spec.seam_x, 0.0, 0.0))


def name_panels(items: dict, spec: LegSpec) -> dict:
    """{'thigh': [(centroid_x, obj), ...], 'shank': [...]} -> {'thigh_front': obj, 'thigh_rear': obj, ...}.
    front = +x of the seam plane, rear = -x; extra components on a side are numbered."""
    parts = {}
    for seg, lst in items.items():
        for cx, obj in lst:
            key = f"{seg}_{'front' if cx > spec.seam_x else 'rear'}"
            base, i = key, 2
            while key in parts:
                key, i = f"{base}{i}", i + 1
            parts[key] = obj
    return dict(sorted(parts.items()))
