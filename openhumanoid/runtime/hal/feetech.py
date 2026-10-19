"""FeetechHAL: the real servo bus (Feetech STS3215/STS3250, TTL half-duplex, e.g. via the Waveshare bus-servo adapter). **UNTESTED ON HARDWARE.**

Status, stated plainly: this module has been exercised only against `MockBus` (an in-memory register file) in tests/test_runtime.py. No
servo has been commanded through it. The register map below is the STS-series memory table as exposed by LeRobot; every address must be
checked against the servo datasheet / LeRobot at the pinned commit during bring-up (`check_register_map()` does the comparison when the
`lerobot` package is installed). Treat the first power-up as a bench test: low torque limit, robot on a stand, e-stop in hand.

What is built:

* `ServoMap`: joint name -> servo id, sign, zero offset (counts), ratio (joint units per servo radian), straight from the `RobotModel`.
* Conversions between joint units and servo registers: position counts (4096 per revolution), signed speed, signed load (0..1000 with a
  direction bit), voltage (0.1 V), temperature (C), current (6.5 mA per count), torque limit (fraction -> 0..1000).
* `Bus` protocol with two implementations: `LeRobotBus` (a thin adapter over `lerobot.motors.SerialMotorsBus`, imported lazily) and
  `MockBus` (register file, optional physics callback; used by the tests).
* `FeetechHAL`: `read()` = one sync-read of the six status registers + IMU, `write()` = one sync-write each of Goal_Position and
  Torque_Limit (+ Torque_Enable on change), `tick()` = sleep to the next control period.

LICENSE / reuse: LeRobot (huggingface/lerobot) is Apache-2.0 (LICENSE re-read 2026-10-19 at commit b192c02dda8d, with MIT notices for
some third-party code). This file imports it at run time and copies none of its source; it only uses the public names `SerialMotorsBus`,
`Motor`, `MotorNormMode` and the register names ("Present_Position", ...). See THIRD_PARTY.md.
"""
from __future__ import annotations

import math
import time
import warnings
from dataclasses import dataclass, field
from typing import Callable, Protocol

import numpy as np

from ..model import RobotModel
from .base import Hal, HalState, ImuSample, JointCmd

TESTED_ON_HARDWARE = False
COUNTS = 4096
CENTRE = 2048
CURRENT_A_PER_COUNT = 0.0065

# STS3215 memory table (SMS/STS series). name -> (address, size in bytes). From Feetech's published table as mirrored by LeRobot; VERIFY.
REGISTERS = {
    "Max_Temperature_Limit": (13, 1), "Max_Voltage_Limit": (14, 1), "Min_Voltage_Limit": (15, 1), "Max_Torque_Limit": (16, 2),
    "P_Coefficient": (21, 1), "D_Coefficient": (22, 1), "I_Coefficient": (23, 1), "Protection_Current": (28, 2), "Operating_Mode": (33, 1),
    "Protective_Torque": (34, 1), "Protection_Time": (35, 1), "Overload_Torque": (36, 1),
    "Torque_Enable": (40, 1), "Acceleration": (41, 1), "Goal_Position": (42, 2), "Goal_Time": (44, 2), "Goal_Velocity": (46, 2),
    "Torque_Limit": (48, 2), "Lock": (55, 1),
    "Present_Position": (56, 2), "Present_Velocity": (58, 2), "Present_Load": (60, 2), "Present_Voltage": (62, 1),
    "Present_Temperature": (63, 1), "Moving": (66, 1), "Present_Current": (69, 2),
}


def check_register_map() -> list:
    """Compare REGISTERS with LeRobot's table when it is installed. Returns a list of mismatch strings ([] when equal or lerobot absent)."""
    try:
        from lerobot.motors.feetech import tables  # type: ignore
    except Exception:  # noqa: BLE001
        return ["lerobot not importable: register map not cross-checked"]
    out = []
    tab = getattr(tables, "STS_SMS_SERIES_CONTROL_TABLE", None)
    if tab is None:
        return ["lerobot has no STS_SMS_SERIES_CONTROL_TABLE at this version: check by hand"]
    for k, (a, n) in REGISTERS.items():
        if k in tab and tuple(tab[k]) != (a, n):
            out.append(f"{k}: ours {(a, n)} lerobot {tuple(tab[k])}")
    return out


# ---------------------------------------------------------------------------------------------------- conversions
@dataclass
class ServoMap:
    ids: np.ndarray
    sign: np.ndarray                     # +1/-1: servo direction relative to the joint's positive direction
    zero_counts: np.ndarray              # count at which the joint is at 0 (calibration; default 2048)
    ratio: np.ndarray                    # joint units per servo radian (1 for hinges, m/rad for the gripper slide)
    names: list

    @classmethod
    def default(cls, model: RobotModel, first_id: int = 1) -> "ServoMap":
        n = model.n
        return cls(np.arange(first_id, first_id + n), np.ones(n), np.full(n, float(CENTRE)), model.ratio.copy(), list(model.names))

    def to_counts(self, q: np.ndarray) -> np.ndarray:
        theta = np.asarray(q) / self.ratio
        c = self.zero_counts + self.sign * theta * COUNTS / (2 * math.pi)
        return np.clip(np.round(c), 0, COUNTS - 1).astype(int)

    def to_joint(self, counts: np.ndarray) -> np.ndarray:
        theta = self.sign * (np.asarray(counts, float) - self.zero_counts) * 2 * math.pi / COUNTS
        return theta * self.ratio


def decode_signed(raw: np.ndarray, bit: int) -> np.ndarray:
    """Feetech sign-magnitude encoding: bit `bit` is the sign, the rest the magnitude."""
    raw = np.asarray(raw, int)
    mag = raw & ((1 << bit) - 1)
    return np.where(raw & (1 << bit), -mag, mag)


def encode_signed(v: np.ndarray, bit: int) -> np.ndarray:
    v = np.asarray(v, int)
    return np.where(v < 0, (-v) | (1 << bit), v)


# ---------------------------------------------------------------------------------------------------- buses
class Bus(Protocol):
    def sync_read(self, register: str, ids: np.ndarray) -> np.ndarray: ...
    def sync_write(self, register: str, ids: np.ndarray, values: np.ndarray) -> None: ...
    def close(self) -> None: ...


class MockBus:
    """In-memory register file with the right register names; `on_write` can mirror writes into a simulation."""

    def __init__(self, ids: np.ndarray, on_write: Callable | None = None):
        self.regs = {k: {int(i): 0 for i in ids} for k in REGISTERS}
        for i in ids:
            self.regs["Present_Position"][int(i)] = CENTRE
            self.regs["Goal_Position"][int(i)] = CENTRE
            self.regs["Present_Voltage"][int(i)] = 120
            self.regs["Present_Temperature"][int(i)] = 25
        self.on_write = on_write
        self.log: list = []

    def sync_read(self, register: str, ids: np.ndarray) -> np.ndarray:
        return np.array([self.regs[register][int(i)] for i in ids])

    def sync_write(self, register: str, ids: np.ndarray, values: np.ndarray) -> None:
        for i, v in zip(ids, values):
            self.regs[register][int(i)] = int(v)
        self.log.append((register, list(map(int, values))))
        if self.on_write:
            self.on_write(register, ids, values)

    def close(self) -> None:
        pass


class LeRobotBus:
    """Adapter over lerobot.motors.SerialMotorsBus (Apache-2.0). Lazy import; requires `pip install lerobot` and a connected adapter."""

    def __init__(self, port: str, names: list, ids: np.ndarray, model: str = "sts3215"):
        from lerobot.motors import Motor, MotorNormMode, SerialMotorsBus  # type: ignore
        motors = {n: Motor(int(i), model, MotorNormMode.RANGE_M100_100) for n, i in zip(names, ids)}
        self.bus = SerialMotorsBus(port=port, motors=motors)
        self.names = names
        self.idx = {int(i): n for n, i in zip(names, ids)}
        self.bus.connect()

    def sync_read(self, register: str, ids: np.ndarray) -> np.ndarray:
        vals = self.bus.sync_read(register, [self.idx[int(i)] for i in ids], normalize=False)
        return np.array([vals[self.idx[int(i)]] for i in ids])

    def sync_write(self, register: str, ids: np.ndarray, values: np.ndarray) -> None:
        self.bus.sync_write(register, {self.idx[int(i)]: int(v) for i, v in zip(ids, values)}, normalize=False)

    def close(self) -> None:
        self.bus.disconnect()


# ---------------------------------------------------------------------------------------------------- IMU source
class ImuSource(Protocol):
    def read(self) -> ImuSample: ...


class Bno085Imu:
    """Placeholder for the BNO085 over I2C (Adafruit CircuitPython driver). Not implemented: raise until bring-up."""

    def read(self) -> ImuSample:
        raise NotImplementedError("BNO085 driver is bring-up work: wire adafruit_bno08x here and return gyro [rad/s] and linear+gravity acceleration [m/s^2] in the pelvis frame")


# ---------------------------------------------------------------------------------------------------- the HAL
class FeetechHAL(Hal):
    """See the module docstring: UNTESTED ON HARDWARE."""

    def __init__(self, model: RobotModel, bus: Bus, imu: ImuSource, servo_map: ServoMap | None = None, control_hz: float = 100.0,
                 max_torque_counts: int = 1000):
        warnings.warn("FeetechHAL has never run on hardware: bench-test with low torque limits, robot on a stand, e-stop in hand", stacklevel=2)
        self.m = model
        self.names = model.names
        self.control_hz = control_hz
        self.bus = bus
        self.imu = imu
        self.map = servo_map or ServoMap.default(model)
        self.max_torque = max_torque_counts
        self._next = time.monotonic()
        self._enabled = np.zeros(model.n, bool)
        self._t0 = time.monotonic()
        self._last_q = None

    # ---- bring-up helpers
    def configure(self, p_coeff: int = 32, d_coeff: int = 32, i_coeff: int = 0, torque_limit: int = 500) -> None:
        """One-time register setup. The D coefficient damps the 6.5 Hz resonance the runtime also damps in software; values are starting points."""
        ids = self.map.ids
        n = len(ids)
        for reg, v in (("P_Coefficient", p_coeff), ("D_Coefficient", d_coeff), ("I_Coefficient", i_coeff), ("Torque_Limit", torque_limit), ("Acceleration", 0)):
            self.bus.sync_write(reg, ids, np.full(n, v))
        self.bus.sync_write("Lock", ids, np.zeros(n, int))

    def estop_pressed(self) -> bool:
        return False                   # wire the hardware e-stop input (GPIO) here

    # ---- Hal
    def read(self) -> HalState:
        ids = self.map.ids
        pos = self.bus.sync_read("Present_Position", ids)
        vel = decode_signed(self.bus.sync_read("Present_Velocity", ids), 15)
        load = decode_signed(self.bus.sync_read("Present_Load", ids), 10)
        volt = self.bus.sync_read("Present_Voltage", ids)
        temp = self.bus.sync_read("Present_Temperature", ids)
        cur = self.bus.sync_read("Present_Current", ids)
        q = self.map.to_joint(pos)
        dq = self.map.sign * vel * 2 * math.pi / COUNTS * self.map.ratio
        imu = self.imu.read()
        t = time.monotonic() - self._t0
        return HalState(
            t=t, q=q, dq=dq, load=np.clip(load / 1000.0, -1, 1) * self.map.sign, current=cur * CURRENT_A_PER_COUNT, temp_c=temp.astype(float),
            voltage=float(np.median(volt)) / 10.0, torque_on=self._enabled.copy(), protected=np.zeros(self.m.n, bool),
            fault=temp >= np.array([self.m.robot.servo[n].max_temp_c for n in self.names]), imu=imu)

    def write(self, cmd: JointCmd) -> None:
        ids = self.map.ids
        goal = self.map.to_counts(cmd.q)
        lim = np.clip(np.round(cmd.torque_limit * self.max_torque), 0, 1000).astype(int)
        en = np.asarray(cmd.enable, bool)
        if (en != self._enabled).any():
            self.bus.sync_write("Torque_Enable", ids, en.astype(int))
            self._enabled = en.copy()
        self.bus.sync_write("Torque_Limit", ids, lim)
        self.bus.sync_write("Goal_Position", ids, goal)

    def tick(self) -> None:
        self._next += 1.0 / self.control_hz
        dt = self._next - time.monotonic()
        if dt > 0:
            time.sleep(dt)
        else:
            self._next = time.monotonic()          # overrun: do not try to catch up

    def close(self) -> None:
        try:
            self.bus.sync_write("Torque_Enable", self.map.ids, np.zeros(self.m.n, int))
        finally:
            self.bus.close()
