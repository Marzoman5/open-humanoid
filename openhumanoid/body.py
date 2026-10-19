"""Shared body model: segment geometry and mass distribution. Used by sizing AND sim generation,
so the two can never disagree."""
from __future__ import annotations

from dataclasses import dataclass, field

# Fraction of printed structure (frame + shell) mass per segment. Sums to 1.0.
STRUCT_SHARE = {
    "torso": 0.30, "pelvis": 0.10, "head": 0.08,
    "thigh": 0.08, "shank": 0.07, "foot": 0.03,       # per leg
    "upper_arm": 0.04, "forearm": 0.04,                 # per arm
}

# Which segment carries each joint's actuator (the parent side of the joint).
ACTUATOR_HOST = {
    "hip_yaw": "pelvis", "hip_roll": "pelvis", "hip_pitch": "thigh", "knee": "thigh",
    "ankle_pitch": "shank", "ankle_roll": "shank",
    "shoulder_pitch": "torso", "shoulder_roll": "upper_arm", "elbow": "upper_arm",
    "neck_yaw": "torso", "neck_pitch": "head",
}
LIMB_DEFAULT_HOST = {"leg": "thigh", "arm": "upper_arm", "head": "torso", "torso": "torso", "hand": "forearm", "attachment": "torso"}

PAIRED = ("thigh", "shank", "foot", "upper_arm", "forearm")


@dataclass
class Body:
    height: float
    geom: dict[str, float]                 # segment lengths/widths in m
    seg_mass: dict[str, float]             # per-segment mass (paired segments: per side)
    breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.seg_mass[s] * (2 if s in PAIRED else 1) for s in self.seg_mass)

    @property
    def leg(self) -> float:
        return self.seg_mass["thigh"] + self.seg_mass["shank"] + self.seg_mass["foot"]

    @property
    def arm(self) -> float:
        return self.seg_mass["upper_arm"] + self.seg_mass["forearm"]


def geometry(spec: dict, height: float) -> dict[str, float]:
    return {k: v * height for k, v in spec["body"]["proportions"].items()}


def build_body(spec: dict, height: float, joints: list[dict], actuator_mass: dict[str, float], fixed_mass_kg: float) -> Body:
    """joints: expanded joints; actuator_mass: expanded joint name -> kg; fixed_mass_kg: compute/battery/etc (torso)."""
    mm = spec["mass_model"]
    struct = mm["structure_kg_at_1m"] * height**3
    seg = {s: struct * share for s, share in STRUCT_SHARE.items()}
    act_total = 0.0
    for j in joints:
        host = ACTUATOR_HOST.get(j["base"], LIMB_DEFAULT_HOST.get(j["limb"], "torso"))
        m = actuator_mass.get(j["name"], 0.0)
        act_total += m
        # Paired segments store mass per side (the model is symmetric), so the l and r
        # actuators each contribute half to the shared per-side value.
        seg[host] += m / 2 if (host in PAIRED and j["side"] is not None) else m
    seg["torso"] += fixed_mass_kg + mm["electronics_kg"]
    body = Body(height, geometry(spec, height), seg)
    target = spec["body"].get("mass_kg")
    if target:
        k = target / body.total
        body.seg_mass = {s: m * k for s, m in body.seg_mass.items()}
    body.breakdown = {
        "structure_kg": round(struct, 3), "actuators_kg": round(act_total, 3),
        "electronics_kg": mm["electronics_kg"], "compute_power_kg": round(fixed_mass_kg, 3),
        "total_kg": round(body.total, 3),
    }
    return body
