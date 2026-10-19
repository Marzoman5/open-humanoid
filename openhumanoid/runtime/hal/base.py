"""Hardware abstraction layer: the one interface the runtime uses to talk to servos and the IMU.

Everything above this file (safety, estimator, behaviours, command API) is identical in simulation and on the robot.
A HAL turns `JointCmd` into servo register writes and `HalState` out of register reads, at a fixed control rate:

    state = hal.read()          # position, velocity, load, current, temperature, voltage + IMU
    hal.write(cmd)              # goal position, torque limit, torque enable, P gain (the Feetech register semantics)
    hal.tick()                  # sim: advance physics one control period; real: sleep to the next period

Units: SI. Joints in rad (grippers in m, the runtime's native joint units). `load` is the signed fraction of full output
(Feetech Present_Load / 1000), `current` is amperes, `temp_c` degrees C, `voltage` volts (one bus).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ImuSample:
    t: float
    gyro: np.ndarray                 # rad/s, body frame
    acc: np.ndarray                  # m/s^2, specific force in the body frame (gravity reads +9.81 on the up axis at rest)
    quat: np.ndarray | None = None   # optional fused orientation (wxyz) from the IMU's own filter; the estimator does not need it


@dataclass
class HalState:
    t: float
    q: np.ndarray
    dq: np.ndarray
    load: np.ndarray
    current: np.ndarray
    temp_c: np.ndarray
    voltage: float
    torque_on: np.ndarray            # servo torque actually enabled (False after a firmware shutdown or a torque-off write)
    protected: np.ndarray            # servo in firmware overload protection (torque cut to the protective level)
    fault: np.ndarray                # firmware alarm latched (over-temperature / voltage)
    imu: ImuSample


@dataclass
class JointCmd:
    q: np.ndarray                    # goal position [rad]
    torque_limit: np.ndarray         # fraction of the servo's maximum torque [0..1] (Feetech Torque_Limit / 1000)
    enable: np.ndarray               # torque enable per joint
    kp_scale: np.ndarray | None = None   # scale on the servo's P coefficient (None: unchanged)

    @staticmethod
    def hold(q: np.ndarray, n: int | None = None) -> "JointCmd":
        n = len(q) if n is None else n
        return JointCmd(np.asarray(q, float).copy(), np.ones(n), np.ones(n, bool))


class Hal(ABC):
    """Abstract HAL. `names` fixes the joint order of every array."""

    names: list
    control_hz: float

    @abstractmethod
    def read(self) -> HalState: ...

    @abstractmethod
    def write(self, cmd: JointCmd) -> None: ...

    @abstractmethod
    def tick(self) -> None: ...

    def close(self) -> None:
        pass

    @property
    def dt(self) -> float:
        return 1.0 / self.control_hz
