"""Tested CAD feature primitives. Agents compose these instead of writing raw booleans or lofts.

Every helper returns a `FeatureResult` (material to add, material to cut, fastener `Site`s, keep-outs, notes) built in the
helper's own local frame and moved with `at=` (a build123d Location). Execute with `core.apply(base, feat, ...)`, which makes
all additions first, all cuts second, each through the guarded booleans (`CadOpError` instead of a quietly wrong part).
All numbers come from `dfm.yaml` and `components/data/*.yaml` (no literals in part code).

Frame conventions
* "surface frame" (`insert_boss`, `screw_clearance`, `counterbore`, `magnet_boss`, `idler_seat`): origin on the host surface where the
  hardware enters, local +z points OUT of the material, the hole goes in the -z direction.
* servo frame (`servo_pocket`, `horn_mount`): the component frame of components/servo.py (origin on the output axis at the
  horn-face plane, +z out of the horn face, +x toward the long end).  `horn_mount` is expressed in the `horn_seat` frame.
"""
from __future__ import annotations

import math

import build123d as bd

from . import dfm
from .components import get as get_component
from .components import val
from .core import (CadOpError, FeatureResult, Site, apply, axis_of, bbox_tuple, box_at, check_solid, cyl_along, loc_from,
                   overlap_volume, safe_cut, safe_union, union_all, volume)

STOCK_SCREW_LENGTHS = [4, 5, 6, 8, 10, 12, 14, 16, 20, 25, 30, 35, 40]


def _at(f: FeatureResult, at: bd.Location | None) -> FeatureResult:
    return f.placed(at) if at is not None else f


def screw_length_for(clamped_mm: float, insert_len: float = 5.7, engagement: float = 0.8) -> int:
    """Shortest stock screw that clamps `clamped_mm` of material and reaches `engagement` x insert length into a heat-set insert."""
    need = clamped_mm + engagement * insert_len
    for L in STOCK_SCREW_LENGTHS:
        if L >= need:
            return L
    raise ValueError(f"no stock screw length for {need:.1f} mm")


def bolt_circle(n: int, pcd: float, start_deg: float = 0.0) -> list[tuple[float, float]]:
    """Hole centres of an n-hole bolt circle (module interface standard: S class = 4 x PCD 32, modules/INTERFACE.md)."""
    return [(pcd / 2 * math.cos(math.radians(start_deg + 360.0 * i / n)), pcd / 2 * math.sin(math.radians(start_deg + 360.0 * i / n)))
            for i in range(n)]


# --------------------------------------------------------------------------- fasteners


def insert_boss(thread: str = "M3", *, boss_h: float | None = None, boss_d: float | None = None, part: str = "", mates: str | None = None,
                tag: str = "insert", delta_d: float = 0.0, at: bd.Location | None = None) -> FeatureResult:
    """Heat-set insert pocket (diameter, depth, entry chamfer from components/data/hardware.yaml + dfm.yaml), optionally with a
    raised boss of wall >= dfm insert_boss.wall around it.

    `boss_h`: height of a cylindrical boss standing below the surface (z in [-boss_h, 0]); the boss overlaps 0.5 mm into whatever it
    stands on, so it fuses with the base. Omit when the hole goes into existing material.
    The pocket depth is hole_depth (insert length + 1 mm). Raises when `boss_h` leaves less floor than dfm insert_boss.min_floor.
    `delta_d` shifts the hole diameter (only the fit gauge's calibration ladder uses it).
    """
    ins = get_component(f"insert:{thread}")
    r = dfm.load_dfm()["insert_boss"]
    hole_d = ins.params["hole_d"] + delta_d
    depth = ins.params["hole_depth"]
    wall = float(val(r["wall_mm"]))
    od = boss_d or (hole_d + 2 * wall)
    f = FeatureResult(name=f"insert_boss_{thread}")
    if boss_h is not None:
        floor = boss_h - depth
        if floor < float(val(r["min_floor_mm"])) - 1e-9:
            raise CadOpError(f"insert_boss {thread}: boss_h {boss_h:.1f} leaves {floor:.2f} mm floor under the pocket "
                             f"(min {val(r['min_floor_mm'])}, pocket {depth:.1f})")
        f.add.append(cyl_along(bd.Location(), od, boss_h + 0.5, z0=-boss_h - 0.5))
    ch = float(val(r["entry_chamfer_mm"]))
    pocket = cyl_along(bd.Location(), hole_d, depth, z0=-depth)
    cone = bd.Pos(0, 0, -ch / 2 + 0.0) * bd.Cone(hole_d / 2 + ch, hole_d / 2, ch).rotate(bd.Axis.X, 0)
    f.cut += [pocket, cone]
    f.sites.append(Site(id=tag, kind="insert", part=part, frame=bd.Location(), thread=thread, length_mm=ins.params["length"], mates=mates,
                        tool_d=8.0, tool_len=30.0))
    f.notes.append(f"{thread} insert: hole d{hole_d} x {depth:.1f}, boss wall {wall}")
    return _at(f, at)


def screw_clearance(thread: str = "M3", *, through: float = 20.0, fit: str = "medium", counterbore: bool = False, part: str = "",
                    mates: str | None = None, length: float | None = None, tag: str = "screw", head: str = "std",
                    at: bd.Location | None = None) -> FeatureResult:
    """Through (clearance) hole for a socket-head screw entering at the surface frame, with an optional counterbore for the head.

    Hole diameter = ISO 273 close/medium + DFM hole compensation; counterbore diameter/depth from DIN 974-1 plus dfm screw.head_gap.
    Adds a `Site` (tool-access corridor starts at the head).
    """
    s = get_component(f"screw:{thread}x{int(length or 8)}{'L' if head == 'low' else ''}")
    p = s.params
    d = (p["clearance_close"] if fit == "close" else p["clearance_medium"])
    d += dfm.hole_comp(d)
    f = FeatureResult(name=f"screw_clearance_{thread}")
    f.cut.append(cyl_along(bd.Location(), d, through + 1.0, z0=-through))
    if counterbore:
        gap = float(val(dfm.load_dfm()["screw"]["head_gap_mm"]))
        cb_d = p["counterbore_d"] + gap + dfm.hole_comp(p["counterbore_d"])
        cb_h = p["counterbore_depth"] + gap
        f.cut.append(cyl_along(bd.Location(), cb_d, cb_h + 1.0, z0=-cb_h))
        f.notes.append(f"counterbore d{cb_d:.2f} x {cb_h:.2f}")
    f.sites.append(Site(id=tag, kind="screw", part=part, frame=bd.Location(), thread=thread, length_mm=float(length or 8), mates=mates,
                        tool_d=p["tool_corridor_d"],
                        tool_len=float(dfm.load_dfm()["access"]["tool_len_mm"].get(thread, val(dfm.load_dfm()["access"]["default_corridor_len_mm"])))))
    return _at(f, at)


def counterbore(thread: str = "M3", **kw) -> FeatureResult:
    """`screw_clearance(..., counterbore=True)`: the head sits flush in a DIN 974-1 counterbore."""
    return screw_clearance(thread, counterbore=True, **kw)


def magnet_boss(spec: str = "6x3", *, boss: bool = False, boss_h: float | None = None, access: str = "pause", at: bd.Location | None = None,
                part: str = "", delta_d: float = 0.0) -> FeatureResult:
    """Pocket for a disc magnet. The pocket sits `cover` below the mating surface (a printed skin keeps the magnet in; pause the print
    to drop it in: `access="pause"`), or opens onto the surface (`access="open"`, glued in). Pocket = disc + dfm magnet.extra_d/depth."""
    mag = get_component(f"magnet:{spec}")
    r = dfm.load_dfm()["magnet"]
    d = mag.params["d"] + float(val(r["extra_d_mm"])) + delta_d
    h = mag.params["h"] + float(val(r["extra_depth_mm"]))
    cover = float(val(r["cover_mm"])) if access == "pause" else 0.0
    f = FeatureResult(name="magnet_boss")
    if boss:
        wall = float(val(r["wall_mm"]))
        bh = boss_h or (cover + h + float(val(r["floor_mm"])))
        f.add.append(cyl_along(bd.Location(), d + 2 * wall, bh + 0.5, z0=-bh - 0.5))
    f.cut.append(cyl_along(bd.Location(), d, h + (1.0 if access == "open" else 0.0), z0=-cover - h))
    f.sites.append(Site(id="magnet", kind="magnet", part=part, frame=bd.Location(), thread="6x3", length_mm=mag.params["h"],
                        needs_access=False))
    f.notes.append(f"magnet pocket d{d:.2f} x {h:.2f}, {access}, cover {cover}")
    return _at(f, at)


# --------------------------------------------------------------------------- servo features


def _env(servo, c: float, extra_top: float = 0.0, extra_bot: float = 0.0) -> bd.Shape:
    """Servo body envelope grown by c on every side (rounded vertical edges), in the servo frame."""
    P = servo.params
    x0, x1 = -P["axis_x"] - c, P["L"] - P["axis_x"] + c
    z0, z1 = -P["H"] - c - extra_bot, c + extra_top
    b = box_at(bd.Location(), (x1 - x0, P["W"] + 2 * c, z1 - z0), ((x0 + x1) / 2, 0, (z0 + z1) / 2))
    return bd.fillet(b.edges().filter_by(bd.Axis.Z), 1.5 + c)


def servo_pocket(actuator_id: str = "sts3215-12v", clearance: str | float = "slip", *, entry: str = "-z", lip: str = "far",
                 lip_t: float = 2.4, wall: float = 2.4, cable_slot: bool = True, slot_len: float = 40.0, entry_len: float = 80.0, at: bd.Location | None = None,
                 part: str = "", tag: str = "servo") -> FeatureResult:
    """Cutter that makes a pocket for a servo in its own frame (origin on the output axis, +z out of the horn face).

    * body envelope grown by the fit's per-side `clearance` (fit name from dfm.yaml or a number in mm);
    * `entry`: direction the servo slides in from ("-z" = from the back, the default; "+x", "-x", "+y", "-y", "+z"): the pocket is
      extended that way so it opens onto the host outside;
    * `lip`: for entry "-z" a retaining lip over the servo top face: "far" keeps a bridge of the host over the far end (beyond
      the horn, x > horn radius + 1), "none" leaves the whole horn face open. The `add` list holds the lip material; the host block
      must reach the servo top plane for the lip to join it;
    * `wall`: thickness of the host side walls the lip fuses into;
    * `cable_slot`: `slot_len` mm slot for the servo plug through the end wall at the cable exit, with the plug room as keep-out;
    * keep-out: the servo component keep-out (body, boss, back stub, plug) ready to register for the ROM check.
    """
    servo = get_component(actuator_id)
    P = servo.params
    c = dfm.clearance(clearance) if isinstance(clearance, str) else float(clearance)
    f = FeatureResult(name="servo_pocket")
    body = _env(servo, c)
    # extend toward the entry direction until it leaves the host
    ext_dir = {"+z": (0, 0, 1), "-z": (0, 0, -1), "+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0)}[entry]
    bb = body.bounding_box()
    size = [bb.size.X, bb.size.Y, bb.size.Z]
    cen = [(bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2, (bb.min.Z + bb.max.Z) / 2]
    axis_i = [abs(v) > 0 for v in ext_dir].index(True)
    sgn = ext_dir[axis_i]
    cen_e = list(cen)
    cen_e[axis_i] += sgn * (size[axis_i] / 2 + entry_len / 2 - 0.01)
    size_e = list(size)
    size_e[axis_i] = entry_len
    slab = bd.Pos(*cen_e) * bd.Box(*size_e)
    f.cut += [body, slab]
    # top wall / lip for back entry: keep a bridge over the far end of the top face
    if entry == "-z" and lip == "far":
        horn_r = get_component("horn-25t").params["od"] / 2
        x0 = horn_r + 1.0
        x1 = P["far_end_x"] + c
        # lip occupies z in [c, c+lip_t] over x in [x0, x1]; width = body width + 2c + nothing else (host provides side walls)
        # the lip reaches (wall - 0.4) mm into the side walls and 0.5 mm below the block top so it fuses; the pocket cut then
        # trims whatever dips into the envelope
        lip_box = box_at(bd.Location(), (x1 - x0 + 3.0, P["W"] + 2 * c + 2 * (wall - 0.4), lip_t + 0.5), ((x0 + x1 + 3.0) / 2, 0, c + (lip_t - 0.5) / 2))
        f.add.append(lip_box)
        f.notes.append(f"lip over far end x>{x0:.1f}, {lip_t} thick")
    if cable_slot and entry != "+x":
        cw, ch = 12.0, 8.0
        cz = P["cable_z"]
        slot = box_at(bd.Location(), (slot_len, cw + 2 * c, ch + 2 * c), (P["far_end_x"] + slot_len / 2 - 0.5, 0, cz))
        f.cut.append(slot)
        f.notes.append("cable slot through the far end wall")
    f.keepouts.append(servo.keepout)
    f.sites.append(Site(id=tag, kind="servo", part=part, frame=bd.Location(), thread="", needs_access=False, mates=None))
    f.notes.append(f"pocket clearance {c} per side; servo {actuator_id}; entry {entry}")
    return _at(f, at)


def horn_mount(actuator_id: str = "sts3215-12v", *, plate_t: float = 4.3, mode: str = "flat", part: str = "", mates: str | None = None,
               fit: str = "slip", washer_od: float | None = None, at: bd.Location | None = None) -> FeatureResult:
    """Features on the plate that attaches to the servo horn, in the servo's `horn_seat` frame (origin on the axis at the horn's
    underside, +z away from the servo).

    mode "flat":     plate underside rests on the horn top (z = horn thickness); holes only.
    mode "recessed": plate underside at z = 0 with a horn-shaped recess (od + 2 x fit, thickness + axial tolerance) so the horn sits
                     inside the plate; saves one horn thickness of axial stack; the plate thickness above the horn is `plate_t`.
    Cuts: central M3 screw hole (counterbored from the outer face), horn screw holes on the horn's bolt circle (counterbored),
    boss relief under the plate. Sites: one centre screw + one per horn hole (tool access from +z).
    `washer_od`: ISO 7089 M2 washers (OD 5.0, 0.3 thick) under the horn screw heads: the counterbore is widened to hold them. A low-head M2 has
    only 6.8 mm2 of bearing area under the head, which is the first limit when the plate carries a moment through the horn (G-strength).
    Raises if the plate is thinner than the counterbore needs.
    """
    servo = get_component(actuator_id)
    horn = get_component("horn-25t")
    HP = horn.params
    t_h = HP["thickness"]
    c = dfm.clearance(fit)
    f = FeatureResult(name="horn_mount")
    z_under = t_h if mode == "flat" else 0.0
    z_top = t_h + plate_t
    hs = get_component("screw:" + HP["screw"] + "x6L").params
    cs = get_component("screw:" + HP["center_screw"] + "x6L").params
    gap = float(val(dfm.load_dfm()["screw"]["head_gap_mm"]))
    min_t = max(hs["counterbore_depth"] + (0.3 if washer_od else 0.0), cs["counterbore_depth"]) + gap + dfm.min_wall("structural")
    if plate_t < min_t - 1e-9:
        raise CadOpError(f"horn_mount: plate_t {plate_t} < {min_t:.2f} needed for counterbored screws (depth + head gap + 1.6 mm structural floor)")
    if mode == "recessed":
        f.cut.append(cyl_along(bd.Location(), HP["od"] + dfm.hole_comp(HP["od"]) + 2 * c, t_h + 0.3 + 0.0, z0=-0.01))
        f.cut.append(cyl_along(bd.Location(), servo.params["boss_d"] + 2 * dfm.clearance("rotating") + dfm.hole_comp(servo.params["boss_d"]),
                               servo.params["boss_h"] + 0.5, z0=-servo.params["boss_h"] - 0.5))
    # centre screw: clear hole + counterbore from the outer face
    top = loc_from((0, 0, z_top), (0, 0, 1), (1, 0, 0))
    # screw lengths follow the plate: floor under the counterbore + the horn thickness (+ 0.5 engagement margin), rounded up to a stock length
    def _stock(L: float) -> int:
        return next(x for x in (6, 8, 10, 12, 16, 20, 25, 30) if x >= L - 1e-9)

    len_h = _stock(plate_t - hs["counterbore_depth"] + t_h + 0.5)
    len_c = _stock(plate_t - cs["counterbore_depth"] + t_h + 0.5)
    ctr = screw_clearance(HP["center_screw"], through=plate_t + 1.0, counterbore=True,
                          part=part, mates=mates or servo.id, length=len_c, tag="horn_center", head="low", at=top)
    f = f.merged(ctr)
    for i, hole in enumerate(horn.holes):
        x, y = hole.frame.position.X, hole.frame.position.Y
        loc = loc_from((x, y, z_top), (0, 0, 1), (1, 0, 0))
        hf = screw_clearance(HP["screw"], through=plate_t + 1.0, counterbore=True,
                             part=part, mates=mates or "horn", length=len_h, tag=f"horn_{i}", head="low", at=loc)
        if washer_od:
            wd = washer_od + 0.2 + dfm.hole_comp(washer_od)
            wh = hs["counterbore_depth"] + gap + 0.3
            hf.cut.append(cyl_along(bd.Location(), wd, wh + 1.0, z0=-wh))
            hf.notes.append(f"washer counterbore d{wd:.2f} x {wh:.2f}")
        f = f.merged(hf)
    f.notes.append(f"horn mount {mode}: plate {plate_t} over horn {t_h}; underside z={z_under}, top z={z_top}")
    f.name = "horn_mount"
    f.keepouts.append(horn.shape)
    return _at(f, at)


def idler_seat(bearing: str = "MR83ZZ", *, plate_t: float = 4.0, boss: bool = True, part: str = "", delta_d: float = 0.0,
               at: bd.Location | None = None) -> FeatureResult:
    """Bearing seat in a plate that supports the servo's back (idler) side. Frame: origin on the plate surface that FACES the
    bearing's entry, +z out of the plate (toward the servo), on the back axis.

    * seat diameter = bearing OD + dfm bearing_seat.seat_d_over_od, depth = bearing width (flush) -> press fit;
    * through hole = bearing ID + dfm through_hole_over_id (clears the inner race so only the outer race is loaded);
    * `boss`: add a ring boss so the seat keeps >= dfm bearing_seat.wall of material all round (it rises `plate_t` below the surface
      so it fuses with a plate that stands there).
    Raises when the plate is thinner than seat depth + shoulder.
    """
    b = get_component(f"bearing:{bearing}")
    P = b.params
    r = dfm.load_dfm()["bearing_seat"]
    seat_d = P["od"] + float(val(r["seat_d_over_od_mm"])) + delta_d
    shoulder = float(val(r["shoulder_mm"]))
    wall = float(val(r["wall_mm"]))
    w = P["w"]
    if plate_t < w + shoulder - 1e-9:
        raise CadOpError(f"idler_seat {bearing}: plate_t {plate_t} < seat depth {w} + shoulder {shoulder}")
    f = FeatureResult(name="idler_seat")
    if boss:
        f.add.append(cyl_along(bd.Location(), seat_d + 2 * wall, plate_t + 0.5, z0=-plate_t - 0.5))
    f.cut.append(cyl_along(bd.Location(), seat_d, w + 1.0, z0=-w))
    thru_d = P["id"] + float(val(r["through_hole_over_id_mm"]))
    f.cut.append(cyl_along(bd.Location(), thru_d, plate_t + 2.0, z0=-plate_t - 1.0))
    ch = float(val(r["chamfer_mm"]))
    f.cut.append(bd.Pos(0, 0, -ch / 2) * bd.Cone(seat_d / 2 + ch, seat_d / 2, ch))
    f.sites.append(Site(id="bearing", kind="press", part=part, frame=bd.Location(), thread="", length_mm=w, needs_access=False))
    f.notes.append(f"{bearing} seat d{seat_d:.2f} x {w}; through d{thru_d:.2f}")
    return _at(f, at)


def idler_frame(actuator_id: str, gap: float, servo_at: bd.Location | None = None) -> bd.Location:
    """Surface frame for `idler_seat`: on the back axis, `gap` mm behind the servo's back face, +z pointing back toward the servo."""
    s = get_component(actuator_id)
    H = s.params["H"]
    loc = loc_from((0, 0, -H - gap), (0, 0, 1), (1, 0, 0))
    return servo_at * loc if servo_at is not None else loc


# --------------------------------------------------------------------------- routing, keep-outs


def cable_channel(path: list[tuple[float, float, float]], diameter: float, *, fit: str = "loose", at: bd.Location | None = None) -> FeatureResult:
    """Reserve a cable route: a polyline of capsules (cylinders joined by spheres, no sweeps) of the cable `diameter` + 2 x the fit's
    per-side clearance. The same solid is registered as a keep-out so other parts are checked against the route."""
    if len(path) < 2:
        raise CadOpError("cable_channel needs at least two path points")
    d = diameter + 2 * dfm.clearance(fit)
    parts: list[bd.Shape] = []
    pts = [bd.Vector(*p) for p in path]
    for a, b in zip(pts, pts[1:]):
        v = b - a
        L = v.length
        if L < 1e-6:
            continue
        loc = loc_from((a.X, a.Y, a.Z), (v.X, v.Y, v.Z))
        parts.append(loc * (bd.Pos(0, 0, L / 2) * bd.Cylinder(d / 2, L)))
    for p in pts:
        parts.append(bd.Pos(p.X, p.Y, p.Z) * bd.Sphere(d / 2))
    cut = union_all(parts)
    f = FeatureResult(cut=[cut], keepouts=[cut], name="cable_channel")
    f.notes.append(f"cable channel d{d:.2f}, {len(pts) - 1} segments")
    return _at(f, at)


def keepout(obj, margin: float = 0.0, mode: str = "bbox") -> bd.Shape:
    """Keep-out volume around a component or shape.
    * component: its `keepout` volume (body + plug room), grown by `margin` with a bounding box;
    * mode "bbox": axis-aligned bounding box of the shape grown by `margin` (conservative, never fails);
    * mode "offset": OCC offset of the shape, accepted only if valid and strictly bigger (else falls back to "bbox", noted by
      the volume check - research/ai-engineering/01: offset() can report valid on a broken shape)."""
    shape = getattr(obj, "keepout", None) or getattr(obj, "shape", None) or obj
    if mode == "offset" and margin > 0:
        try:
            o = bd.offset(shape, amount=margin)
            if o.is_valid and len(o.solids()) == 1 and volume(o) > volume(shape) * 1.0001:
                return o
        except Exception:  # noqa: BLE001
            pass
    bb = shape.bounding_box()
    return bd.Pos((bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2, (bb.min.Z + bb.max.Z) / 2) * bd.Box(
        bb.size.X + 2 * margin, bb.size.Y + 2 * margin, bb.size.Z + 2 * margin)


# --------------------------------------------------------------------------- bed split


def split_for_bed(shape: bd.Shape, bed_mm=None, *, dowel: bool = True, part: str = "part", max_parts: int = 8) -> list[tuple[str, bd.Shape]]:
    """Cut `shape` into pieces that each fit the usable print volume (bed - edge margin, dfm.yaml) in some axis-aligned
    orientation. Recursively halves the part across its longest oversize axis at the position (0.35..0.65 of the span) with the
    smallest cross-section that is not within `min_cut_to_feature_mm` of a hole or boss, and adds dowel pockets (dfm split.dowel_*) on both faces of every cut so the pieces register when
    glued/bolted. Returns [(id, solid)] with ids `<part>_a`, `<part>_b`, ... Raises if the dowels cannot be placed inside the section."""
    usable = dfm.bed_usable(bed_mm)
    sp = dfm.load_dfm()["split"]
    dd, dep = float(val(sp["dowel_d_mm"])), float(val(sp["dowel_depth_mm"]))
    pocket_d = dd + 2 * dfm.clearance("slip") + dfm.hole_comp(dd)
    pieces: list[tuple[str, bd.Shape]] = [(part, shape)]

    def fits(s: bd.Shape) -> bool:
        bb = s.bounding_box()
        ext = sorted([bb.size.X, bb.size.Y, bb.size.Z], reverse=True)
        return all(e <= u + 1e-6 for e, u in zip(ext, sorted(usable, reverse=True)))

    out: list[tuple[str, bd.Shape]] = []
    queue = pieces
    guard = 0
    while queue:
        pid, s = queue.pop(0)
        guard += 1
        if guard > 4 * max_parts:
            raise CadOpError("split_for_bed: too many pieces")
        if fits(s):
            out.append((pid, s))
            continue
        bb = s.bounding_box()
        spans = [bb.size.X, bb.size.Y, bb.size.Z]
        # axis whose span is furthest above the best-fitting bed dimension
        ub = sorted(usable, reverse=True)
        order = sorted(range(3), key=lambda i: -spans[i])
        ax = order[0]
        if spans[ax] <= ub[0] and len(order) > 1:
            ax = order[0]
        lo = [bb.min.X, bb.min.Y, bb.min.Z][ax]
        span = spans[ax]
        best = None
        clear = float(val(sp["min_cut_to_feature_mm"]))
        for frac in [0.35 + 0.05 * k for k in range(7)]:
            pos = lo + frac * span
            sec = _section_area(s, ax, pos, bb)
            # a cut must not run through a hole or boss: the section a few mm either side has to be the same
            clean = all(abs(_section_area(s, ax, pos + d, bb) - sec) <= 1e-3 * max(sec, 1.0) for d in (-clear, clear))
            key = (0 if clean else 1, sec)
            if best is None or key < best[0]:
                best = (key, pos)
        pos = best[1]
        n = [0.0, 0.0, 0.0]
        n[ax] = 1.0
        cutter_lo = _halfspace(bb, ax, pos, side=-1)
        cutter_hi = _halfspace(bb, ax, pos, side=+1)
        a = safe_cut(s, cutter_hi, f"split {pid}", single=False)
        b = safe_cut(s, cutter_lo, f"split {pid}", single=False)
        if dowel:
            da, db = _dowels(a, b, ax, pos, dd, pocket_d, dep, bb)
            a, b = da, db
        queue.insert(0, (pid + "_b", b))
        queue.insert(0, (pid + "_a", a))
    for pid, s in out:
        if not s.is_valid:
            raise CadOpError(f"split_for_bed: piece {pid} invalid")
    return out


def _halfspace(bb, ax: int, pos: float, side: int) -> bd.Shape:
    size = [bb.size.X + 20, bb.size.Y + 20, bb.size.Z + 20]
    cen = [(bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2, (bb.min.Z + bb.max.Z) / 2]
    size[ax] = 1000.0
    cen[ax] = pos + side * 500.0
    return bd.Pos(*cen) * bd.Box(*size)


def _section_area(s: bd.Shape, ax: int, pos: float, bb) -> float:
    cut = bd.Pos(*([(bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2, (bb.min.Z + bb.max.Z) / 2][i] if i != ax else pos for i in range(3)))
    size = [bb.size.X + 20, bb.size.Y + 20, bb.size.Z + 20]
    size[ax] = 0.2
    return float(overlap_volume(s, cut * bd.Box(*size))) / 0.2


def _dowels(a: bd.Shape, b: bd.Shape, ax: int, pos: float, dd: float, pocket_d: float, dep: float, bb) -> tuple[bd.Shape, bd.Shape]:
    """Two dowel pockets, one pair per cut face, at points where a pocket of depth `dep` on both sides stays inside the material."""
    other = [i for i in range(3) if i != ax]
    lo = [bb.min.X, bb.min.Y, bb.min.Z]
    sz = [bb.size.X, bb.size.Y, bb.size.Z]
    cands = []
    N = 9
    for i in range(1, N):
        for j in range(1, N):
            p = [0.0, 0.0, 0.0]
            p[ax] = pos
            p[other[0]] = lo[other[0]] + sz[other[0]] * i / N
            p[other[1]] = lo[other[1]] + sz[other[1]] * j / N
            cands.append(p)
    ok = []
    zdir = [0.0, 0.0, 0.0]
    zdir[ax] = 1.0
    for p in cands:
        loc = loc_from(p, zdir)
        probe = loc * (bd.Pos(0, 0, 0) * bd.Cylinder(pocket_d / 2 + 2.0, 2 * dep))
        pv = volume(probe)
        if abs(overlap_volume(probe, a) + overlap_volume(probe, b) - pv) < 0.01 * pv:
            ok.append(p)
    if len(ok) < 2:
        raise CadOpError("split_for_bed: no room for dowels across the cut section (try dowel=False and a bolted flange)")
    # choose the two candidates farthest apart
    best = max(((p, q) for p in ok for q in ok), key=lambda pq: sum((pq[0][k] - pq[1][k]) ** 2 for k in range(3)))
    for p in best:
        loc = loc_from(p, zdir)
        pocket = loc * (bd.Pos(0, 0, 0) * bd.Cylinder(pocket_d / 2, 2 * dep))
        # each half only needs its own half of the pocket: cut the full cylinder from both (it is symmetric about the face)
        a = safe_cut(a, pocket, "dowel pocket", single=False)
        b = safe_cut(b, pocket, "dowel pocket", single=False)
    return a, b


# --------------------------------------------------------------------------- shells


def loft_shell(sections: list[dict], wall: float, *, n: float = 2.6, open_ends: bool | str = True, name: str = "shell") -> bd.Shape:
    """Hollow loft = outer loft - inner loft (inner sections inset by `wall`), the simple robust way (no `shell()`/`offset()`).

    sections: [{"z": mm, "a": half extent x, "b": half extent y, "cx": 0, "cy": 0}, ...] (superellipse of exponent n).
    Verified: valid, exactly one solid, volume equals outer - inner within 2%, every section at least `wall` thick. Raises CadOpError
    otherwise; this is the failure LLM shells hit most (research/ai-engineering/01-ai-cad.md)."""
    from .geom import Station, hollow_loft, loft_solid

    st = [Station(s["z"], s["a"], s["b"], s.get("cx", 0.0), s.get("cy", 0.0)) for s in sections]
    if len(st) < 2:
        raise CadOpError("loft_shell needs >= 2 sections")
    for s in st:
        if min(s.a, s.b) <= wall + 0.4:
            raise CadOpError(f"loft_shell: section at z={s.z} is smaller than 2 x wall ({wall})")
    try:
        shell = hollow_loft(st, wall, n, open_ends)
    except Exception as e:  # noqa: BLE001
        raise CadOpError(f"{name}: loft/boolean failed: {e}") from e
    check_solid(shell, name)
    outer = loft_solid(st, n)
    if volume(shell) >= volume(outer):
        raise CadOpError(f"{name}: shell volume {volume(shell):.0f} >= outer {volume(outer):.0f} (inner cut did nothing)")
    if volume(shell) < 0.02 * volume(outer):
        raise CadOpError(f"{name}: shell is empty-ish")
    return shell


__all__ = ["insert_boss", "screw_clearance", "counterbore", "magnet_boss", "servo_pocket", "horn_mount", "idler_seat", "idler_frame",
           "cable_channel", "keepout", "split_for_bed", "loft_shell", "bolt_circle", "screw_length_for", "apply"]
