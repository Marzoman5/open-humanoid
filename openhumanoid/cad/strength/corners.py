"""Internal corners of a B-rep part: sharp concave edges (radius 0) and concave fillets, with their position, direction, length and radius.

These are the places where a printed part cracks first (stress concentration, and the layer lines may open across them). The section
check raises the stress of sections that cut near a corner transverse to its direction (Kt from stress_concentration in strength.yaml).

    corners(shape) -> [ {kind: 'sharp'|'fillet', mid: [x,y,z], dir: [dx,dy,dz], length, r, angle_deg} ]

Straight concave edges between two planar faces are 'sharp'. Cylindrical faces that are concave, span less than ~200 degrees and are at
least 3 mm long are 'fillet' with their radius (a hole spans 360 degrees and is skipped).
"""
from __future__ import annotations

import math

import build123d as bd
import numpy as np


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def corners(shape: bd.Shape, min_len: float = 3.0) -> list[dict]:
    out: list[dict] = []
    solid = shape
    # ---- concave cylinders (fillets)
    for f in shape.faces():
        if f.geom_type != bd.GeomType.CYLINDER:
            continue
        try:
            r = float(f.radius)
            ctr = f.center()
            n = f.normal_at(ctr)
            bb = f.bounding_box()
            # axis direction of the cylinder
            ax = _cyl_axis(f)
            if ax is None:
                continue
            org, adir = ax
            length = _extent_along(f, adir)
            if length < min_len or r > 12.0:
                continue
            span = f.area / max(r * length, 1e-9)
            if span > 3.5:                  # hole or full boss
                continue
            c = np.array([ctr.X, ctr.Y, ctr.Z])
            nv = np.array([n.X, n.Y, n.Z])
            # concave when the outward normal points toward the axis
            radial = _unit((c - org) - adir * float((c - org) @ adir))
            if float(nv @ radial) < 0:
                out.append({"kind": "fillet", "mid": c.tolist(), "dir": adir.tolist(), "length": float(length), "r": r, "angle_deg": math.degrees(span)})
        except Exception:  # noqa: BLE001
            continue
    # ---- sharp straight concave edges between two planar faces
    seen = set()
    for e, faces in _edge_faces(shape):
        if e.geom_type != bd.GeomType.LINE or e.length < min_len:
            continue
        if len(faces) != 2 or any(f.geom_type != bd.GeomType.PLANE for f in faces):
            continue
        mid = e.center()
        p = np.array([mid.X, mid.Y, mid.Z])
        e0 = e.start_point()
        e1 = e.end_point()
        ev = _unit(np.array([e1.X - e0.X, e1.Y - e0.Y, e1.Z - e0.Z]))
        ns = []
        ts = []
        for f in faces:
            nn = f.normal_at(mid)
            nv = np.array([nn.X, nn.Y, nn.Z])
            ns.append(nv)
            t = _unit(np.cross(nv, ev))
            ok = None
            for sgn in (1.0, -1.0):
                q = p + 0.05 * sgn * t
                try:
                    if f.distance_to(bd.Vector(*q)) < 1e-4:
                        ok = sgn * t
                        break
                except Exception:  # noqa: BLE001
                    pass
            ts.append(ok)
        if ts[0] is None or ts[1] is None:
            continue
        ang = math.degrees(math.acos(max(-1.0, min(1.0, float(ns[0] @ ns[1])))))
        if ang < 20:
            continue
        q = p + 0.15 * (ts[0] + ts[1])
        try:
            inside = solid.is_inside(bd.Vector(*q))
        except Exception:  # noqa: BLE001
            continue
        if not inside:                      # free wedge: the edge is concave
            key = (tuple(np.round(p, 1)), tuple(np.round(ev, 2)))
            if key in seen:
                continue
            seen.add(key)
            out.append({"kind": "sharp", "mid": p.tolist(), "dir": ev.tolist(), "length": float(e.length), "r": 0.0, "angle_deg": ang})
    return out


def _edge_faces(shape: bd.Shape):
    """[(Edge, [Face, ...])]: faces sharing each edge, matched by the edge's midpoint and length (robust against wrapper identity)."""
    table: dict = {}
    for f in shape.faces():
        for e in f.edges():
            c = e.center()
            key = (round(c.X, 3), round(c.Y, 3), round(c.Z, 3), round(e.length, 3))
            ent = table.setdefault(key, [e, []])
            ent[1].append(f)
    return [(e, fs) for e, fs in table.values()]


def _cyl_axis(f: bd.Face):
    try:
        from OCP.BRepAdaptor import BRepAdaptor_Surface

        cyl = BRepAdaptor_Surface(f.wrapped).Cylinder()
        ax = cyl.Axis()
        loc, d = ax.Location(), ax.Direction()
        return np.array([loc.X(), loc.Y(), loc.Z()]), np.array([d.X(), d.Y(), d.Z()])
    except Exception:  # noqa: BLE001
        return None


def _extent_along(f: bd.Face, adir: np.ndarray) -> float:
    pts = [np.array([v.X, v.Y, v.Z]) for v in f.vertices()]
    if not pts:
        return 0.0
    proj = [float(p @ adir) for p in pts]
    return max(proj) - min(proj)
