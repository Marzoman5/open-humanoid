"""`interfaces.yaml` generator (research C4, connector-first): written BEFORE any part geometry.

    generate(spec, layout)  ->  dict       joint axes, actuator placement/orientation, horn and idler interfaces, ROM, keep-outs,
                                           mount patterns, links; with analytic pre-checks (servo bodies overlapping at the zero pose)
    write(spec, layout)     ->  Path       variants/<id>/generated/interfaces.yaml
    load(spec_or_path)      ->  Interfaces consumer API:  .servo_loc(joint), .axis(joint), .link_origin(link), .joint(joint) ...

Parts are later checked numerically against this file (geometry_gate `interface` expectations) and are built by asking it for frames, so
a part cannot disagree with the joint it serves.

INPUTS
* spec.yaml: joint axes/ranges (authoritative where the joint exists), body proportions, actuation, manufacturing bed.
* sizing.json (optional): chosen actuator per expanded joint and the height.
* layout (`variants/<id>/cad/layout*.yaml`): the mechanical packaging decisions the concept loop is meant to produce:
  height, proportion overrides, the chain of joints per limb, and for each joint where its servo sits.
  Layout keys:  name, status, height_m, proportions{}, actuators{default, overrides{base_joint: catalog id}},
                limbs{ <limb>: {mirror: [l,r]|[], root: <link>, joints: [ {name, axis?, range?, point: <joint point name>,
                                  servo: {host: <link>, horn: [dx,dy,dz], long: [dx,dy,dz], horn_at: mm along +axis from the joint
                                          point to the horn-face plane, idler: {bearing, gap_mm}?}} ]}},
                points{ <name>: [x, y, z] expressions in mm using height-derived symbols h, hip_y, ankle, shank, thigh... }
  Point expressions are python expressions over the proportion symbols (mm) and may be plain numbers.

UNITS mm, degrees. FRAME world: x forward, y left, z up, zero pose (all joint angles 0, legs straight).
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import build123d as bd
import yaml

from .. import catalog
from ..paths import generated_header
from ..spec import deep_merge, expand_joints, generated_dir
from . import dfm
from .components import get as get_component
from .core import loc_from, overlap_volume

SCHEMA = "interfaces/0.1"
SIDES = {"l": 1, "r": -1}


def _vec(v):
    return [round(float(x), 4) for x in v]


def _norm(v):
    n = math.sqrt(sum(x * x for x in v))
    if n < 1e-9:
        raise ValueError(f"zero-length direction {v}")
    return [x / n for x in v]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _symbols(spec: dict, layout: dict, sizing: dict | None) -> dict[str, float]:
    h = float(layout.get("height_m") or (sizing or {}).get("height_m") or spec["body"]["height_m"]["target"]) * 1000.0
    prop = deep_merge(dict(spec["body"]["proportions"]), layout.get("proportions", {}) or {})
    sym = {k: v * h for k, v in prop.items()}
    sym["h"] = h
    sym["hip_y"] = sym["hip_width"] / 2
    sym["ankle"] = sym["ankle_height"]
    sym["hip_z"] = sym["ankle_height"] + sym["shank"] + sym["thigh"]
    sym["knee_z"] = sym["ankle_height"] + sym["shank"]
    sym["shoulder_y"] = sym["shoulder_width"] / 2
    sym["shoulder_z"] = sym["hip_z"] + sym["pelvis"] + sym["torso"] * 0.92
    return sym


def _safe_eval(expr: str, sym: dict[str, float]) -> float:
    """Arithmetic only (+ - * / unary minus, parentheses, numbers, symbol names): layout files are data, not code."""
    import ast
    import operator as op

    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.USub: op.neg, ast.UAdd: op.pos}

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name) and n.id in sym:
            return float(sym[n.id])
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.operand))
        raise ValueError(f"unsupported expression '{expr}' (symbols: {sorted(sym)})")

    return ev(ast.parse(expr, mode="eval"))


def _eval_point(expr, sym: dict) -> list[float]:
    return [_safe_eval(e, sym) if isinstance(e, str) else float(e) for e in expr]


def _mirror_pt(p):
    return [p[0], -p[1], p[2]]


def load_layout(spec: dict, path: str | Path | None = None) -> dict:
    cad = Path(spec["_dir"]) / "cad"
    p = Path(path) if path else cad / "layout.yaml"
    if not path and not p.exists():
        cands = sorted(cad.glob("layout_*.yaml"))
        p = cands[-1] if cands else p
    if not p.exists():
        raise FileNotFoundError(f"no layout at {p}: the interfaces generator needs the packaging layout (see openhumanoid/cad/interfaces.py docstring)")
    lay = yaml.safe_load(p.read_text(encoding="utf-8"))
    lay["_path"] = str(p)
    return lay


def generate(spec: dict, layout: dict, sizing: dict | None = None) -> dict:
    sym = _symbols(spec, layout, sizing)
    base_joints = {j["name"]: j for j in spec["kinematics"]["joints"]}
    pts = {k: _eval_point(v, sym) for k, v in (layout.get("points") or {}).items()}
    act_default = (layout.get("actuators") or {}).get("default") or "sts3215-12v"
    act_over = (layout.get("actuators") or {}).get("overrides") or {}
    horn = get_component("horn-25t")
    links: dict[str, dict] = {}
    joints: dict[str, dict] = {}
    notes: list[str] = []
    estimates: set[str] = set()

    def link(name, parent, origin, side=None):
        links[name] = {"parent": parent, "origin_mm": _vec(origin), "side": side}

    for root, o in (layout.get("roots") or {"pelvis": [0, 0, "hip_z"]}).items():
        link(root, None, _eval_point(o, sym))

    for limb, ld in layout["limbs"].items():
        for side in ld.get("mirror", []) or [None]:
            sgn = SIDES.get(side, 1)
            sfx = f"_{side}" if side else ""
            parent = ld.get("root", "pelvis")
            prev_origin = links[parent]["origin_mm"]
            for jd in ld["joints"]:
                bj = base_joints.get(jd["name"], {})
                axis_name = jd.get("axis") or bj.get("axis")
                rng = jd.get("range") or bj.get("range")
                if axis_name is None or rng is None:
                    raise ValueError(f"joint {jd['name']}: axis/range missing from both spec and layout")
                lo, hi = rng
                if side == "r" and axis_name in ("x", "z"):
                    lo, hi = -hi, -lo
                p = pts[jd["point"]]
                p = _mirror_pt(p) if sgn < 0 else list(p)
                jname = f"{jd['name']}{sfx}"
                lname = f"{jd['name']}{sfx}_link"
                link(lname, parent, p, side)
                axis_dir = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}[axis_name]
                sv = jd.get("servo") or {}
                aid = act_over.get(jd["name"], sv.get("actuator", act_default))
                servo = get_component(aid)
                horn_dir = _norm(sv["horn"])
                long_dir = _norm(sv["long"])
                if sgn < 0:
                    horn_dir, long_dir = _mirror_pt(horn_dir), _mirror_pt(long_dir)
                if abs(_dot(horn_dir, long_dir)) > 1e-6:
                    raise ValueError(f"{jname}: servo long direction must be perpendicular to the horn direction")
                if abs(abs(_dot(horn_dir, axis_dir)) - 1) > 1e-6:
                    raise ValueError(f"{jname}: servo horn direction must lie along the joint axis")
                horn_at = float(sv.get("horn_at", 0.0))
                # signed offset along the joint axis from the joint point to the horn-face plane; mirrored for the right side
                off_axis = [axis_dir[i] * horn_at for i in range(3)]
                if sgn < 0:
                    off_axis = _mirror_pt(off_axis)
                origin = [p[i] + off_axis[i] for i in range(3)]
                z_dir, x_dir = horn_dir, long_dir
                y_dir = [z_dir[1] * x_dir[2] - z_dir[2] * x_dir[1], z_dir[2] * x_dir[0] - z_dir[0] * x_dir[2],
                         z_dir[0] * x_dir[1] - z_dir[1] * x_dir[0]]
                P = servo.params
                horn_seat = [origin[i] + z_dir[i] * P["boss_h"] for i in range(3)]
                back = [origin[i] - z_dir[i] * P["H"] for i in range(3)]
                case_holes = []
                for h in servo.holes:
                    pos = h.frame.position
                    wp = [origin[i] + x_dir[i] * pos.X + y_dir[i] * pos.Y + z_dir[i] * pos.Z for i in range(3)]
                    case_holes.append({"id": h.id, "at_mm": _vec(wp), "thread": h.thread, "depth_mm": h.depth})
                joint = {
                    "limb": limb, "side": side, "base": jd["name"], "parent_link": parent, "child_link": lname,
                    "axis": {"origin_mm": _vec(p), "direction": axis_dir, "name": axis_name},
                    "rom_deg": [lo, hi],
                    "actuator": {
                        "id": aid, "host_link": sv.get("host", parent).replace("_l_link", "_r_link") if side == "r" else sv.get("host", parent), "mass_kg": float(catalog.get(aid).get("mass_kg", 0.0)),
                        "frame": {"origin_mm": _vec(origin), "z_dir": _vec(z_dir), "x_dir": _vec(x_dir), "y_dir": _vec(y_dir)},
                        "horn_plane_offset_mm": horn_at,
                        "body_mm": [P["L"], P["W"], P["H"]], "axis_from_near_end_mm": P["axis_x"],
                        "corner_radius_mm": round(P["corner_r"], 3),
                        "case_holes": case_holes,
                    },
                    "horn": {"seat_origin_mm": _vec(horn_seat), "dir": _vec(z_dir), "type": "round_25t", "od_mm": horn.params["od"],
                             "thickness_mm": horn.params["thickness"], "bolt_circle_d_mm": horn.params["bolt_circle_d"],
                             "n_holes": horn.params["n_holes"], "screw": horn.params["screw"], "center_screw": horn.params["center_screw"],
                             "clock_deg": 0.0,
                             "note": "25T spline: set the horn within 14.4 deg of the zero pose, trim the rest with the servo's calibrated offset"},
                    "back": {"origin_mm": _vec(back), "dir": _vec([-c for c in z_dir]), "stub_od_mm": P["back_boss_d"]},
                    "idler": None,
                    "keepout": {"servo": {"frame": "actuator.frame", "kind": "servo_envelope", "plug_len_mm": P["plug_len"]}},
                }
                idl = sv.get("idler")
                if idl:
                    joint["idler"] = {"bearing": idl["bearing"], "gap_mm": float(idl.get("gap_mm", 1.5)),
                                      "seat_origin_mm": _vec([back[i] - z_dir[i] * float(idl.get("gap_mm", 1.5)) for i in range(3)]),
                                      "seat_dir": _vec(z_dir)}
                estimates.update(servo.estimates())
                joints[jname] = joint
                parent, prev_origin = lname, p

    # ---- analytic pre-checks: servo envelopes must not overlap each other at the zero pose
    problems = []
    names = list(joints)
    envs = {}
    for n in names:
        a = joints[n]["actuator"]
        f = a["frame"]
        loc = loc_from(f["origin_mm"], f["z_dir"], f["x_dir"])
        envs[n] = loc * get_component(a["id"]).shape
    for i in range(len(names)):
        for k in range(i + 1, len(names)):
            v = overlap_volume(envs[names[i]], envs[names[k]])
            if v > 1.0:
                problems.append(f"servo bodies of {names[i]} and {names[k]} overlap by {v:.0f} mm3 at the zero pose")
    ptxt = yaml.safe_dump({"layout": {k: v for k, v in layout.items() if not k.startswith("_")}}, sort_keys=True)
    out = {
        "schema": SCHEMA,
        "variant": spec["id"],
        "layout": layout.get("name"),
        "layout_status": layout.get("status"),
        "layout_sha": hashlib.sha256(ptxt.encode()).hexdigest()[:12],
        "units": {"length": "mm", "angle": "deg"},
        "frame": "world: x forward, y left, z up; zero pose = all joint angles 0; links axis-aligned with the world at the zero pose",
        "height_mm": round(sym["h"], 2),
        "bed_mm": list(spec.get("manufacturing", {}).get("printer_bed_mm", dfm.load_dfm()["bed"]["default_mm"])),
        "proportions_mm": {k: round(v, 3) for k, v in sym.items()},
        "links": links,
        "joints": joints,
        "estimates_to_confirm": sorted(estimates),
        "problems": problems,
    }
    return out


def write(spec: dict, layout: dict, sizing: dict | None = None) -> Path:
    d = generate(spec, layout, sizing)
    p = generated_dir(spec) / "interfaces.yaml"
    p.write_text(generated_header("cad interfaces", "#") + yaml.safe_dump(d, sort_keys=False, default_flow_style=None, width=140), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- consumer API


class Interfaces:
    def __init__(self, data: dict):
        self.d = data

    def joint(self, name: str) -> dict:
        return self.d["joints"][name]

    def link_origin(self, link: str) -> list[float]:
        return self.d["links"][link]["origin_mm"]

    def axis_origin(self, joint: str) -> list[float]:
        return self.joint(joint)["axis"]["origin_mm"]

    def servo_loc(self, joint: str, link: str | None = None) -> bd.Location:
        """Servo frame (origin on the output axis at the horn-face plane, +z = horn direction, +x = long end) in world coordinates, or
        relative to `link`'s frame if given (link frames are world-aligned, so only the origin shifts)."""
        f = self.joint(joint)["actuator"]["frame"]
        o = list(f["origin_mm"])
        if link:
            lo = self.link_origin(link)
            o = [o[i] - lo[i] for i in range(3)]
        return loc_from(o, f["z_dir"], f["x_dir"])

    def in_link(self, link: str, p) -> list[float]:
        lo = self.link_origin(link)
        return [p[i] - lo[i] for i in range(3)]


def load(src) -> Interfaces:
    p = Path(src) if isinstance(src, (str, Path)) else Path(src["_dir"]) / "generated" / "interfaces.yaml"
    return Interfaces(yaml.safe_load(p.read_text(encoding="utf-8")))
