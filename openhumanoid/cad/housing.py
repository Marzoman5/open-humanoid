"""`servo_housing`: a printed cradle for one servo, composed only of tested helpers (servo_pocket, insert_boss, screw_clearance).

Built in the servo frame (origin on the output axis at the horn-face plane, +z out of the horn face, +x toward the long end):

    z = +lip_t..c   far-end lip over the servo top face (retains the servo against +z, clear of the horn disc)
    z = c           block top (flush with the servo top face + fit clearance), near end open for the horn
    z = -H-c        block bottom: open pocket entry. A separate COVER plate closes it:
                    2 x M3 low-head screws into heat-set inserts in the thick far-end wall, one screw per side.
    walls           `wall` on both sides and the near end; the far end is `end_wall` thick (insert boss width) with the cable slot.

The housing exposes `servo_frame` so callers place it with `loc * housing.shape`. Everything stays parametric in the actuator, fit
class and wall; the numbers come from dfm.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import build123d as bd

from . import dfm
from .components import get as get_component
from .core import FeatureResult, Site, apply, box_at, loc_from
from .features import insert_boss, screw_clearance, servo_pocket


@dataclass
class Housing:
    shape: bd.Shape                      # block with pocket, lip and insert holes (servo frame)
    cover: bd.Shape                      # back cover plate (servo frame)
    sites: list[Site]
    servo_id: str
    params: dict
    keepouts: list[bd.Shape] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def placed(self, loc: bd.Location) -> "Housing":
        return Housing(loc * self.shape, loc * self.cover,
                       [Site(**{**s.__dict__, "frame": loc * s.frame}) for s in self.sites], self.servo_id, self.params,
                       [loc * k for k in self.keepouts], list(self.notes))


def servo_housing(actuator_id: str = "sts3215-12v", *, fit: str = "slip", wall: float | None = None, lip_t: float = 1.6,
                  cover_t: float = 3.2, stub_hole: bool = True, part: str = "housing", cover_part: str = "cover",
                  side_extra: tuple[float, float] = (0.0, 0.0), idler_boss_d: float | None = None) -> Housing:
    """Cradle for one servo with a screwed back cover. See module docstring.
    `side_extra` = extra wall thickness on (-y, +y) for joints that need material there (e.g. a bearing boss)."""
    servo = get_component(actuator_id)
    P = servo.params
    c = dfm.clearance(fit)
    w = wall or dfm.min_wall("load_path")
    ins = get_component("insert:M3")
    end_w = 2 * (ins.params["hole_d"] / 2 + dfm.load_dfm()["insert_boss"]["wall_mm"]["v"])      # 8.0 mm
    x0, x1 = -P["axis_x"] - c, P["far_end_x"] + c
    hw = P["W"] / 2 + c
    z_top, z_bot = c, -P["H"] - c
    block = box_at(bd.Location(), (x1 - x0 + w + end_w, 2 * (hw + w) + side_extra[0] + side_extra[1], z_top - z_bot),
                   ((x0 - w + x1 + end_w) / 2, (side_extra[1] - side_extra[0]) / 2, (z_top + z_bot) / 2))
    block = bd.fillet(block.edges().filter_by(bd.Axis.Z), 3.0)
    feats = [servo_pocket(actuator_id, fit, lip_t=lip_t, wall=w, part=part)]
    # cover inserts: two, in the far-end wall, outboard of the cable slot, opening onto the block bottom (z = z_bot), pointing -z
    y_ins = hw - 1.5     # keeps the hole edge 2 mm inside the outer wall and clear of the 12 mm cable slot
    x_ins = x1 + end_w / 2
    for i, sy in enumerate((-1, 1)):
        feats.append(insert_boss("M3", part=part, mates=cover_part, tag=f"cover_insert_{i}",
                                 at=loc_from((x_ins, sy * y_ins, z_bot), (0, 0, -1), (1, 0, 0))))
    shape, sites = apply(block, *feats, name=part)
    # cover plate
    cov = box_at(bd.Location(), (x1 - x0 + w + end_w, 2 * (hw + w) + side_extra[0] + side_extra[1], cover_t),
                 ((x0 - w + x1 + end_w) / 2, (side_extra[1] - side_extra[0]) / 2, z_bot - cover_t / 2))
    cov = bd.fillet(cov.edges().filter_by(bd.Axis.Z), 3.0)
    cfeats = []
    for i, sy in enumerate((-1, 1)):
        cfeats.append(screw_clearance("M3", through=cover_t, counterbore=True, head="low", part=cover_part, mates=part, length=8,
                                      tag=f"cover_screw_{i}", at=loc_from((x_ins, sy * y_ins, z_bot - cover_t), (0, 0, -1), (1, 0, 0))))
    if stub_hole:
        d = P["back_boss_d"] + 2 * dfm.clearance("sliding") + dfm.hole_comp(P["back_boss_d"])
        cfeats.append(FeatureResult(cut=[bd.Pos(0, 0, z_bot - cover_t / 2) * bd.Cylinder(d / 2, cover_t + 2)], name="stub_hole"))
    cov, csites = apply(cov, *cfeats, name=cover_part)
    return Housing(shape, cov, sites + csites, actuator_id,
                   {"x0": x0, "x1": x1, "hw": hw, "wall": w, "end_w": end_w, "z_top": z_top, "z_bot": z_bot, "cover_t": cover_t,
                    "outer_x": (x0 - w, x1 + end_w), "outer_y": (-(hw + w) - side_extra[0], hw + w + side_extra[1]),
                    "lip_t": lip_t, "x_ins": x_ins, "y_ins": y_ins},
                   [servo.keepout], [f"housing for {actuator_id}: outer {x1 - x0 + w + end_w:.1f} x {2 * (hw + w):.1f} x {z_top - z_bot:.1f}"])
