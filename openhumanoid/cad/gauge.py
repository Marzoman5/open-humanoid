"""Fit gauge generator (research F2): a small printable test part built from the SAME helper code as the real parts.

Print this first (about 20-30 min). It tells you, with a servo, a horn, a handful of inserts, magnets and bearings in hand, whether
the tolerances in `dfm.yaml` and the ESTIMATED servo dimensions in the catalog are right, BEFORE any real part is printed.

Tiles (separate bodies, print flat as arranged; numbers are engraved if a font is available, otherwise counted notches on the edge):
  G1 servo slice     the real pocket cross-section (sts3215 envelope + slip fit + cable slot) 8 mm thick. The servo must drop through, snug.
  G2 height gauge    a slot of width H + 2 x clearance: the servo (35 mm across its axis) laid in it. Also a slot for width W.
  G3 horn probe      centre screw hole + four radial slots r = 4..9 mm at 45 deg: find the horn's real bolt circle; a disc outline of the horn OD.
  G4 insert ladder   M3 insert holes at -0.3 .. +0.3 mm around the dfm diameter (and M2). Press an insert in with a soldering iron.
  G5 bearing ladder  bearing seats at -0.2 .. +0.3 mm around the dfm diameter, with through holes (default bearing MR105ZZ).
  G6 clearance       holes for a 5.0 mm peg at per-side clearance 0.05 .. 0.40 mm (hole = 5 + hole_comp + 2 c, exactly like the real parts) + the peg bar.
  G7 magnets         6x3 pockets at +0.0 .. +0.3 mm (open) and a covered one (pause-print).
  G8 walls/bridges   wall steps 0.8 .. 2.4 mm and bridge spans 6 .. 18 mm.

`python -m openhumanoid.cad gauge --out DIR` writes gauge.step, gauge.stl, gauge_key.md (what each hole means and how to read the result) and
gauge.json. `read_results({...})` turns the maintainer's readings into proposed dfm.yaml values (never applied automatically).
"""
from __future__ import annotations

import json
from pathlib import Path

import build123d as bd

from . import dfm
from .components import get as get_component
from .core import FeatureResult, apply, box_at, cyl_along, loc_from, safe_cut, safe_union
from .features import horn_mount, idler_seat, insert_boss, magnet_boss
from .housing import servo_housing

PITCH = 9.0
LADDER_INSERT = [-0.2, -0.1, 0.0, 0.1, 0.2]
LADDER_BEARING = [-0.1, 0.0, 0.1, 0.2, 0.3]
LADDER_CLEAR = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40]
LADDER_MAGNET = [0.0, 0.1, 0.2, 0.3]
WALLS = [0.8, 1.2, 1.6, 2.0, 2.4]
BRIDGES = [6, 12, 18]


def _label(n: int, at_xy: tuple[float, float], z: float) -> bd.Shape | None:
    """Engraved digit `n` as a cutter (None if no font is available)."""
    try:
        t = bd.Text(str(n), 3.2, 0.5, align=(bd.Align.CENTER, bd.Align.CENTER))
        return bd.Pos(at_xy[0], at_xy[1], z - 0.25) * t
    except Exception:  # noqa: BLE001
        return None


def _tile_servo_slice(actuator: str) -> tuple[bd.Shape, dict]:
    h = servo_housing(actuator)
    P = get_component(actuator).params
    z0, z1 = -29.0, -24.0                      # slab through the body mid-lower region: pocket outline + cable slot, no lip
    slab = box_at(bd.Location(), (200, 200, z1 - z0), (0, 0, (z0 + z1) / 2))
    piece = h.shape & slab
    piece = bd.Pos(0, 0, -z0) * piece           # axis z' is the build direction; slab bottom on z = 0
    return piece, {"id": "G1", "what": "servo pocket slice (L x W outline, corner radius, cable slot)", "drop_servo": True,
                   "expect_mm": {"pocket_L": P["L"] + 2 * dfm.clearance("slip"), "pocket_W": P["W"] + 2 * dfm.clearance("slip")}}


def _tile_height(actuator: str) -> tuple[bd.Shape, dict]:
    P = get_component(actuator).params
    c = dfm.clearance("slip")
    slot_h, slot_w = P["H"] + 2 * c, P["W"] + 2 * c
    w = slot_h + 2 * 4
    blk = box_at(bd.Location(), (w, 10, 6), (0, 0, 3))
    blk = safe_cut(blk, box_at(bd.Location(), (slot_h, 12, 5), (0, 0, 4.5)), "G2 slot H", single=False)
    blk2 = box_at(bd.Location(), (slot_w + 8, 10, 6), (0, 0, 3))
    blk2 = safe_cut(blk2, box_at(bd.Location(), (slot_w, 12, 5), (0, 0, 4.5)), "G2 slot W", single=False)
    both = bd.Compound(children=[blk, bd.Pos(0, -12, 0) * blk2])
    return both, {"id": "G2", "what": "servo height (35 mm across the axis) and width slots", "expect_mm": {"slot_H": slot_h, "slot_W": slot_w}}


def _tile_horn(actuator: str) -> tuple[bd.Shape, dict]:
    P = get_component(actuator).params
    horn = get_component("horn-25t")
    t = 3.2
    plate = box_at(bd.Location(), (44, 30, t), (0, 0, t / 2))
    plate = bd.fillet(plate.edges().filter_by(bd.Axis.Z), 4.0)
    hm = horn_mount(actuator, plate_t=t, mode="flat")
    # in the horn_seat frame the plate would sit at z = horn_t; shift the feature down so the plate is at z in [0, t]
    shift = bd.Pos(0, 0, -horn.params["thickness"])
    cuts = [shift * c for c in hm.cut]
    for c in cuts:
        plate = safe_cut(plate, c, "G3 horn", single=False)
    # radial probe slots: from r=4 to 9 along the four 45-degree directions, width = horn screw clearance
    scr = get_component("screw:" + horn.params["screw"] + "x6L").params
    sw = scr["clearance_medium"] + dfm.hole_comp(scr["clearance_medium"])
    import math
    for k in range(4):
        a = math.radians(45 + 90 * k)
        cx, cy = 6.5 * math.cos(a), 6.5 * math.sin(a)
        # slot as a stadium: box + two cylinders
        s = bd.Pos(cx, cy, t / 2) * bd.Rot(0, 0, math.degrees(a)) * (bd.Box(5.0, sw, t + 2) + bd.Pos(2.5, 0, 0) * bd.Cylinder(sw / 2, t + 2)
                                                                          + bd.Pos(-2.5, 0, 0) * bd.Cylinder(sw / 2, t + 2))
        plate = safe_cut(plate, s, "G3 slot", single=False)
    return plate, {"id": "G3", "what": "horn probe: the four screw slots span r = 4..9 mm; find where the horn's real holes sit",
                   "expect_mm": {"horn_od": horn.params["od"], "bolt_circle_d_estimate": horn.params["bolt_circle_d"]}}


def _ladder_block(n: int, pitch: float, depth: float, thick: float, width: float = 13.0) -> bd.Shape:
    return box_at(bd.Location(), (n * pitch + 2, width, thick), ((n - 1) * pitch / 2, 0, thick / 2))


def _tile_inserts() -> tuple[bd.Shape, dict]:
    ins = get_component("insert:M3")
    thick = ins.params["hole_depth"] + dfm.load_dfm()["insert_boss"]["min_floor_mm"]["v"] + 0.4
    base = _ladder_block(len(LADDER_INSERT), PITCH, ins.params["hole_depth"], thick, 9.0)
    feats = [insert_boss("M3", delta_d=d, at=loc_from((i * PITCH, 0, thick), (0, 0, 1))) for i, d in enumerate(LADDER_INSERT)]
    m2 = get_component("insert:M2")
    thick2 = m2.params["hole_depth"] + 1.6
    shape, _ = apply(base, *feats, name="G4")
    key = {"id": "G4", "what": "M3 heat-set insert holes (index 1 = smallest). Pick the hole where the insert seats flush with a steady push.",
           "nominal_d_mm": ins.params["hole_d"], "ladder_delta_mm": LADDER_INSERT, "depth_mm": ins.params["hole_depth"]}
    return shape, key


def _tile_bearing(bearing: str) -> tuple[bd.Shape, dict]:
    b = get_component(f"bearing:{bearing}")
    plate_t = b.params["w"] + dfm.load_dfm()["bearing_seat"]["shoulder_mm"]["v"]
    wall = 1.6
    pitch = b.params["od"] + 2 * wall + 0.4
    n = len(LADDER_BEARING)
    base = box_at(bd.Location(), (n * pitch + 2, b.params["od"] + 2 * wall, plate_t), ((n - 1) * pitch / 2, 0, plate_t / 2))
    feats = [idler_seat(bearing, plate_t=plate_t, boss=False, delta_d=d, at=loc_from((i * pitch, 0, plate_t), (0, 0, 1)))
             for i, d in enumerate(LADDER_BEARING)]
    shape, _ = apply(base, *feats, name="G5")
    seat = b.params["od"] + dfm.load_dfm()["bearing_seat"]["seat_d_over_od_mm"]["v"]
    return shape, {"id": "G5", "what": f"{bearing} bearing seats (index 1 = tightest). Pick the seat where the bearing needs a firm thumb push and does not fall out.",
                   "bearing": bearing, "nominal_seat_d_mm": seat, "ladder_delta_mm": LADDER_BEARING}


def _tile_clearance() -> tuple[bd.Shape, dict]:
    peg_d = 5.0
    n = len(LADDER_CLEAR)
    pitch = 10.0
    plate = box_at(bd.Location(), (n * pitch + 2, 11, 3), ((n - 1) * pitch / 2, 0, 1.5))
    for i, c in enumerate(LADDER_CLEAR):
        d = dfm.hole_d(peg_d, None) + 2 * c           # hole = nominal + hole_comp + 2 c: same recipe as the real parts
        plate = safe_cut(plate, cyl_along(loc_from((i * pitch, 0, 0), (0, 0, 1)), d, 5.0, z0=-1), "G6 hole", single=False)
    bar = box_at(bd.Location(), (n * pitch + 2, 8, 1.6), ((n - 1) * pitch / 2, -15, 0.8))
    for i in range(n):
        bar = safe_union(bar, cyl_along(loc_from((i * pitch, -15, 0), (0, 0, 1)), peg_d, 6.0, z0=1.0), "G6 peg", single=True)
    return bd.Compound(children=[plate, bar]), {
        "id": "G6", "what": "clearance ladder: hole k takes the 5.0 mm peg at per-side clearance c_k. Smallest hole where the peg slides by hand = slip; "
                            "where it also spins freely = rotating.", "peg_d_mm": peg_d, "per_side_clearance_mm": LADDER_CLEAR,
        "hole_comp_mm": dfm.hole_comp(peg_d)}


def _tile_magnets() -> tuple[bd.Shape, dict]:
    n = len(LADDER_MAGNET) + 1
    pitch = 9.0
    t = 4.2
    base = box_at(bd.Location(), (n * pitch + 2, 10, t), ((n - 1) * pitch / 2, 0, t / 2))
    feats = [magnet_boss("6x3", access="open", delta_d=d, at=loc_from((i * pitch, 0, t), (0, 0, 1))) for i, d in enumerate(LADDER_MAGNET)]
    feats.append(magnet_boss("6x3", access="pause", at=loc_from(((n - 1) * pitch, 0, t), (0, 0, 1))))
    shape, _ = apply(base, *feats, name="G7")
    return shape, {"id": "G7", "what": "magnet pockets (open, +0.0..+0.3 mm). Last one is the covered, pause-print version.",
                   "ladder_delta_mm": LADDER_MAGNET}


def _tile_walls() -> tuple[bd.Shape, dict]:
    base = box_at(bd.Location(), (58, 30, 1.2), (24, 8, 0.6))
    for i, w in enumerate(WALLS):
        base = safe_union(base, box_at(bd.Location(), (w, 14, 7), (i * 8, 0, 3.5 + 0.6)), "G8 wall", single=True)
    for i, span in enumerate(BRIDGES):
        x0 = i * 22 - 4
        y = 13
        post = lambda xc: box_at(bd.Location(), (3, 6, 6), (xc, y, 3.0 + 0.6))   # noqa: E731
        deck = box_at(bd.Location(), (span + 6, 6, 1.2), (x0 + (span + 3) / 2, y, 6.0 + 0.6 - 0.6 + 0.6))
        # posts and deck are added together so the part is never momentarily in two pieces
        group = safe_union(safe_union(post(x0), deck, "G8 deck", single=True), post(x0 + span + 3), "G8 post", single=True)
        base = safe_union(base, group, "G8 bridge", single=True)
    return base, {"id": "G8", "what": "wall steps (0.8..2.4 mm) and bridge spans (6, 12, 18 mm); note which walls print as solid lines and which bridges sag.",
                  "walls_mm": WALLS, "bridges_mm": BRIDGES}


def build(actuator: str = "sts3215-12v", bearing: str = "MR105ZZ") -> tuple[bd.Shape, list[dict]]:
    """All tiles arranged on a 2-row sheet (separate bodies). Returns (compound, key list)."""
    tiles = [_tile_servo_slice(actuator), _tile_height(actuator), _tile_horn(actuator), _tile_inserts(), _tile_bearing(bearing),
             _tile_clearance(), _tile_magnets(), _tile_walls()]
    placed, keys = [], []
    x, y, row_h = 0.0, 0.0, 0.0
    max_w = 210.0
    for shape, key in tiles:
        bb = shape.bounding_box()
        w, d = bb.size.X, bb.size.Y
        if x + w > max_w:
            x, y, row_h = 0.0, y + row_h + 6.0, 0.0
        loc = bd.Pos(x - bb.min.X, y - bb.min.Y, -bb.min.Z)
        placed.append(loc * shape)
        key = dict(key)
        key["origin_mm"] = [round(x, 1), round(y, 1)]
        key["size_mm"] = [round(w, 1), round(d, 1), round(bb.size.Z, 1)]
        keys.append(key)
        x += w + 6.0
        row_h = max(row_h, d)
    return bd.Compound(children=placed), keys


def volume_mm3(shape: bd.Shape) -> float:
    return float(sum(s.volume for s in shape.solids()))


def estimate_minutes(shape: bd.Shape, infill: float = 0.15) -> float:
    """Crude print-time estimate: extruded volume ~ (perimeter shells + infill) at ~7 mm3/s, plus a few minutes of travel/heat-up."""
    v = volume_mm3(shape)
    extruded = v * (0.35 + 0.65 * infill)         # thin tiles are mostly shell
    return extruded / 7.0 / 60.0 + 3.0


def write(out_dir: Path, actuator: str = "sts3215-12v", bearing: str = "MR105ZZ") -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    shape, keys = build(actuator, bearing)
    bd.export_step(shape, str(out_dir / "gauge.step"))
    bd.export_stl(shape, str(out_dir / "gauge.stl"), tolerance=0.02, angular_tolerance=0.1)
    info = {"actuator": actuator, "bearing": bearing, "volume_cm3": round(volume_mm3(shape) / 1000, 2),
            "est_print_min": round(estimate_minutes(shape), 0), "tiles": keys, "dfm_version": dfm.load_dfm()["version"],
            "estimates_to_confirm": get_component(actuator).estimates()}
    (out_dir / "gauge.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (out_dir / "gauge_key.md").write_text(_key_md(info), encoding="utf-8")
    return info


def _key_md(info: dict) -> str:
    L = ["# Fit gauge key", "", f"Generated by `python -m openhumanoid.cad gauge`; dfm version {info['dfm_version']}. Volume {info['volume_cm3']} cm3, "
         f"print-time estimate {info['est_print_min']:.0f} min at 0.2 mm layers, 15% infill, PETG or PLA+ (the material the real parts use).", "",
         "Print the sheet flat as arranged. Then, with a servo, a horn, M3 and M2 heat-set inserts, a 6x3 magnet and the bearing in hand:", ""]
    for t in info["tiles"]:
        L.append(f"- **{t['id']}** {t['what']}")
        for k, v in t.items():
            if k.endswith("_mm") or k.startswith("ladder") or k in ("expect_mm",):
                L.append(f"    - {k}: {v}")
    L += ["", "## Record the result", "", "Fill in `gauge_results.yaml` (see `read_results` in openhumanoid/cad/gauge.py) with the index (1 = first hole) that fits:", "",
          "```yaml", "servo_slice_drops_in: true            # G1, snug but no force", "servo_height_fits: true               # G2 (35 mm axis)",
          "horn_hole_radius_mm: 7.0               # G3, where the horn screw holes line up in the slots",
          "horn_od_mm: 20.0", "insert_m3_hole_index: 4", "bearing_seat_index: 3", "clearance_slip_index: 3     # G6, smallest hole where the peg slides by hand",
          "clearance_rotating_index: 6", "magnet_pocket_index: 2", "```", "",
          "Items marked ESTIMATE in the catalog (`estimates_to_confirm` in gauge.json) are what G1-G3 verify: the horn axis offset, boss height, "
          "horn bolt circle, back-shaft and cable-exit positions. Measure them with calipers while the servo is out."]
    return "\n".join(L) + "\n"


def read_results(res: dict) -> dict:
    """Turn gauge readings into PROPOSED dfm.yaml changes (printed for a human to apply; nothing is edited)."""
    prop: dict = {}
    if "clearance_slip_index" in res:
        prop["clearance.slip.per_side_mm"] = LADDER_CLEAR[int(res["clearance_slip_index"]) - 1]
    if "clearance_rotating_index" in res:
        prop["clearance.rotating.per_side_mm"] = LADDER_CLEAR[int(res["clearance_rotating_index"]) - 1]
    if "insert_m3_hole_index" in res:
        prop["components/data/hardware.yaml inserts.M3.hole_d"] = round(get_component("insert:M3").params["hole_d"] + LADDER_INSERT[int(res["insert_m3_hole_index"]) - 1], 2)
    if "bearing_seat_index" in res:
        prop["bearing_seat.seat_d_over_od_mm"] = round(dfm.load_dfm()["bearing_seat"]["seat_d_over_od_mm"]["v"] + LADDER_BEARING[int(res["bearing_seat_index"]) - 1], 2)
    if "magnet_pocket_index" in res:
        prop["magnet.extra_d_mm"] = round(dfm.load_dfm()["magnet"]["extra_d_mm"]["v"] + LADDER_MAGNET[int(res["magnet_pocket_index"]) - 1], 2)
    if "horn_hole_radius_mm" in res:
        prop["components/data/hardware.yaml horns.round_25t.bolt_circle_d"] = round(2 * float(res["horn_hole_radius_mm"]), 2)
    if "horn_od_mm" in res:
        prop["components/data/hardware.yaml horns.round_25t.od"] = float(res["horn_od_mm"])
    if res.get("servo_slice_drops_in") is False:
        prop["clearance.slip.per_side_mm"] = "increase by 0.1 and re-run G1"
    return prop
