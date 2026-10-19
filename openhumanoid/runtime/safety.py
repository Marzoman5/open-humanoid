"""Safety layer: the last stage before the HAL. Nothing a behaviour, command front end or plugin does can reach the servos except through
`Safety.filter`.

What it enforces, every control tick:

* **Joint limits** (from the concept/spec) with a margin, and a per-tick **rate limit** on every goal position (the servo's own firmware
  rate limit is not a protection: a 3 rad step would still be accepted).
* **Torque / thermal derating and cutoffs:** servo temperature above `temp_derate_c` lowers that joint's torque limit linearly to
  `derate_floor` at `temp_cutoff_c`; at the cutoff the robot is lowered into a crouch and torqued off (an overheated servo is never asked
  to hold the robot up). A servo in firmware overload protection is logged, and several at once start a controlled crouch.
* **Battery:** the filtered loaded cell voltage below `batt_warn_v_cell` raises a warning and refuses new locomotion commands; below
  `batt_cut_v_cell` the robot crouches and torques off before the servos or the Pi brown out.
* **Fall:** tilt beyond `fall_tilt_deg` (or a fast tilt beyond `fall_tilt_fast_deg`) drops to the safe-fall pose: arms and legs tucked,
  torque limited to cut impact current, then torque off once the robot has stopped moving.
* **E-stop:** a latched flag (software command, hardware input via the HAL, or the watchdog). While latched every servo is torqued off and
  every goal position is held at the last measured value. Clearing needs an explicit `reset_estop()` and a stationary robot; no behaviour
  call clears it.
* **Watchdog:** `Safety.heartbeat()` is called by the runtime each cycle; a stalled loop (`max_cycle_s`) latches the e-stop from the
  monitor side (`check_watchdog`, meant for a separate thread or the servo's own timeout on hardware).

States: ok -> warn -> crouch (controlled lowering) -> limp, fall -> limp, estop. `override` tells the behaviour manager which behaviour the
safety layer wants (crouch / fall); the filter itself still clamps whatever arrives.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from .estimator import EstState
from .hal.base import HalState, JointCmd
from .model import RobotModel


@dataclass
class SafetyConfig:
    limit_margin: float = 0.02                 # rad inside the joint limit (m for the gripper: scaled below)
    rate_scale: float = 0.85                   # fraction of the servo's no-load speed allowed as a goal-position rate
    max_rate_rad_s: float = 8.0
    temp_derate_c: float = 55.0
    temp_cutoff_c: float = 65.0                # servo firmware cuts at max_temp_c (70 C): the software cutoff acts first
    derate_floor: float = 0.4
    batt_warn_v_cell: float = 3.55             # loaded cell voltage (filtered)
    batt_cut_v_cell: float = 3.35
    batt_cells: int = 3
    batt_tau_s: float = 1.0
    fall_tilt_deg: float = 32.0
    fall_tilt_fast_deg: float = 18.0
    fall_tilt_rate: float = 2.0                # rad/s
    protect_joints_for_crouch: int = 3         # this many servos in firmware overload protection -> controlled crouch
    fall_torque: float = 0.45                  # torque fraction in the safe-fall pose
    still_gyro: float = 0.35                   # rad/s: "stopped moving"
    still_time_s: float = 1.0
    max_cycle_s: float = 0.08


@dataclass
class SafetyEvent:
    t: float
    kind: str
    detail: str


class Safety:
    def __init__(self, model: RobotModel, cfg: SafetyConfig | None = None, dt: float = 0.01):
        self.m = model
        self.cfg = cfg or SafetyConfig()
        self.dt = dt
        n = model.n
        c = self.cfg
        pad = np.where(np.array([nm.startswith("gripper") for nm in model.names]), 0.001, c.limit_margin)
        self.lo = model.lo + pad
        self.hi = model.hi - pad
        noload = np.array([model.robot.servo[nm].noload_rad_s_ref for nm in model.names]) * model.ratio
        self.rate = np.minimum(c.rate_scale * noload, c.max_rate_rad_s * np.where(model.ratio != 1.0, model.ratio, 1.0))
        self.max_temp = np.array([model.robot.servo[nm].max_temp_c for nm in model.names])
        self._estop = threading.Event()
        self._estop_reason = ""
        self.state = "ok"
        self.events: list = []
        self.last_q = None
        self.v_batt = None
        self.t = 0.0
        self.override: str | None = None            # None | "crouch" | "fall" | "limp"
        self.reasons: set = set()
        self.warn_batt = False
        self.still_t = 0.0
        self.torque_derate = np.ones(n)
        self.limp_latched = False
        self._last_beat = time.monotonic()
        self.hw_estop = lambda: False               # replaced by the HAL's hardware input where one exists
        self.fall_count = 0
        self._tilt_hist: list = []

    # ------------------------------------------------------------------ e-stop (thread safe)
    def estop(self, reason: str = "command") -> None:
        if not self._estop.is_set():
            self._estop_reason = reason
            self._log(self.t, "estop", reason)
        self._estop.set()

    @property
    def estopped(self) -> bool:
        return self._estop.is_set()

    def reset_estop(self, est: EstState | None = None) -> bool:
        """Clear a latched e-stop. Refused while the hardware input is asserted or the robot is moving/tilted."""
        if self.hw_estop():
            return False
        if est is not None and (est.tilt > math.radians(20) or float(np.linalg.norm(est.gyro)) > 1.0):
            return False
        self._estop.clear()
        self.state = "limp"
        self.limp_latched = True                    # comes back limp: the operator must re-enable (command `enable`)
        self._log(self.t, "estop_cleared", "")
        return True

    def enable(self) -> bool:
        if self.estopped or self.state in ("fall",):
            return False
        if self.reasons - {"batt_warn"}:
            return False
        self.limp_latched = False
        self.override = None
        self.state = "ok"
        return True

    def heartbeat(self) -> None:
        self._last_beat = time.monotonic()

    def check_watchdog(self) -> bool:
        if time.monotonic() - self._last_beat > self.cfg.max_cycle_s * 25:
            self.estop("watchdog: control loop stalled")
            return True
        return False

    # ------------------------------------------------------------------ helpers
    def _log(self, t: float, kind: str, detail: str) -> None:
        self.events.append(SafetyEvent(float(t), kind, detail))

    def _raise(self, key: str, t: float, detail: str) -> bool:
        if key in self.reasons:
            return False
        self.reasons.add(key)
        self._log(t, key, detail)
        return True

    # ------------------------------------------------------------------ the monitor (before the behaviours run)
    def monitor(self, s: HalState, est: EstState) -> None:
        c = self.cfg
        self.t = s.t
        if self.hw_estop():
            self.estop("hardware e-stop input")
        # battery: low-pass the loaded voltage
        if self.v_batt is None:
            self.v_batt = s.voltage
        a = 1 - math.exp(-self.dt / c.batt_tau_s)
        self.v_batt += a * (s.voltage - self.v_batt)
        vc = self.v_batt / c.batt_cells
        self.warn_batt = vc < c.batt_warn_v_cell
        if self.warn_batt:
            self._raise("batt_warn", s.t, f"cell {vc:.2f} V")
        if vc < c.batt_cut_v_cell and self.state in ("ok", "warn"):
            if self._raise("batt_cut", s.t, f"cell {vc:.2f} V below {c.batt_cut_v_cell}"):
                self.override = "crouch"
                self.state = "crouch"
        # temperature: derate then cut
        T = s.temp_c
        frac = np.clip((T - c.temp_derate_c) / max(c.temp_cutoff_c - c.temp_derate_c, 1e-6), 0, 1)
        self.torque_derate = 1.0 - (1.0 - c.derate_floor) * frac
        hot = np.where(T >= c.temp_cutoff_c)[0]
        if len(hot) and self.state in ("ok", "warn"):
            if self._raise("overheat", s.t, f"{self.m.names[hot[0]]} at {T[hot[0]]:.0f} C"):
                self.override = "crouch"
                self.state = "crouch"
        elif (T > c.temp_derate_c).any():
            self._raise("temp_warn", s.t, f"{self.m.names[int(np.argmax(T))]} at {T.max():.0f} C")
        # firmware overload protection on many servos
        if int(s.protected.sum()) >= c.protect_joints_for_crouch and self.state in ("ok", "warn"):
            if self._raise("overload", s.t, f"{int(s.protected.sum())} servos in overload protection"):
                self.override = "crouch"
                self.state = "crouch"
        if bool(s.fault.any()) and self.state in ("ok", "warn", "crouch"):
            self._raise("servo_fault", s.t, f"firmware alarm on {[self.m.names[i] for i in np.where(s.fault)[0][:3]]}")
        # fall detection
        tilt_deg = math.degrees(est.tilt)
        fast = tilt_deg > c.fall_tilt_fast_deg and est.tilt_rate > c.fall_tilt_rate
        if self.state not in ("fall", "limp", "estop") and (tilt_deg > c.fall_tilt_deg or fast):
            self.state = "fall"
            self.override = "fall"
            self.fall_count += 1
            self._raise("fall", s.t, f"tilt {tilt_deg:.0f} deg")
        if self.state == "fall":
            moving = float(np.linalg.norm(est.gyro)) > c.still_gyro
            self.still_t = 0.0 if moving else self.still_t + self.dt
            if self.still_t >= c.still_time_s:
                self.state = "limp"
                self.limp_latched = True
                self._log(s.t, "fallen", "at rest: torque off")
        if self.estopped:
            self.state = "estop"

    # ------------------------------------------------------------------ the filter (after the behaviours)
    def filter(self, target_q: np.ndarray, torque_limit: np.ndarray | None, s: HalState, safe_pose: np.ndarray | None = None,
               fall_q: np.ndarray | None = None) -> JointCmd:
        """Return the only command that is allowed to reach the HAL."""
        n = self.m.n
        c = self.cfg
        q_meas = s.q
        if self.last_q is None:
            self.last_q = q_meas.copy()
        tl = np.ones(n) if torque_limit is None else np.clip(np.asarray(torque_limit, float), 0.0, 1.0)
        # e-stop and limp: torque off, hold the measured position (so re-enabling does not jump)
        if self.estopped or self.limp_latched or self.state in ("estop", "limp"):
            self.last_q = q_meas.copy()
            return JointCmd(q_meas.copy(), np.zeros(n), np.zeros(n, bool))
        q = np.asarray(target_q, float).copy()
        if not np.isfinite(q).all():                                    # NaN guard: hold the last safe command
            self._raise("bad_command", s.t, "non-finite target")
            q = self.last_q.copy()
        if self.state == "fall" and fall_q is not None:
            q = np.asarray(fall_q, float).copy()
            tl = np.minimum(tl, c.fall_torque)
        q = np.clip(q, self.lo, self.hi)
        rate = self.rate * (2.5 if self.state == "fall" else 1.0)
        step = rate * self.dt
        q = np.clip(q, self.last_q - step, self.last_q + step)
        self.last_q = q.copy()
        tl = tl * self.torque_derate
        return JointCmd(q, tl, np.ones(n, bool))

    # ------------------------------------------------------------------ status
    def status(self) -> dict:
        return {"state": self.state, "estop": self.estopped, "estop_reason": self._estop_reason if self.estopped else "",
                "reasons": sorted(self.reasons), "battery_v": None if self.v_batt is None else round(self.v_batt, 2),
                "battery_warn": self.warn_batt, "falls": self.fall_count}
