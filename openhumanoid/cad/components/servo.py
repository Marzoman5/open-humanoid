"""STS3215 / STS3250 servo model built from the catalog `mechanical:` block (catalog/actuators/*.yaml).

Frame: origin on the output axis at the horn-face plane, +z out of the horn face, +x toward the long end of the body, y = width.
The body occupies z in [-H, 0]; the output boss and spline stand on top (z > 0); the back boss/stub sits at z < -H.

Features exposed (`component.frames`): `axis` (identity), `horn_seat` (z = boss height, where a horn's underside sits),
`back_axis` (on the back face, +z pointing away from the body, i.e. -z of the servo frame), `cable_exit`.
`component.holes` are the case mounting holes (side faces). `component.keepout` includes the plug and cable bend room.
`component.params` carries: L, W, H, axis_x (axis distance from the near end), boss_h, spline_od, ...
"""
from __future__ import annotations

import build123d as bd

from .. import core
from ..core import loc_from
from . import Component, HoleSpec, load_data, prov, val


def _mech(catalog_id: str) -> tuple[dict, dict]:
    from ... import catalog

    p = catalog.get(catalog_id)
    if "mechanical" not in p:
        raise KeyError(f"catalog part '{catalog_id}' has no `mechanical:` block (see catalog/actuators/sts3215-12v.yaml)")
    return p, p["mechanical"]


def build(catalog_id: str = "sts3215-12v", horn: bool = False) -> Component:
    """Servo body + output boss/spline + back boss/stub. `horn=True` also fits the 25T round horn on the output (as a second solid)."""
    p, m = _mech(catalog_id)
    pv: dict = {}
    L, W, H = (float(x) for x in val(m["body_mm"]))
    prov(m["body_mm"], "body_mm", pv)
    ax = float(val(m["axis_from_near_end_mm"]))
    prov(m["axis_from_near_end_mm"], "axis_from_near_end_mm", pv)
    rf = float(val(m["corner_fillet_mm"]))
    sp = m["output_spline"]
    boss_d, boss_h = float(val(sp["boss_d_mm"])), float(val(sp["boss_h_mm"]))
    spl_od, spl_top = float(val(sp["od_mm"])), float(val(sp["protrusion_mm"]))
    horn_float = float(val(sp["horn_float_mm"])) if "horn_float_mm" in sp else 0.0
    if "horn_float_mm" in sp:
        prov(sp["horn_float_mm"], "output_spline.horn_float_mm", pv)
    for k in ("teeth", "od_mm", "boss_d_mm", "boss_h_mm", "protrusion_mm", "center_screw"):
        prov(sp[k], f"output_spline.{k}", pv)
    bs = m["back_shaft"]
    back_d, back_h = float(val(bs["boss_d_mm"])), 1.0
    stub_od, stub_top = float(val(bs["spline_od_mm"])), float(val(bs["protrusion_mm"]))
    for k in ("spline_od_mm", "protrusion_mm", "boss_d_mm"):
        prov(bs[k], f"back_shaft.{k}", pv)

    body = bd.Pos((L - 2 * ax) / 2, 0, -H / 2) * bd.Box(L, W, H)
    body = bd.fillet(body.edges().filter_by(bd.Axis.Z), rf)
    boss = bd.Pos(0, 0, boss_h / 2) * bd.Cylinder(boss_d / 2, boss_h)
    spline = bd.Pos(0, 0, (boss_h + spl_top) / 2) * bd.Cylinder(spl_od / 2, spl_top - boss_h)
    back_boss = bd.Pos(0, 0, -H - back_h / 2) * bd.Cylinder(back_d / 2, back_h)
    stub = bd.Pos(0, 0, -H - (back_h + stub_top) / 2) * bd.Cylinder(stub_od / 2, stub_top - back_h)
    shape = core.union_all([body, boss, spline, back_boss, stub])
    case_shape = core.union_all([body, boss, back_boss])          # static part of the servo
    shaft_front, shaft_back = spline, stub                        # these two turn with the output

    frames = {
        "axis": bd.Location(),
        "horn_seat": loc_from((0, 0, boss_h + horn_float), (0, 0, 1), (1, 0, 0)),
        "back_axis": loc_from((0, 0, -H), (0, 0, -1), (1, 0, 0)),
    }

    # case mounting holes on both long side faces; frame z points out of the face
    ch = m["case_holes"]
    thr, depth = str(val(ch["thread"])), float(val(ch["depth_mm"]))
    for k in ("thread", "depth_mm", "x_mm", "z_mm"):
        prov(ch[k], f"case_holes.{k}", pv)
    holes = []
    for side, sgn in (("+y", 1), ("-y", -1)):
        for i, x in enumerate(val(ch["x_mm"])):
            for j, z in enumerate(val(ch["z_mm"])):
                holes.append(HoleSpec(f"case_{side}_{i}{j}", loc_from((x, sgn * W / 2, z), (0, sgn, 0), (1, 0, 0)), thr, depth,
                                      "tapped", float(thr[1:])))

    # cable: connector face, plug/bend keep-out beyond the end
    cb = m["cable"]
    cz = float(val(cb["z_mm"]))
    cw, chh = (float(x) for x in val(cb["socket_wh_mm"]))
    plug = float(val(cb["plug_len_mm"]))
    for k in ("connector", "face", "z_mm", "socket_wh_mm", "plug_len_mm"):
        prov(cb[k], f"cable.{k}", pv)
    x_end = L - ax
    frames["cable_exit"] = loc_from((x_end, 0, cz), (1, 0, 0), (0, 0, 1))
    plug_ko = bd.Pos(x_end + plug / 2, 0, cz) * bd.Box(plug, cw, chh)

    keepout = core.union_all([shape, plug_ko])
    comp = Component(
        id=catalog_id, kind="servo", shape=shape, mass_kg=float(p.get("mass_kg", 0.055)), frames=frames, holes=holes,
        keepout=keepout, catalog_id=catalog_id,
        params={"L": L, "W": W, "H": H, "axis_x": ax, "near_end_x": -ax, "far_end_x": L - ax, "boss_h": boss_h, "horn_float": horn_float, "boss_d": boss_d,
                "spline_od": spl_od, "spline_top": spl_top, "back_boss_d": back_d, "back_top": stub_top, "plug_len": plug,
                "corner_r": float(((W / 2) ** 2 + max(ax, L - ax) ** 2) ** 0.5), "cable_z": cz, "case_hole_thread": thr,
                "case_shape": case_shape, "shaft_shapes": (shaft_front, shaft_back)},
        provenance=pv)
    if horn:
        from .hardware import horn as mk_horn

        h = mk_horn()
        hs = frames["horn_seat"]
        comp.shape = bd.Compound(children=[shape, hs * h.shape])
        comp.params["horn"] = h.params
        comp.provenance.update({f"horn.{k}": v for k, v in h.provenance.items()})
        comp.params["top_z"] = boss_h + horn_float + h.params["thickness"]
    else:
        comp.params["top_z"] = spl_top
    return comp
