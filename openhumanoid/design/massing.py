"""profiles -> smooth massing mesh.

Each segment is a loft of superellipse sections whose width/depth/exponent vary smoothly (PCHIP) along the segment axis,
evaluated as an approximate signed distance field. Segments are merged with a polynomial smooth-min, so joints blend
instead of creasing, and the zero level set is meshed with marching cubes. This is a *massing*, not a production shell:
it fixes the silhouette and form language (ADR 0010 step D2). Production shells are a later CAD task.
"""
from __future__ import annotations

import numpy as np
from scipy.interpolate import PchipInterpolator

DEFAULT_VOXEL_DIV = 250  # voxel = height / 250  (2 mm for a 0.5 m robot)
DEFAULT_K_DIV = 40       # smooth-union radius = height / 40 (12.5 mm at 0.5 m)


def superellipse_sd(u, v, a, b, n):
    """Approximate signed distance (first-order) to the superellipse |u/a|^n + |v/b|^n = 1. Negative inside."""
    a = np.maximum(a, 1e-5)
    b = np.maximum(b, 1e-5)
    pu = np.abs(u) / a
    pv = np.abs(v) / b
    g = np.maximum((pu ** n + pv ** n) ** (1.0 / n), 1e-6)
    gu = g ** (1 - n) * pu ** (n - 1) / a
    gv = g ** (1 - n) * pv ** (n - 1) / b
    gm = np.maximum(np.sqrt(gu * gu + gv * gv), 0.5 / np.maximum(a, b))
    return (g - 1.0) / gm


class SegmentField:
    """Signed-distance evaluator for one expanded segment."""

    def __init__(self, seg: dict):
        self.id = seg["id"]
        self.axis = seg["axis"]
        self.k_m = seg.get("k_m")
        st = seg["stations"]
        t = np.array([s[self.axis] for s in st], float)
        self.t0, self.t1 = float(t[0]), float(t[-1])

        def mk(key):
            vals = np.array([s[key] for s in st], float)
            return PchipInterpolator(t, vals, extrapolate=False)

        self.w, self.d, self.n = mk("w"), mk("d"), mk("n")
        self.cx, self.cy, self.cz = mk("cx"), mk("cy"), mk("cz")
        # bounding box (with the section extent) for local evaluation
        wmax = max(s["w"] for s in st)
        dmax = max(s["d"] for s in st)
        cxs = [s["cx"] for s in st]; cys = [s["cy"] for s in st]; czs = [s["cz"] for s in st]
        if self.axis == "z":
            lo = [min(cxs) - dmax / 2, min(cys) - wmax / 2, self.t0]
            hi = [max(cxs) + dmax / 2, max(cys) + wmax / 2, self.t1]
        else:
            lo = [self.t0, min(cys) - wmax / 2, min(czs) - dmax / 2]
            hi = [self.t1, max(cys) + wmax / 2, max(czs) + dmax / 2]
        self.lo, self.hi = np.array(lo), np.array(hi)

    def sdf(self, X, Y, Z):
        if self.axis == "z":
            s, p, q = Z, Y, X  # section coords: u=y (width), v=x (depth)
        else:
            s, p, q = X, Y, Z  # section coords: u=y (width), v=z (depth)
        sc = np.clip(s, self.t0, self.t1)
        w, d, n = self.w(sc), self.d(sc), self.n(sc)
        cy = self.cy(sc)
        c2 = self.cx(sc) if self.axis == "z" else self.cz(sc)
        d2 = superellipse_sd(p - cy, q - c2, w / 2, d / 2, n)
        dz = np.maximum(self.t0 - s, s - self.t1)  # >0 beyond the end caps
        return np.minimum(np.maximum(d2, dz), 0.0) + np.hypot(np.maximum(d2, 0.0), np.maximum(dz, 0.0))


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def fields(profiles: dict) -> list[SegmentField]:
    return [SegmentField(s) for s in profiles["segments"]]


def sdf_union(profiles: dict, pts: np.ndarray, segments: list[SegmentField] | None = None) -> np.ndarray:
    """Smooth-union SDF at points (N,3)."""
    k0 = profiles.get("blend", {}).get("k_m", profiles["height_m"] / DEFAULT_K_DIV)
    out = np.full(len(pts), 1e3)
    for f in segments or fields(profiles):
        k = k0 if f.k_m is None else f.k_m
        out = smin(out, f.sdf(pts[:, 0], pts[:, 1], pts[:, 2]), k)
    return out


def build_massing(profiles: dict, voxel_m: float | None = None, smooth_iters: int = 10):
    """Return (trimesh.Trimesh, face_labels: list[str] segment id per face)."""
    import trimesh
    from skimage.measure import marching_cubes

    H = profiles["height_m"]
    blend = profiles.get("blend", {})
    voxel = voxel_m or blend.get("voxel_m") or H / DEFAULT_VOXEL_DIV
    k0 = blend.get("k_m", H / DEFAULT_K_DIV)
    segs = fields(profiles)
    pad = 2 * voxel + k0
    lo = np.min([f.lo for f in segs], axis=0) - pad
    hi = np.max([f.hi for f in segs], axis=0) + pad
    xs = np.arange(lo[0], hi[0], voxel); ys = np.arange(lo[1], hi[1], voxel); zs = np.arange(lo[2], hi[2], voxel)
    field = np.full((len(xs), len(ys), len(zs)), 1e3, dtype=np.float32)
    label = np.full(field.shape, -1, dtype=np.int16)
    for i, f in enumerate(segs):
        k = k0 if f.k_m is None else f.k_m
        flo, fhi = f.lo - pad, f.hi + pad
        ix = np.where((xs >= flo[0]) & (xs <= fhi[0]))[0]
        iy = np.where((ys >= flo[1]) & (ys <= fhi[1]))[0]
        iz = np.where((zs >= flo[2]) & (zs <= fhi[2]))[0]
        if not (len(ix) and len(iy) and len(iz)):
            continue
        sl = np.ix_(ix, iy, iz)
        X, Y, Z = np.meshgrid(xs[ix], ys[iy], zs[iz], indexing="ij")
        d = f.sdf(X, Y, Z).astype(np.float32)
        cur = field[sl]
        field[sl] = smin(cur, d, k)
        lab = label[sl]
        lab[d < cur] = i
        label[sl] = lab
    verts, faces, normals, _ = marching_cubes(field, level=0.0, spacing=(voxel, voxel, voxel))
    verts = verts + lo
    mesh = trimesh.Trimesh(verts, faces, process=False)
    if smooth_iters:
        trimesh.smoothing.filter_taubin(mesh, iterations=smooth_iters)
    # smooth-shading normals: central differences of the analytic field at the vertices (the triangulation is only
    # voxel-accurate, the field is smooth)
    eps = voxel * 0.5
    V = np.asarray(mesh.vertices)
    grad = np.zeros_like(V)
    for ax in range(3):
        dv = np.zeros(3); dv[ax] = eps
        grad[:, ax] = sdf_union(profiles, V + dv, segs) - sdf_union(profiles, V - dv, segs)
    nrm = grad / (np.linalg.norm(grad, axis=1, keepdims=True) + 1e-12)
    mesh._cache.clear()
    mesh.metadata["sdf_normals"] = nrm
    # label faces by the nearest-voxel owner
    cent = verts[faces].mean(axis=1)
    idx = np.clip(np.round((cent - lo) / voxel).astype(int), 0, np.array(field.shape) - 1)
    lab = label[idx[:, 0], idx[:, 1], idx[:, 2]]
    face_labels = [segs[l].id if l >= 0 else "unlabelled" for l in lab]
    return mesh, face_labels


def split_by_label(mesh, face_labels) -> dict:
    """Split a labelled massing into per-segment sub-meshes (for per-part metrics)."""
    labels = np.array(face_labels)
    parts = {}
    for name in sorted(set(face_labels)):
        sel = np.where(labels == name)[0]
        if len(sel):
            parts[name] = mesh.submesh([sel], append=True)
    return parts


def hard_point_margins(profiles: dict) -> list[dict]:
    """For each hard point box, the minimum clearance (m) between the box and the enclosing surface.
    Positive = the box is inside with that much wall + gap to spare. Uses the named segment's field, else the union."""
    segs = {f.id: f for f in fields(profiles)}
    res = []
    for hp in profiles.get("hard_points", []):
        c = np.array(hp["center"], float)
        h = np.array(hp["size"], float) / 2
        g = np.array([[sx, sy, sz] for sx in (-1, 0, 1) for sy in (-1, 0, 1) for sz in (-1, 0, 1)], float)
        pts = c + g * h
        if hp.get("segment") and hp["segment"] in segs:
            f = segs[hp["segment"]]
            d = f.sdf(pts[:, 0], pts[:, 1], pts[:, 2])
        else:
            d = sdf_union(profiles, pts, list(segs.values()))
        margin = float(-np.max(d))
        need = hp.get("margin_m", 0.0)
        res.append({"id": hp["id"], "segment": hp.get("segment"), "margin_m": round(margin, 5),
                    "required_m": need, "pass": margin >= need})
    return res
