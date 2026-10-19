"""Spec + sizing -> MuJoCo MJCF built from primitives (pre-CAD) and a kinematic template. Plus a physics smoke test.

The link/joint tree comes from `openhumanoid/templates/<kinematics.template>.yaml` (data, not code). The spec's
chosen joints are placed on that tree; a joint the template does not define raises ValueError (it used to be
skipped silently).

Conventions: x forward, y left, z up. Pitch joints about +y (knee bends positive), roll about +x,
yaw about +z. Right-side roll/yaw ranges are mirrored by spec.expand_joints.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import catalog
from .body import PAIRED
from .paths import generated_header
from .spec import expand_joints, generated_dir
from .templates import available, check_joints, joint_host_map, load_template, resolve_geometry, safe_eval

AXIS = {"x": "1 0 0", "y": "0 1 0", "z": "0 0 1"}
# base joint -> body, merged over every kinematic template (kept for render.py / cad helpers). The authority is
# the template file (openhumanoid/templates/<id>.yaml); this is only a lookup.
JOINT_BODY = joint_host_map()
JOINT_ORDER = ["hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch", "ankle_roll", "waist_yaw",
               "shoulder_pitch", "shoulder_roll", "elbow", "wrist", "gripper", "neck_yaw", "neck_pitch"]


def joint_kind(base: str) -> dict:
    """{"type": "hinge"|"slide", "ratio": joint units per servo radian} for a base joint name."""
    for n in available():
        info = load_template(n)["joints"].get(base)
        if info:
            return {"type": info.get("type", "hinge"), "ratio": float(info.get("ratio_m_per_rad", 1.0))}
    return {"type": "hinge", "ratio": 1.0}


def load_sizing(spec: dict) -> dict:
    p = generated_dir(spec) / "sizing.json"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing. Run `oh size {spec['id']}` first.")
    return json.loads(p.read_text(encoding="utf-8"))


def stand_pose(spec: dict, joints: list[dict]) -> dict[str, float]:
    flex = math.radians(spec["locomotion"].get("walk", {}).get("stance_knee_flex_deg", 30))
    pose = {}
    for j in joints:
        v = {"hip_pitch": -flex / 2, "knee": flex, "ankle_pitch": -flex / 2}.get(j["base"], 0.0)
        if joint_kind(j["base"])["type"] == "slide":
            pose[j["name"]] = 0.0
            continue
        lo, hi = (math.radians(x) for x in j["range"])
        pose[j["name"]] = min(max(v, lo), hi)
    return pose


def _range_native(j: dict) -> tuple[float, float]:
    """Joint range in MuJoCo units (rad for hinges, m for slides; the spec gives slide ranges in mm)."""
    lo, hi = j["range"]
    if joint_kind(j["base"])["type"] == "slide":
        return lo / 1000.0, hi / 1000.0
    return math.radians(lo), math.radians(hi)


def actuator_lines(joints: list[dict], acts: dict[str, str]) -> list[str]:
    """Position actuators (servo-like) for every sim-supported joint. Shared by primitive and CAD models."""
    out = []
    for j in joints:
        if JOINT_BODY.get(j["base"]) is None:
            continue
        a = catalog.get(acts[j["name"]])["actuator"]
        kp = a["stall_torque_nm"] / 0.3
        lo, hi = _range_native(j)
        kind = joint_kind(j["base"])
        if kind["type"] == "slide":  # servo torque -> jaw force through the pinion
            lim, kp = a["stall_torque_nm"] / kind["ratio"], kp / kind["ratio"] ** 2
        else:
            lim = a["stall_torque_nm"]
        out.append(f'    <position name="{j["name"]}" joint="{j["name"]}" kp="{kp:.3f}" forcerange="{-lim:.3f} {lim:.3f}" '
                   f'ctrlrange="{lo:.4f} {hi:.4f}"/>')
    return out


def sensor_lines(joints: list[dict]) -> str:
    return "\n".join(f'    <jointpos name="q_{j["name"]}" joint="{j["name"]}"/>' for j in joints if JOINT_BODY.get(j["base"]))


def joint_xml(j: dict, act_id: str, ind: str, params: dict | None = None, axis: str | None = None) -> str:
    """One <joint>. `params` (armature/damping/frictionloss) overrides the catalog-derived defaults, which is how the
    concept engine hands over measured actuator parameters. `axis` is a MuJoCo axis string (mirrored slides)."""
    a = catalog.get(act_id)["actuator"]
    p = {"armature": a.get("armature_kg_m2", 0.01), "damping": 0.02 * a["stall_torque_nm"],
         "frictionloss": 0.01 * a["stall_torque_nm"], **(params or {})}
    kind = joint_kind(j["base"])
    if kind["type"] == "slide":
        lo, hi = _range_native(j)
        return (f'{ind}<joint name="{j["name"]}" type="slide" axis="{axis or AXIS[j["axis"]]}" range="{lo:.5f} {hi:.5f}" '
                f'armature="{p["armature"]:.5g}" damping="{p["damping"]:.5g}" frictionloss="{p["frictionloss"]:.5g}"/>')
    return (f'{ind}<joint name="{j["name"]}" axis="{AXIS[j["axis"]]}" range="{j["range"][0]} {j["range"][1]}" '
            f'armature="{p["armature"]:.5g}" damping="{p["damping"]:.5g}" frictionloss="{p["frictionloss"]:.5g}"/>')


def stand_height(sizing: dict, spec: dict) -> float:
    """Pelvis origin height (m) for the stand pose."""
    g = sizing["geometry_m"]
    flex = math.radians(spec["locomotion"].get("walk", {}).get("stance_knee_flex_deg", 30))
    return g["ankle_height"] + (g["thigh"] + g["shank"]) * math.cos(flex / 2) + g["pelvis"] / 2 + 0.003


def _geom_volume(g: dict, val) -> float:
    t = g.get("type", "box")
    if t == "box":
        s = val(g["size"])
        return 8 * s[0] * s[1] * s[2]
    if t == "ellipsoid":
        s = val(g["size"])
        return 4 / 3 * math.pi * s[0] * s[1] * s[2]
    if t == "capsule":
        r = val(g["size"])[0]
        ft = val(g["fromto"])
        return math.pi * r * r * math.dist(ft[:3], ft[3:]) + 4 / 3 * math.pi * r ** 3
    raise ValueError(f"template geom type '{t}' not supported")


def _f(v, nd=5) -> str:
    return " ".join(f"{x:.{nd}g}" if abs(x) > 1e-12 else "0" for x in v)


def build_mjcf(spec: dict, sizing: dict, *, actuator_mode: str = "position", joint_params: dict | None = None,
               extra_world_xml: str = "", torque_limits: dict | None = None, model_name: str | None = None) -> str:
    """MJCF from the kinematic template named by `spec.kinematics.template` plus the spec's chosen joints.

    actuator_mode: "position" (servo-like, used by `oh sim test`) or "motor" (raw torque; the concept engine's
    actuator model closes the loop in Python). `joint_params`: {joint name: {armature, damping, frictionloss}}.
    `torque_limits`: {joint name: servo torque ceiling in N*m} for motor mode. `extra_world_xml` is spliced into
    <worldbody> (tables, objects). A spec joint the template lacks raises ValueError.
    """
    tpl = load_template(spec["kinematics"].get("template", "biped_v1"))
    g, m = sizing["geometry_m"], sizing["segment_mass_kg"]
    h = sizing["height_m"]
    joints = expand_joints(spec, sizing["joints_base"])
    check_joints(tpl, [j["base"] for j in joints])
    acts = sizing["actuators"]
    names = resolve_geometry(tpl, g, h)
    jp = joint_params or {}
    z0 = stand_height(sizing, spec)
    by_name = {j["name"]: j for j in joints}

    def val(x):
        return [safe_eval(e, names) for e in x] if isinstance(x, (list, tuple)) else safe_eval(x, names)

    # Optional bodies (hand, jaw) exist only if one of their joints was chosen or a descendant needs them; otherwise
    # their mass is folded into the parent so the total never changes.
    bodies = tpl["bodies"]
    selected = {j["base"] for j in joints}
    parent_of = {b["name"]: b["parent"] for b in bodies}
    keep = {b["name"] for b in bodies if not b.get("optional") or (set(b.get("joints", [])) & selected)}
    for n in list(keep):
        p = parent_of[n]
        while p != "world":
            keep.add(p)
            p = parent_of[p]

    def kept_parent(n: str) -> str:
        p = parent_of[n]
        while p != "world" and p not in keep:
            p = parent_of[p]
        return p

    def body_mass(b) -> float:
        return m[b["mass"]["key"]] * b["mass"].get("fraction", 1.0)

    merged_mass: dict[str, float] = {}
    children: dict[str, list[dict]] = {}
    for b in bodies:
        if b["name"] in keep:
            children.setdefault(kept_parent(b["name"]), []).append(b)
        else:
            p = kept_parent(b["name"])
            merged_mass[p] = merged_mass.get(p, 0.0) + body_mass(b)

    def mirror(vec, side, idx):
        v = list(vec)
        if side == "r":
            for i in idx:
                v[i] = -v[i]
        return v

    def emit(b, side, ind) -> str:
        nm = b["name"] + (f"_{side}" if side else "")
        pos = [0, 0, z0] if b.get("root") else mirror(val(b.get("pos", [0, 0, 0])), side, [1])
        lines = [f'{ind}<body name="{nm}" pos="{_f(pos)}">']
        if b.get("root"):
            lines.append(f'{ind}  <freejoint name="root"/>')
        for jb in b.get("joints", []):
            j = by_name.get(f"{jb}_{side}" if side else jb) or by_name.get(jb)
            if j is None:
                continue
            axis = None
            if joint_kind(jb)["type"] == "slide":
                axis = " ".join(str(int(c)) for c in mirror([float(c) for c in AXIS[j["axis"]].split()], side, [1]))
            lines.append(joint_xml(j, acts[j["name"]], ind + "  ", jp.get(j["name"]), axis))
        total = body_mass(b) + merged_mass.get(b["name"], 0.0)
        vols = [_geom_volume(gm, val) for gm in b["geoms"]]
        vsum = sum(vols) or 1.0
        for gm, vol in zip(b["geoms"], vols):
            gname = ""
            if gm.get("name"):
                gname = f' name="{gm["name"]}_{side}"' if side else f' name="{gm["name"]}"'
            attrs = f'type="{gm.get("type", "box")}" size="{_f(val(gm["size"]))}"'
            if "fromto" in gm:
                attrs += f' fromto="{_f(mirror(val(gm["fromto"]), side, [1, 4]))}"'
            if "pos" in gm:
                attrs += f' pos="{_f(mirror(val(gm["pos"]), side, [1]))}"'
            lines.append(f'{ind}  <geom{gname} {attrs} mass="{total * vol / vsum:.5g}" class="{gm.get("class", "visual")}"/>')
        for st in b.get("sites", []):
            sname = f'{st["name"]}_{side}' if side else st["name"]
            lines.append(f'{ind}  <site name="{sname}" pos="{_f(mirror(val(st["pos"]), side, [1]))}"/>')
        for ch in children.get(b["name"], []):
            for sd in ((side,) if side else ("l", "r")) if ch.get("side") else (None,):
                lines.append(emit(ch, sd, ind + "  "))
        lines.append(f"{ind}</body>")
        return "\n".join(lines)

    tree = emit(children["world"][0], None, "    ")

    sim_joints = [j for j in joints if JOINT_BODY.get(j["base"])]
    if actuator_mode == "position":
        act_xml = "\n".join(actuator_lines(sim_joints, acts))
    elif actuator_mode == "motor":
        rows = []
        for j in sim_joints:
            kind = joint_kind(j["base"])
            lim = (torque_limits or {}).get(j["name"], catalog.get(acts[j["name"]])["actuator"]["stall_torque_nm"])
            lim = lim / kind["ratio"] if kind["type"] == "slide" else lim
            rows.append(f'    <motor name="{j["name"]}" joint="{j["name"]}" gear="1" ctrlrange="{-2 * lim:.4f} {2 * lim:.4f}"/>')
        act_xml = "\n".join(rows)
    else:
        raise ValueError(f"actuator_mode must be 'position' or 'motor', not {actuator_mode!r}")
    mass_total = sum(m[k] * (2 if k in PAIRED else 1) for k in m)
    xml = f"""{generated_header('sim build', '<!--').rstrip()} -->
<!-- {spec['name']}: primitive (pre-CAD) model from template '{tpl['id']}'. h={h:.3f} m, mass≈{mass_total:.2f} kg. Replaced by CAD export in P4. -->
<mujoco model="{model_name or spec['id']}">
  <compiler angle="degree" autolimits="true"/>
  <option timestep="{spec['sim'].get('timestep_s', 0.002)}" integrator="implicitfast"/>
  <default>
    <default class="visual"><geom contype="0" conaffinity="0" rgba="0.92 0.92 0.94 1"/></default>
    <default class="contact"><geom contype="1" conaffinity="1" friction="1.0 0.02 0.01" rgba="0.15 0.15 0.18 1"/></default>
  </default>
  <visual><headlight diffuse="0.7 0.7 0.7"/></visual>
  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.95 0.95 0.97" rgb2="0.62 0.64 0.68" width="512" height="512"/>
    <texture name="grid" type="2d" builtin="checker" rgb1="0.2 0.22 0.25" rgb2="0.28 0.3 0.33" width="512" height="512"/>
    <material name="grid" texture="grid" texrepeat="8 8"/>
  </asset>
  <worldbody>
    <light pos="0 0 3" dir="0 0 -1" directional="true"/>
    <geom name="floor" type="plane" size="0 0 0.05" material="grid" contype="1" conaffinity="1"/>
{tree}
{extra_world_xml}
  </worldbody>
  <actuator>
{act_xml}
  </actuator>
  <sensor>
    <framequat name="imu_quat" objtype="site" objname="imu"/>
    <gyro name="imu_gyro" site="imu"/>
    <accelerometer name="imu_acc" site="imu"/>
{sensor_lines(joints)}
  </sensor>
</mujoco>
"""
    return xml


def write_mjcf(spec: dict) -> Path:
    sizing = load_sizing(spec)
    if not sizing.get("actuators"):
        raise ValueError("Sizing is infeasible (no actuator selection). Fix the spec before generating a sim.")
    out = generated_dir(spec) / "sim"
    out.mkdir(exist_ok=True)
    path = out / f"{spec['id']}.xml"
    path.write_text(build_mjcf(spec, sizing), encoding="utf-8")
    return path


def smoke_test(spec: dict, seconds: float = 3.0) -> dict:
    """Hold the stand pose with position control. Reports stability and actuator torque usage."""
    import mujoco
    import numpy as np

    path = generated_dir(spec) / "sim" / f"{spec['id']}.xml"
    if not path.exists():
        path = write_mjcf(spec)
    model = mujoco.MjModel.from_xml_path(str(path))
    data = mujoco.MjData(model)
    sizing = load_sizing(spec)
    joints = [j for j in expand_joints(spec, sizing["joints_base"]) if JOINT_BODY.get(j["base"])]
    pose = stand_pose(spec, joints)
    for name, q in pose.items():
        data.joint(name).qpos[0] = q
        data.actuator(name).ctrl[0] = q
    mujoco.mj_forward(model, data)
    z0 = float(data.body("pelvis").xpos[2])
    peak = np.zeros(model.nu)
    steps = int(seconds / model.opt.timestep)
    for _ in range(steps):
        mujoco.mj_step(model, data)
        peak = np.maximum(peak, np.abs(data.actuator_force))
        if not np.all(np.isfinite(data.qpos)):
            return {"ok": False, "reason": "simulation diverged (NaN)", "model": str(path)}
    z1 = float(data.body("pelvis").xpos[2])
    qw = data.body("pelvis").xquat
    tilt = math.degrees(2 * math.acos(min(1.0, abs(float(qw[0])))))
    stall = np.array([model.actuator_forcerange[i][1] for i in range(model.nu)])
    usage = {model.actuator(i).name: round(float(peak[i] / stall[i]), 3) for i in range(model.nu)}
    worst = max(usage, key=usage.get)
    fell = z1 < 0.7 * z0 or tilt > 35
    mass = float(sum(model.body_mass))
    return {"ok": not fell, "reason": "stood" if not fell else "fell over", "model": str(path),
            "mass_kg": round(mass, 3), "pelvis_z_start": round(z0, 4), "pelvis_z_end": round(z1, 4),
            "tilt_deg": round(tilt, 1), "peak_torque_fraction_of_stall": usage, "worst_joint": worst,
            "seconds": seconds}


def view(spec: dict) -> None:
    import mujoco
    import mujoco.viewer

    path = generated_dir(spec) / "sim" / f"{spec['id']}.xml"
    if not path.exists():
        path = write_mjcf(spec)
    model = mujoco.MjModel.from_xml_path(str(path))
    data = mujoco.MjData(model)
    sizing = load_sizing(spec)
    for name, q in stand_pose(spec, [j for j in expand_joints(spec, sizing["joints_base"]) if JOINT_BODY.get(j["base"])]).items():
        data.joint(name).qpos[0] = q
        data.actuator(name).ctrl[0] = q
    mujoco.viewer.launch(model, data)


__all__ = ["build_mjcf", "write_mjcf", "smoke_test", "view"]
