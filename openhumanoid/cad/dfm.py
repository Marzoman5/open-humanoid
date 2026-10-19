"""Loader and helpers for `dfm.yaml` (design-for-manufacture rules) plus the thin-wall analysis used by the geometry gate.

Part code never hard-codes a clearance: `clearance("slip")`, `hole_d(3.0)`, `min_wall("structural")`, `bed_usable(bed)`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

DFM_PATH = Path(__file__).with_name("dfm.yaml")


@lru_cache(maxsize=1)
def load_dfm() -> dict:
    return yaml.safe_load(DFM_PATH.read_text(encoding="utf-8"))


def _v(x):
    """Unwrap a {v, src, conf} entry."""
    return x["v"] if isinstance(x, dict) and "v" in x else x


def clearance(kind: str) -> float:
    """Per-side clearance (mm) for a fit class: press | slip | sliding | rotating | loose."""
    c = load_dfm()["clearance"]
    if kind not in c:
        raise KeyError(f"unknown fit class '{kind}'. Known: {sorted(c)}")
    return float(c[kind]["per_side_mm"])


def hole_comp(d: float) -> float:
    """Diameter compensation (mm, added to the diameter) for a printed round hole of nominal diameter d."""
    for r in load_dfm()["hole_compensation"]:
        if d <= r["max_d_mm"]:
            return float(r["add_mm"])
    return float(load_dfm()["hole_compensation"][-1]["add_mm"])


def hole_d(nominal: float, fit: str | None = None) -> float:
    """Printed hole diameter for a part of `nominal` diameter: nominal + hole compensation + 2 x per-side clearance of `fit`."""
    c = clearance(fit) if fit else 0.0
    return float(nominal + hole_comp(nominal) + 2 * c)


def min_wall(cls: str | None = None) -> float:
    m = load_dfm()["min_wall"]
    return float(_v(m[(cls or m["default_class"]) + "_mm"]))


def bed_usable(bed_mm=None) -> tuple[float, float, float]:
    """Usable print volume: the printer bed minus the edge margin (X, Y both sides; Z once)."""
    d = load_dfm()["bed"]
    bed = list(bed_mm or d["default_mm"])
    m = float(_v(d["edge_margin_mm"]))
    return (bed[0] - 2 * m, bed[1] - 2 * m, bed[2] - m)


def z_knockdown(material: str) -> float:
    return float(load_dfm()["orientation"]["z_over_xy_strength"].get(material, 0.6))


def snap_strain_limit(material: str) -> float:
    """Allowable cantilever bending strain, as a fraction (not percent)."""
    return float(load_dfm()["snap_fit"]["allowable_strain_pct"].get(material, 1.5)) / 100.0


def snap_strain(deflection: float, thickness: float, length: float) -> float:
    """Max strain of a rectangular cantilever with end deflection y: eps = 1.5 t y / L^2."""
    return 1.5 * thickness * deflection / (length**2)


def tuned_rules() -> list[str]:
    """Names of the rules marked `tune: true` (the fit gauge calibrates these)."""
    out = []

    def walk(prefix, node):
        if isinstance(node, dict):
            if node.get("tune") is True:
                out.append(prefix)
            for k, v in node.items():
                walk(f"{prefix}.{k}" if prefix else k, v)

    walk("", load_dfm())
    return out


# --------------------------------------------------------------------------- thin-wall analysis


def voxelize_solid(mesh, pitch: float):
    """Solid voxelisation of a closed triangle mesh by z-parity along columns (pure numpy, no rtree).
    Returns (grid[nx, ny, nz] bool, origin xyz of voxel [0,0,0] corner)."""
    import numpy as np

    v = np.asarray(mesh.vertices, float)
    f = np.asarray(mesh.faces, int)
    lo = v.min(axis=0) - pitch
    hi = v.max(axis=0) + pitch
    n = np.ceil((hi - lo) / pitch).astype(int) + 1
    grid = np.zeros(tuple(n), bool)
    jitter = np.array([1.234e-4, 2.718e-4]) * pitch          # keeps sample points off shared triangle edges
    cols: dict[tuple[int, int], list[float]] = {}
    tri = v[f]                                              # (T, 3, 3)
    for t in tri:
        a, b, c = t[0, :2], t[1, :2], t[2, :2]
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-12:
            continue                                         # vertical triangle: parallel to the ray
        x0, x1 = t[:, 0].min(), t[:, 0].max()
        y0, y1 = t[:, 1].min(), t[:, 1].max()
        ix0, ix1 = int(np.floor((x0 - lo[0]) / pitch)), int(np.ceil((x1 - lo[0]) / pitch))
        iy0, iy1 = int(np.floor((y0 - lo[1]) / pitch)), int(np.ceil((y1 - lo[1]) / pitch))
        ix = np.arange(max(ix0, 0), min(ix1, n[0] - 1) + 1)
        iy = np.arange(max(iy0, 0), min(iy1, n[1] - 1) + 1)
        if len(ix) == 0 or len(iy) == 0:
            continue
        px = lo[0] + (ix + 0.5) * pitch + jitter[0]
        py = lo[1] + (iy + 0.5) * pitch + jitter[1]
        PX, PY = np.meshgrid(px, py, indexing="ij")
        l1 = ((b[1] - c[1]) * (PX - c[0]) + (c[0] - b[0]) * (PY - c[1])) / det
        l2 = ((c[1] - a[1]) * (PX - c[0]) + (a[0] - c[0]) * (PY - c[1])) / det
        l3 = 1 - l1 - l2
        inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not inside.any():
            continue
        Z = l1 * t[0, 2] + l2 * t[1, 2] + l3 * t[2, 2]
        ii, jj = np.nonzero(inside)
        for a_, b_ in zip(ii, jj):
            cols.setdefault((int(ix[a_]), int(iy[b_])), []).append(float(Z[a_, b_]))
    zc = lo[2] + (np.arange(n[2]) + 0.5) * pitch
    for (i, j), zs in cols.items():
        zs.sort()
        if len(zs) % 2:
            zs = zs[:-1]                                     # open/odd column: ignore the stray crossing
        for k in range(0, len(zs), 2):
            grid[i, j, (zc >= zs[k]) & (zc <= zs[k + 1])] = True
    return grid, lo


def thin_wall_report(shape, min_mm: float, pitch: float | None = None, max_voxels: int = 25_000_000) -> dict:
    """Find material thinner than `min_mm` by morphological opening of a voxelised solid.

    Material that no ball of radius min_mm/2 (fitting inside the solid) can reach is a wall thinner than `min_mm`.
    Resolution is `pitch` (default: 0.25 mm, coarser only if the grid would exceed `max_voxels`), so walls within one pitch
    of the limit are reported with that tolerance. Features smaller than ~2 pitches (a small chamfer) are ignored by design.
    Returns {'ok', 'thin_volume_mm3', 'thin_fraction', 'pitch_mm', 'worst_location' (mm, shape frame)}.
    """
    import numpy as np
    from scipy import ndimage as ndi

    from .core import mesh_of

    mesh = mesh_of(shape, tol=0.05)
    ext = mesh.bounds[1] - mesh.bounds[0]
    p = pitch or max(0.25, float((np.prod(ext + 2) / max_voxels) ** (1 / 3)))
    grid, origin = voxelize_solid(mesh, p)
    total = float(grid.sum() * p**3)
    edt = ndi.distance_transform_edt(np.pad(grid, 1))[1:-1, 1:-1, 1:-1] * p
    r = min_mm / 2.0
    core = edt >= r - 0.5 * p                       # centres of balls of radius r (half-voxel tolerance)
    if not core.any():
        return {"ok": False, "thin_volume_mm3": total, "thin_fraction": 1.0, "pitch_mm": p, "worst_location": None}
    reached = grid & (ndi.distance_transform_edt(~core) * p <= r + 0.5 * p)
    thin = ndi.binary_opening(grid & ~reached, structure=np.ones((2, 2, 2)))   # drop single-voxel fuzz
    thin_vol = float(thin.sum() * p**3)
    loc = None
    if thin.any():
        c = np.argwhere(thin).mean(axis=0)
        loc = [float(origin[i] + (c[i] + 0.5) * p) for i in range(3)]
    return {"ok": thin_vol < max(0.0005 * total, 1.0), "thin_volume_mm3": thin_vol,
            "thin_fraction": thin_vol / total if total else 0.0, "pitch_mm": p, "worst_location": loc}
