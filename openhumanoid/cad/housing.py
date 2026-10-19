"""`servo_housing`: a printed cradle for one servo, composed only of tested helpers (servo_pocket, insert_boss, screw_clearance).

Built in the servo frame (origin on the output axis at the horn-face plane, +z out of the horn face, +x toward the long end):

    z = +lip_t..c   far-end lip over the servo top face (retains the servo against +z, clear of the horn disc)
    z = c           block top (flush with the servo top face + fit clearance), near end open for the horn
    z = -H-c        block bottom: open pocket entry. A separate COVER plate closes it:
                    2 x M3 low-head screws into heat-set inserts in the thick far-end wall, one screw per side.
    walls           `wall` on both sides and the near end; the far end is `end_wall` thick (insert boss width) with the cable slot.

Composition rule: a bracket that contains a housing must UNION its other bodies with `housing.block` first and apply the housing's
features (pocket, inserts) afterwards, otherwise a later union would refill the pocket. `Housing.build(loc, adds=[...])` does that.
Everything stays parametric in the actuator, fit class and wall; the numbers come from dfm.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import build123d as bd

from . import dfm
from .components import get as get_component
from .core import FeatureResult, Site, apply, box_at, check_solid, cyl_along, loc_from, safe_union
from .features import insert_boss, screw_clearance, servo_pocket


@dataclass
class Housing:
    block: bd.Shape                      # raw outer block, servo frame (no pocket yet)
    feats: list[FeatureResult]           # pocket, lip, cover inserts (servo frame)
    cover: bd.Shape                      # back cover plate (servo frame), with idler pin if requested
    cover_sites: list[Site]
    servo_id: str
    params: dict
    shape: bd.Shape = None               # block + feats applied (standalone housing)
    sites: list[Site] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def build(self, loc: bd.Location, adds: list[bd.Shape] | None = None, extra: list[FeatureResult] | None = None,
              name: str = "bracket", fillet: float | None = None) -> tuple[bd.Shape, list[Site]]:
        """Union `adds` (world shapes) with the placed raw block, round the internal corners the union creates (dfm `fillet.default_mm`, set
        `fillet=0` to skip), then apply the housing features placed by `loc` and any `extra` features (world frame). Returns (shape, sites)
        in the same frame as `loc`."""
        base = loc * self.block
        for a in adds or []:       # bodies may only connect through each other: check for one solid after all are in
            base = safe_union(base, a, f"{name}+", single=False)
        check_solid(base, f"{name}: bodies do not form one solid (a plate or beam misses the housing)")
        if adds and (fillet is None or fillet > 0):
            from .fillets import fillet_internal

            base, rep = fillet_internal(base, fillet, min_len=6.0, name=name)
            self.notes.append(f"{name}: {rep['filleted']}/{rep['candidates']} internal edges filleted r={rep['radius_mm']:.1f}" + (f" ({'; '.join(rep['notes'])})" if rep["notes"] else ""))
        return apply(base, *[f.placed(loc) for f in self.feats], *(extra or []), name=name)

    def placed_cover(self, loc: bd.Location) -> tuple[bd.Shape, list[Site]]:
        return loc * self.cover, [Site(**{**s.__dict__, "frame": loc * s.frame}) for s in self.cover_sites]


def servo_housing(actuator_id: str = "sts3215-12v", *, fit: str = "slip", wall: float | None = None, lip_t: float = 1.6,
                  cover_t: float = 3.2, stub_hole: bool = True, part: str = "housing", cover_part: str = "cover",
                  side_extra: tuple[float, float] = (0.0, 0.0), idler: dict | None = None, slot_len: float = 40.0) -> Housing:
    """Cradle for one servo with a screwed back cover. See module docstring.
    `side_extra` = extra wall thickness on (-y, +y) for brackets that must reach plates beside the housing.
    `idler` = {"bearing": "MR105ZZ", "gap_mm": 1.5}: the cover carries a printed pin the bearing in the opposite plate rides on."""
    servo = get_component(actuator_id)
    P = servo.params
    c = dfm.clearance(fit)
    w = wall or dfm.min_wall("load_path")
    ins = get_component("insert:M3")
    scr = get_component("screw:M3x8L").params
    cb_r = (scr["counterbore_d"] + dfm.load_dfm()["screw"]["head_gap_mm"]["v"] + dfm.hole_comp(scr["counterbore_d"])) / 2
    # the far end must hold the insert (hole + 2 mm wall) AND leave >= the structural wall behind the cover's counterbore
    end_w = 2 * max(ins.params["hole_d"] / 2 + dfm.load_dfm()["insert_boss"]["wall_mm"]["v"], cb_r + dfm.min_wall("structural"))   # 9.7 mm
    x0, x1 = -P["axis_x"] - c, P["far_end_x"] + c
    hw = P["W"] / 2 + c
    z_top, z_bot = c, -P["H"] - c
    ylo, yhi = -(hw + w) - side_extra[0], hw + w + side_extra[1]
    xlo, xhi = x0 - w, x1 + end_w
    block = box_at(bd.Location(), (xhi - xlo, yhi - ylo, z_top - z_bot), ((xlo + xhi) / 2, (ylo + yhi) / 2, (z_top + z_bot) / 2))
    block = bd.fillet(block.edges().filter_by(bd.Axis.Z), 3.0)
    feats = [servo_pocket(actuator_id, fit, lip_t=lip_t, wall=w, slot_len=slot_len, part=part)]
    y_ins = hw + w - dfm.min_wall("structural") - cb_r      # counterbore keeps the structural wall to the side edge
    x_ins = x1 + end_w / 2
    for i, sy in enumerate((-1, 1)):
        feats.append(insert_boss("M3", part=part, mates=cover_part, tag=f"cover_insert_{i}",
                                 at=loc_from((x_ins, sy * y_ins, z_bot), (0, 0, -1), (1, 0, 0))))
    shape, sites = apply(block, *[f for f in feats], name=part)
    cov = box_at(bd.Location(), (xhi - xlo, yhi - ylo, cover_t), ((xlo + xhi) / 2, (ylo + yhi) / 2, z_bot - cover_t / 2))
    cov = bd.fillet(cov.edges().filter_by(bd.Axis.Z), 3.0)
    cfeats = []
    for i, sy in enumerate((-1, 1)):
        cfeats.append(screw_clearance("M3", through=cover_t, counterbore=True, head="low", part=cover_part, mates=part, length=8,
                                      tag=f"cover_screw_{i}", at=loc_from((x_ins, sy * y_ins, z_bot - cover_t), (0, 0, -1), (1, 0, 0))))
    if stub_hole:
        d = P["back_boss_d"] + 2 * dfm.clearance("sliding") + dfm.hole_comp(P["back_boss_d"])
        cfeats.append(FeatureResult(cut=[bd.Pos(0, 0, z_bot - cover_t / 2) * bd.Cylinder(d / 2, cover_t + 2)], name="stub_hole"))
    pin_info = None
    if idler:
        b = get_component(f"bearing:{idler['bearing']}")
        gap = float(idler.get("gap_mm", 1.5))
        pin_len = gap + b.params["w"] + 0.5
        pin_d = b.params["id"] - 2 * dfm.clearance("press")
        # the stub hole would be inside the pin footprint: the pin replaces it (the servo's back stub ends at z = -H - 3)
        cfeats = [f for f in cfeats if f.name != "stub_hole"]
        pin = cyl_along(loc_from((0, 0, z_bot - cover_t), (0, 0, -1), (1, 0, 0)), pin_d, pin_len + 0.5, z0=-0.5)
        cfeats.append(FeatureResult(add=[pin], name="idler_pin"))
        # relief for the servo back stub inside the cover (blind, from the inner face) so the pin is not weakened
        d = P["back_boss_d"] + 2 * dfm.clearance("sliding") + dfm.hole_comp(P["back_boss_d"])
        depth = P["back_top"] + 0.4
        if cover_t - depth < dfm.min_wall("structural") - 1e-9:
            from .core import CadOpError
            raise CadOpError(f"cover_t {cover_t} leaves {cover_t - depth:.2f} mm behind the stub relief (need {dfm.min_wall('structural')}): use a thicker cover")
        cfeats.append(FeatureResult(cut=[cyl_along(loc_from((0, 0, z_bot), (0, 0, 1), (1, 0, 0)), d, depth + 0.5, z0=-depth)], name="stub_relief"))
        pin_info = {"d": pin_d, "len": pin_len, "tip_z": z_bot - cover_t - pin_len}
    cov, csites = apply(cov, *cfeats, name=cover_part)
    prm = {"x0": x0, "x1": x1, "hw": hw, "wall": w, "end_w": end_w, "z_top": z_top, "z_bot": z_bot, "cover_t": cover_t,
           "outer_x": (xlo, xhi), "outer_y": (ylo, yhi), "lip_t": lip_t, "x_ins": x_ins, "y_ins": y_ins, "pin": pin_info,
           "cover_back_z": z_bot - cover_t}
    return Housing(block, feats, cov, csites, actuator_id, prm, shape, sites,
                   [f"housing for {actuator_id}: outer {xhi - xlo:.1f} x {yhi - ylo:.1f} x {z_top - z_bot:.1f}"])
