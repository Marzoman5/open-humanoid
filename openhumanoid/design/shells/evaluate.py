"""Method-independent evaluation of a ShellSet (what the bake-off scores): look metrics, fit, printability.

Everything here works on the final panel meshes only (mm, knee-axis frame), never on how a method built them.
Needs trimesh with its optional rtree + shapely (ray/closest-point queries, section polygons): `pip install rtree shapely`.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from .spec import KeepOut, LegSpec, PolarRegion, SegProfile, keepout_points, knee_cutter_polygon

PPM = 2.0   # px per mm for the silhouette masks


# ================================================================================================ silhouettes (look)
def _canvas(spec: LegSpec, ppm: float, margin: float = 6.0):
    zs = [s[0] for s in spec.thigh_stations() + spec.shank_stations()]
    z_hi, z_lo = max(zs) + margin, min(zs) - margin
    half = 52.0 * max(spec.width_scale, 1.0)
    return dict(z_hi=z_hi, z_lo=z_lo, half=half, rows=int(round((z_hi - z_lo) * ppm)), cols=int(round(2 * half * ppm)))


@lru_cache(maxsize=16)
def _target_cached(label: str, ppm: float, margin: float, spec_json: str):
    import json

    d = json.loads(spec_json)
    spec = LegSpec(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in d.items()})
    c = _canvas(spec, ppm, margin)
    thigh, shank = SegProfile(spec.thigh_stations()), SegProfile(spec.shank_stations())
    cutter = PolarRegion(knee_cutter_polygon(spec, spec.band))
    from .spec import target_occupancy

    xs = (np.arange(c["cols"]) + 0.5) / ppm - c["half"]
    ys = xs
    front = np.zeros((c["rows"], c["cols"]), bool)
    side = np.zeros_like(front)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    for r in range(c["rows"]):
        z = c["z_hi"] - (r + 0.5) / ppm
        occ = target_occupancy(spec, X, Y, np.full_like(X, z), thigh, shank, cutter)
        front[r] = occ.any(axis=0)     # over x -> function of y
        side[r] = occ.any(axis=1)      # over y -> function of x
    return {"front": front, "side": side, "canvas": c}


def target_silhouettes(spec: LegSpec, ppm: float = PPM, margin: float = 6.0) -> dict:
    """Analytic target silhouettes: front (columns = y, +y right) and side (columns = x, +x right), rows = z downwards."""
    import json
    from dataclasses import asdict

    return _target_cached(spec.label(), ppm, margin, json.dumps(asdict(spec), sort_keys=True))


def candidate_masks(parts: dict, spec: LegSpec, ppm: float = PPM, margin: float = 6.0) -> dict:
    """Rasterise the panels onto the target canvas (filled triangles of the orthographic projection)."""
    from PIL import Image, ImageDraw

    c = _canvas(spec, ppm, margin)
    out = {}
    for view, k in (("front", 1), ("side", 0)):
        img = Image.new("L", (c["cols"], c["rows"]), 0)
        d = ImageDraw.Draw(img)
        for m in parts.values():
            V = np.asarray(m.vertices)
            px = np.c_[(V[:, k] + c["half"]) * ppm, (c["z_hi"] - V[:, 2]) * ppm]
            for t in px[np.asarray(m.faces)]:
                d.polygon([tuple(t[0]), tuple(t[1]), tuple(t[2])], fill=255)
        out[view] = np.asarray(img) > 0
    return out


def iou(a: np.ndarray, b: np.ndarray) -> float:
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def _row_extent(mask: np.ndarray, ppm: float):
    """(left, right) edge in mm for every row (NaN where empty)."""
    any_ = mask.any(axis=1)
    cols = np.arange(mask.shape[1])
    left = np.where(any_, np.argmax(mask, axis=1), np.nan)
    right = np.where(any_, mask.shape[1] - 1 - np.argmax(mask[:, ::-1], axis=1), np.nan)
    return left / ppm, right / ppm, any_


def look_metrics(parts: dict, spec: LegSpec) -> dict:
    """Numbers for the critic and the scoring table: fidelity to the target silhouette, taper, widest points, ledges, flat share."""
    from .. import metrics as dm
    from .. import silhouette as sil
    from ..meshio import Subject

    M: dict = {}
    tm, cm = target_silhouettes(spec), candidate_masks(parts, spec)
    M["T1_iou_front"] = round(iou(cm["front"], tm["front"]), 4)
    M["T1_iou_side"] = round(iou(cm["side"], tm["side"]), 4)
    c = tm["canvas"]
    zrow = lambda z: int(round((c["z_hi"] - z) * PPM - 0.5))
    l, r, ok = _row_extent(cm["front"], PPM)
    width = np.where(ok, r - l, np.nan)       # y-extent by row (mm)
    ls = spec.length_scale
    # widest points (fraction of segment length from its top)
    t_rows = np.arange(zrow(spec.thigh_stations()[-1][0]) + 2, zrow(0.0))
    s_rows = np.arange(zrow(-8.0 * 1.0) + 1, zrow(spec.shank_stations()[-1][0]) - 1)
    t_w = width[t_rows]
    z_of = lambda rows: c["z_hi"] - (rows + 0.5) / PPM
    zt = z_of(t_rows)[np.nanargmax(t_w)]
    zs = z_of(s_rows)[np.nanargmax(width[s_rows])]
    t_top, t_bot = spec.thigh_stations()[-1][0], 0.0
    s_top, s_bot = -8.0, spec.shank_stations()[-1][0]
    M["P9a_thigh_widest_from_top"] = round((t_top - zt) / (t_top - t_bot), 3)
    M["P9b_calf_widest_from_top"] = round((s_top - zs) / (s_top - s_bot), 3)
    # taper: section-area ratios from true cross-sections of the panels (outer envelope of the shell ring)
    A = lambda z: _section_area(parts, z)
    thigh_prox = max(A(z) for z in np.linspace(0.66 * spec.hip_z, 0.92 * spec.hip_z, 5))
    M["P8a_thigh_taper_area"] = round(A(8.0) / thigh_prox, 3) if thigh_prox else None
    calf = max(A(z) for z in np.linspace(-0.62 * 112.5 * ls, -0.43 * 112.5 * ls, 5))   # below the knee pocket
    M["P8b_shank_taper_area"] = round(A(spec.ankle_z + 8.0) / calf, 3) if calf else None
    # ledges + flat share on the committed metric code (studio framing, metres)
    H = (max(m.bounds[1][2] for m in parts.values()) - min(m.bounds[0][2] for m in parts.values())) * 1e-3
    pm = {k: m.copy() for k, m in parts.items()}
    lo = np.min([m.bounds[0] for m in pm.values()], axis=0)
    hi = np.max([m.bounds[1] for m in pm.values()], axis=0)
    for m in pm.values():
        m.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
        m.apply_scale(1e-3)
    led = []
    for view in ("front", "side"):
        P = dm.Profile(sil.rasterise(list(pm.values()), view, H))
        led.append(dm._edge_steps(P, z0=0.02, z1=0.98)["S3_ledge_count"])
    M["S3_ledges_front"], M["S3_ledges_side"] = led
    subj = Subject("leg", pm, H, None, {}, [], "bakeoff", {k: "shell" for k in pm})
    fl = dm._flatness(subj, H)
    M["S4_flat_area_fraction"] = round(fl["S4_flat_area_fraction"], 4)
    M["S4_worst_part_flat_fraction"] = round(fl["S4_worst_part_flat_fraction"], 4)
    return M


def pocket_volume(spec: LegSpec, step: float = 1.0) -> float:
    """Volume (mm^3) the knee pocket removes from the shank shell envelope for this spec's flexion range (analytic target)."""
    from .spec import knee_cutter_polygon as kcp

    prof = SegProfile(spec.shank_stations())
    cut = PolarRegion(kcp(spec, spec.band))
    xs = np.arange(-40, 40, step)
    ys = np.arange(-40, 40, step)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    tot = 0.0
    for z in np.arange(prof.z0, prof.z1, step):
        inside = prof.depth(X, Y, np.full_like(X, z)) <= 0
        tot += float((inside & cut.contains(X, np.full_like(X, z))).sum())
    return tot * step ** 3


def _section_area(parts: dict, z: float) -> float:
    """Filled area (mm^2) of the outer envelope of all panels at height z (union of the section rings, exterior only)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    import trimesh

    polys = []
    for m in parts.values():
        if not (m.bounds[0][2] < z < m.bounds[1][2]):
            continue
        sec = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if sec is None:
            continue
        p2, _ = sec.to_planar(to_2D=np.eye(4), check=False)
        polys += [Polygon(e) for e in (poly.exterior for poly in p2.polygons_full) if len(e.coords) > 3]
    if not polys:
        return 0.0
    u = unary_union([p.buffer(0.45) for p in polys])       # bridge the 0.8 mm reveal gap
    geoms = list(u.geoms) if hasattr(u, "geoms") else [u]
    return float(sum(Polygon(g.exterior).area for g in geoms))


# ======================================================================================================= fit
def _union(parts: dict):
    import trimesh

    return trimesh.util.concatenate(list(parts.values()))


_DIRS = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1],
                  [1, 1, 1], [1, 1, -1], [1, -1, 1], [1, -1, -1], [-1, 1, 1], [-1, 1, -1], [-1, -1, 1], [-1, -1, -1]], float)
_DIRS = _DIRS / np.linalg.norm(_DIRS, axis=1, keepdims=True)


def fit_keepouts(parts: dict, spec: LegSpec) -> dict:
    """Every keep-out sample must lie inside the shell cavity with >= clearance to the nearest shell surface.
    Enclosure: >= 13 of 14 rays from every sample (outside the 1 mm around the reveal gap) cross the shell. Clearance: exact
    point-to-triangle distance to the union of the host segment's panels."""
    import trimesh

    res: dict = {}
    for k in spec.keepouts():
        host = trimesh.util.concatenate([m for n, m in parts.items() if n.startswith(k.host)])
        pts = keepout_points(k, 2.0)
        dist = np.concatenate([trimesh.proximity.closest_point(host, pts[i:i + 800])[1] for i in range(0, len(pts), 800)])
        pts_r = keepout_points(k, 4.0)
        pts_r = pts_r[np.abs(pts_r[:, 0] - spec.seam_x) > spec.seam_gap / 2 + 1.0]     # rays from inside the reveal gap would escape through it
        origins = np.repeat(pts_r, len(_DIRS), axis=0)
        dirs = np.tile(_DIRS, (len(pts_r), 1))
        _, ray_idx, _ = host.ray.intersects_location(origins, dirs, multiple_hits=False)
        hit = np.zeros(len(origins), bool)
        hit[np.unique(ray_idx)] = True
        per_point = hit.reshape(len(pts_r), len(_DIRS)).sum(axis=1)
        enclosed = bool((per_point >= 13).all())
        res[k.name] = {"min_clearance_mm": round(float(dist.min()), 3), "enclosed": enclosed,
                       "worst_point_rays_hit": int(per_point.min()),
                       "ok": bool(enclosed and dist.min() >= spec.clearance - 0.05)}
    res["all_ok"] = all(v["ok"] for v in res.values())
    return res


def _manifolds(parts: dict, prefix: str):
    from .meshutil import to_manifold

    ms = [to_manifold(m) for n, m in parts.items() if n.startswith(prefix)]
    out = ms[0]
    for m in ms[1:]:
        out = out + m
    return out


def rom_sweep(parts: dict, spec: LegSpec, step_deg: float = 5.0) -> dict:
    """Flex the shank 0..flex_max about the knee axis; at every step boolean-intersect thigh and shank panels (collision
    volume) and track the closest approach (dense surface samples, exact refinement at the worst step)."""
    import trimesh
    from scipy.spatial import cKDTree

    from .meshutil import to_manifold
    from .render import rotate_shank

    thigh = {n: m for n, m in parts.items() if n.startswith("thigh")}
    shank = {n: m for n, m in parts.items() if n.startswith("shank")}
    t_m = _manifolds(thigh, "thigh")
    t_all = trimesh.util.concatenate(list(thigh.values()))
    s_all = trimesh.util.concatenate(list(shank.values()))
    t_pts = np.vstack([t_all.sample(60000), t_all.vertices])
    tree = cKDTree(t_pts)
    s_pts = np.vstack([s_all.sample(40000), s_all.vertices])
    rows = []
    for th in np.arange(0.0, spec.flex_max_deg + 1e-9, step_deg):
        R = rotate_shank(trimesh.Trimesh(s_pts, np.zeros((0, 3), int), process=False), th).vertices
        dmin = float(tree.query(R)[0].min())
        moved = trimesh.util.concatenate([rotate_shank(m, th) for m in shank.values()])
        try:
            vol = float((t_m ^ to_manifold(moved)).volume())
        except Exception:
            vol = float("nan")
        rows.append({"theta": float(th), "approx_min_gap_mm": round(dmin, 3), "collision_mm3": round(vol, 3)})
    worst = min(rows, key=lambda r: r["approx_min_gap_mm"])
    # exact distance at the worst step
    mv = trimesh.util.concatenate([rotate_shank(m, worst["theta"]) for m in shank.values()])
    near = np.argsort(tree.query(mv.vertices)[0])[:300]                  # refine only the closest candidates
    exact = float(trimesh.proximity.closest_point(t_all, mv.vertices[near])[1].min())
    colliding = [r["theta"] for r in rows if (r["collision_mm3"] != r["collision_mm3"]) or r["collision_mm3"] > 0.5]
    return {"collision_free": not colliding, "colliding_thetas": colliding[:10],
            "min_gap_mm": round(min(exact, worst["approx_min_gap_mm"]), 3), "min_gap_at_deg": worst["theta"],
            "gap_at_0deg_mm": next(r["approx_min_gap_mm"] for r in rows if r["theta"] == 0.0), "steps": rows}


# ================================================================================================ printability
def wall_thickness(m, n: int = 5000, seed: int = 0, tol: float = 1.45, edge_mm: float = 1.5, seam_x: float | None = None) -> dict:
    """Local wall thickness: from points sampled on the surface, shoot a ray inwards (-normal) and take the first hit.
    `min_mm` is over all samples (knife edges at the pocket rim and the cap/panel borders count). `interior_min_mm`
    ignores samples within `edge_mm` of a sharp edge (> 40 deg), which is the wall of the free surface."""
    import trimesh
    from scipy.spatial import cKDTree

    pts, fidx = trimesh.sample.sample_surface(m, n, seed=seed)
    nrm = m.face_normals[fidx]
    off = 0.05                                  # start the ray a little inside so it cannot re-hit its own facet
    o = pts - nrm * off
    loc, ridx, _ = m.ray.intersects_location(o, -nrm, multiple_hits=False)
    t = np.full(len(pts), np.nan)
    if len(ridx):
        d = np.linalg.norm(loc - o[ridx], axis=1) + off
        order = np.argsort(d)[::-1]            # write far hits first so the nearest hit per ray wins
        t[ridx[order]] = d[order]
    ok = ~np.isnan(t)
    if not ok.any():
        return {"min_mm": None}
    sharp = m.face_adjacency_angles > np.radians(40)
    edge_pts = m.vertices[m.face_adjacency_edges[sharp]].mean(axis=1) if sharp.any() else np.zeros((0, 3))
    near_edge = cKDTree(edge_pts).query(pts)[0] < edge_mm if len(edge_pts) else np.zeros(len(pts), bool)
    if seam_x is not None:                      # the panel border: rays near it exit through the seam face
        near_edge |= np.abs(pts[:, 0] - seam_x) < 3.0
    tt, ti = t[ok], t[ok & ~near_edge]
    return {"min_mm": round(float(tt.min()), 3), "interior_min_mm": round(float(ti.min()), 3) if len(ti) else None,
            "interior_p1_mm": round(float(np.percentile(ti, 1)), 3) if len(ti) else None,
            "p1_mm": round(float(np.percentile(tt, 1)), 3), "p5_mm": round(float(np.percentile(tt, 5)), 3),
            "median_mm": round(float(np.median(tt)), 3), "frac_below_1.2mm": round(float((tt < 1.2).mean()), 4),
            "frac_below_tol": round(float((tt < tol).mean()), 4), "n": int(len(tt))}


_UPS = {"+z": (0, 0, 1), "-z": (0, 0, -1), "+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0)}


def _rot_to_z(up) -> np.ndarray:
    import trimesh

    up = np.asarray(up, float)
    return trimesh.geometry.align_vectors(up, [0, 0, 1])


def overhang(m, up, limit_deg: float = 45.0) -> dict:
    """Area (mm^2) of faces that need support when `up` is the build direction: downward-facing beyond `limit_deg` from
    vertical and not touching the bed."""
    T = _rot_to_z(up)
    mm = m.copy()
    mm.apply_transform(T)
    mm.apply_translation([0, 0, -mm.bounds[0][2]])
    nz = mm.face_normals[:, 2]
    zmin = mm.triangles[:, :, 2].min(axis=1)
    bed = (zmin < 0.25) & (nz < -0.99)
    need = (nz < -math.cos(math.radians(limit_deg)) + 1e-9) & ~bed
    A = mm.area_faces
    ext = mm.extents
    fits = _fits_bed(mm)
    return {"overhang_mm2": round(float(A[need].sum()), 1), "overhang_frac": round(float(A[need].sum() / A.sum()), 4),
            "bed_contact_mm2": round(float(A[bed].sum()), 1), "height_mm": round(float(ext[2]), 1), "fits_bed": fits}


def _fits_bed(m, bed=(220.0, 220.0, 250.0)) -> bool:
    if m.extents[2] > bed[2]:
        return False
    v = m.vertices[:, :2]
    for a in np.radians(np.arange(0, 90, 5)):
        R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        e = (v @ R.T).max(axis=0) - (v @ R.T).min(axis=0)
        if e[0] <= bed[0] and e[1] <= bed[1]:
            return True
    return False


def printability(parts: dict, spec: LegSpec, with_wall: bool = True) -> dict:
    import manifold3d as mf

    out: dict = {"parts": {}}
    for name, m in parts.items():
        d: dict = {"faces": int(len(m.faces)), "watertight": bool(m.is_watertight), "winding_ok": bool(m.is_winding_consistent),
                   "volume_mm3": round(float(abs(m.volume)), 1), "euler": int(m.euler_number),
                   "extents_mm": [round(float(v), 1) for v in m.extents]}
        try:
            mm = mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
            d["manifold3d_valid"] = mm.status() == mf.Error.NoError
        except Exception:
            d["manifold3d_valid"] = False
        if with_wall:
            d["wall"] = wall_thickness(m, seam_x=spec.seam_x)
        orient = {u: overhang(m, v) for u, v in _UPS.items()}
        feas = {u: o for u, o in orient.items() if o["fits_bed"]}
        best = min(feas, key=lambda u: feas[u]["overhang_mm2"]) if feas else None
        d["orientations"] = orient
        d["best_orientation"] = best
        d["best_overhang_mm2"] = feas[best]["overhang_mm2"] if best else None
        d["best_overhang_frac"] = feas[best]["overhang_frac"] if best else None
        d["best_bed_contact_mm2"] = feas[best]["bed_contact_mm2"] if best else None
        d["fits_bed"] = bool(feas)
        out["parts"][name] = d
    P = out["parts"].values()
    out["part_count"] = len(parts)
    out["all_watertight"] = all(d["watertight"] and d["winding_ok"] and d["manifold3d_valid"] for d in P)
    out["all_fit_bed"] = all(d["fits_bed"] for d in P)
    walls = [d["wall"]["min_mm"] for d in P if with_wall and d["wall"].get("min_mm") is not None]
    inner = [d["wall"]["interior_min_mm"] for d in P if with_wall and d["wall"].get("interior_min_mm") is not None]
    out["min_wall_mm"] = min(walls) if walls else None
    out["interior_min_wall_mm"] = min(inner) if inner else None
    p1i = [d["wall"]["interior_p1_mm"] for d in P if with_wall and d["wall"].get("interior_p1_mm") is not None]
    out["interior_p1_wall_mm"] = min(p1i) if p1i else None
    out["wall_ok"] = bool(p1i) and min(p1i) >= spec.wall - 0.2     # 1st percentile of interior samples; tolerance covers tessellation / marching cubes
    out["p1_wall_mm"] = min((d["wall"].get("p1_mm") for d in P if with_wall and d["wall"].get("p1_mm") is not None), default=None)
    out["total_overhang_mm2"] = round(sum(d["best_overhang_mm2"] or 0 for d in P), 1)
    out["seams"] = [{"segment": s, "plane": f"x = {spec.seam_x:+.1f} mm (coronal, on the side planes)", "reveal_gap_mm": spec.seam_gap}
                    for s in ("thigh", "shank")]
    return out


def evaluate(parts: dict, spec: LegSpec, with_wall: bool = True, rom_step: float = 5.0) -> dict:
    """Run everything. Slow parts (wall rays, ROM sweep) can be skipped via arguments for smoke tests."""
    return {"look": look_metrics(parts, spec), "fit": {"keepouts": fit_keepouts(parts, spec), "rom": rom_sweep(parts, spec, rom_step)},
            "print": printability(parts, spec, with_wall)}
