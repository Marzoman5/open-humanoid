"""The shared test piece for the shell-method bake-off (T-20261019-9746): one leg segment, thigh + knee + shank.

Every method (M1 build123d lofts, M2 SDF, M3 Blender) receives the SAME `LegSpec`: the same outer-silhouette stations,
the same keep-outs, the same knee requirement and the same print rules. This module is numpy/scipy only so that the
Blender method can run in a separate virtualenv from the exported JSON (`LegSpec.to_dict`).

Frame (millimetres, right-handed): the KNEE AXIS is the y axis through the origin; x forward, y left, z up. The thigh
lies at z > 0, the shank at z < 0. Knee flexion by `theta` rotates the shank about +y so the foot swings backwards
(x -> -x): a point (x, z) of the shank goes to (x cos t + z sin t, -x sin t + z cos t).

Keep-outs (from coordination/handoffs/2026-10-19-0222-T-0004-adam-cad.md and variants/adam/design-language.md):
STS3215 servo = 45.2 (along the limb) x 35.0 (along the joint axis, y) x 24.7 (x) mm, shaft 25 % of the length from
the near end. Hip pitch and knee servos are in the thigh, the ankle pitch servo is in the shank, plus a cable channel.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import numpy as np
from scipy.interpolate import PchipInterpolator

# --------------------------------------------------------------------------------------------- nominal silhouette
# station = (z, w = y-extent, d = x-extent, n = superellipse exponent, cx = x offset of the section centre), mm.
# Widths are dictated by physics: a pitch joint puts 35 mm of servo across the limb (w), only 25 mm along x (d).
# Thigh: widest at the hip end (top third), tapering to a cylinder-ended knee cap of radius ~22 about the knee axis.
THIGH = [
    (-21.0, 40.0, 14.0, 2.6, 0.0),
    (-17.5, 48.0, 27.0, 2.7, 0.0),
    (-13.0, 51.0, 35.0, 2.8, 0.0),
    (-8.0, 52.0, 40.5, 2.8, 0.0),
    (-3.0, 52.5, 43.5, 2.8, 0.0),
    (2.0, 53.0, 45.0, 2.8, 0.0),
    (30.0, 54.0, 46.0, 2.8, 0.0),
    (60.0, 57.0, 51.0, 2.7, 0.5),
    (95.0, 62.0, 56.0, 2.6, 1.0),
    (118.0, 60.0, 54.0, 2.6, 1.0),
    (126.0, 56.0, 48.0, 2.6, 0.5),
    (131.0, 42.0, 34.0, 2.4, 0.0),
]
# Shank: calf swell in the upper third (widest 34 mm below the top, i.e. 0.28 of the shank), ankle cap at the bottom.
SHANK = [
    (-8.0, 52.5, 44.0, 2.8, 0.0),
    (-25.0, 58.0, 49.0, 2.7, -1.0),
    (-42.0, 64.0, 54.0, 2.6, -1.5),
    (-70.0, 58.0, 48.0, 2.7, -1.5),
    (-95.0, 53.0, 43.0, 2.9, -1.5),
    (-112.0, 52.0, 41.0, 3.0, -1.0),
    (-122.0, 52.0, 41.0, 3.0, -1.0),
    (-128.0, 46.0, 34.0, 2.8, -1.0),
    (-132.0, 36.0, 24.0, 2.5, -1.0),
]
THIGH_LEN = 115.0     # knee axis -> hip axis
SHANK_LEN = 112.5     # knee axis -> ankle axis
KNEE_CAP_ZONE = 2.0   # thigh stations at/below this z are the fixed knee cap
SHANK_TOP = -8.0      # first shank station


@dataclass
class KeepOut:
    name: str
    host: str                     # 'thigh' | 'shank'
    kind: str                     # 'box' | 'capsule'
    center: tuple = (0.0, 0.0, 0.0)   # box centre
    size: tuple = (0.0, 0.0, 0.0)     # box size (x, y, z)
    p0: tuple = (0.0, 0.0, 0.0)       # capsule end points
    p1: tuple = (0.0, 0.0, 0.0)
    radius: float = 0.0

    def to_dict(self) -> dict:
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()}


@dataclass
class LegSpec:
    """Parameters of the test piece. `length_scale`, `width_scale` are the +-10 % regeneration knobs."""
    length_scale: float = 1.0     # thigh and shank lengths
    width_scale: float = 1.0      # every station's w and d
    wall: float = 1.6             # shell wall (mm)
    clearance: float = 1.5        # keep-out to cavity wall (mm)
    band: float = 3.0             # knee recess band: minimum gap between thigh and shank shell (mm)
    flex_max_deg: float = 130.0
    seam_x: float = 0.0           # coronal split plane (panel line on the side planes)
    seam_gap: float = 0.8         # reveal gap at the panel line
    servo: tuple = (45.2, 35.0, 24.7)   # length (limb), across the joint axis (y), x
    shaft_offset: float = 11.3
    bed: tuple = (220.0, 220.0, 250.0)

    # ---- stations -------------------------------------------------------------------------------------------
    def thigh_stations(self) -> list[tuple]:
        ls, ws = self.length_scale, self.width_scale
        L = THIGH_LEN
        out = []
        for z, w, d, n, cx in THIGH:
            if z <= KNEE_CAP_ZONE:
                zz = z
            elif z <= L:
                zz = KNEE_CAP_ZONE + (z - KNEE_CAP_ZONE) * (L * ls - KNEE_CAP_ZONE) / (L - KNEE_CAP_ZONE)
            else:
                zz = L * ls + (z - L)
            out.append((zz, w * ws, d * ws, n, cx))
        return out

    def shank_stations(self) -> list[tuple]:
        ls, ws = self.length_scale, self.width_scale
        L = SHANK_LEN
        out = []
        for z, w, d, n, cx in SHANK:
            if z >= -L:
                zz = SHANK_TOP + (z - SHANK_TOP) * (L * ls - (-SHANK_TOP)) / (L - (-SHANK_TOP))
            else:
                zz = -L * ls + (z + L)
            out.append((zz, w * ws, d * ws, n, cx))
        return out

    @property
    def hip_z(self) -> float:
        return THIGH_LEN * self.length_scale

    @property
    def ankle_z(self) -> float:
        return -SHANK_LEN * self.length_scale

    # ---- keep-outs ------------------------------------------------------------------------------------------
    def keepouts(self) -> list[KeepOut]:
        L, H, W = self.servo        # along limb, across axis (y), x
        so = self.shaft_offset
        ko = []
        # knee servo: shaft (knee axis) near the bottom end, body extends up the thigh
        ko.append(KeepOut("servo_knee", "thigh", "box", (0.0, 0.0, -so + L / 2), (W, H, L)))
        # hip pitch servo: shaft near the top end, body extends down
        ko.append(KeepOut("servo_hip_pitch", "thigh", "box", (0.0, 0.0, self.hip_z + so - L / 2), (W, H, L)))
        # ankle pitch servo (in the shank): shaft at the ankle axis near the bottom end, body extends up
        ko.append(KeepOut("servo_ankle_pitch", "shank", "box", (0.0, 0.0, self.ankle_z - so + L / 2), (W, H, L)))
        # cable channel (6 mm bore, straight, along the rear): thigh part ends at the knee cap, shank part starts below the pocket
        ko.append(KeepOut("cable_thigh", "thigh", "capsule", p0=(-15.5, 0.0, 2.0), p1=(-15.5, 0.0, self.hip_z - 15.0), radius=2.5))
        ko.append(KeepOut("cable_shank", "shank", "capsule", p0=(-15.5, 0.0, -62.0 * self.length_scale),
                          p1=(-15.5, 0.0, self.ankle_z + 30.0), radius=2.5))
        return ko

    # ---- serialisation (for the Blender subprocess) -----------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()},
            "thigh_stations": [list(s) for s in self.thigh_stations()],
            "shank_stations": [list(s) for s in self.shank_stations()],
            "keepouts": [k.to_dict() for k in self.keepouts()],
            "cutter_outer": knee_cutter_polygon(self, self.band).tolist(),
            "cutter_wall": knee_cutter_polygon(self, self.band + self.wall).tolist(),
        }

    def to_json(self, path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f)

    def label(self) -> str:
        return f"L{self.length_scale:.2f}_W{self.width_scale:.2f}"


# ------------------------------------------------------------------------------------------------ section profiles
class SegProfile:
    """PCHIP interpolation of the stations along z (C1, no overshoot)."""

    def __init__(self, stations: list[tuple]):
        st = sorted(stations)
        z = np.array([s[0] for s in st], float)
        self.z0, self.z1 = float(z[0]), float(z[-1])
        self.stations = st
        self.w, self.d, self.n, self.cx = (PchipInterpolator(z, np.array([s[i] for s in st], float)) for i in (1, 2, 3, 4))

    def section(self, z):
        z = np.clip(z, self.z0, self.z1)
        return self.w(z), self.d(z), self.n(z), self.cx(z)

    def xy(self, z: float, k: int = 48, shrink: float = 0.0) -> np.ndarray:
        """Closed superellipse section at height z (k points, x then y), shrunk by `shrink` mm on every side."""
        w, d, n, cx = (float(v) for v in self.section(z))
        t = np.linspace(0, 2 * np.pi, k, endpoint=False)
        c, s = np.cos(t), np.sin(t)
        a, b = d / 2 - shrink, w / 2 - shrink
        return np.c_[cx + a * np.sign(c) * np.abs(c) ** (2 / n), b * np.sign(s) * np.abs(s) ** (2 / n)]

    def depth(self, X, Y, Z, shrink: float = 0.0):
        """First-order signed distance (negative inside) to the lofted solid shrunk by `shrink` (mm)."""
        w, d, n, cx = self.section(Z)
        a = np.maximum(d / 2 - shrink, 1e-3)
        b = np.maximum(w / 2 - shrink, 1e-3)
        pu, pv = np.abs(X - cx) / a, np.abs(Y) / b
        g = np.maximum((pu ** n + pv ** n) ** (1.0 / n), 1e-9)
        gu = g ** (1 - n) * pu ** (n - 1) / a
        gv = g ** (1 - n) * pv ** (n - 1) / b
        gm = np.maximum(np.sqrt(gu * gu + gv * gv), 0.5 / np.maximum(a, b))
        d2 = (g - 1.0) / gm
        dz = np.maximum(self.z0 - Z, Z - self.z1)
        return np.minimum(np.maximum(d2, dz), 0.0) + np.hypot(np.maximum(d2, 0.0), np.maximum(dz, 0.0))


# -------------------------------------------------------------------------------------------------- the knee cutter
def _outline_xz(prof: SegProfile, n: int = 600) -> np.ndarray:
    """Sagittal (x,z) outline of a lofted segment (max x-extent of every section), closed polygon."""
    zz = np.linspace(prof.z0, prof.z1, n)
    w, d, nn, cx = prof.section(zz)
    return np.r_[np.c_[cx + d / 2, zz], np.c_[cx - d / 2, zz][::-1]]


def polar_radius(poly: np.ndarray, phis: np.ndarray) -> np.ndarray:
    """Outer radius of a polygon along rays from the origin (max over edge intersections)."""
    a, b = poly, np.roll(poly, -1, axis=0)
    e = b - a
    dirs = np.c_[np.cos(phis), np.sin(phis)]
    # ray: t*dir ; edge: a + u*e ;  t*dir - u*e = a  -> 2x2 solve, vectorised over (rays, edges)
    den = dirs[:, 0:1] * (-e[:, 1][None]) - dirs[:, 1:2] * (-e[:, 0][None])
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (a[:, 0][None] * (-e[:, 1][None]) - a[:, 1][None] * (-e[:, 0][None])) / den
        u = (dirs[:, 0:1] * a[:, 1][None] - dirs[:, 1:2] * a[:, 0][None]) / den
    ok = (np.abs(den) > 1e-12) & (u >= -1e-9) & (u <= 1 + 1e-9) & (t > 0)
    return np.where(ok, t, 0.0).max(axis=1)


def thigh_polar(spec: LegSpec, nphi: int = 1440):
    prof = SegProfile(spec.thigh_stations())
    phis = np.linspace(-np.pi, np.pi, nphi, endpoint=False)
    return phis, polar_radius(_outline_xz(prof), phis)


def knee_sweep_radius(spec: LegSpec, nphi: int = 1440, step_deg: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    """Polar envelope R(phi) of the thigh outline swept over 0..flex_max, seen in the SHANK frame.
    In the shank frame the thigh rotates counter-clockwise (x right, z up) by theta, so R_sweep(phi) = max_theta R0(phi-theta)."""
    phis, r0 = thigh_polar(spec, nphi)
    shifts = int(round(spec.flex_max_deg / step_deg))
    dphi = 2 * np.pi / nphi
    out = r0.copy()
    for k in range(1, int(round(math.radians(spec.flex_max_deg) / dphi)) + 1):
        out = np.maximum(out, np.roll(r0, k))   # roll by +k : value at phi-k*dphi moves to phi
    return phis, out


def knee_cutter_polygon(spec: LegSpec, offset: float, simplify_mm: float = 0.04) -> np.ndarray:
    """(x,z) polygon, in mm and the shank frame, of the volume the thigh sweeps through over the flexion range, offset by `offset` mm.
    Extruded along y it is the cutter that gives the shank its knee pocket. Star-shaped about the knee axis."""
    from skimage.measure import approximate_polygon

    phis, r = knee_sweep_radius(spec)
    pts = np.c_[r * np.cos(phis), r * np.sin(phis)]
    if offset > 0:
        tang = np.roll(pts, -1, axis=0) - np.roll(pts, 1, axis=0)
        nrm = np.c_[tang[:, 1], -tang[:, 0]]
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        off = pts + offset * nrm          # outward normal of a CCW star-shaped curve
        r2 = polar_radius(off, phis)
        pts = np.c_[r2 * np.cos(phis), r2 * np.sin(phis)]
    closed = np.r_[pts, pts[:1]]
    poly = approximate_polygon(closed, simplify_mm)[:-1]
    return poly


class PolarRegion:
    """Occupancy of a star-shaped (x, z) polygon about the origin, with the radius table precomputed."""

    def __init__(self, poly: np.ndarray, nphi: int = 1440):
        self.ph = np.linspace(-np.pi, np.pi, nphi, endpoint=False)
        rp = polar_radius(poly, self.ph)
        self.ph = np.r_[self.ph, np.pi]
        self.rp = np.r_[rp, rp[0]]

    def contains(self, x, z):
        return np.hypot(x, z) <= np.interp(np.arctan2(z, x), self.ph, self.rp)


def point_in_polar(poly: np.ndarray, x, z):
    return PolarRegion(poly).contains(x, z)


# ------------------------------------------------------------------------------------------------ target + feasibility
def target_occupancy(spec: LegSpec, X, Y, Z, thigh=None, shank=None, cutter=None):
    """Analytic target solid (union of thigh and the shank minus the knee pocket) at points."""
    thigh = thigh or SegProfile(spec.thigh_stations())
    shank = shank or SegProfile(spec.shank_stations())
    cutter = cutter if cutter is not None else PolarRegion(knee_cutter_polygon(spec, spec.band))
    in_t = thigh.depth(X, Y, Z) <= 0
    in_s = (shank.depth(X, Y, Z) <= 0) & ~cutter.contains(X, Z)
    return in_t | in_s


def keepout_points(k: KeepOut, spacing: float = 2.0) -> np.ndarray:
    """Surface sample points of a keep-out (box faces / capsule surface)."""
    if k.kind == "box":
        c, s = np.array(k.center), np.array(k.size)
        g = [np.linspace(-h, h, max(2, int(round(2 * h / spacing)) + 1)) for h in s / 2]
        pts = []
        for ax in range(3):
            for sign in (-1, 1):
                grids = list(g)
                grids[ax] = np.array([sign * s[ax] / 2])
                m = np.meshgrid(*grids, indexing="ij")
                pts.append(np.c_[m[0].ravel(), m[1].ravel(), m[2].ravel()])
        return np.unique(np.round(np.vstack(pts) + c, 4), axis=0)
    p0, p1 = np.array(k.p0), np.array(k.p1)
    ts = np.linspace(0, 1, max(2, int(np.linalg.norm(p1 - p0) / spacing)))
    ang = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    ring = np.c_[np.cos(ang), np.sin(ang)] * k.radius
    pts = [np.array([p[0] + r[0], p[1] + r[1], p[2]]) for p in (p0 + t * (p1 - p0) for t in ts) for r in ring]
    pts += [p0 - [0, 0, k.radius], p1 + [0, 0, k.radius]]
    return np.array(pts)


def feasibility(spec: LegSpec | None = None) -> dict:
    """Design-time check on the ANALYTIC outer sections: margin = how far inside the outer surface every keep-out sample lies.
    Needs margin >= wall + clearance. (The real check runs on the generated meshes in evaluate.fit.)"""
    spec = spec or LegSpec()
    prof = {"thigh": SegProfile(spec.thigh_stations()), "shank": SegProfile(spec.shank_stations())}
    need = spec.wall + spec.clearance
    out = {}
    for k in spec.keepouts():
        pts = keepout_points(k)
        d = prof[k.host].depth(pts[:, 0], pts[:, 1], pts[:, 2])
        out[k.name] = {"margin_mm": round(float(-d.max()), 2), "need_mm": need, "ok": bool(-d.max() >= need)}
    return out


if __name__ == "__main__":
    import pprint
    pprint.pprint(feasibility())
