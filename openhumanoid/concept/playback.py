"""Play a reference motion in MuJoCo with contacts, closing the loop through the servo model.

Per sim step (dt = spec sim.timestep_s, 2 ms): reference -> latency/rate-limit/P-law (ServoBank) -> motor torque ->
MuJoCo `motor` actuator; BAM friction written to dof_frictionloss/damping; battery sag from the summed servo draw;
first-order thermal state per servo.

The base is free. A bounded "assist" wrench pulls the pelvis towards the reference pose (limited to a few percent of body
weight), like a light safety tether: it keeps an open-loop gait from drifting while the legs still carry the load.
The assist usage is logged; a gait that needs more than a few percent is not dynamically consistent and the report says so.
`mode="ideal"` swaps the servo for a stiff torque-source PD with no limits: that run gives the *demand* of the motion.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..actuators import ServoBank, ThermalBank
from .kin import Reference, RobotKin, catmull
from .power import Pack, compute_power_w, regulator_efficiency
from .robot import Robot

G = 9.81
GRIPPER_TORQUE_FRAC = 0.15   # gripper servos run with a reduced torque limit (LeRobot's SO-100 setup limits the gripper too)


class IdealBank:
    """Stiff torque-source PD with the ServoBank interface (no voltage, cap, latency or friction)."""

    def __init__(self, specs, dt, torque_frac=None, kp=300.0, kd=6.0):
        self.n, self.dt = len(specs), dt
        tf = np.ones(self.n) if torque_frac is None else np.asarray(torque_frac, float)
        self.cap = np.where(tf < 1, np.array([x.stall_nm_ref for x in specs]) * tf, 1e3)
        self.kp, self.kd = kp, kd
        self.vin = np.array([s.vin_ref for s in specs], float)
        self.kt_cur = np.array([s.kt_current for s in specs])
        self.R_heat = np.array([s.R_heat for s in specs])
        self.tau_m = np.zeros(self.n)
        self.duty = np.zeros(self.n)

    def reset(self, theta0):
        pass

    def set_supply(self, vin):
        pass

    def control(self, theta_cmd, theta, omega):
        self.tau_m = np.clip(self.kp * (theta_cmd - theta) - self.kd * omega, -self.cap, self.cap)
        return self.tau_m

    def frictions(self, tau_m, tau_ext, omega):
        z = np.zeros(self.n)
        return z, z

    def current(self, tau_m):
        return np.abs(tau_m) / self.kt_cur

    def heat_w(self, tau_m, fp):
        return self.current(tau_m) ** 2 * self.R_heat

    def battery_w(self, tau_m, omega):
        return np.maximum(self.current(tau_m) ** 2 * self.R_heat + tau_m * omega, 0.0)


@dataclass
class PlayConfig:
    mode: str = "servo"             # servo | ideal
    sim_dt: float = 0.002
    log_every: int = 5              # log at 100 Hz
    warmup_s: float = 0.4
    assist_frac: float = 0.06       # max assist force as a fraction of body weight
    assist_free: bool = False       # True: no assist at all (does the open-loop gait stand by itself?)
    extra_latency_s: float = 0.0
    backlash_rad: float | None = None
    kp_scale: float = 1.0
    pack: Pack | None = None
    ambient_c: float = 35.0
    t0_c: float | None = None
    compute_w: float = 0.0
    regulator_eff: float = 0.9
    lead_s: float = 0.0             # command lead (q_ref + lead*dq_ref): firmware-lag compensation
    servo_scale: dict | None = None  # Monte Carlo: per-joint arrays {"stall":..,"speed":..,"friction":..,"rth":..}
    hold_end_s: float = 0.0
    fall_tilt_deg: float = 45.0
    model_hook: object = None          # callable(MjModel) applied after the model is built (COM shift, floor friction)
    cmd_offset: tuple | None = None   # (t_log, offsets[T, n]) learned by `learn_offsets` (stand-in for policy feedforward)


@dataclass
class Log:
    name: str
    t: np.ndarray
    q: np.ndarray
    dq: np.ndarray
    q_ref: np.ndarray
    tau: np.ndarray            # motor torque, servo domain
    omega: np.ndarray          # servo-domain speed
    current: np.ndarray
    p_batt: np.ndarray         # per-servo battery power
    p_heat: np.ndarray
    temp: np.ndarray
    vin: np.ndarray
    i_total: np.ndarray
    assist: np.ndarray         # assist force magnitude / weight
    base_z: np.ndarray
    tilt_deg: np.ndarray
    warmup_n: int
    fell: bool
    names: list
    extras: dict = field(default_factory=dict)

    def sl(self):
        return slice(self.warmup_n, None)


def _servo_scales(robot: Robot, cfg: PlayConfig):
    sc = cfg.servo_scale or {}
    return {k: np.broadcast_to(np.asarray(v, float), (len(robot.names),)) for k, v in sc.items()}


def play(robot: Robot, ref: Reference, cfg: PlayConfig | None = None, kin: RobotKin | None = None, model=None) -> Log:
    import mujoco
    cfg = cfg or PlayConfig()
    extra = ref.scene["xml"] if ref.scene else ""
    model = model or robot.build_model(extra)
    if cfg.model_hook is not None:
        cfg.model_hook(model)
    data = mujoco.MjData(model)
    model.opt.timestep = cfg.sim_dt
    names = robot.names
    n = len(names)
    qadr = np.array([model.joint(x).qposadr[0] for x in names])
    dadr = np.array([model.joint(x).dofadr[0] for x in names])
    aidx = np.array([model.actuator(x).id for x in names])
    ratio = robot.ratio
    eff = robot.eff if robot.eff is not None else np.ones(n)
    specs = [robot.servo[x] for x in names]
    sc = _servo_scales(robot, cfg)
    if sc:
        specs = [s.perturbed(stall=float(sc.get("stall", np.ones(n))[i]), speed=float(sc.get("speed", np.ones(n))[i]),
                             friction=float(sc.get("friction", np.ones(n))[i]), rth=float(sc.get("rth", np.ones(n))[i]),
                             kp=float(cfg.kp_scale)) for i, s in enumerate(specs)]
    elif cfg.kp_scale != 1.0:
        specs = [s.perturbed(kp=cfg.kp_scale) for s in specs]
    dt = cfg.sim_dt
    pack = cfg.pack.copy() if cfg.pack else None
    tfrac = np.array([GRIPPER_TORQUE_FRAC if x.startswith("gripper") else 1.0 for x in names])
    if cfg.mode == "ideal":
        bank = IdealBank(specs, dt, torque_frac=tfrac)
    else:
        bank = ServoBank(specs, dt, extra_latency_s=cfg.extra_latency_s, backlash_rad=cfg.backlash_rad, torque_frac=tfrac)
    thermal = ThermalBank(specs, cfg.ambient_c, cfg.t0_c)

    # ---- reference at sim rate (with a warm-up hold in front)
    warm = int(round(cfg.warmup_s / dt))
    hold_end = int(round(cfg.hold_end_s / dt))
    t_end = ref.duration
    n_main = int(round(t_end / dt)) + 1
    t_sim = np.arange(n_main) * dt
    q_ref = catmull(ref.t, ref.q, np.clip(t_sim, 0, t_end))
    p_ref = catmull(ref.t, ref.base_pos, np.clip(t_sim, 0, t_end))
    v_ref = np.gradient(p_ref, dt, axis=0)
    qu_ref = catmull(ref.t, ref.base_quat, np.clip(t_sim, 0, t_end))
    qu_ref /= np.linalg.norm(qu_ref, axis=1, keepdims=True)
    dq_ref = np.gradient(q_ref, dt, axis=0)
    pre = lambda a: np.concatenate([np.repeat(a[:1], warm, 0), a, np.repeat(a[-1:], hold_end, 0)])  # noqa: E731
    q_ref, p_ref, v_ref, qu_ref, dq_ref = map(pre, (q_ref, p_ref, v_ref, qu_ref, dq_ref))
    v_ref[:warm] = 0
    dq_ref[:warm] = 0
    N = len(q_ref)
    off_sim = np.zeros_like(q_ref)
    if cfg.cmd_offset is not None:
        t_off, off = cfg.cmd_offset
        for j in range(n):
            off_sim[warm:warm + n_main, j] = np.interp(t_sim, t_off, off[:, j])

    # ---- initial state
    data.qpos[:3] = p_ref[0] + np.array([0, 0, 0.001])
    data.qpos[3:7] = qu_ref[0]
    data.qpos[qadr] = q_ref[0]
    mujoco.mj_forward(model, data)
    bank.reset(q_ref[0] / ratio)

    pelvis = model.body("pelvis").id
    mass = float(model.body_mass.sum())
    zc = max(float(data.subtree_com[1][2]), 0.05)
    wn, wr = 2 * np.pi * 0.25, 1.5       # very soft tether: 1% of body weight needs ~13 cm of drift
    f_max = cfg.assist_frac * mass * G
    t_max = cfg.assist_frac * mass * G * zc
    fr_rows = None

    pack_i = 0.0
    vin = pack.voltage(0.0) if pack else float(np.mean([s.vin_ref for s in specs]))
    ce = compute_power_w_total = cfg.compute_w / max(cfg.regulator_eff, 0.5)

    L = {k: [] for k in ("t", "q", "dq", "q_ref", "tau", "omega", "cur", "pb", "ph", "T", "vin", "it", "as", "bz", "tilt")}
    fell = False
    log_every = cfg.log_every
    tau_prev = np.zeros(n)
    efc_type_fr = mujoco.mjtConstraint.mjCNSTR_FRICTION_DOF
    for k in range(N):
        q = data.qpos[qadr]
        dq = data.qvel[dadr]
        theta, omega = q / ratio, dq / ratio
        cmd = q_ref[k] + cfg.lead_s * dq_ref[k] + off_sim[k]
        if pack:
            bank.set_supply(vin)
        tau = bank.control(cmd / ratio, theta, omega)
        # joint force from servo torque through the linkage: eta when the motor drives, 1/eta when the load back-drives it
        data.ctrl[aidx] = tau * np.where(tau * omega >= 0, eff, 1.0 / eff) / ratio
        # friction budget from last step's constraint forces (BAM Mujoco controller convention)
        if cfg.mode == "servo":
            fric = np.zeros(model.nv)
            if data.nefc:
                m = data.efc_type == efc_type_fr
                if m.any():
                    np.add.at(fric, data.efc_id[m], data.efc_force[m])
            ext = (-data.qfrc_bias[dadr] + data.qfrc_constraint[dadr] - fric[dadr]) * ratio
            fl, dmp = bank.frictions(data.qfrc_actuator[dadr] * ratio, ext, omega)
            model.dof_frictionloss[dadr] = fl / ratio
            model.dof_damping[dadr] = dmp / ratio ** 2
            fp = np.abs(fl * omega) + dmp * omega ** 2
        else:
            fp = np.zeros(n)
        # assist wrench on the pelvis
        if not cfg.assist_free:
            pos, vel = data.qpos[:3], data.qvel[:3]
            f = wn ** 2 * mass * (p_ref[k] - pos) + 2 * 0.8 * wn * mass * (v_ref[k] - vel)
            fn = np.linalg.norm(f)
            if fn > f_max:
                f *= f_max / fn
            qa = data.qpos[3:7]
            dqr = np.zeros(3)
            mujoco.mju_subQuat(dqr, qu_ref[k], qa)           # rotation (world frame) taking qa to the reference
            w = data.qvel[3:6]
            tq = (wr ** 2) * mass * zc * zc * dqr - 2 * 0.8 * wr * mass * zc * zc * w
            tn = np.linalg.norm(tq)
            if tn > t_max:
                tq *= t_max / tn
            data.xfrc_applied[pelvis, :3] = f
            data.xfrc_applied[pelvis, 3:] = tq
            a_use = min(fn, f_max) / (mass * G)
        else:
            a_use = 0.0
        mujoco.mj_step(model, data)
        if not np.all(np.isfinite(data.qpos)):
            fell = True
            break
        # electrical / thermal bookkeeping
        pb = bank.battery_w(tau, omega)
        ph = bank.heat_w(tau, fp)
        cur_servo = bank.current(tau)
        i_tot = float(pb.sum() / max(vin, 1.0)) + ce / max(vin, 1.0)
        if pack:
            vin = pack.step(i_tot, dt)
            vin = max(vin, 3.0)
        T = thermal.step(ph, dt)
        if k % log_every == 0:
            zq = data.qpos[3:7]
            tilt = np.degrees(2 * np.arccos(np.clip(abs(zq[0]), 0, 1)))
            # tilt from vertical: angle between body z and world z
            upz = 1 - 2 * (zq[1] ** 2 + zq[2] ** 2)
            tilt = float(np.degrees(np.arccos(np.clip(upz, -1, 1))))
            L["t"].append((k - warm) * dt)
            L["q"].append(q.copy()); L["dq"].append(dq.copy()); L["q_ref"].append(q_ref[k].copy())
            L["tau"].append(tau.copy()); L["omega"].append(omega.copy()); L["cur"].append(cur_servo)
            L["pb"].append(pb); L["ph"].append(ph); L["T"].append(T.copy()); L["vin"].append(vin); L["it"].append(i_tot)
            L["as"].append(a_use); L["bz"].append(float(data.qpos[2])); L["tilt"].append(tilt)
            if tilt > cfg.fall_tilt_deg or data.qpos[2] < 0.5 * float(p_ref[:, 2].min()):
                fell = True
                break
    A = {k: np.array(v) for k, v in L.items()}
    wn_log = int(round(warm / log_every))
    extras = {"mass_kg": mass, "pack_soc_end": pack.soc if pack else None,
              "sat_frac": (getattr(bank, "sat_steps", np.zeros(n)) / max(getattr(bank, "steps", 1), 1)).tolist(),
              "protection_trips": getattr(bank, "trips", np.zeros(n, int)).tolist(),
              "assist_mean_bw": float(np.mean(A["as"][wn_log:])) if len(A["as"]) > wn_log else 0.0,
              "assist_peak_bw": float(np.max(A["as"][wn_log:])) if len(A["as"]) > wn_log else 0.0,
              "assist_free": cfg.assist_free}
    if ref.scene and ref.scene.get("object"):
        try:
            extras["object_pos"] = data.body(ref.scene["object"]).xpos.copy()
            extras["object_z_ref"] = ref.scene.get("object_z0")
        except Exception:  # noqa: BLE001
            pass
    return Log(ref.name, A["t"], A["q"], A["dq"], A["q_ref"], A["tau"], A["omega"], A["cur"], A["pb"], A["ph"], A["T"],
               A["vin"], A["it"], A["as"], A["bz"], A["tilt"], wn_log, fell, names, extras)


def learn_offsets(robot: Robot, ref: Reference, cfg: PlayConfig, iters: int = 3, gain: float = 0.9, lag_s: float = 0.025,
                  limit: float = 0.35) -> tuple:
    """Iterative learning of a command offset so the *servo-in-the-loop* motion follows the reference.

    A position-only servo has a steady error proportional to the torque it delivers (stiffness ~24 N*m/rad), so a raw
    replay drifts away from the designed motion. A trained policy learns exactly this feedforward; here a few
    iterations of c += gain * e(t + lag) stand in for it. Residual error after learning is real (saturation, speed
    limit) and is reported as tracking error. Returns (offsets (t_log, T x n), last Log)."""
    n = len(robot.names)
    off = None
    lg = None
    for _ in range(iters + 1):
        c = PlayConfig(**{**cfg.__dict__, "cmd_offset": off})
        lg = play(robot, ref, c)
        if _ == iters:
            break
        sl = lg.sl()
        t = lg.t[sl]
        e = lg.q_ref[sl] - lg.q[sl]
        e_shift = np.stack([np.interp(t + lag_s, t, e[:, j]) for j in range(n)], 1)
        new = (off[1] if off is not None else 0.0) + gain * e_shift
        new = np.clip(new, -limit, limit)
        off = (t, new)
    return off, lg
