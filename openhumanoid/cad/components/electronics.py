"""Boards, battery, connector and switch models (data: components/data/electronics.yaml).

Frame: origin at the lower-left corner of the underside, +z up, +x along the long edge, +y along the short edge.
`holes` are the mounting holes with frame z pointing DOWN (out of the board toward the standoff / mounting surface);
`keepout` is the body grown by the part's margin (cables, header plugs, battery swelling).
"""
from __future__ import annotations

import build123d as bd

from ..core import loc_from
from . import Component, HoleSpec, load_data, prov, val


def build(component_id: str, margin: float | None = None, tall: float | None = None) -> Component:
    data = load_data("electronics")
    if component_id not in data:
        raise KeyError(f"unknown electronics part '{component_id}'")
    d = data[component_id]
    pv: dict = {}
    x, y, z = (float(v) for v in val(d["dims"]))
    prov(d["dims"], "dims", pv)
    z = float(tall or z)
    holes_xy = val(d["holes"])
    prov(d["holes"], "holes", pv)
    hd = float(val(d["hole_d"])) if "hole_d" in d else 0.0
    if "hole_d" in d:
        prov(d["hole_d"], "hole_d", pv)
    shape = bd.Pos(x / 2, y / 2, z / 2) * bd.Box(x, y, z)
    if component_id.startswith("rpi") or "adapter" in component_id or "buck" in component_id or "imu" in component_id:
        shape = bd.fillet(shape.edges().filter_by(bd.Axis.Z), min(2.0, 0.08 * min(x, y)))   # board corner radius
        shape = shape - core_holes(holes_xy, hd, z)
    m = float(margin if margin is not None else d.get("margin_mm", 1.0))
    keepout = bd.Pos(x / 2, y / 2, z / 2) * bd.Box(x + 2 * m, y + 2 * m, z + 2 * m)
    screw = str(d.get("screw", "M2.5"))
    holes = [HoleSpec(f"hole_{i}", loc_from((hx, hy, 0), (0, 0, -1), (1, 0, 0)), screw, 0.0, "clear", hd)
             for i, (hx, hy) in enumerate(holes_xy)]
    return Component(component_id, "board" if holes_xy else "battery" if "lipo" in component_id else "connector", shape,
                     float(d.get("mass_kg", 0.0)), {"origin": bd.Location(), "top": loc_from((x / 2, y / 2, z), (0, 0, 1))},
                     holes, keepout, {"x": x, "y": y, "z": z, "margin": m, "screw": screw, "hole_d": hd}, pv, catalog_id=component_id)


def core_holes(holes_xy, hd: float, z: float):
    out = None
    for hx, hy in holes_xy:
        c = bd.Pos(hx, hy, z / 2) * bd.Cylinder(hd / 2, z + 2)
        out = c if out is None else out + c
    return out
