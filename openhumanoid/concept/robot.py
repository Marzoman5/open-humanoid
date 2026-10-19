"""A concept (candidate YAML) -> a simulatable robot: spec, component-sum mass model, MJCF, joint tables.

The concept names a base variant (defaults: proportions, mass model, BOM style), a kinematic template, the joints and
the actuator per joint, plus power/compute parts. Nothing here knows about Adam.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from .. import catalog, simgen
from ..actuators import ServoSpec, servo_spec
from ..body import Body, build_body
from ..spec import deep_merge, expand_joints, load_spec
from ..templates import load_template

G = 9.81

# Default joint tables for template joints a concept lists by name only. Ranges in degrees (millimetres for slides).
JOINT_DEFAULTS = {
    "hip_yaw": ("leg", [-45, 45]), "hip_roll": ("leg", [-30, 45]), "hip_pitch": ("leg", [-110, 60]),
    "knee": ("leg", [0, 130]), "ankle_pitch": ("leg", [-60, 60]), "ankle_roll": ("leg", [-30, 30]),
    "waist_yaw": ("torso", [-60, 60]), "neck_yaw": ("head", [-90, 90]), "neck_pitch": ("head", [-30, 30]),
    "shoulder_pitch": ("arm", [-180, 60]), "shoulder_roll": ("arm", [-10, 160]), "elbow": ("arm", [-130, 0]),
    "wrist": ("arm", [-90, 90]), "gripper": ("hand", [0, 60]),
}
LEG_BASES = ["hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch", "ankle_roll"]


@dataclass
class Robot:
    concept: dict
    spec: dict
    height: float
    body: Body
    joints: list[dict]                      # expanded, simulated joints (mirrored ranges)
    acts: dict[str, str]                    # joint name -> catalog actuator id
    servo: dict[str, ServoSpec]             # joint name -> servo constants
    xml: str = ""
    names: list[str] = field(default_factory=list)
    ratio: np.ndarray | None = None         # joint units per servo radian (1 for hinges)
    mass_breakdown: dict = field(default_factory=dict)
    power_parts: dict = field(default_factory=dict)
    eff: np.ndarray | None = None           # transmission efficiency per joint (1.0 = direct drive)
    transmissions: dict = field(default_factory=dict)   # joint name -> {ratio, efficiency, host, note}
    mass_case: dict = field(default_factory=dict)

    @property
    def geom(self) -> dict:
        return self.body.geom

    @property
    def total_mass(self) -> float:
        return self.body.total

    def has(self, *bases) -> bool:
        have = {j["base"] for j in self.joints}
        return all(b in have for b in bases)

    def build_model(self, extra_world_xml: str = "", joint_params: dict | None = None):
        import mujoco
        xml = self.make_xml(extra_world_xml, joint_params)
        return mujoco.MjModel.from_xml_string(xml)

    def make_xml(self, extra_world_xml: str = "", joint_params: dict | None = None) -> str:
        sizing = {"geometry_m": self.body.geom, "segment_mass_kg": self.body.seg_mass, "height_m": self.height,
                  "joints_base": [j["name"] for j in self.spec["kinematics"]["joints"]], "actuators": self.acts}
        jp = joint_params if joint_params is not None else self.default_joint_params()
        # servo-domain torque ceiling per joint, divided by the linkage ratio (the builder divides slides by the pinion ratio itself)
        limits = {n: float(self.servo[n].stall_cap(self.servo[n].vin_ref)) * 1.05 / self.trans_ratio(n) for n in self.names}
        return simgen.build_mjcf(self.spec, sizing, actuator_mode="motor", joint_params=jp, extra_world_xml=extra_world_xml,
                                 torque_limits=limits, model_name=self.concept["id"])

    def trans_ratio(self, name: str) -> float:
        return float(self.transmissions.get(name, {}).get("ratio", 1.0))

    def default_joint_params(self) -> dict:
        out = {}
        for n in self.names:
            s = self.servo[n]
            r = float(self.ratio[self.names.index(n)])
            out[n] = {"armature": s.armature / r ** 2, "damping": 0.0, "frictionloss": 0.0}
        return out


def load_concept(path_or_dict) -> dict:
    if isinstance(path_or_dict, dict):
        return copy.deepcopy(path_or_dict)
    p = Path(path_or_dict)
    c = yaml.safe_load(p.read_text(encoding="utf-8"))
    c["_path"] = str(p)
    return c


def _joint_list(concept: dict, tpl: dict) -> list[dict]:
    out = []
    for item in concept["joints"]:
        j = {"name": item} if isinstance(item, str) else dict(item)
        n = j["name"]
        if n not in JOINT_DEFAULTS:
            raise ValueError(f"concept joint '{n}' has no default table; known: {sorted(JOINT_DEFAULTS)}")
        if n not in tpl["joints"]:
            raise ValueError(f"template '{tpl['id']}' has no joint '{n}'")
        limb, rng = JOINT_DEFAULTS[n]
        j.setdefault("limb", limb)
        j.setdefault("axis", tpl["joints"][n]["axis"])
        j.setdefault("range", rng)
        j.setdefault("priority", "required")
        out.append(j)
    return out


def build_spec(concept: dict) -> dict:
    """The base variant's spec with the concept's height, proportions, template and joints applied."""
    base = load_spec(concept.get("base", "adam"))
    tpl = load_template(concept.get("template", base["kinematics"].get("template", "biped_v1")))
    spec = copy.deepcopy(base)
    spec["body"]["height_m"] = float(concept["height_m"])
    spec["body"]["proportions"] = {**spec["body"]["proportions"], **concept.get("proportions", {})}
    spec["kinematics"] = {"template": tpl["id"], "mirror": True, "joints": _joint_list(concept, tpl)}
    spec["locomotion"] = deep_merge(spec["locomotion"], concept.get("locomotion", {}))
    if "mass_model" in concept:
        spec["mass_model"] = {**spec["mass_model"], **concept["mass_model"]}
    spec["id"] = concept["id"]
    return spec


def part_list(concept: dict) -> list[dict]:
    """On-robot parts [{part, qty}] and off-board parts. Concept `parts.onboard` / `parts.offboard`."""
    parts = concept.get("parts", {})
    return parts.get("onboard", []), parts.get("offboard", [])


def build_robot(concept, *, actuator_variants: dict | None = None, structure_scale: float = 0.0,
                parts_scale: float = 1.0) -> Robot:
    """structure_scale: fractional change of the printed structure+shell mass (nominal 0; evidence band -0.15..+0.40).
    parts_scale: scale on every catalog-mass part (servos, battery, boards; evidence band +-5%)."""
    concept = load_concept(concept)
    spec = build_spec(concept)
    spec["mass_model"] = {**spec["mass_model"], "structure_kg_at_1m": spec["mass_model"]["structure_kg_at_1m"] * (1 + structure_scale),
                          "electronics_kg": spec["mass_model"]["electronics_kg"] * parts_scale}
    h = float(concept["height_m"])
    joints = expand_joints(spec)
    # transmissions: a joint driven through a linkage/offset: servo angle = joint angle / ratio, efficiency eta, servo mounted on `host`
    trans = {}
    for key, tcfg in concept.get("transmissions", {}).items():
        for j in joints:
            if j["name"] == key or j["base"] == key:
                trans[j["name"]] = {"ratio": float(tcfg.get("ratio", 1.0)), "efficiency": float(tcfg.get("efficiency", 1.0)),
                                    "host": tcfg.get("host"), "note": tcfg.get("note", "")}
                if tcfg.get("host"):
                    j["host"] = tcfg["host"]
    default_act = concept["actuator_default"]
    overrides = concept.get("actuators", {})
    variants = {**concept.get("model_variants", {}), **(actuator_variants or {})}
    acts, servo = {}, {}
    for j in joints:
        aid = overrides.get(j["name"]) or overrides.get(j["base"]) or default_act
        acts[j["name"]] = aid
        servo[j["name"]] = servo_spec(aid, variants.get(aid))
    onboard, offboard = part_list(concept)
    fixed_mass = 0.0
    power_parts = {"onboard": [], "offboard": []}
    for item in onboard:
        p = catalog.get(item["part"])
        fixed_mass += p.get("mass_kg", 0.0) * item.get("qty", 1) * parts_scale
        power_parts["onboard"].append({**item, "mass_kg": p.get("mass_kg", 0.0), "price": catalog.price(p)})
    for item in offboard:
        p = catalog.get(item["part"])
        power_parts["offboard"].append({**item, "mass_kg": p.get("mass_kg", 0.0), "price": catalog.price(p)})
    # wiring harness: assumed 6 g per servo (cable + connector), 25 g trunk
    wiring = (0.006 * len(joints) + 0.025) * parts_scale
    act_mass = {n: servo[n].mass_kg * parts_scale for n in servo}
    body = build_body(spec, h, joints, act_mass, fixed_mass + wiring)
    names = [j["name"] for j in joints if simgen.JOINT_BODY.get(j["base"])]
    sim_joints = [j for j in joints if simgen.JOINT_BODY.get(j["base"])]
    ratio = np.array([(simgen.joint_kind(j["base"])["ratio"] if simgen.joint_kind(j["base"])["type"] == "slide" else 1.0)
                      * trans.get(j["name"], {}).get("ratio", 1.0) for j in sim_joints])
    eff = np.array([trans.get(j["name"], {}).get("efficiency", 1.0) for j in sim_joints])
    mb = {"structure_kg": body.breakdown["structure_kg"], "actuators_kg": body.breakdown["actuators_kg"],
          "onboard_parts_kg": round(fixed_mass, 4), "wiring_kg": round(wiring, 4),
          "electronics_misc_kg": spec["mass_model"]["electronics_kg"], "total_kg": round(body.total, 4)}
    robot = Robot(concept, spec, h, body, joints, acts, servo, names=names, ratio=ratio, mass_breakdown=mb, power_parts=power_parts,
                  eff=eff, transmissions=trans, mass_case={"structure_scale": structure_scale, "parts_scale": parts_scale})
    return robot


def benchmark_mass_kg(height_m: float) -> float:
    """SANITY BOUND ONLY (never Adam's estimate): fit over 9 comparable robots (research/robots/benchmarks.md), mass = 18.5 h^2.28."""
    return 18.5 * height_m ** 2.28


def mass_sanity(robot: Robot) -> dict:
    bm = benchmark_mass_kg(robot.height)
    ratio = robot.total_mass / bm
    status = "within" if 0.6 <= ratio <= 1.6 else ("below" if ratio < 0.6 else "above")
    return {"component_sum_kg": round(robot.total_mass, 3), "benchmark_fit_kg": round(bm, 3), "ratio": round(ratio, 3),
            "status": f"{status} the sanity band (0.6x-1.6x of the fit)",
            "note": "The fit 18.5*h^2.28 (N=9, R2 0.93, research/robots/benchmarks.md) and the ToddlerBot/OP3 masses are SANITY BOUNDS "
                    "ONLY. The mass used everywhere in this report is the component sum (catalog masses +-5% + printed structure with "
                    "its own -15%/+40% band); the structure term is a pre-CAD guess."}
