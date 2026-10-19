"""M2: SDF smooth-union. Ellipsoids and rounded cylinders, blended with a polynomial smooth-min, walled by an offset of
the signed distance, keep-outs and the knee pocket subtracted as fields, meshed with marching cubes. Mesh only (no STEP).

Unlike M1 the sections are not given: the agent picks a handful of primitives per segment. Their sizes start from the
target stations and are then calibrated (a few damped passes) so the blended surface lands on the target widths.
"""
from __future__ import annotations

import numpy as np

from .meshutil import ShellSet, Timer, decimate, name_panels
from .spec import LegSpec, PolarRegion, SegProfile, knee_cutter_polygon


# ------------------------------------------------------------------------------------------------ SDF primitives
def sd_ellipsoid(X, Y, Z, c, r):
    """Approximate SDF of an ellipsoid (Quilez): k0 (k0 - 1) / k1."""
    p = np.stack(np.broadcast_arrays(X - c[0], Y - c[1], Z - c[2]), axis=-1)
    k0 = np.linalg.norm(p / r, axis=-1)
    k1 = np.linalg.norm(p / (r * r), axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def sd_rounded_cyl_y(X, Y, Z, c, radius, half_len, rnd):
    """Cylinder about an axis parallel to y (the joint axis), radius `radius`, half length `half_len`, edges rounded by `rnd`."""
    q0 = np.hypot(X - c[0], Z - c[2]) - (radius - rnd)
    q1 = np.abs(Y - c[1]) - (half_len - rnd)
    return np.minimum(np.maximum(q0, q1), 0.0) + np.hypot(np.maximum(q0, 0.0), np.maximum(q1, 0.0)) - rnd


def sd_round_box(X, Y, Z, c, half, rnd):
    """Rounded box (half-sizes `half`, corner radius `rnd`): the squarish end caps an ellipsoid cannot make."""
    q = np.stack(np.broadcast_arrays(np.abs(X - c[0]), np.abs(Y - c[1]), np.abs(Z - c[2])), axis=-1) - (np.asarray(half) - rnd)
    return np.linalg.norm(np.maximum(q, 0.0), axis=-1) + np.minimum(q.max(axis=-1), 0.0) - rnd


def smin(a, b, k):
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def sd_box(X, Y, Z, centre, size):
    q = np.stack(np.broadcast_arrays(np.abs(X - centre[0]), np.abs(Y - centre[1]), np.abs(Z - centre[2])), axis=-1) - np.array(size) / 2
    return np.linalg.norm(np.maximum(q, 0.0), axis=-1) + np.minimum(q.max(axis=-1), 0.0)


def sd_capsule_z(X, Y, Z, p0, p1, r):
    z0, z1 = sorted((p0[2], p1[2]))
    zc = np.clip(Z, z0, z1)
    return np.hypot(np.hypot(X - p0[0], Y - p0[1]), Z - zc) - r


# ------------------------------------------------------------------------------------------------------- bead layout
K_BLEND = 20.0   # smooth-union radius (mm)
BEAD_ROUND = 0.8  # bead corner radius / smallest half-size: 1 = ellipsoid-like, 0 = box. Ellipsoids could not enclose the servo corners
CAP_EXTRA = 0.7  # extra radius on top of servo corner + clearance + wall
class Beads:
    """The primitive layout of one segment, sized from the target stations and calibrated against them."""

    def __init__(self, prof: SegProfile, kind: str, spec: LegSpec):
        L, ls = spec.hip_z, spec.length_scale
        self.prof, self.k = prof, K_BLEND
        # joint cap radius: must clear the servo corner swept about the axis (found by the first fit check, not by inspection)
        r_min = float(np.hypot(spec.servo[2] / 2, spec.shaft_offset) + spec.clearance + spec.wall + CAP_EXTRA)
        if kind == "thigh":      # centres every ~0.24 L, reach 1.25x the spacing so the necks between beads do not dip
            sp = 0.24 * L
            zs = [(f * L, 1.25 * sp) for f in (0.84, 0.60, 0.36)]
            self.cyl = {"z": 0.0, "from": 2.0, "r_min": r_min}
        else:
            sp = 25.0 * ls
            zs = [(-16.0, 12.0)] + [(z * ls, 1.25 * sp) for z in (-44.0, -69.0, -94.0)]
            self.cyl = {"z": spec.ankle_z, "from": spec.ankle_z + 1.0, "r_min": r_min}
        self.cap = {"z": L + 1.0, "hz": 15.0, "sx": 1.0, "sy": 1.0} if kind == "thigh" else None   # hip cap: a rounded box
        self.ell = [{"z": z, "rz": rz, "sx": 1.0, "sy": 1.0} for z, rz in zs]

    def _target(self, z):
        w, d, n, cx = (float(v) for v in self.prof.section(z))
        return w / 2, d / 2, cx

    def sdf(self, X, Y, Z):
        out = None
        for e in self.ell:
            hw, hd, cx = self._target(e["z"])
            half = (hd * e["sx"], hw * e["sy"], e["rz"])
            f = sd_round_box(X, Y, Z, (cx, 0.0, e["z"]), half, BEAD_ROUND * min(half))
            out = f if out is None else smin(out, f, self.k)
        hw, hd, cx = self._target(self.cyl["from"])
        f = sd_rounded_cyl_y(X, Y, Z, (cx, 0.0, self.cyl["z"]), max(hd, self.cyl["r_min"]), hw, 6.0)
        out = smin(out, f, self.k)
        if self.cap:
            hw, hd, cx = self._target(self.cap["z"] - 4.0)
            f = sd_round_box(X, Y, Z, (cx, 0.0, self.cap["z"]), (hd * 0.92, hw * 0.92, self.cap["hz"]), 8.0)
            out = smin(out, f, self.k * 0.5)
        return out

    def width_probe(self, z):
        """Measured (y half-extent, x front, x rear) of the blended surface at height z (1-D sign-change probes)."""
        t = np.linspace(0.0, 45.0, 901)
        _, _, cx = self._target(z)
        def first_out(axis, sign):
            P = [np.full_like(t, cx), np.zeros_like(t), np.full_like(t, z)]
            P[axis] = P[axis] + sign * t
            f = self.sdf(*P)
            idx = np.argmax(f > 0)
            return t[idx] if (f > 0).any() else t[-1]
        return first_out(1, 1), first_out(0, 1), first_out(0, -1)

    def calibrate(self, passes: int = 10, damp: float = 0.8) -> list[float]:
        """Scale each bead's x/y semi-axes so the blended width and depth at its centre equal the target's."""
        errs = []
        for _ in range(passes):
            worst = 0.0
            for e in self.ell:
                hw, hd, cx = self._target(e["z"])
                y, xf, xr = self.width_probe(e["z"])
                worst = max(worst, abs(y - hw), abs((xf + xr) / 2 - hd))
                e["sy"] *= 1 + damp * (hw / max(y, 1e-3) - 1)
                e["sx"] *= 1 + damp * (hd / max((xf + xr) / 2, 1e-3) - 1)
            errs.append(round(float(worst), 3))
        return errs


def renormalise(f: np.ndarray, voxel: float) -> np.ndarray:
    """Approximate SDFs (ellipsoids, smooth-min) have |grad| != 1; divide by the local gradient magnitude so the wall offset is metric."""
    g = np.gradient(f, voxel)
    gm = np.sqrt(g[0] ** 2 + g[1] ** 2 + g[2] ** 2)
    return f / np.clip(gm, 0.4, 3.0)


def mesh_from_field(field: np.ndarray, lo: np.ndarray, voxel: float):
    import trimesh
    from skimage.measure import marching_cubes

    v, f, _, _ = marching_cubes(field, level=0.0, spacing=(voxel, voxel, voxel))
    m = trimesh.Trimesh(v + lo, f, process=True)
    m.merge_vertices()
    return m


def segment_field(spec: LegSpec, seg: str, voxel: float, calib: list):
    prof = SegProfile(spec.thigh_stations() if seg == "thigh" else spec.shank_stations())
    beads = Beads(prof, seg, spec)
    calib.append({seg: beads.calibrate()})
    z0, z1 = prof.z0, prof.z1
    half_x, half_y = 36.0 * max(spec.width_scale, 1.0), 38.0 * max(spec.width_scale, 1.0)
    pad = 6.0
    lo = np.array([-half_x, -half_y, z0 - pad])
    hi = np.array([half_x, half_y, z1 + pad])
    xs, ys, zs = (np.arange(lo[i], hi[i], voxel, dtype=np.float32) for i in range(3))
    X, Y, Z = xs[:, None, None], ys[None, :, None], zs[None, None, :]
    f = beads.sdf(X, Y, Z).astype(np.float32)
    f = renormalise(f, voxel)
    if seg == "shank":      # knee pocket: subtract the swept-thigh cutter (offset by the recess band)
        cut = PolarRegion(knee_cutter_polygon(spec, spec.band))
        r = np.hypot(X, Z)
        ph = np.arctan2(Z, X)
        Rcut = np.interp(ph, cut.ph, cut.rp)
        f = np.maximum(f, -(r - Rcut).astype(np.float32))
        f = renormalise(f, voxel)       # the cutter field is not metric: without this the pocket wall came out 0.6-1.0 mm instead of 1.6
    t = spec.wall
    shell0 = np.maximum(f, -f - t)                      # |f + t/2| - t/2 : the walled shell, closed inside
    s = shell0
    for k in (k for k in spec.keepouts() if k.host == seg):   # keep-outs inflated by the clearance, subtracted
        d = (sd_box(X, Y, Z, k.center, np.array(k.size) + 2 * spec.clearance) if k.kind == "box"
             else sd_capsule_z(X, Y, Z, k.p0, k.p1, k.radius + spec.clearance))
        s = np.maximum(s, -d.astype(np.float32))
    cut_vox = int(((shell0 <= 0) & (s > 0)).sum())
    s = np.maximum(s, -(np.abs(X - spec.seam_x) - spec.seam_gap / 2).astype(np.float32))     # reveal gap -> two panels
    return s, lo, cut_vox, beads


def build(spec: LegSpec | None = None, voxel: float = 0.5) -> ShellSet:
    spec = spec or LegSpec()
    calib: list = []
    items: dict = {}
    cut = 0.0
    with Timer() as T:
        for seg in ("thigh", "shank"):
            s, lo, cv, _ = segment_field(spec, seg, voxel, calib)
            cut += cv * voxel ** 3
            m = mesh_from_field(s, lo, voxel)
            comps = [c for c in m.split(only_watertight=False) if len(c.faces) > 200]
            items[seg] = [(float(c.centroid[0]), decimate(c)) for c in comps]
        parts = name_panels(items, spec)
    ss = ShellSet("M2_sdf", spec, parts, None, T.seconds)
    ss.notes["calibration_max_error_mm_per_pass"] = calib
    ss.notes["keepout_cut_volume_mm3"] = round(cut, 1)
    ss.notes["voxel_mm"] = voxel
    return ss
