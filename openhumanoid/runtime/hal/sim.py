"""SimHAL: MuJoCo plus the measured servo model, behind the same interface as the real servo bus.

What is simulated (and where it comes from):

* **Physics:** the concept robot's MJCF (`Robot.build_model`), free base, contacts, 2 ms steps.
* **Servos:** `openhumanoid.actuators.ServoBank` per joint: BAM-identified firmware control law (kp, rate limit, 4.9 ms command
  delay), DC torque-speed with the datasheet stall cap, load-dependent friction, backlash, armature, and the firmware overload
  protection state machine (Overload_Torque / Protection_Time / Protective_Torque). `ThermalBank` gives the temperature.
* **Register semantics:** goal position (quantised to 4096 counts per servo revolution), torque limit (fraction of stall),
  torque enable, P-coefficient scale; read-back of position / speed / load / current / temperature (integer C) / voltage (0.1 V).
  Firmware thermal shutdown at the servo's `max_temp_c` (latched until it cools by 10 C).
* **Battery:** `concept.power.Pack` (open-circuit curve, internal resistance, sag) fed by the summed servo draw plus the compute load.
* **IMU:** the model's gyro and accelerometer on the pelvis, with white noise, a slowly drifting gyro bias and a fixed latency.

Not simulated (flagged): bus errors and dropped packets, servo-to-servo calibration offsets, cable drag, foot compliance beyond
MuJoCo's soft contact, the Pi's real scheduling jitter. Ground truth (`ground_truth()`) exists for scoring and tests only; the
runtime never reads it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ...actuators import ServoBank, ThermalBank
from ...concept.playback import GRIPPER_TORQUE_FRAC
from ...concept.power import Pack, pack_from_catalog
from ..model import RobotModel
from .base import Hal, HalState, ImuSample, JointCmd

COUNTS_PER_REV = 4096          # STS3215 position resolution


@dataclass
class SimConfig:
    control_hz: float = 100.0
    sim_dt: float = 0.002
    bus_latency_s: float = 0.003          # extra command latency on top of the BAM-identified 4.9 ms (sync_write over a 1 Mbit bus)
    quantize: bool = True
    ambient_c: float = 25.0
    pack_id: str | None = None            # default: the concept's own pack
    soc: float = 1.0
    compute_w: float = 5.0                # Pi 5 + camera + IMU on the 5 V rail (the regulator efficiency is applied below)
    regulator_eff: float = 0.9
    gyro_noise: float = 0.004             # rad/s per sample (BNO085-class)
    gyro_bias_walk: float = 2e-5          # rad/s per sqrt(s)
    acc_noise: float = 0.06               # m/s^2 per sample
    imu_latency_s: float = 0.006
    speed_noise: float = 0.03             # rad/s on the servo speed register
    fw_min_voltage_v: float = 5.0         # servo firmware under-voltage alarm (assumed; verify on the bench)
    seed: int = 0
    floor_friction: float | None = None


class SimHAL(Hal):
    def __init__(self, model: RobotModel, cfg: SimConfig | None = None, q0: np.ndarray | None = None):
        import mujoco
        self.mj = mujoco
        self.m = model
        self.cfg = cfg or SimConfig()
        c = self.cfg
        self.names = model.names
        self.control_hz = c.control_hz
        self.rng = np.random.default_rng(c.seed)
        self.mjm = model.robot.build_model()
        self.mjm.opt.timestep = c.sim_dt
        if c.floor_friction is not None:
            self.mjm.geom_friction[self.mjm.geom("floor").id, 0] = c.floor_friction
        self.data = mujoco.MjData(self.mjm)
        n = model.n
        self.n = n
        self.qadr = np.array([self.mjm.joint(x).qposadr[0] for x in self.names])
        self.dadr = np.array([self.mjm.joint(x).dofadr[0] for x in self.names])
        self.aidx = np.array([self.mjm.actuator(x).id for x in self.names])
        self.ratio = model.ratio
        self.eff = model.robot.eff if model.robot.eff is not None else np.ones(n)
        self.specs = [model.robot.servo[x] for x in self.names]
        self.tfrac_default = np.array([GRIPPER_TORQUE_FRAC if x.startswith("gripper") else 1.0 for x in self.names])
        self.bank = ServoBank(self.specs, c.sim_dt, extra_latency_s=c.bus_latency_s, torque_frac=self.tfrac_default)
        self.thermal = ThermalBank(self.specs, c.ambient_c)
        self.limit_c = np.array([s.max_temp_c for s in self.specs])
        pid = c.pack_id or model.robot.concept.get("power", {}).get("pack", "lipo-3s-1300-tattu")
        self.pack: Pack = pack_from_catalog(pid, soc=c.soc)
        self.vin = self.pack.voltage(0.0)
        self.substeps = int(round(1.0 / (c.control_hz * c.sim_dt)))
        self.sub_dt = c.sim_dt
        self.mass = float(self.mjm.body_mass.sum())
        # command state (register image)
        q0 = model.stand_q() if q0 is None else np.asarray(q0, float)
        self.cmd = JointCmd.hold(q0)
        self.kp_scale = np.ones(n)
        self.base_gain = self.bank.gain.copy()
        self.fault = np.zeros(n, bool)
        self.i_total = 0.0
        self.t = 0.0
        self._imu_hist: list = []
        self._gyro_bias = self.rng.normal(0, 0.002, 3)
        self._push = None
        self._efc_fr = mujoco.mjtConstraint.mjCNSTR_FRICTION_DOF
        self._pelvis = self.mjm.body("pelvis").id
        self._torso = self.mjm.body("torso").id
        self._foot_gid = {self.mjm.geom("foot_l").id: "l", self.mjm.geom("foot_r").id: "r"}
        self._last_tau = np.zeros(n)
        self._last_duty = np.zeros(n)
        self._cur = np.zeros(n)
        self.reset(q0)

    # ------------------------------------------------------------------ setup / sim-only controls
    def reset(self, q0: np.ndarray, base_pos=None, base_quat=None) -> None:
        """Place the robot in the pose `q0` standing on its feet (the pelvis height comes from the feet at the floor)."""
        mj, d = self.mj, self.data
        mj.mj_resetData(self.mjm, d)
        d.qpos[self.qadr] = q0
        d.qpos[3:7] = [1, 0, 0, 0] if base_quat is None else base_quat
        d.qpos[0:3] = [0, 0, 0.5] if base_pos is None else base_pos
        mj.mj_forward(self.mjm, d)
        if base_pos is None:                                # lower to the floor: lowest foot point at z = 0.001
            zs = self._lowest_foot_point()
            d.qpos[2] += 0.001 - zs
        mj.mj_forward(self.mjm, d)
        self.bank.reset(np.asarray(q0) / self.ratio)
        self.thermal.T[:] = self.cfg.ambient_c
        self.cmd = JointCmd.hold(np.asarray(q0, float))
        self.bank.torque_frac = self.tfrac_default.copy()
        self.fault[:] = False
        self.t = 0.0
        self._imu_hist = []
        self._record_imu()

    def _lowest_foot_point(self) -> float:
        # sole plane of the foot box in world frame
        mj, d, m = self.mj, self.data, self.mjm
        zmin = 1e9
        for g in self._foot_gid:
            R = d.geom_xmat[g].reshape(3, 3)
            sz = m.geom_size[g]
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz_ in (-1, 1):
                        p = d.geom_xpos[g] + R @ (np.array([sx, sy, sz_]) * sz)
                        zmin = min(zmin, p[2])
        return zmin

    def push(self, impulse_ns, duration_s: float = 0.05, mode: str = "force") -> None:
        """External push, N s as a vector in the world frame (x forward, y left). mode 'force': a constant force over `duration_s` on the
        torso (carries a torque because the torso is above the whole-body COM); mode 'dv': an instantaneous base velocity change J/M (the
        concept engine's convention)."""
        J = np.asarray(impulse_ns, float)
        if mode == "dv":
            self.data.qvel[:3] += J / self.mass
            return
        self._push = [J / duration_s, self.t + duration_s]

    def set_battery_soc(self, soc: float) -> None:
        self.pack.soc = float(soc)

    def set_temperature(self, joint: str, temp_c: float) -> None:
        self.thermal.T[self.names.index(joint)] = temp_c

    # ------------------------------------------------------------------ Hal interface
    def write(self, cmd: JointCmd) -> None:
        self.cmd = JointCmd(np.asarray(cmd.q, float).copy(), np.clip(np.asarray(cmd.torque_limit, float), 0.0, 1.0),
                            np.asarray(cmd.enable, bool).copy(), None if cmd.kp_scale is None else np.asarray(cmd.kp_scale, float).copy())
        if cmd.kp_scale is not None:
            self.bank.gain = self.base_gain * np.clip(cmd.kp_scale, 0.0, 2.0)
        self.bank.torque_frac = self.cmd.torque_limit * self.tfrac_default

    def tick(self) -> None:
        mj, m, d, bank = self.mj, self.mjm, self.data, self.bank
        q_cmd = self.cmd.q / self.ratio
        enable = self.cmd.enable & ~self.fault
        for _ in range(self.substeps):
            q, dq = d.qpos[self.qadr], d.qvel[self.dadr]
            theta, omega = q / self.ratio, dq / self.ratio
            bank.set_supply(self.vin)
            tau = bank.control(q_cmd, theta, omega)
            tau = np.where(enable, tau, 0.0)
            d.ctrl[self.aidx] = tau * np.where(tau * omega >= 0, self.eff, 1.0 / self.eff) / self.ratio
            fric = np.zeros(m.nv)
            if d.nefc:
                mk = d.efc_type == self._efc_fr
                if mk.any():
                    np.add.at(fric, d.efc_id[mk], d.efc_force[mk])
            ext = (-d.qfrc_bias[self.dadr] + d.qfrc_constraint[self.dadr] - fric[self.dadr]) * self.ratio
            fl, dmp = bank.frictions(d.qfrc_actuator[self.dadr] * self.ratio, ext, omega)
            m.dof_frictionloss[self.dadr] = fl / self.ratio
            m.dof_damping[self.dadr] = dmp / self.ratio ** 2
            fp = np.abs(fl * omega) + dmp * omega ** 2
            if self._push is not None:
                if self.t < self._push[1]:
                    d.xfrc_applied[self._torso, :3] = self._push[0]
                else:
                    d.xfrc_applied[self._torso, :3] = 0.0
                    self._push = None
            mj.mj_step(m, d)
            self.t += self.sub_dt
            pb = bank.battery_w(tau, omega)
            ph = bank.heat_w(tau, fp)
            self.i_total = float(pb.sum() / max(self.vin, 1.0)) + self.cfg.compute_w / self.cfg.regulator_eff / max(self.vin, 1.0)
            self.vin = max(self.pack.step(self.i_total, self.sub_dt), 3.0)
            T = self.thermal.step(ph, self.sub_dt)
            self._record_imu()
            self._last_tau, self._last_duty = tau, bank.duty
            self._cur = bank.current(tau)
        self.fault |= T >= self.limit_c
        self.fault &= ~(self.fault & (T < self.limit_c - 10.0))
        if self.vin < self.cfg.fw_min_voltage_v:
            self.fault[:] = True

    def _record_imu(self) -> None:
        sd = self.data.sensordata
        gyro = sd[4:7].copy()
        acc = sd[7:10].copy()
        self._gyro_bias += self.rng.normal(0, self.cfg.gyro_bias_walk * np.sqrt(self.sub_dt), 3)
        self._imu_hist.append((self.t, gyro + self._gyro_bias, acc))
        keep = int(self.cfg.imu_latency_s / self.sub_dt) + 4
        if len(self._imu_hist) > keep:
            del self._imu_hist[:len(self._imu_hist) - keep]

    def read(self) -> HalState:
        c = self.cfg
        d = self.data
        q = d.qpos[self.qadr].copy()
        dq = d.qvel[self.dadr].copy()
        theta = q / self.ratio
        if c.quantize:
            step = 2 * np.pi / COUNTS_PER_REV
            theta = np.round(theta / step) * step
        q = theta * self.ratio + self.m.offset
        dq = dq + self.rng.normal(0, c.speed_noise, self.n) * self.ratio
        tgt = self.t - c.imu_latency_s
        samp = self._imu_hist[0]
        for s in self._imu_hist:
            if s[0] <= tgt:
                samp = s
            else:
                break
        imu = ImuSample(samp[0], samp[1] + self.rng.normal(0, c.gyro_noise, 3), samp[2] + self.rng.normal(0, c.acc_noise, 3))
        volt = round(self.vin, 1) if c.quantize else self.vin
        stall = np.array([s.stall_cap(s.vin_ref) for s in self.specs])
        return HalState(
            t=self.t, q=q, dq=dq, load=np.clip(self._last_duty / np.array([s.pwm_max for s in self.specs]), -1, 1) * np.where(self.cmd.enable & ~self.fault, 1.0, 0.0),
            current=self._cur.copy(), temp_c=np.round(self.thermal.T) if c.quantize else self.thermal.T.copy(), voltage=float(volt),
            torque_on=self.cmd.enable & ~self.fault, protected=self.bank.protected.copy(), fault=self.fault.copy(), imu=imu)

    # ------------------------------------------------------------------ ground truth (tests and scoring only)
    def ground_truth(self) -> dict:
        mj, d, m = self.mj, self.data, self.mjm
        quat = d.qpos[3:7].copy()
        R = d.xmat[self._pelvis].reshape(3, 3)
        up = R[:, 2]
        com = d.subtree_com[1].copy()
        mj.mj_subtreeVel(m, d)
        comv = d.subtree_linvel[1].copy()
        feet = {s: d.site(f"foot_{s}").xpos.copy() for s in "lr"}
        f6 = np.zeros(6)
        force = {"l": 0.0, "r": 0.0}
        for ci in range(d.ncon):
            cn = d.contact[ci]
            side = self._foot_gid.get(int(cn.geom1)) or self._foot_gid.get(int(cn.geom2))
            if side:
                mj.mj_contactForce(m, d, ci, f6)
                force[side] += abs(f6[0])
        return {"t": self.t, "base_pos": d.qpos[:3].copy(), "base_quat": quat, "tilt_deg": float(np.degrees(np.arccos(np.clip(up[2], -1, 1)))),
                "com": com, "com_vel": comv, "feet": feet, "foot_force_n": force, "base_vel": d.qvel[:3].copy(), "pelvis_z": float(d.qpos[2]),
                "pack_soc": self.pack.soc, "temp_c": self.thermal.T.copy(), "vin": self.vin}
