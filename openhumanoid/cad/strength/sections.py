"""Cross-section engine: slice a part mesh with a plane, build the *effective* (print-profile-weighted) section and evaluate stresses.

A cut is a valid free-body separation of the part (a plane splits space in two; the two halves touch only through the section), so the
internal wrench at any plane follows from the loads applied on ONE side. The section is weighted by the print profile: material within
`shell` of the outline is solid (perimeters), the interior carries `infill` of the stress (weight < 1).

Conventions: plane basis (u, v, n) is right-handed with n pointing from the near side to the far side. Stress resultants are those
transmitted from the near body to the far body:
    N  : tension positive,  V = (Vu, Vv): shear,  T: torsion about n,  M_int = internal moment vector about the centroid (3D).
Linear normal-stress field s(u, v) = N/A + a u + b v, with [P, Q] = [Sxx Sxy; Sxy Syy] [a, b],  P = M_int . v,  Q = -(M_int . u).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union


# --------------------------------------------------------------------------------------------------------------- polygon moments
def _ring_moments(coords) -> tuple[float, float, float, float, float, float]:
    """A, Cx*A (first moments Sx=int x, Sy=int y), Ixx_o=int y^2, Iyy_o=int x^2, Ixy_o=int xy about the ORIGIN (signed by orientation)."""
    x = np.asarray([c[0] for c in coords], float)
    y = np.asarray([c[1] for c in coords], float)
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y
    A = 0.5 * cr.sum()
    Sx = ((x + x1) * cr).sum() / 6.0
    Sy = ((y + y1) * cr).sum() / 6.0
    Iyy = ((x * x + x * x1 + x1 * x1) * cr).sum() / 12.0
    Ixx = ((y * y + y * y1 + y1 * y1) * cr).sum() / 12.0
    Ixy = ((x * y1 + 2 * x * y + 2 * x1 * y1 + x1 * y) * cr).sum() / 24.0
    return A, Sx, Sy, Ixx, Iyy, Ixy


def poly_moments(p: Polygon) -> np.ndarray:
    """[A, int x, int y, int y^2, int x^2, int xy] about the origin, holes subtracted."""
    tot = np.zeros(6)
    ext = np.array(_ring_moments(list(p.exterior.coords)[:-1]))
    tot += ext * (1 if ext[0] > 0 else -1)
    for h in p.interiors:
        r = np.array(_ring_moments(list(h.coords)[:-1]))
        tot -= r * (1 if r[0] > 0 else -1)
    return tot


def _polys(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [q for q in getattr(g, "geoms", []) if q.geom_type == "Polygon" and not q.is_empty]


@dataclass
class Section:
    """One cut of one part. Frame: origin `c` (weighted centroid, 3D, part frame), basis (u, v, n)."""
    pos: float                       # position of the plane along the normal (mm, part frame)
    normal: np.ndarray               # n (unit), pointing to the far side
    u: np.ndarray
    v: np.ndarray
    c: np.ndarray                    # weighted centroid, 3D
    A: float                         # weighted area
    A_solid: float
    Suu: float                       # int u^2 dA (weighted, about the centroid)
    Svv: float
    Suv: float
    J: float                         # torsion constant (effective)
    t_min: float                     # thin dimension (mm) of the largest component
    t_tors: float                    # thickness used in tau = T t / J (wall for closed cells, thin dimension for solid)
    n_cells: int                     # closed cells (holes)
    verts_uv: np.ndarray             # exterior vertices (u, v) relative to the centroid, for fibre extremes
    bbox_uv: tuple                   # (umin, umax, vmin, vmax) relative to the centroid
    shell: float
    fill: float

    def to3(self, u: float, v: float) -> np.ndarray:
        return self.c + u * self.u + v * self.v


def plane_basis(normal: np.ndarray, hint: np.ndarray | None = None):
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    if hint is None:
        hint = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = hint - n * float(hint @ n)
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    return u, v, n


def slice_mesh(mesh: trimesh.Trimesh, origin: np.ndarray, normal: np.ndarray, shell: float, fill: float) -> Section | None:
    """Effective section of `mesh` by the plane through `origin` with normal `normal`. None when the plane misses the part."""
    u, v, n = plane_basis(normal)
    try:
        path = mesh.section(plane_origin=origin, plane_normal=n)
    except Exception:  # noqa: BLE001
        return None
    if path is None:
        return None
    # planar polygons in our own (u, v) coordinates
    pts3 = None
    polys = []
    try:
        M = np.eye(4)
        M[0, :3], M[1, :3], M[2, :3] = u, v, n
        M[:3, 3] = -M[:3, :3] @ origin
        planar, _ = path.to_planar(to_2D=M, check=False)
        polys = list(planar.polygons_full)
    except Exception:  # noqa: BLE001
        return None
    polys = [p for p in polys if p.area > 1e-6]
    if not polys:
        return None
    geom = unary_union(polys)
    comps = _polys(geom)
    if not comps:
        return None
    # weighted moments about the origin of the (u, v) plane
    tot = np.zeros(6)
    A_solid = 0.0
    n_cells = 0
    verts = []
    for p in comps:
        A_solid += p.area
        n_cells += len(p.interiors)
        verts.append(np.array(p.exterior.coords)[:-1])
        core = p.buffer(-shell) if shell > 0 else None
        core_polys = _polys(core) if core is not None and not core.is_empty else []
        core_area = sum(q.area for q in core_polys)
        # ring weight 1, core weight `fill`
        m_all = poly_moments(p)
        m_core = sum((poly_moments(q) for q in core_polys), np.zeros(6)) if core_polys else np.zeros(6)
        tot += m_all - (1.0 - fill) * m_core if core_polys else m_all
    A = tot[0]
    if A < 1e-6:
        return None
    cu, cv = tot[1] / A, tot[2] / A
    Suu = tot[4] - A * cu * cu       # int u^2
    Svv = tot[3] - A * cv * cv       # int v^2
    Suv = tot[5] - A * cu * cv
    allv = np.vstack(verts) - np.array([cu, cv])
    # thin dimension of the largest component, in its own principal frame (rotating calipers via the minimum-area rectangle)
    big = max(comps, key=lambda q: q.area)
    try:
        mrr = big.minimum_rotated_rectangle
        xs = np.array(mrr.exterior.coords)[:-1]
        e1, e2 = np.linalg.norm(xs[1] - xs[0]), np.linalg.norm(xs[2] - xs[1])
        t_min = float(min(e1, e2))
    except Exception:  # noqa: BLE001
        t_min = float(math.sqrt(big.area))
    # torsion constant: closed single cell -> Bredt (4 Am^2 t / Pm); solid -> A^4 / (40 Ip)
    Ip = Suu + Svv
    J = max(A_solid ** 4 / (40.0 * max(Ip, 1e-9)), 1e-6)
    t_tors = t_min
    if n_cells >= 1:
        p0 = big
        hole = Polygon(p0.interiors[0]) if len(p0.interiors) else None
        if hole is not None:
            t_wall = max((p0.area) / max(0.5 * (p0.exterior.length + hole.exterior.length), 1e-6), shell)
            Am = hole.area + 0.5 * hole.exterior.length * t_wall
            Pm = hole.exterior.length + 2 * math.pi * 0.5 * t_wall
            Jc = 4.0 * Am * Am * t_wall / Pm
            if Jc > J:
                J, t_tors = Jc, t_wall
    c3 = origin + cu * u + cv * v
    bbox = (float(allv[:, 0].min()), float(allv[:, 0].max()), float(allv[:, 1].min()), float(allv[:, 1].max()))
    return Section(pos=float(origin @ n), normal=n, u=u, v=v, c=c3, A=float(A), A_solid=float(A_solid), Suu=float(Suu), Svv=float(Svv),
                   Suv=float(Suv), J=float(J), t_min=t_min, t_tors=float(t_tors), n_cells=n_cells, verts_uv=allv, bbox_uv=bbox, shell=shell, fill=fill)


# ------------------------------------------------------------------------------------------------------------------- stresses
@dataclass
class StressResult:
    sigma: float            # max |normal stress| at the extreme fibre (MPa), tension or compression
    sigma_tension: float    # max tensile stress (MPa)
    tau: float              # shear stress estimate (V + torsion) at the same section (MPa)
    N: float
    Vu: float
    Vv: float
    T: float
    Mu: float               # |M| components in the plane (N.mm)
    Mv: float
    where: np.ndarray       # 3D point of the max-tension fibre
    bending_axis: float


def stress(sec: Section, F_int: np.ndarray, M_int: np.ndarray, shear_form: float = 1.5) -> StressResult:
    """Stresses from the internal wrench (F_int, M_int about the section centroid) the near body exerts on the far body."""
    n, u, v = sec.normal, sec.u, sec.v
    m_out = -n                                  # outward normal of the far body at the cut
    N = float(F_int @ m_out)                    # tension positive
    Vu, Vv = float(F_int @ u), float(F_int @ v)
    P = float(M_int @ v)
    Q = -float(M_int @ u)
    S = np.array([[sec.Suu, sec.Suv], [sec.Suv, sec.Svv]])
    try:
        ab = np.linalg.solve(S + 1e-9 * np.eye(2), np.array([P, Q]))
    except np.linalg.LinAlgError:
        ab = np.zeros(2)
    s = N / sec.A + ab[0] * sec.verts_uv[:, 0] + ab[1] * sec.verts_uv[:, 1]
    i_t = int(np.argmax(s))
    T = float(M_int @ n)
    tau_v = shear_form * math.hypot(Vu, Vv) / sec.A
    tau_t = abs(T) * sec.t_tors / sec.J
    return StressResult(sigma=float(np.max(np.abs(s))), sigma_tension=float(s[i_t]), tau=float(tau_v + tau_t), N=N, Vu=Vu, Vv=Vv, T=T,
                        Mu=float(M_int @ u), Mv=float(M_int @ v),
                        where=sec.to3(float(sec.verts_uv[i_t, 0]), float(sec.verts_uv[i_t, 1])), bending_axis=float(math.degrees(math.atan2(ab[1], ab[0]))))


def combined(res: StressResult, kt: float = 1.0) -> float:
    """Equivalent stress for the allowable comparison: sqrt((Kt * sigma)^2 + 3 tau^2)."""
    return math.sqrt((kt * res.sigma) ** 2 + 3.0 * res.tau ** 2)
