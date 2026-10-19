"""State estimator: base orientation (IMU), COM and feet from kinematics, foot contact, COM position/velocity relative to the support.

Inputs are only what the real robot has: joint encoders, the pelvis IMU, and the commanded contact schedule (a hint).

* **Attitude:** gyro integration with a Mahony-style accelerometer correction (gain scaled down when |acc| is far from 1 g, i.e.
  during impacts or hard accelerations). Yaw is the integrated gyro (no magnetometer): it drifts, so behaviours use yaw *differences*.
* **Kinematics:** the runtime's own MuJoCo model, kinematics only (`mj_kinematics`, `mj_comPos`; ~15 us), with the base set to the
  estimated orientation. Gives the whole-body COM and the foot sole centres in the pelvis frame.
* **Contact:** hint weights from the gait schedule, else the foot(s) lowest in the gravity-aligned frame (within 6 mm of the lowest).
* **COM state relative to support:** `c` = COM minus the support point (weighted sole centres) in the heading frame
  (x forward, y left); `v` from a two-state alpha-beta tracker on `c` of each foot (a foot that stays on the ground gives the COM velocity).
  The DCM is `xi = c + v / omega`, omega = sqrt(g / z_com).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .hal.base import HalState
from .model import G, RobotModel


def exp_so3(w: np.ndarray) -> np.ndarray:
    th = float(np.linalg.norm(w))
    if th < 1e-9:
        return np.eye(3) + skew(w)
    k = w / th
    K = skew(k)
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K)


def skew(v) -> np.ndarray:
    return np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0.0]])


def yaw_of(R: np.ndarray) -> float:
    return math.atan2(R[1, 0], R[0, 0])


def rot_z(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


@dataclass
class EstState:
    t: float
    R: np.ndarray                    # world <- pelvis
    roll: float
    pitch: float                     # forward lean positive (pelvis pitch about +y, nose down)
    yaw: float
    gyro: np.ndarray                 # body rates (bias-corrected)
    tilt: float                      # angle between pelvis z and gravity [rad]
    tilt_rate: float
    com_b: np.ndarray                # COM in the gravity-aligned frame at the pelvis origin (z up, yaw of the pelvis)
    feet_b: dict                     # sole centre 'l'/'r' in the same frame
    foot_R: dict                     # foot orientation matrices in the same frame
    contact: np.ndarray              # weights [l, r], sum 1
    support: np.ndarray              # support point (weighted sole centres) in the gravity-aligned frame at the pelvis origin
    c: np.ndarray                    # COM minus support, heading frame (x fwd, y left, z up)
    v: np.ndarray                    # COM velocity (heading frame)
    omega: float                     # sqrt(g / zc)
    dcm: np.ndarray                  # c[:2] + v[:2] / omega
    heading: float                   # yaw used for the frame
    c_foot: dict = field(default_factory=dict)   # COM minus each foot's sole centre, heading frame
    v_foot: dict = field(default_factory=dict)


class StateEstimator:
    def __init__(self, model: RobotModel, dt: float, acc_gain: float = 1.5, v_bw_hz: float = 9.0):
        self.m = model
        self.dt = dt
        self.kin = model.kin
        self.R = np.eye(3)
        self.acc_gain = acc_gain
        self.bias = np.zeros(3)
        self.t = 0.0
        self._c_prev = None
        self._v_f = {"l": np.zeros(3), "r": np.zeros(3)}
        self._x_f = {"l": None, "r": None}
        self._w = 2 * math.pi * v_bw_hz
        self._tilt_prev = 0.0
        self.initialised = False
        # alpha-beta gains for critical damping at bandwidth w: alpha = 1 - e^{-2 w dt}-like; use the usual g-h from a double pole
        a = 1 - math.exp(-self._w * dt)
        self._alpha = a * (2 - a) if a < 1 else 1.0
        self._beta = a * a

    # ---------------------------------------------------------------- init from stillness
    def initialise(self, hal_state: HalState, still_samples: list | None = None) -> None:
        """Gravity-align the attitude from the accelerometer at rest and (optionally) estimate the gyro bias."""
        acc = hal_state.imu.acc if not still_samples else np.mean([s.acc for s in still_samples], 0)
        z = acc / np.linalg.norm(acc)
        x = np.array([1.0, 0, 0]) - z * z[0]
        x /= np.linalg.norm(x)
        y = np.cross(z, x)
        self.R = np.stack([x, y, z], 1)           # world <- pelvis with world z = gravity up and yaw 0 along the body x projection
        if still_samples:
            g = np.array([s.gyro for s in still_samples])
            # only trust the mean as a bias when the robot really was still (a settling robot rotates: that is not bias)
            self.bias = g.mean(0) if float(np.abs(g.mean(0)).max()) < 0.03 and float(g.std(0).max()) < 0.02 else np.zeros(3)
        self.t = hal_state.t
        self.initialised = True

    # ---------------------------------------------------------------- update
    def update(self, s: HalState, contact_hint: np.ndarray | None = None) -> EstState:
        if not self.initialised:
            self.initialise(s)
        dt = self.dt
        gyro = s.imu.gyro - self.bias
        # attitude: Mahony correction using the accelerometer's gravity direction
        a = s.imu.acc
        an = float(np.linalg.norm(a))
        corr = np.zeros(3)
        if an > 1e-3:
            trust = max(0.0, 1.0 - abs(an - G) / (0.35 * G))
            g_body = self.R.T @ np.array([0, 0, 1.0])
            corr = self.acc_gain * trust * np.cross(a / an, g_body)
        self.R = self.R @ exp_so3((gyro + corr) * dt)
        if abs(self.R[2, 2]) > 1.5 or not np.isfinite(self.R).all():
            self.R = np.eye(3)
        # re-orthonormalise occasionally (cheap SVD-free Gram-Schmidt)
        x = self.R[:, 0] / np.linalg.norm(self.R[:, 0])
        y = self.R[:, 1] - x * (x @ self.R[:, 1])
        y /= np.linalg.norm(y)
        self.R = np.stack([x, y, np.cross(x, y)], 1)
        yaw = yaw_of(self.R)
        pitch = math.atan2(-self.R[2, 0], self.R[2, 2])                                  # Ry(pitch): forward lean positive
        roll = math.atan2(self.R[2, 1], self.R[2, 2])
        tilt = math.acos(float(np.clip(self.R[2, 2], -1, 1)))
        tilt_rate = (tilt - self._tilt_prev) / dt
        self._tilt_prev = tilt
        # kinematics with the estimated base orientation. Express everything in the gravity-aligned frame whose yaw is the pelvis yaw.
        k = self.kin
        quat = np.zeros(4)
        k.mj.mju_mat2Quat(quat, self.R.reshape(-1))
        k.set_state(s.q, np.zeros(3), quat)
        k.mj.mj_kinematics(k.model, k.data)
        k.mj.mj_comPos(k.model, k.data)
        com = k.data.subtree_com[1].copy()
        feet, foot_R = {}, {}
        for side in "lr":
            feet[side] = k.data.site(f"foot_{side}").xpos.copy()
            foot_R[side] = k.data.site(f"foot_{side}").xmat.reshape(3, 3).copy()
        Rz = rot_z(-yaw)                                   # heading frame: remove yaw only
        com_h = Rz @ com
        feet_h = {sd: Rz @ feet[sd] for sd in "lr"}
        # contact weights
        if contact_hint is not None:
            w = np.asarray(contact_hint, float)
            w = w / max(w.sum(), 1e-9)
        else:
            zl, zr = feet_h["l"][2], feet_h["r"][2]
            zmin = min(zl, zr)
            w = np.array([1.0 if zl - zmin < 0.006 else 0.0, 1.0 if zr - zmin < 0.006 else 0.0])
            w = w / w.sum()
        support = w[0] * feet_h["l"] + w[1] * feet_h["r"]
        c = com_h - support
        # per-foot COM position and velocity (alpha-beta tracker on each foot-relative COM)
        c_foot, v_foot = {}, {}
        for i, sd in enumerate("lr"):
            cf = com_h - feet_h[sd]
            # the heading frame rotates with the estimated yaw: rotate the previous estimate by the yaw change implicit in using Rz(-yaw)
            xp = self._x_f[sd]
            if xp is None:
                self._x_f[sd] = cf.copy()
                self._v_f[sd] = np.zeros(3)
            else:
                pred = xp + self._v_f[sd] * dt
                r = cf - pred
                self._x_f[sd] = pred + self._alpha * r
                self._v_f[sd] = self._v_f[sd] + self._beta * r / dt
            c_foot[sd], v_foot[sd] = cf, self._v_f[sd].copy()
        v = w[0] * v_foot["l"] + w[1] * v_foot["r"]
        zc = max(float(c[2]), 0.05)
        omega = math.sqrt(G / zc)
        self.t = s.t
        return EstState(
            t=s.t, R=self.R.copy(), roll=roll, pitch=pitch, yaw=yaw, gyro=gyro, tilt=tilt, tilt_rate=tilt_rate, com_b=com_h,
            feet_b=feet_h, foot_R=foot_R, contact=w, support=support, c=c, v=v, omega=omega,
            dcm=c[:2] + v[:2] / omega, heading=yaw, c_foot=c_foot, v_foot=v_foot)
