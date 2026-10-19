"""Bolted-joint model: a group of screws plus a compression-only contact patch between two printed parts.

The connection transmits a wrench (force and moment about the group centroid C). With the plane (u, v, d) at the interface, d pointing from the
part that holds the threads (inserts) toward the part that holds the screw heads, the interface is a rigid plane with a separation field
s(u, v) = s0 + a u + b v (positive = parts moving apart). Screws are linear springs that carry tension only (k_b); the patch is a bed of
compression-only springs (k_c per unit area). Equilibrium in the three out-of-plane components (force along d, two moments) gives the screw
tensions and the patch pressure; in-plane shear is shared by the screws (force / n plus torsion about C). No preload credit.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import least_squares
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from .model import Model, SiteRec
from .policy import pv, policy
from .sections import plane_basis, section_geometry

STEEL_E = 200e3                # MPa
THREAD_AREA = {"M2": 2.07, "M2.5": 3.39, "M3": 5.03}           # tensile stress area, mm2 (ISO 898-1)
SHANK_D = {"M2": 2.0, "M2.5": 2.5, "M3": 3.0}
HEAD_D = {"M2": 3.8, "M2.5": 4.5, "M3": 5.5}
HOLE_D = {"M2": 2.4, "M2.5": 2.9, "M3": 3.4}


@dataclass
class Connection:
    child: str
    parent: str
    insert_part: str
    screw_part: str
    centroid: np.ndarray
    d: np.ndarray                    # from the insert part toward the screw part (link frame)
    u: np.ndarray
    v: np.ndarray
    bolts: list[dict]                # {site, p_uv, thread, length, screw_site}
    patch: object | None             # shapely geometry in (u, v)
    patch_area: float
    edge_dist: list[float]           # per bolt: distance to the nearest free edge or hole of the screw part's section
    edge_dist_ins: list[float]
    notes: list[str] = field(default_factory=list)


def _insert_len(thread: str) -> float:
    return {"M2": 3.0, "M2.5": 4.0, "M3": 5.7}.get(thread, 5.7)


def build_connection(model: Model, child: str, parent: str, sites: list[SiteRec]) -> Connection | None:
    ins = [s for s in sites if s.kind == "insert"]
    scr = [s for s in sites if s.kind == "screw"]
    if not ins:
        return None
    ins_part = ins[0].part
    scr_part = parent if ins_part == child else child
    if scr:
        scr_part = scr[0].part
    d = np.mean([s.z for s in ins], axis=0)
    d /= np.linalg.norm(d)
    u, v, n = plane_basis(d)
    C = np.mean([s.p for s in ins], axis=0)
    bolts = []
    for s in ins:
        rel = s.p - C
        match = None
        if scr:
            match = min(scr, key=lambda t: np.linalg.norm((t.p - s.p) - d * float((t.p - s.p) @ d)))
        bolts.append({"site": s, "p_uv": np.array([rel @ u, rel @ v]), "thread": s.thread, "length": (match.length if match else 8.0),
                      "screw_site": match})
    # contact patch: the two parts' sections just inside the interface
    plane_o = C
    g1 = section_geometry(model.parts[ins_part].mesh, plane_o - 0.4 * d, d)
    g2 = section_geometry(model.parts[scr_part].mesh, plane_o + 0.4 * d, d)
    patch, area, ed_s, ed_i = None, 0.0, [], []
    notes = []
    if g1 and g2:
        # both sections are expressed relative to their own origin along the plane; origins differ only along d so (u, v) coincide
        patch = g1[0].intersection(g2[0])
        area = float(patch.area)
    else:
        notes.append("no contact patch found (sections missing): screws take the full load")
    for b in bolts:
        pt = Point(*b["p_uv"])
        for g, lst in ((g2, ed_s), (g1, ed_i)):
            if g:
                rings = []
                for poly in (g[0].geoms if g[0].geom_type != "Polygon" else [g[0]]):
                    rings.append(poly.exterior)
                    rings += [r for r in poly.interiors if Polygon(r).centroid.distance(pt) > 2.5]       # not the bolt's own hole
                lst.append(float(min(pt.distance(r) for r in rings)))
            else:
                lst.append(float("inf"))
    return Connection(child, parent, ins_part, scr_part, C, d, u, v, bolts, patch, area, ed_s, ed_i, notes)


def solve_connection(con: Connection, F_on_insert_from_screw: np.ndarray, M_on_insert_from_screw: np.ndarray, cell: float = 1.0,
                     preload_n: float | None = None) -> dict:
    """Bolt tensions / shears and patch pressure for the load that the SCREW part exerts on the INSERT part, wrench about C in the link frame."""
    d, u, v = con.d, con.u, con.v
    Fd = float(F_on_insert_from_screw @ d)                  # positive = along +d = tension on the bolts (net)
    Mu, Mv = float(M_on_insert_from_screw @ u), float(M_on_insert_from_screw @ v)
    Mz = float(M_on_insert_from_screw @ d)
    Fu, Fv = float(F_on_insert_from_screw @ u), float(F_on_insert_from_screw @ v)
    pts = np.array([b["p_uv"] for b in con.bolts])
    thread = con.bolts[0]["thread"]
    As = THREAD_AREA.get(thread, 5.03)
    Lg = 20.0
    kb = STEEL_E * As / Lg
    # patch cells
    cells = np.zeros((0, 2))
    dA = cell * cell
    if con.patch is not None and not con.patch.is_empty:
        minx, miny, maxx, maxy = con.patch.bounds
        gx, gy = np.meshgrid(np.arange(minx + cell / 2, maxx, cell), np.arange(miny + cell / 2, maxy, cell))
        P = np.column_stack([gx.ravel(), gy.ravel()])
        from shapely import contains_xy
        P = P[contains_xy(con.patch, P[:, 0], P[:, 1])]
        cells = P
    Ep = 1700.0
    kc = Ep * dA / 10.0
    if preload_n is None:
        fr = float(pv(policy()["fasteners"], "preload_fraction_of_clamp", default=0.0))
        clamp = float(policy()["handling"]["screw_clamp_force_n"].get(thread, 0.0))
        preload_n = fr * clamp
    # preloaded joint: bolt force P + kb s while it stays in tension, the patch starts compressed by delta0 = sum(P) / (kc N_cells)
    delta0 = (preload_n * len(pts)) / (kc * len(cells)) if (len(cells) and preload_n > 0) else 0.0

    def forces(x):
        s0, a, b = x
        sb = s0 + a * pts[:, 0] + b * pts[:, 1]
        T = np.maximum(preload_n + kb * sb, 0.0)
        if len(cells):
            sc = s0 + a * cells[:, 0] + b * cells[:, 1]
            Pn = kc * np.maximum(delta0 - sc, 0.0)
        else:
            sc, Pn = np.zeros(0), np.zeros(0)
        return sb, T, sc, Pn

    def resid(x):
        sb, T, sc, Pn = forces(x)
        fz = T.sum() - Pn.sum()
        m_u = (T * pts[:, 1]).sum() - (Pn * cells[:, 1]).sum() if len(cells) else (T * pts[:, 1]).sum()
        m_v = -((T * pts[:, 0]).sum() - (Pn * cells[:, 0]).sum()) if len(cells) else -(T * pts[:, 0]).sum()
        # scale: force units N, moments N.mm / 10 mm
        return np.array([fz - Fd, (m_u - Mu) / 10.0, (m_v - Mv) / 10.0])

    best = None
    for x0 in ([0.0, 0.0, 0.0], [0.001, 0.0, 0.0], [-0.001, 0.0, 0.0], [0.0, 1e-4, 0.0], [0.0, 0.0, 1e-4], [0.0, -1e-4, 0.0], [0.0, 0.0, -1e-4]):
        r = least_squares(resid, x0, xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=200)
        if best is None or r.cost < best.cost:
            best = r
        if r.cost < 1e-6:
            break
    sb, T, sc, Pn = forces(best.x)
    n = len(pts)
    # shear: force / n + torsion about C
    r2 = (pts ** 2).sum()
    V = []
    for i in range(n):
        vi = np.array([Fu / n, Fv / n])
        if r2 > 1e-9:
            # torque Mz about d: tangential force on bolt i = Mz * (d x r) / sum r^2   (2-D rotation of r by +90 deg)
            vi = vi + Mz * np.array([-pts[i, 1], pts[i, 0]]) / r2
        V.append(float(np.linalg.norm(vi)))
    p_max = float(Pn.max() / dA) if len(Pn) else 0.0
    return {"tension": [float(t) for t in T], "shear": V, "patch_pressure_max_mpa": p_max,
            "residual": float(np.linalg.norm(resid(best.x))), "separated": bool(np.any(T <= 1e-6) and Fd + 1e-9 > 0 and False),
            "net_axial_n": Fd, "moment_nmm": [Mu, Mv], "shear_force_n": [Fu, Fv], "torque_nmm": Mz,
            "patch_area_mm2": con.patch_area, "preload_n": float(preload_n)}
