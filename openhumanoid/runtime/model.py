"""RobotModel: what the runtime knows about the robot, built from a concept (or spec) and nothing else.

Joint names, limits, calibration offsets, servo constants, geometry and the MuJoCo kinematic model all come from the
concept engine (`openhumanoid.concept.robot.build_robot`), so the runtime, the sim and the concept report agree. Nothing here
knows about Adam: pass any concept YAML.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..concept.kin import RobotKin
from ..concept.robot import Robot, build_robot, load_concept
from ..paths import repo_root

DEFAULT_CONCEPT = "variants/adam/concepts/R1-P1r-0p55-3s-sts3250-knee-hiproll.yaml"
G = 9.81


@dataclass
class RobotModel:
    robot: Robot
    kin: RobotKin
    names: list
    index: dict
    lo: np.ndarray                   # joint limits, native units (rad; gripper: m)
    hi: np.ndarray
    ratio: np.ndarray                # joint units per servo radian (1 for hinges)
    stall: np.ndarray                # datasheet stall torque per joint at its rated voltage [N m] (servo domain)
    offset: np.ndarray = field(default=None)   # calibration offset: joint = servo_angle * ratio - offset (zero unless calibrated)
    walk_flex: float = 0.7           # nominal stance knee flexion [rad]
    concept_id: str = ""

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_concept(cls, path_or_dict=DEFAULT_CONCEPT) -> "RobotModel":
        if isinstance(path_or_dict, (str, Path)) and not Path(path_or_dict).is_absolute():
            path_or_dict = repo_root() / path_or_dict
        robot = build_robot(path_or_dict)
        kin = RobotKin(robot)
        names = list(robot.names)
        lo, hi = np.zeros(len(names)), np.zeros(len(names))
        for j in robot.joints:
            if j["name"] in names:
                i = names.index(j["name"])
                if j["base"] == "gripper":
                    lo[i], hi[i] = j["range"][0] / 1000.0, j["range"][1] / 1000.0
                else:
                    lo[i], hi[i] = math.radians(j["range"][0]), math.radians(j["range"][1])
        stall = np.array([robot.servo[n].stall_nm_ref for n in names])
        flex = math.radians(robot.spec["locomotion"].get("walk", {}).get("stance_knee_flex_deg", 30))
        return cls(robot, kin, names, {n: i for i, n in enumerate(names)}, lo, hi, np.asarray(robot.ratio, float), stall,
                   np.zeros(len(names)), flex, robot.concept["id"])

    # ------------------------------------------------------------------ helpers
    @property
    def n(self) -> int:
        return len(self.names)

    @property
    def mass(self) -> float:
        return self.kin.total_mass

    @property
    def lg(self):
        return self.kin.lg

    def idx(self, *names) -> list:
        return [self.index[n] for n in names]

    def has(self, name: str) -> bool:
        return name in self.index

    def clamp(self, q: np.ndarray) -> np.ndarray:
        return np.clip(q, self.lo, self.hi)

    def side_idx(self, base: str) -> tuple:
        return self.index.get(f"{base}_l", -1), self.index.get(f"{base}_r", -1)

    def stand_q(self, flex: float | None = None) -> np.ndarray:
        """Standing joint vector (arms at rest). Uses the concept's own rest posture so sim and concept agree."""
        from ..concept.motions.common import rest_upper_body
        q = rest_upper_body(self.kin, 1)[0]
        flex = self.walk_flex if flex is None else flex
        return np.where(q != 0, q, self.kin.stand_q(flex))

    def summary(self) -> dict:
        return {"concept": self.concept_id, "height_m": self.robot.height, "mass_kg": round(self.mass, 3), "dof": self.n,
                "joints": self.names}
