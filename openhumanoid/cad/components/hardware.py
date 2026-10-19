"""Screws, heat-set inserts, magnets, bearings and servo horns (data: components/data/hardware.yaml).

Installed-hardware frame: origin on the host surface, +z out of the host part. Screw head at z > 0 (underside of the head at z = 0),
shank at z < 0. Insert / magnet / bearing bodies at z < 0 (the opening is at z = 0).
"""
from __future__ import annotations

import math
import re

import build123d as bd

from ..core import loc_from
from . import Component, HoleSpec, load_data, prov, val

# densities for catalog masses (g/cm3)
_STEEL, _BRASS, _NDFEB = 7.85, 8.4, 7.5


def _g(sect: str, key: str) -> dict:
    d = load_data("hardware")[sect]
    if key not in d:
        raise KeyError(f"'{key}' not in hardware.yaml {sect}. Known: {sorted(d)}")
    return d[key]


def screw(spec: str = "M3x8") -> Component:
    """Socket-head cap screw (ISO 4762). `spec` = "M3x8" (thread x length in mm); a trailing L ("M3x8L") means the low-head
    DIN 7984 variant (shorter head, shallower counterbore)."""
    m = re.fullmatch(r"(M[0-9.]+)x([0-9.]+)(L?)", spec)
    if not m:
        raise ValueError(f"screw spec must look like 'M3x8' or 'M3x8L', got '{spec}'")
    thread, length, low = m.group(1), float(m.group(2)), bool(m.group(3))
    s = _g("screws", thread)
    d = float(thread[1:])
    head_d, head_k = float(val(s["head_d"])), float(val(s["low_head_k" if low else "head_k"]))
    head = bd.Pos(0, 0, head_k / 2) * bd.Cylinder(head_d / 2, head_k)
    key = float(val(s["hex_key"]))
    sock_d = 0.6 * head_k
    head = head - bd.Pos(0, 0, head_k - sock_d) * bd.extrude(bd.RegularPolygon(key / math.sqrt(3), 6), amount=sock_d + 0.01)
    shank = bd.Pos(0, 0, -length / 2) * bd.Cylinder(d / 2, length)
    shape = head + shank
    pv: dict = {}
    for k in ("head_d", "head_k", "hex_key"):
        prov(s[k], k, pv)
    mass = (math.pi * (head_d / 2) ** 2 * head_k + math.pi * (d / 2) ** 2 * length) * _STEEL * 1e-6   # kg
    return Component(f"screw:{spec}", "screw", shape, mass, {"seat": bd.Location()}, [], None,
                     {"thread": thread, "length": length, "d": d, "head_d": head_d, "head_k": head_k, "hex_key": key,
                      "clearance_close": float(val(s["clearance_close"])), "clearance_medium": float(val(s["clearance_medium"])),
                      "counterbore_d": float(val(s["counterbore_d"])), "counterbore_depth": float(val(s["low_counterbore_depth" if low else "counterbore_depth"])), "low_head": low,
                      "tap_drill": float(val(s["tap_drill"])), "tool_corridor_d": float(val(s["tool_corridor_d"]))}, pv)


def insert(thread: str = "M3", length: float | None = None) -> Component:
    """Heat-set brass insert. Opening at z = 0, body at z < 0."""
    s = _g("inserts", thread)
    od, ln = float(val(s["od"])), float(length or val(s["length"]))
    shape = bd.Pos(0, 0, -ln / 2) * (bd.Cylinder(od / 2, ln) - bd.Cylinder(float(thread[1:]) / 2, ln + 1))
    pv: dict = {}
    for k in ("od", "length", "hole_d", "hole_depth", "wall"):
        prov(s[k], k, pv)
    mass = math.pi * ((od / 2) ** 2 - (float(thread[1:]) / 2) ** 2) * ln * _BRASS * 1e-6
    return Component(f"insert:{thread}", "insert", shape, mass, {"seat": bd.Location()}, [], None,
                     {"thread": thread, "od": od, "length": ln, "hole_d": float(val(s["hole_d"])),
                      "hole_depth": float(val(s["hole_depth"])) - float(val(s["length"])) + ln, "wall": float(val(s["wall"]))}, pv)


def magnet(spec: str = "6x3") -> Component:
    """Neodymium disc magnet 'DxH'. Opening at z = 0, body at z < 0."""
    m = re.fullmatch(r"([0-9.]+)x([0-9.]+)", spec)
    if not m:
        raise ValueError("magnet spec must look like '6x3'")
    d, h = float(m.group(1)), float(m.group(2))
    ref = _g("magnets", "disc_6x3")
    pv: dict = {}
    prov(ref["d"], "d", pv)
    prov(ref["h"], "h", pv)
    shape = bd.Pos(0, 0, -h / 2) * bd.Cylinder(d / 2, h)
    return Component(f"magnet:{spec}", "magnet", shape, math.pi * (d / 2) ** 2 * h * _NDFEB * 1e-6, {"seat": bd.Location()}, [], None,
                     {"d": d, "h": h, "tolerance": float(val(ref["tolerance"]))}, pv)


def bearing(name: str = "MR85ZZ") -> Component:
    """Radial ball bearing (ring, simplified). Body spans z in [-w, 0] (one face on the host surface); flange (if any) sits above z = 0."""
    b = _g("bearings", name)
    idm, od, w = float(val(b["id"])), float(val(b["od"])), float(val(b["w"]))
    pv: dict = {}
    for k in ("id", "od", "w"):
        prov(b[k], k, pv)
    ring = bd.Pos(0, 0, -w / 2) * (bd.Cylinder(od / 2, w) - bd.Cylinder(idm / 2, w + 1))
    params = {"id": idm, "od": od, "w": w, "flange_d": None, "flange_t": 0.0}
    if "flange_d" in b:
        fd, ft = float(val(b["flange_d"])), float(val(b["flange_t"]))
        prov(b["flange_d"], "flange_d", pv)
        prov(b["flange_t"], "flange_t", pv)
        ring = ring + bd.Pos(0, 0, ft / 2) * (bd.Cylinder(fd / 2, ft) - bd.Cylinder(idm / 2, ft + 1))
        params.update(flange_d=fd, flange_t=ft)
    mass = math.pi * ((od / 2) ** 2 - (idm / 2) ** 2) * w * _STEEL * 0.6 * 1e-6
    return Component(f"bearing:{name}", "bearing", ring, mass, {"seat": bd.Location()}, [], None, params, pv)


def horn(variant: str = "round_25t") -> Component:
    """25-tooth round servo horn. Underside (seating plane) at z = 0, disc extends to +thickness. Holes on a bolt circle."""
    h = _g("horns", variant)
    od, t = float(val(h["od"])), float(val(h["thickness"]))
    bore = float(val(h["spline_od"]))
    bcd, n, hd = float(val(h["bolt_circle_d"])), int(val(h["n_holes"])), float(val(h["hole_d"]))
    pv: dict = {}
    for k in ("teeth", "spline_od", "od", "thickness", "bolt_circle_d", "n_holes", "hole_d", "screw", "center_screw"):
        prov(h[k], k, pv)
    disc = bd.Pos(0, 0, t / 2) * bd.Cylinder(od / 2, t)
    disc = disc - bd.Pos(0, 0, t / 2) * bd.Cylinder(bore / 2, t + 1)
    holes = []
    for i in range(n):
        a = 2 * math.pi * i / n + math.pi / 4
        x, y = bcd / 2 * math.cos(a), bcd / 2 * math.sin(a)
        disc = disc - bd.Pos(x, y, t / 2) * bd.Cylinder(hd / 2, t + 1)
        holes.append(HoleSpec(f"horn_{i}", loc_from((x, y, t), (0, 0, 1), (1, 0, 0)), str(val(h["screw"])), t, "clear", hd))
    return Component(f"horn-25t", "horn", disc, 0.004, {"seat": bd.Location(), "top": loc_from((0, 0, t), (0, 0, 1))}, holes, None,
                     {"od": od, "thickness": t, "bore": bore, "bolt_circle_d": bcd, "n_holes": n, "hole_d": hd,
                      "screw": str(val(h["screw"])), "center_screw": str(val(h["center_screw"]))}, pv)
