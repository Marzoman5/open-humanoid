"""The control loop: HAL -> estimator -> safety monitor -> commands -> behaviours -> safety filter -> HAL, at a fixed rate, with logging and timing.

    rt = Runtime(model, SimHAL(model))      # or Runtime(model, FeetechHAL(...)) on the robot
    rt.startup()                            # stand still, gravity-align the IMU
    rt.client.behaviour("walk"); rt.client.velocity(0.1)
    rt.run(10.0)

`Runtime.step()` is one cycle; `compute_ms` in the log is the time spent in everything except `hal.tick()`/sleep (the number the CPU budget
check reports).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from .clips import ClipStore
from .commands import CommandBus, RobotClient, error, ok
from .control import BehaviourManager, StabiliserConfig
from .estimator import StateEstimator
from .hal.base import Hal
from .locomotion import GaitConfig
from .model import RobotModel
from .safety import Safety, SafetyConfig


@dataclass
class RuntimeConfig:
    gait: GaitConfig = field(default_factory=GaitConfig)
    stab: StabiliserConfig = field(default_factory=StabiliserConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    clip_dir: str | None = None
    log_every: int = 1
    vel_default_ttl: float = 0.5


class Recorder:
    """In-memory log of every cycle (numpy on exit): estimator, command, safety, timing. `save()` writes an npz."""

    def __init__(self):
        self.rows: dict = {}

    def add(self, **kw) -> None:
        for k, v in kw.items():
            self.rows.setdefault(k, []).append(np.asarray(v, float).copy() if not isinstance(v, str) else v)

    def arrays(self) -> dict:
        out = {}
        for k, v in self.rows.items():
            out[k] = np.array(v) if not isinstance(v[0], str) else np.array(v, dtype=object)
        return out

    def save(self, path) -> None:
        a = {k: v for k, v in self.arrays().items() if v.dtype != object}
        np.savez_compressed(path, **a)


class Runtime:
    def __init__(self, model: RobotModel, hal: Hal, cfg: RuntimeConfig | None = None):
        self.m = model
        self.hal = hal
        self.cfg = cfg or RuntimeConfig()
        self.dt = 1.0 / hal.control_hz
        self.est = StateEstimator(model, self.dt)
        self.safety = Safety(model, self.cfg.safety, self.dt)
        hw = getattr(hal, "estop_pressed", None)
        if hw:
            self.safety.hw_estop = hw
        self.clips = ClipStore(model, self.cfg.clip_dir)
        self.mgr = BehaviourManager(model, self.dt, self.cfg.gait, self.cfg.stab, clip_provider=self.clips)
        self.bus = CommandBus()
        self.client = RobotClient(self.bus)
        self.rec = Recorder()
        self.k = 0
        self.vel_expiry = 0.0
        self.last_est = None
        self.last_state = None
        self.compute_ms: list = []
        self.hal_ms: list = []
        self.hold_after_override = False
        self.started = False

    # ------------------------------------------------------------------ lifecycle
    def startup(self, settle_s: float = 0.4) -> None:
        """Hold the current posture, collect still IMU samples, gravity-align the attitude and zero the gyro bias."""
        m = self.m
        s = self.hal.read()
        from .hal.base import JointCmd
        samples = []
        n = max(int(settle_s / self.dt), 5)
        for i in range(n):
            self.hal.write(JointCmd.hold(s.q))
            self.hal.tick()
            s = self.hal.read()
            if i >= n // 3:
                samples.append(s.imu)
        self.est.initialise(s, samples)
        self.safety.last_q = s.q.copy()
        self.mgr.q_out = s.q.copy()
        self.started = True

    # ------------------------------------------------------------------ commands
    def _apply(self, msg: dict, est) -> None:
        cmd = msg["cmd"]
        mgr, sf = self.mgr, self.safety
        now = self.last_state.t if self.last_state else 0.0
        if cmd == "estop":
            sf.estop(msg.get("reason", "command"))
        elif cmd == "reset_estop":
            sf.reset_estop(est)
        elif cmd == "enable":
            sf.enable()
        elif sf.estopped or sf.state in ("estop", "limp", "fall", "crouch"):
            return                                                # locomotion/behaviour commands are ignored while the safety layer owns the robot
        elif cmd == "velocity":
            if sf.warn_batt and (abs(msg.get("vx", 0)) + abs(msg.get("vy", 0)) + abs(msg.get("wz", 0)) > 0):
                return                                            # low battery: no new locomotion
            if mgr.behaviour != "walk" and mgr.player is None:
                mgr.start("walk", {}, est)
            mgr.set_velocity(float(msg.get("vx", 0)), float(msg.get("vy", 0)), float(msg.get("wz", 0)))
            self.vel_expiry = now + float(msg.get("ttl", self.cfg.vel_default_ttl))
        elif cmd == "behaviour":
            if sf.warn_batt and msg["name"] in ("walk", "dance", "pickup"):
                return
            ok_, why = mgr.start(msg["name"], msg.get("params"), est)
            self.rec_event("behaviour", f"{msg['name']}: {why}")
        elif cmd == "stop":
            mgr.stop(msg.get("name"))
            if msg.get("name") in (None, "look_at"):
                mgr.look_at(None)
        elif cmd == "pose":
            mgr.set_pose(msg["joints"])
        elif cmd == "look_at":
            t = msg.get("target")
            mgr.look_at(None if t is None else np.array(t, float))

    def rec_event(self, kind: str, detail: str) -> None:
        self.safety._log(self.last_state.t if self.last_state else 0.0, kind, detail)

    # ------------------------------------------------------------------ one cycle
    def step(self) -> dict:
        t0 = time.perf_counter()
        hal, mgr, sf = self.hal, self.mgr, self.safety
        s = hal.read()
        t_read = time.perf_counter()
        est = self.est.update(s, mgr.contact)
        self.last_state, self.last_est = s, est
        sf.heartbeat()
        for p in self.bus.drain():
            self._apply(p.msg, est)
        # dead-man: velocity commands expire
        if mgr.behaviour == "walk" and s.t > self.vel_expiry and np.linalg.norm(mgr.cmd_vel) > 0:
            mgr.set_velocity(0, 0, 0)
        sf.monitor(s, est)
        # safety owns the robot in these modes
        if sf.state == "fall":
            mgr.enter("fall", est)
        elif sf.override == "crouch" and mgr.mode not in ("crouch", "limp"):
            mgr.enter("crouch", est)
        if mgr.mode == "crouch" and mgr.player is not None and mgr.player.done:
            sf.state = "limp"
            sf.limp_latched = True
            sf._log(s.t, "crouched", "controlled lowering finished: torque off")
            mgr.mode = "limp"
        q, tl, contact = mgr.update(est, s)
        cmd = sf.filter(q, tl, s, fall_q=mgr.fall_q)
        t_w0 = time.perf_counter()
        hal.write(cmd)
        t1 = time.perf_counter()
        # compute = everything but the HAL calls (on hardware those are bus transfers, not CPU work; the sim's own cost is not the robot's)
        compute = (t_w0 - t_read)
        self.compute_ms.append(compute * 1e3)
        self.hal_ms.append(((t_read - t0) + (t1 - t_w0)) * 1e3)
        if self.k % self.cfg.log_every == 0:
            self.rec.add(t=s.t, q=s.q, q_cmd=cmd.q, tilt=est.tilt, pitch=est.pitch, roll=est.roll, c=est.c, v=est.v, dcm=est.dcm,
                         temp=s.temp_c, volt=s.voltage, load=s.load, compute_ms=compute * 1e3,
                         stab=mgr.stab.last, gait_mode=0 if mgr.gait.mode == "hold" else (1 if mgr.gait.mode == "shift" else 2))
        hal.tick()
        self.k += 1
        if self.k % 5 == 0:
            self.bus.set_status(self.status())
        return {"t": s.t}

    def run(self, seconds: float, callback=None, stop_when=None) -> float:
        n = int(round(seconds / self.dt))
        for i in range(n):
            self.step()
            if callback:
                callback(self)
            if stop_when and stop_when(self):
                break
        return self.hal.read().t if hasattr(self.hal, "read") else 0.0

    # ------------------------------------------------------------------ reporting
    def status(self) -> dict:
        s, e = self.last_state, self.last_est
        if s is None:
            return {}
        return {"t": round(s.t, 3), "safety": self.safety.status(), "behaviour": self.mgr.status(),
                "tilt_deg": round(math.degrees(e.tilt), 2), "battery_v": round(s.voltage, 2),
                "max_temp_c": float(s.temp_c.max()), "hottest": self.m.names[int(np.argmax(s.temp_c))],
                "load_max": round(float(np.abs(s.load).max()), 2), "events": [(round(x.t, 2), x.kind, x.detail) for x in self.safety.events[-5:]]}

    def timing(self) -> dict:
        a = np.array(self.compute_ms[5:]) if len(self.compute_ms) > 10 else np.array(self.compute_ms or [0.0])
        return {"cycles": len(a), "mean_ms": float(a.mean()), "p50_ms": float(np.percentile(a, 50)), "p99_ms": float(np.percentile(a, 99)),
                "max_ms": float(a.max()), "period_ms": self.dt * 1e3, "load_frac_mean": float(a.mean() / (self.dt * 1e3))}
