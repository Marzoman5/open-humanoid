"""Shared pieces of the motion library: default posture, stand geometry, range checks, finishing a Reference."""
from __future__ import annotations

import math

import numpy as np

from ..kin import Reference, RobotKin, lower_body, quat_from_yaw_pitch

GRIP_CLOSED = 0.004     # idle jaw opening (m): slightly open so the servo does not push on its stop all day
ARM_REST = {"shoulder_roll": math.radians(8.0), "elbow": math.radians(-20.0)}   # left-arm values; right is mirrored


def set_col(kin: RobotKin, Q: np.ndarray, name: str, value) -> None:
    if kin.has(name):
        Q[:, kin.index[name]] = value


def rest_upper_body(kin: RobotKin, T: int) -> np.ndarray:
    """(T, nj) posture with arms relaxed at the sides, everything else zero."""
    Q = np.zeros((T, len(kin.names)))
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        set_col(kin, Q, f"shoulder_roll_{side}", sgn * ARM_REST["shoulder_roll"])
        set_col(kin, Q, f"elbow_{side}", ARM_REST["elbow"])
        set_col(kin, Q, f"gripper_{side}", GRIP_CLOSED)
    return Q


def stand_geometry(kin: RobotKin, knee_flex: float) -> dict:
    """Pelvis height and ankle positions of the symmetric crouched stand (ankles under the hips)."""
    lg = kin.lg
    l = math.sqrt(lg.L1 ** 2 + lg.L2 ** 2 + 2 * lg.L1 * lg.L2 * math.cos(knee_flex))
    z_hip = lg.ankle_h + l
    return {"pelvis_z": z_hip - lg.hip_z, "ankle_z": lg.ankle_h, "hip_y": lg.hip_y, "leg_len": l}


def knee_flex_from(kin: RobotKin) -> float:
    return math.radians(kin.robot.spec["locomotion"].get("walk", {}).get("stance_knee_flex_deg", 30))


def check_ranges(kin: RobotKin, Q: np.ndarray, tol: float = 1e-3) -> list[str]:
    bad = []
    for j in kin.robot.joints:
        n = j["name"]
        if n not in kin.index:
            continue
        lo, hi = (j["range"][0] / 1000.0, j["range"][1] / 1000.0) if j["base"] == "gripper" else \
            (math.radians(j["range"][0]), math.radians(j["range"][1]))
        v = Q[:, kin.index[n]]
        if v.min() < lo - tol or v.max() > hi + tol:
            bad.append(f"{n}: [{v.min():.3f},{v.max():.3f}] outside [{lo:.3f},{hi:.3f}]")
    return bad


def finish(kin: RobotKin, name: str, dt: float, Q: np.ndarray, pelvis: np.ndarray, yaw: np.ndarray, pitch: np.ndarray,
           ok: np.ndarray | None = None, notes: list | None = None, meta: dict | None = None, **kw) -> Reference:
    notes = list(notes or [])
    feasible = True
    if ok is not None and not ok.all():
        notes.append(f"leg IK unreachable at {int((~ok).sum())} of {len(ok)} samples")
        feasible = False
    bad = check_ranges(kin, Q)
    if bad:
        notes.append("joint range violations: " + "; ".join(bad))
        feasible = False
    return Reference(name, dt, Q, pelvis, quat_from_yaw_pitch(yaw, pitch), feasible, notes, meta or {}, **kw)


def fill_legs(kin: RobotKin, Q: np.ndarray, pelvis, yaw, pitch, ank_l, ank_r, fy_l, fy_r) -> np.ndarray:
    out, ok = lower_body(kin, pelvis, yaw, pitch, ank_l, ank_r, fy_l, fy_r)
    for n, v in out.items():
        set_col(kin, Q, n, v)
    return ok
