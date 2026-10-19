"""Kinematics helpers for the motion library: analytic leg IK, MuJoCo-based COM/FK, pose assembly, interpolation.

Frames: world x forward, y left, z up. Pelvis orientation R = Rz(yaw) * Ry(pitch) (pitch > 0 leans forward).
Hinge angles: Ry(q) swings a downward vector backward for q > 0, so hip_pitch < 0 means thigh forward, knee > 0
flexes (shank back), and shoulder_pitch < 0 raises the arm forward.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .robot import Robot


def rot_z(a):
    c, s = np.cos(a), np.sin(a)
    z, o = np.zeros_like(c), np.ones_like(c)
    return np.stack([np.stack([c, -s, z], -1), np.stack([s, c, z], -1), np.stack([z, z, o], -1)], -2)


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    z, o = np.zeros_like(c), np.ones_like(c)
    return np.stack([np.stack([c, z, s], -1), np.stack([z, o, z], -1), np.stack([-s, z, c], -1)], -2)


def quat_from_yaw_pitch(yaw, pitch) -> np.ndarray:
    """(T,) yaw & pitch -> (T,4) wxyz for Rz(yaw) Ry(pitch)."""
    yaw, pitch = np.atleast_1d(yaw).astype(float), np.atleast_1d(pitch).astype(float)
    cz, sz, cy, sy = np.cos(yaw / 2), np.sin(yaw / 2), np.cos(pitch / 2), np.sin(pitch / 2)
    return np.stack([cz * cy, -sz * sy, cz * sy, sz * cy], -1)


def smoothstep5(s):
    s = np.clip(s, 0.0, 1.0)
    return s ** 3 * (10 - 15 * s + 6 * s * s)


def catmull(t_src: np.ndarray, y: np.ndarray, t_new: np.ndarray) -> np.ndarray:
    """Cubic Hermite (Catmull-Rom tangents) resampling of y(t) with uniform t_src. y: (T,) or (T,n)."""
    y = np.asarray(y, dtype=float)
    dt = t_src[1] - t_src[0]
    idx = np.clip(((t_new - t_src[0]) / dt).astype(int), 0, len(t_src) - 2)
    s = ((t_new - t_src[idx]) / dt)
    if y.ndim == 2:
        s = s[:, None]
    m = np.gradient(y, dt, axis=0)
    h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
    return h00 * y[idx] + h10 * dt * m[idx] + h01 * y[idx + 1] + h11 * dt * m[idx + 1]


@dataclass
class LegGeom:
    L1: float            # thigh
    L2: float            # shank
    hip_y: float         # |y| of hip joint in the pelvis frame
    hip_z: float         # z of hip joint in the pelvis frame (negative)
    ankle_h: float       # ankle height above the sole
    foot_len: float
    foot_w: float
    foot_off: float      # sole centre offset forward of the ankle


def leg_geom(robot: Robot) -> LegGeom:
    g = robot.geom
    return LegGeom(g["thigh"], g["shank"], g["hip_width"] / 2, -g["pelvis"] / 2, g["ankle_height"], g["foot_length"],
                   g["foot_width"], 0.15 * g["foot_length"])


def leg_ik(r: np.ndarray, psi: np.ndarray, pitch: np.ndarray, lg: LegGeom):
    """r: (T,3) ankle minus hip in the PELVIS frame; psi: foot yaw relative to the pelvis; pitch: pelvis pitch.
    Returns q (T,6) = [hip_yaw, hip_roll, hip_pitch, knee, ankle_pitch, ankle_roll] and reach_ok (T,) bool.
    Assumes a flat foot (foot orientation = Rz(world yaw))."""
    c, s = np.cos(-psi), np.sin(-psi)
    rx = c * r[:, 0] - s * r[:, 1]
    ry = s * r[:, 0] + c * r[:, 1]
    rz = r[:, 2]
    d = np.hypot(ry, rz)
    l2 = rx * rx + d * d
    cosk = (l2 - lg.L1 ** 2 - lg.L2 ** 2) / (2 * lg.L1 * lg.L2)
    ok = (cosk <= 1.0) & (cosk >= -1.0)
    cosk = np.clip(cosk, -1.0, 1.0)
    q4 = np.arccos(cosk)
    q2 = np.arctan2(ry, -rz)
    ax, az = -lg.L2 * np.sin(q4), -lg.L1 - lg.L2 * np.cos(q4)
    q3 = np.arctan2(ax, -az) - np.arctan2(rx, d)
    q5 = -pitch - q3 - q4
    q6 = -q2
    return np.stack([psi, q2, q3, q4, q5, q6], -1), ok


class RobotKin:
    """Wraps the concept robot's MuJoCo model for forward kinematics, COM and joint bookkeeping."""

    LEG = ["hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch", "ankle_roll"]

    def __init__(self, robot: Robot, model=None):
        import mujoco
        self.mj = mujoco
        self.robot = robot
        self.model = model or robot.build_model()
        self.data = mujoco.MjData(self.model)
        self.names = robot.names
        self.qadr = np.array([self.model.joint(n).qposadr[0] for n in self.names])
        self.dadr = np.array([self.model.joint(n).dofadr[0] for n in self.names])
        self.index = {n: i for i, n in enumerate(self.names)}
        self.lg = leg_geom(robot)
        self.total_mass = float(sum(self.model.body_mass))

    def jidx(self, *names) -> list[int]:
        return [self.index[n] for n in names]

    def has(self, name: str) -> bool:
        return name in self.index

    def set_state(self, q: np.ndarray, pos, quat):
        d = self.data
        d.qpos[:3] = pos
        d.qpos[3:7] = quat
        d.qpos[self.qadr] = q

    def com(self, q, pos, quat) -> np.ndarray:
        self.set_state(q, pos, quat)
        self.mj.mj_kinematics(self.model, self.data)
        self.mj.mj_comPos(self.model, self.data)
        return self.data.subtree_com[1].copy()

    def com_traj(self, Q, P, QU) -> np.ndarray:
        return np.array([self.com(Q[i], P[i], QU[i]) for i in range(len(Q))])

    def site(self, name, q, pos, quat) -> np.ndarray:
        self.set_state(q, pos, quat)
        self.mj.mj_kinematics(self.model, self.data)
        return self.data.site(name).xpos.copy()

    def stand_q(self, knee_flex: float) -> np.ndarray:
        q = np.zeros(len(self.names))
        for side in "lr":
            for base, v in (("hip_pitch", -knee_flex / 2), ("knee", knee_flex), ("ankle_pitch", -knee_flex / 2)):
                if self.has(f"{base}_{side}"):
                    q[self.index[f"{base}_{side}"]] = v
        return q


@dataclass
class Reference:
    """A joint-space reference with the base trajectory it assumes. q columns follow Robot.names (native units)."""
    name: str
    dt: float
    q: np.ndarray                  # (T, nj)
    base_pos: np.ndarray           # (T, 3) pelvis origin
    base_quat: np.ndarray          # (T, 4) wxyz
    feasible: bool = True
    notes: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    scene: dict | None = None      # extra world (table/object) description for the pickup
    stance: np.ndarray | None = None   # (T,2) foot-in-contact flags L,R

    @property
    def t(self) -> np.ndarray:
        return np.arange(len(self.q)) * self.dt

    @property
    def duration(self) -> float:
        return (len(self.q) - 1) * self.dt


def lower_body(kin: RobotKin, pelvis: np.ndarray, yaw: np.ndarray, pitch: np.ndarray, ankle_l: np.ndarray,
               ankle_r: np.ndarray, foot_yaw_l: np.ndarray, foot_yaw_r: np.ndarray):
    """World pelvis/ankle trajectories -> 12 leg joint angles. Returns (dict name->(T,), ok(T,))."""
    lg = kin.lg
    out, ok_all = {}, np.ones(len(pelvis), bool)
    R = rot_z(yaw) @ rot_y(pitch)                                  # (T,3,3)
    for side, ank, fy, sgn in (("l", ankle_l, foot_yaw_l, 1.0), ("r", ankle_r, foot_yaw_r, -1.0)):
        hip_local = np.array([0.0, sgn * lg.hip_y, lg.hip_z])
        hip_w = pelvis + R @ hip_local
        r = np.einsum("tji,tj->ti", R, ank - hip_w)                # R^T (ank - hip)
        q, ok = leg_ik(r, fy - yaw, pitch, lg)
        ok_all &= ok
        for i, base in enumerate(RobotKin.LEG):
            out[f"{base}_{sgn_name(side)}"] = q[:, i]
    return out, ok_all


def sgn_name(side: str) -> str:
    return side


def compensate_com(kin: RobotKin, build_q, pelvis0: np.ndarray, yaw, pitch, com_target: np.ndarray, iters: int = 3,
                   adjust=None):
    """Shift the pelvis xy so the whole-body COM follows `com_target` (T,2). `build_q(pelvis)` returns Q (T,nj).
    `adjust(pelvis)` (optional) re-derives dependent pelvis coordinates (e.g. height from a knee-flexion profile)."""
    pelvis = pelvis0.copy()
    quat = quat_from_yaw_pitch(yaw, pitch)
    if adjust:
        pelvis = adjust(pelvis)
    Q = build_q(pelvis)
    for _ in range(iters):
        com = kin.com_traj(Q, pelvis, quat)
        pelvis[:, :2] += com_target - com[:, :2]
        if adjust:
            pelvis = adjust(pelvis)
        Q = build_q(pelvis)
    com = kin.com_traj(Q, pelvis, quat)
    return pelvis, Q, float(np.abs(com_target - com[:, :2]).max())
