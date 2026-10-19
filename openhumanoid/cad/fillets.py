"""Internal fillets for load-bearing corners (DFM rule `fillet_*` in dfm.yaml; strength check G-strength).

A sharp concave corner in a printed part is a stress raiser (Kt about 2.3 at 0.3 mm effective radius for a 4 mm plate, Kt 1.4 at r = 3 mm) and
the place layer lines open first. `fillet_internal(shape, r)` rounds every long straight concave edge between two planar faces, through the guarded
route of the CAD foundation: the result must be one valid solid that gained a little volume, otherwise the radius is reduced, then the edges are
tried one by one, and what cannot be filleted is reported (never silently skipped).

    concave_edges(shape, min_len)  -> [(Edge, {mid, dir, length, angle_deg})]
    fillet_internal(shape, r=None, min_len=6.0, name="part")  -> (shape, report)
"""
from __future__ import annotations

import math

import build123d as bd
import numpy as np

from . import dfm
from .core import CadOpError, check_solid


LOG: list[dict] = []          # one report per fillet_internal call (the builder or the CLI may print it)


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def edge_faces(shape: bd.Shape):
    """[(Edge, [Face, ...])] faces sharing each edge, matched by midpoint and length."""
    table: dict = {}
    for f in shape.faces():
        for e in f.edges():
            c = e.center()
            key = (round(c.X, 3), round(c.Y, 3), round(c.Z, 3), round(e.length, 3))
            ent = table.setdefault(key, [e, []])
            ent[1].append(f)
    return [(e, fs) for e, fs in table.values()]


def concave_edges(shape: bd.Shape, min_len: float = 3.0, min_angle_deg: float = 20.0) -> list[tuple[bd.Edge, dict]]:
    """Straight edges between two planar faces whose material wedge is larger than 180 degrees (internal corners)."""
    out = []
    for e, faces in edge_faces(shape):
        if e.geom_type != bd.GeomType.LINE or e.length < min_len:
            continue
        if len(faces) != 2 or any(f.geom_type != bd.GeomType.PLANE for f in faces):
            continue
        mid = e.center()
        p = np.array([mid.X, mid.Y, mid.Z])
        e0, e1 = e.start_point(), e.end_point()
        ev = _unit(np.array([e1.X - e0.X, e1.Y - e0.Y, e1.Z - e0.Z]))
        ns, ts = [], []
        for f in faces:
            nn = f.normal_at(mid)
            nv = np.array([nn.X, nn.Y, nn.Z])
            ns.append(nv)
            t = _unit(np.cross(nv, ev))
            ok = None
            for sgn in (1.0, -1.0):
                try:
                    if f.distance_to(bd.Vector(*(p + 0.05 * sgn * t))) < 1e-4:
                        ok = sgn * t
                        break
                except Exception:  # noqa: BLE001
                    pass
            ts.append(ok)
        if ts[0] is None or ts[1] is None:
            continue
        ang = math.degrees(math.acos(max(-1.0, min(1.0, float(ns[0] @ ns[1])))))
        if ang < min_angle_deg:
            continue
        q = p + 0.15 * (ts[0] + ts[1])
        try:
            inside = shape.is_inside(bd.Vector(*q))
        except Exception:  # noqa: BLE001
            continue
        if not inside:
            out.append((e, {"mid": p.tolist(), "dir": ev.tolist(), "length": float(e.length), "angle_deg": ang}))
    return out


def fillet_internal(shape: bd.Shape, r: float | None = None, min_len: float = 6.0, name: str = "part", region: tuple | None = None) -> tuple[bd.Shape, dict]:
    """Fillet all long concave edges of `shape` with radius r (default dfm `fillet_default_mm`). `region` = (min_xyz, max_xyz) limits the edges.
    Returns (shape, report) with the number filleted / skipped; raises CadOpError only if the result is invalid."""
    r = float(r if r is not None else dfm.fillet_default())
    edges = []
    for e, inf in concave_edges(shape, min_len):
        if region is not None:
            lo, hi = np.asarray(region[0]), np.asarray(region[1])
            m = np.asarray(inf["mid"])
            if np.any(m < lo) or np.any(m > hi):
                continue
        edges.append(e)
    rep = {"name": name, "candidates": len(edges), "filleted": 0, "skipped": 0, "radius_mm": r, "notes": []}
    LOG.append(rep)
    if not edges:
        return shape, rep
    v0 = float(shape.volume)

    def try_fillet(es, rad):
        try:
            out = bd.fillet(es, rad)
            check_solid(out, f"{name}: fillet r={rad:.1f}")
            if float(out.volume) < v0 - 1e-6 * v0:
                return None
            return out
        except Exception:  # noqa: BLE001
            return None

    for rad in (r, 0.7 * r, 0.5 * r):
        out = try_fillet(edges, rad)
        if out is not None:
            rep.update(filleted=len(edges), radius_mm=rad)
            if rad < r:
                rep["notes"].append(f"all {len(edges)} edges filleted at {rad:.1f} mm (requested {r:.1f})")
            return out, rep
    cur, done = shape, 0
    for e in edges:                                    # one by one: whatever works
        tgt = None
        for c, _ in concave_edges(cur, min_len):
            m1, m2 = c.center(), e.center()
            if abs(m1.X - m2.X) + abs(m1.Y - m2.Y) + abs(m1.Z - m2.Z) < 1e-2 and abs(c.length - e.length) < 1e-2:
                tgt = c
                break
        if tgt is None:
            rep["skipped"] += 1
            continue
        for rad in (r, 0.6 * r):
            out = try_fillet([tgt], rad)
            if out is not None:
                cur, done = out, done + 1
                break
        else:
            rep["skipped"] += 1
    rep["filleted"] = done
    if rep["skipped"]:
        rep["notes"].append(f"{rep['skipped']} concave edge(s) could not be filleted (vertex blends): check them in the strength report")
    return cur, rep
