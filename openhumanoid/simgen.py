"""Spec + sizing -> MuJoCo MJCF built from primitives (pre-CAD). Plus a physics smoke test.

Conventions: x forward, y left, z up. Pitch joints about +y (knee bends positive), roll about +x,
yaw about +z. Right-side roll/yaw ranges are mirrored by spec.expand_joints.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import catalog
from .paths import generated_header
from .spec import expand_joints, generated_dir

AXIS = {"x": "1 0 0", "y": "0 1 0", "z": "0 0 1"}
# Which body each base joint lives in (MuJoCo allows several joints per body: compound joints).
JOINT_BODY = {
    "hip_yaw": "thigh", "hip_roll": "thigh", "hip_pitch": "thigh", "knee": "shank",
    "ankle_pitch": "foot", "ankle_roll": "foot",
    "shoulder_pitch": "upper_arm", "shoulder_roll": "upper_arm", "elbow": "forearm",
    "neck_yaw": "head", "neck_pitch": "head",
}
JOINT_ORDER = ["hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch", "ankle_roll",
               "shoulder_pitch", "shoulder_roll", "elbow", "neck_yaw", "neck_pitch"]


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
        lo, hi = (math.radians(x) for x in j["range"])
        pose[j["name"]] = min(max(v, lo), hi)
    return pose


def actuator_lines(joints: list[dict], acts: dict[str, str]) -> list[str]:
    """Position actuators (servo-like) for every sim-supported joint. Shared by primitive and CAD models."""
    out = []
    for j in joints:
        if JOINT_BODY.get(j["base"]) is None:
            continue
        a = catalog.get(acts[j["name"]])["actuator"]
        kp = a["stall_torque_nm"] / 0.3
        out.append(f'    <position name="{j["name"]}" joint="{j["name"]}" kp="{kp:.3f}" forcerange="{-a["stall_torque_nm"]:.3f} {a["stall_torque_nm"]:.3f}" '
                   f'ctrlrange="{math.radians(j["range"][0]):.4f} {math.radians(j["range"][1]):.4f}"/>')
    return out


def sensor_lines(joints: list[dict]) -> str:
    return "\n".join(f'    <jointpos name="q_{j["name"]}" joint="{j["name"]}"/>' for j in joints if JOINT_BODY.get(j["base"]))


def joint_xml(j: dict, act_id: str, ind: str) -> str:
    a = catalog.get(act_id)["actuator"]
    return (f'{ind}<joint name="{j["name"]}" axis="{AXIS[j["axis"]]}" range="{j["range"][0]} {j["range"][1]}" '
            f'armature="{a.get("armature_kg_m2", 0.01)}" damping="{0.02 * a["stall_torque_nm"]:.4f}" frictionloss="{0.01 * a["stall_torque_nm"]:.4f}"/>')


def stand_height(sizing: dict, spec: dict) -> float:
    """Pelvis origin height (m) for the stand pose."""
    g = sizing["geometry_m"]
    flex = math.radians(spec["locomotion"].get("walk", {}).get("stance_knee_flex_deg", 30))
    return g["ankle_height"] + (g["thigh"] + g["shank"]) * math.cos(flex / 2) + g["pelvis"] / 2 + 0.003


def build_mjcf(spec: dict, sizing: dict) -> str:
    g, m = sizing["geometry_m"], sizing["segment_mass_kg"]
    h = sizing["height_m"]
    base = sizing["joints_base"]
    joints = expand_joints(spec, base)
    acts = sizing["actuators"]
    by_body: dict[tuple, list[dict]] = {}
    for j in sorted(joints, key=lambda j: JOINT_ORDER.index(j["base"]) if j["base"] in JOINT_ORDER else 99):
        body = JOINT_BODY.get(j["base"])
        if body is None:
            continue  # unknown joint: needs a module-provided body (future)
        by_body.setdefault((body, j["side"]), []).append(j)
    flex = math.radians(spec["locomotion"].get("walk", {}).get("stance_knee_flex_deg", 30))
    r_leg, r_arm = 0.045 * h, 0.035 * h
    z0 = stand_height(sizing, spec)

    def jxml(body, side, ind):
        return "\n".join(joint_xml(j, acts[j["name"]], ind) for j in by_body.get((body, side), []))

    def leg(side):
        y = (1 if side == "l" else -1) * g["hip_width"] / 2
        fl, fw, ah = g["foot_length"], g["foot_width"], g["ankle_height"]
        return f"""
      <body name="thigh_{side}" pos="0 {y:.4f} {-g['pelvis'] / 2:.4f}">
{jxml('thigh', side, '        ')}
        <geom type="capsule" fromto="0 0 0 0 0 {-g['thigh']:.4f}" size="{r_leg:.4f}" mass="{m['thigh']:.4f}" class="visual"/>
        <body name="shank_{side}" pos="0 0 {-g['thigh']:.4f}">
{jxml('shank', side, '          ')}
          <geom type="capsule" fromto="0 0 0 0 0 {-g['shank']:.4f}" size="{r_leg * 0.9:.4f}" mass="{m['shank']:.4f}" class="visual"/>
          <body name="foot_{side}" pos="0 0 {-g['shank']:.4f}">
{jxml('foot', side, '            ')}
            <geom name="foot_{side}" type="box" pos="{fl * 0.15:.4f} 0 {-ah / 2:.4f}" size="{fl / 2:.4f} {fw / 2:.4f} {ah / 2:.4f}" mass="{m['foot']:.4f}" class="contact"/>
            <site name="foot_{side}" pos="{fl * 0.15:.4f} 0 {-ah:.4f}"/>
          </body>
        </body>
      </body>"""

    def arm(side):
        y = (1 if side == "l" else -1) * g["shoulder_width"] / 2
        return f"""
        <body name="upper_arm_{side}" pos="0 {y:.4f} {g['torso'] * 0.9:.4f}">
{jxml('upper_arm', side, '          ')}
          <geom type="capsule" fromto="0 0 0 0 0 {-g['upper_arm']:.4f}" size="{r_arm:.4f}" mass="{m['upper_arm']:.4f}" class="visual"/>
          <body name="forearm_{side}" pos="0 0 {-g['upper_arm']:.4f}">
{jxml('forearm', side, '            ')}
            <geom type="capsule" fromto="0 0 0 0 0 {-g['forearm']:.4f}" size="{r_arm * 0.85:.4f}" mass="{m['forearm']:.4f}" class="visual"/>
          </body>
        </body>"""

    actuators = actuator_lines(joints, acts)
    sensors = sensor_lines(joints)
    head_w = g["head"] * 0.62
    xml = f"""{generated_header('sim build', '<!--').rstrip()} -->
<!-- {spec['name']}: primitive (pre-CAD) model. h={h:.3f} m, mass≈{sizing['mass']['total_kg']:.2f} kg. Replaced by CAD export in P4. -->
<mujoco model="{spec['id']}">
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
    <body name="pelvis" pos="0 0 {z0:.4f}">
      <freejoint name="root"/>
      <geom type="box" size="{g['hip_width'] * 0.75:.4f} {g['hip_width'] * 0.9:.4f} {g['pelvis'] / 2:.4f}" mass="{m['pelvis']:.4f}" class="visual"/>
      <site name="imu" pos="0 0 0"/>
      <body name="torso" pos="0 0 {g['pelvis'] / 2:.4f}">
        <geom type="box" pos="0 0 {g['torso'] / 2:.4f}" size="{g['shoulder_width'] * 0.22:.4f} {g['shoulder_width'] * 0.38:.4f} {g['torso'] / 2:.4f}" mass="{m['torso']:.4f}" class="visual"/>
        <body name="head" pos="0 0 {g['torso'] + g['neck']:.4f}">
{jxml('head', None, '          ')}
          <geom type="ellipsoid" pos="0 0 {g['head'] / 2:.4f}" size="{head_w * 0.62:.4f} {head_w / 2:.4f} {g['head'] / 2:.4f}" mass="{m['head']:.4f}" class="visual"/>
        </body>{arm('l')}{arm('r')}
      </body>{leg('l')}{leg('r')}
    </body>
  </worldbody>
  <actuator>
{chr(10).join(actuators)}
  </actuator>
  <sensor>
    <framequat name="imu_quat" objtype="site" objname="imu"/>
    <gyro name="imu_gyro" site="imu"/>
    <accelerometer name="imu_acc" site="imu"/>
{sensors}
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
