"""Generic build123d helpers for spec-driven humanoid CAD. Variant-agnostic: everything is a parameter.

Units: millimetres inside CAD (build123d convention), SI at the export boundary.
Frames: x forward, y left, z up (same as the sim). Every link is modelled in its own joint frame.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import build123d as bd

# --------------------------------------------------------------------------- data model


@dataclass
class Part:
    """One physical part placed in its link frame (mm)."""
    id: str
    shape: bd.Shape
    kind: str                    # frame | shell | servo | horn | purchased | sole
    material: str                # pla-plus | petg | tpu | purchased
    color: str = "frame"         # render material key (see EXPORT palette)
    mass_kg: float | None = None  # purchased parts: catalog mass. Printed parts: computed from volume
    catalog: str | None = None
    fit: bool = True             # include in shell clearance fitting
    print: dict = field(default_factory=dict)
    # --- CAD-foundation fields (all optional, ignored by the older biped_v1 template) ---
    sites: list = field(default_factory=list)      # core.Site fastener/insert locations in the LINK frame
    meta: dict = field(default_factory=dict)       # interface checks etc. (see geometry_gate)
    process: str = "fdm"                           # fdm | purchased
    print_up: tuple[float, float, float] | None = None   # build direction (+z of the print) in the part frame; None = as modelled
    keepout: bool = False                          # reserved volume: counted for clearance, never for mass/BOM
    hardware: bool = False                         # fasteners/inserts: excluded from interference, included in access/BOM


@dataclass
class Link:
    name: str
    parent: str | None
    pos_mm: tuple[float, float, float]          # origin in the parent frame at zero pose
    joints: list[dict] = field(default_factory=list)  # [{name, axis, range}] all at the link origin
    parts: list[Part] = field(default_factory=list)
    rot_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)  # fixed xyz rotation of the frame (before joints)


# --------------------------------------------------------------------------- servo envelopes


@dataclass
class ServoDims:
    """Box servo: length L along the body, width W, height H along the output shaft.
    `shaft_offset` is the shaft distance from the near end (default 25% of L, typical of bus servos)."""
    L: float
    W: float
    H: float
    shaft_offset: float | None = None
    horn_d: float | None = None
    horn_t: float | None = None

    def __post_init__(self):
        self.shaft_offset = self.shaft_offset or 0.25 * self.L
        self.horn_d = self.horn_d or 0.9 * self.W
        self.horn_t = self.horn_t or max(2.0, 0.085 * self.H)

    @classmethod
    def from_catalog(cls, part: dict) -> "ServoDims":
        d = sorted(part["dimensions_mm"], reverse=True)   # L > H > W for box servos
        a = part.get("actuator", {})
        return cls(L=d[0], W=d[2], H=d[1], shaft_offset=a.get("shaft_offset_mm"),
                   horn_d=a.get("horn_d_mm"), horn_t=a.get("horn_t_mm"))

    @property
    def corner_r(self) -> float:
        """Radius swept by the body corners at the shaft end (clearance radius around the axis)."""
        return math.hypot(self.W / 2, self.shaft_offset)


def frame_at(origin, z_dir, x_dir) -> bd.Location:
    return bd.Location(bd.Plane(origin=tuple(origin), x_dir=tuple(x_dir), z_dir=tuple(z_dir)))


def servo_shapes(s: ServoDims, origin, axis, length_dir) -> tuple[bd.Shape, bd.Shape]:
    """Servo body + horn. `origin` is the shaft axis on the top (horn) face, `axis` the shaft direction,
    `length_dir` the direction the long body extends from the shaft."""
    body = bd.Pos(s.L / 2 - s.shaft_offset, 0, -s.H / 2) * bd.Box(s.L, s.W, s.H)
    body = bd.fillet(body.edges().filter_by(bd.Axis.Z), min(2.0, s.W * 0.08))
    horn = bd.Pos(0, 0, s.horn_t / 2) * bd.Cylinder(s.horn_d / 2, s.horn_t)
    loc = frame_at(origin, axis, length_dir)
    return loc * body, loc * horn


def box(xr, yr, zr) -> bd.Solid:
    """Axis-aligned box from (min, max) ranges."""
    (x0, x1), (y0, y1), (z0, z1) = sorted(xr), sorted(yr), sorted(zr)
    return bd.Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * bd.Box(x1 - x0, y1 - y0, z1 - z0)


def rounded_plate(xr, yr, zr, r: float) -> bd.Solid:
    """Box with its edges parallel to the thinnest direction filleted (a plate with rounded corners)."""
    b = box(xr, yr, zr)
    spans = [abs(xr[1] - xr[0]), abs(yr[1] - yr[0]), abs(zr[1] - zr[0])]
    ax = [bd.Axis.X, bd.Axis.Y, bd.Axis.Z][spans.index(min(spans))]
    r = min(r, 0.45 * sorted(spans)[1])
    return bd.fillet(b.edges().filter_by(ax), r) if r > 0.2 else b


# --------------------------------------------------------------------------- lofted shells


def superellipse_wire(a: float, b: float, n: float, center=(0.0, 0.0), z: float = 0.0, samples: int = 40) -> bd.Wire:
    """Closed superellipse |x/a|^n + |y/b|^n = 1 (n=2 ellipse, n≈2.5–3 'squircle'), as a periodic spline."""
    pts = []
    for i in range(samples):
        t = 2 * math.pi * i / samples
        c, s = math.cos(t), math.sin(t)
        pts.append((center[0] + a * math.copysign(abs(c) ** (2 / n), c),
                    center[1] + b * math.copysign(abs(s) ** (2 / n), s), z))
    return bd.Wire([bd.Edge.make_spline(pts, periodic=True)])


@dataclass
class Station:
    z: float
    a: float          # half extent along local x
    b: float          # half extent along local y
    cx: float = 0.0
    cy: float = 0.0


def loft_solid(stations: list[Station], n: float = 2.6) -> bd.Solid:
    st = sorted(stations, key=lambda s: s.z)
    return bd.Solid.make_loft([superellipse_wire(s.a, s.b, n, (s.cx, s.cy), s.z) for s in st])


def hollow_loft(stations: list[Station], wall: float, n: float = 2.6, open_ends: bool | str = True) -> bd.Solid:
    """Thin-walled lofted shell: outer loft minus an inner loft offset by `wall`.
    open_ends: True = tube open at both ends (frame and joints pass through), False = closed at both ends,
    "lo" / "hi" = open only at the low-z / high-z end."""
    st = sorted(stations, key=lambda s: s.z)
    outer = loft_solid(st, n)
    inner_st = [Station(s.z, max(s.a - wall, 0.3), max(s.b - wall, 0.3), s.cx, s.cy) for s in st]
    lo, hi = inner_st[0], inner_st[-1]
    open_lo, open_hi = open_ends in (True, "lo"), open_ends in (True, "hi")
    if open_lo:
        inner_st.insert(0, Station(lo.z - 2 * wall, lo.a, lo.b, lo.cx, lo.cy))
    else:
        inner_st[0] = Station(lo.z + wall, lo.a, lo.b, lo.cx, lo.cy)
    if open_hi:
        inner_st.append(Station(hi.z + 2 * wall, hi.a, hi.b, hi.cx, hi.cy))
    else:
        inner_st[-1] = Station(hi.z - wall, hi.a, hi.b, hi.cx, hi.cy)
    inner_st = [s for i, s in enumerate(inner_st) if i == 0 or s.z > inner_st[i - 1].z + 1e-3]
    return outer - loft_solid(inner_st, n)


def shape_at(samples: list[tuple[float, float]], t: float) -> float:
    """Piecewise-linear lookup in [(t, value), ...] with t in 0..1."""
    pts = sorted(samples)
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0 or 1)
    return pts[-1][1]


def bbox_of(shape: bd.Shape):
    bb = shape.bounding_box()
    return (bb.min.X, bb.max.X), (bb.min.Y, bb.max.Y), (bb.min.Z, bb.max.Z)


def section_boxes(shapes: list[bd.Shape], z: float, slab: float = 1.0) -> list[tuple]:
    """XY bounding boxes of each shape's cross-section in a thin slab at height z."""
    cut = bd.Pos(0, 0, z) * bd.Box(1e4, 1e4, slab)
    out = []
    for sh in shapes:
        bb = sh.bounding_box()
        if bb.max.Z < z - slab / 2 or bb.min.Z > z + slab / 2:
            continue
        try:
            sec = sh & cut
            if sec.volume <= 1e-6:
                continue
            (x0, x1), (y0, y1), _ = bbox_of(sec)
        except Exception:  # noqa: BLE001  fall back to the full bounding box
            (x0, x1), (y0, y1), _ = bbox_of(sh)
        out.append(((x0, x1), (y0, y1)))
    return out


def fit_stations(parts: list[bd.Shape], z_top: float, z_bot: float, profile: list[tuple[float, float]],
                 margin: float, n: float = 2.6, count: int = 9, center: tuple[float, float] | None = None,
                 min_half: tuple[float, float] = (0.0, 0.0), dome: float = 0.2,
                 max_shrink: float = 0.07, dome_shrink: float = 0.86) -> list[Station]:
    """Stations for a shell that clears `parts` along z in [z_bot, z_top] (real cross-sections, sampled at
    each station) and follows the style `profile` (t=0 at z_top .. t=1 at z_bot, value = relative size).
    Where the parts need less room than the profile, the profile wins (the designed taper/swell); where they
    need more, the shell grows locally. `margin` (gap + wall) is added on top. `dome` rounds the ends."""
    boxes = [bbox_of(p) for p in parts]
    if center is None:
        xs = [v for bx in boxes for v in bx[0]] or [0.0]
        ys = [v for bx in boxes for v in bx[1]] or [0.0]
        center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    cx, cy = center
    rx = max([max(abs(bx[0][0] - cx), abs(bx[0][1] - cx)) for bx in boxes] + [min_half[0], 1.0])
    ry = max([max(abs(bx[1][0] - cy), abs(bx[1][1] - cy)) for bx in boxes] + [min_half[1], 1.0])
    zs = [z_top + (z_bot - z_top) * i / (count - 1) for i in range(count)]
    gs = [shape_at(profile, i / (count - 1)) for i in range(count)]
    req = []
    for z in zs:
        r = 0.0
        for (x0, x1), (y0, y1) in section_boxes(parts, z):
            for x in (x0, x1):
                for y in (y0, y1):
                    r = max(r, ((abs(x - cx) / rx) ** n + (abs(y - cy) / ry) ** n) ** (1 / n))
        req.append(r)
    ratios = sorted(r / g for r, g in zip(req, gs) if r > 0) or [1.0]
    lam0 = max(ratios[len(ratios) // 2], max(min_half[0] / rx, min_half[1] / ry))
    lams = [max(r, lam0 * g) for r, g in zip(req, gs)]
    for rng in (range(1, count), range(count - 2, -1, -1)):   # limit how fast the section may shrink
        for i in rng:
            j = i - 1 if rng.step == 1 else i + 1
            lams[i] = max(lams[i], lams[j] * (1 - max_shrink))
    out = []
    for z, g in zip(zs, lams):
        out.append(Station(z, g * rx + margin, g * ry + margin, cx, cy))
    if dome > 0:
        # Rounded lips: pull the first/last full-size sections inwards and close with smaller end sections.
        top, bot = out[0], out[-1]
        dt, db = dome * min(top.a, top.b), dome * min(bot.a, bot.b)
        sgn = 1 if z_bot < z_top else -1
        inner = [s for s in out if (z_top - s.z) * sgn > dt and (s.z - z_bot) * sgn > db]
        # end sections still clear whatever passes through the opening
        ta, tb = max(top.a * dome_shrink, req[0] * rx + 0.6 * margin), max(top.b * dome_shrink, req[0] * ry + 0.6 * margin)
        ba, bb = max(bot.a * dome_shrink, req[-1] * rx + 0.6 * margin), max(bot.b * dome_shrink, req[-1] * ry + 0.6 * margin)
        out = ([Station(z_top, ta, tb, cx, cy), Station(z_top - sgn * dt, top.a, top.b, cx, cy)] + inner
               + [Station(z_bot + sgn * db, bot.a, bot.b, cx, cy), Station(z_bot, ba, bb, cx, cy)])
    return out


# --------------------------------------------------------------------------- mass properties


def mass_properties(shape: bd.Shape, density_kg_m3: float) -> dict:
    """Mass (kg), COM (m) and inertia about the COM (kg·m²) of a solid in mm, at a uniform density."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, props)
    vol = props.Mass()                      # mm³
    c = props.CentreOfMass()
    m = props.MatrixOfInertia()             # about COM, density 1, mm^5
    k = density_kg_m3 * 1e-15
    inertia = [[m.Value(i, j) * k for j in (1, 2, 3)] for i in (1, 2, 3)]
    return {"mass": vol * 1e-9 * density_kg_m3, "com": [c.X() / 1000, c.Y() / 1000, c.Z() / 1000], "inertia": inertia,
            "volume_mm3": vol}


def box_mass_properties(shape: bd.Shape, mass: float) -> dict:
    """Uniform-box approximation for purchased parts (catalog mass, bounding-box geometry)."""
    (x0, x1), (y0, y1), (z0, z1) = bbox_of(shape)
    dx, dy, dz = (x1 - x0) / 1000, (y1 - y0) / 1000, (z1 - z0) / 1000
    i = [[mass * (dy**2 + dz**2) / 12, 0, 0], [0, mass * (dx**2 + dz**2) / 12, 0], [0, 0, mass * (dx**2 + dy**2) / 12]]
    return {"mass": mass, "com": [(x0 + x1) / 2000, (y0 + y1) / 2000, (z0 + z1) / 2000], "inertia": i}


def combine_mass(items: list[dict]) -> dict:
    """Sum rigid bodies (each mass, com, inertia about its own COM) into one about the combined COM."""
    import numpy as np

    M = sum(it["mass"] for it in items)
    if M <= 0:
        return {"mass": 0.0, "com": [0.0, 0.0, 0.0], "inertia": [[0.0] * 3 for _ in range(3)]}
    com = sum(np.array(it["com"]) * it["mass"] for it in items) / M
    I = np.zeros((3, 3))
    for it in items:
        d = np.array(it["com"]) - com
        I += np.array(it["inertia"]) + it["mass"] * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    return {"mass": float(M), "com": com.tolist(), "inertia": I.tolist()}


# --------------------------------------------------------------------------- checks


def interference(a: bd.Shape, b: bd.Shape) -> float:
    """Overlap volume in mm³ (0 if the bounding boxes don't touch)."""
    ba, bb = a.bounding_box(), b.bounding_box()
    if (ba.max.X < bb.min.X or bb.max.X < ba.min.X or ba.max.Y < bb.min.Y or bb.max.Y < ba.min.Y
            or ba.max.Z < bb.min.Z or bb.max.Z < ba.min.Z):
        return 0.0
    try:
        return float((a & b).volume)
    except Exception:  # noqa: BLE001  OCC boolean failure: report as unknown overlap
        return -1.0


def fits_bed(shape: bd.Shape, bed_mm: tuple[float, float, float]) -> tuple[bool, tuple[float, float, float]]:
    """Does the part fit the print volume in some axis-aligned orientation? Returns (ok, sorted extents)."""
    (x0, x1), (y0, y1), (z0, z1) = bbox_of(shape)
    ext = tuple(sorted((x1 - x0, y1 - y0, z1 - z0), reverse=True))
    bed = sorted(bed_mm, reverse=True)
    return all(e <= b for e, b in zip(ext, bed)), ext
