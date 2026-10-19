"""BAM-style serial-bus servo model (position-servo control law, back-EMF torque-speed, load-dependent friction,
armature, latency) plus a thermal model. Vectorised over joints; torques in the SERVO domain (N*m at the output
shaft, radians). Joints that are not rotary (the gripper's slide) are converted by the caller with `ratio`.

Derived from the published Rhoban BAM work (Apache-2.0, https://github.com/Rhoban/bam, commit e9a619d, paper
Duclusaud et al., arXiv:2410.08650): the firmware control law (bam/feetech/actuator.py), the DC-motor torque equation
(bam/actuator.py) and the friction budget models M1-M6 (bam/model.py). This is a re-implementation (vectorised, with a
stall cap, latency ring buffer, backlash play operator and thermal state), not a copy. Constants and their sources are
in data/servo_models.yaml; the BAM parameter files are verbatim copies in data/ (see THIRD_PARTY.md).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from .. import catalog

_DATA = Path(__file__).resolve().parent / "data"
KGCM = 0.0980665
_FRICTION_TORQUE_KEYS = frozenset({"friction_base", "friction_stribeck", "friction_viscous"})
IDLE_CURRENT_A = 0.03     # assumed per-servo standby draw (logic + holding electronics); no source found, see docs


@lru_cache(maxsize=None)
def _models_yaml() -> dict:
    return yaml.safe_load((_DATA / "servo_models.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def bam_params(file_name: str) -> dict:
    return json.loads((_DATA / file_name).read_text(encoding="utf-8"))


def bam_models_available() -> list[str]:
    return sorted(p.stem.split("_")[-1] for p in _DATA.glob("bam_feetech_sts3215_7_4V_m*.json"))


@dataclass(frozen=True)
class ServoSpec:
    """Resolved constants of one actuator type. Immutable; `perturbed()` returns a modified copy (Monte Carlo)."""
    key: str
    label: str
    quality: str                 # measured_7v4 | extrapolated_12v | datasheet_only | generic_datasheet
    quality_score: float
    vin_ref: float               # volts the stall/no-load figures belong to
    voltage_rating_v: tuple
    kt: float                    # back-EMF constant [V/(rad/s)] = DC torque constant [N*m/A] (BAM convention)
    R_dc: float                  # [ohm]
    pwm_max: float
    kp_fw: float
    error_gain: float
    error_gain_ratio: float
    delay_s: float
    rate_limit_rad_s: float      # firmware limit on how fast its internal target moves
    armature: float              # [kg m^2] reflected at the output
    friction: dict               # BAM friction parameters (+ "model": "m4")
    stall_nm_ref: float          # datasheet stall at vin_ref (the conservative reference)
    stall_current_a: float
    rated_continuous_nm: float
    noload_rad_s_ref: float
    mass_kg: float
    rth_k_per_w: float
    tau_th_s: float
    uncertainty: dict
    max_temp_c: float = 70.0
    backlash_rad: float = 0.0087  # +-0.5 deg: datasheet <=0.5 deg; Robonine measured 0.87 deg on one 12 V unit
    notes: tuple = field(default_factory=tuple)

    # ---- derived capability (all at a supply voltage `vin`) -----------------------------------------------------
    @property
    def kt_current(self) -> float:
        """N*m of output torque per ampere of motor current (datasheet stall torque / stall current)."""
        return self.stall_nm_ref / self.stall_current_a

    @property
    def R_heat(self) -> float:
        return self.vin_ref / self.stall_current_a

    def stall_cap(self, vin) -> np.ndarray | float:
        """Usable (conservative) stall torque at supply `vin`: the datasheet figure scaled linearly with voltage."""
        return self.stall_nm_ref * np.asarray(vin) / self.vin_ref

    def stall_electrical(self, vin) -> np.ndarray | float:
        """DC-law stall torque at `vin` (kt*V*pwm/R). With BAM's 7.4 V fit this is ~2x the datasheet stall."""
        return self.kt * np.asarray(vin) * self.pwm_max / self.R_dc

    def noload(self, vin) -> np.ndarray | float:
        return np.asarray(vin) * self.pwm_max / self.kt

    def tau_available(self, w, vin, *, optimistic: bool = False):
        """Maximum motor torque at output speed `w` (rad/s, same direction as torque). Conservative = capped at the datasheet stall."""
        w = np.abs(np.asarray(w, dtype=float))
        vin = np.asarray(vin, dtype=float)
        dc = self.kt * (vin * self.pwm_max - self.kt * w) / self.R_dc
        cap = self.stall_electrical(vin) if optimistic else self.stall_cap(vin)
        return np.clip(np.minimum(dc, cap), 0.0, None)

    def perturbed(self, *, stall: float = 1.0, speed: float = 1.0, friction: float = 1.0, rth: float = 1.0,
                  kp: float = 1.0) -> "ServoSpec":
        """Scaled copy for Monte Carlo draws. `speed` scales the no-load speed (kt and R move together, so the DC stall
        stays put); `stall` scales the usable stall cap; `friction` the friction terms; `kp` the firmware error gain."""
        fr = {k: (v * friction if k in _FRICTION_TORQUE_KEYS else v) for k, v in self.friction.items()}
        return replace(self, kt=self.kt / speed, R_dc=self.R_dc / speed, stall_nm_ref=self.stall_nm_ref * stall,
                       friction=fr, rth_k_per_w=self.rth_k_per_w * rth, error_gain_ratio=self.error_gain_ratio * kp)


def _resolve(entry: dict, key: str, vin_op: float | None, variant: str | None) -> ServoSpec:
    fw = _models_yaml()["BAM_SOURCE"]["firmware"]
    dyn_file = entry.get("bam_file") or entry["dynamics_from"]
    bam = bam_params(dyn_file)
    dc = dict(entry["dc"])
    stall = entry["stall_nm"]["v"]
    stall_i = entry["stall_current_a"]["v"]
    vin_ref = entry["vin_ref"]
    noload = entry["noload_rad_s"]["v"]
    notes = []
    label = entry["label"]
    quality, qscore = entry["quality"], entry["quality_score"]
    if variant and variant != "default":
        alt = entry.get("alt_model")
        if not alt or alt["name"] != variant:
            raise KeyError(f"actuator '{key}' has no model variant '{variant}'")
        dc, stall = dict(alt["dc"]), alt["stall_nm"]["v"]
        notes.append(f"variant {variant}: {alt['note']}")
        label += f" [{variant}]"
    if dc["mode"] == "bam":
        kt, R = bam["kt"], bam["R"]
        if "vin" in dc:   # BAM 7.4 V motor run at another supply (the 'kt same, R same, V scales' extrapolation)
            vin_ref = dc["vin"]
            noload = vin_ref * fw["pwm_max"] / kt
    else:
        kt = vin_ref * fw["pwm_max"] / noload
        R = vin_ref / stall_i
    scale = entry.get("dynamics_scale", {})
    fr = {k: v for k, v in bam.items() if k not in ("model", "actuator", "kt", "R", "armature", "q_offset", "command_delay",
                                                    "max_velocity", "error_gain_ratio")}
    fr["model"] = "m4" if "m4" in dyn_file else dyn_file.split("_")[-1].split(".")[0]
    for k in _FRICTION_TORQUE_KEYS & set(fr):
        fr[k] = fr[k] * scale.get("torque", 1.0)
    ratio_noload = noload  # rate limit follows BAM's identified/dc ratio (5.07 rad/s vs 5.67 rad/s no-load)
    spec = ServoSpec(
        key=key, label=label, quality=quality, quality_score=qscore, vin_ref=vin_ref,
        voltage_rating_v=tuple(entry["voltage_rating_v"]), kt=kt, R_dc=R, pwm_max=fw["pwm_max"], kp_fw=fw["kp_fw"],
        error_gain=fw["error_gain"], error_gain_ratio=bam["error_gain_ratio"], delay_s=bam["command_delay"],
        rate_limit_rad_s=0.894 * ratio_noload, armature=bam["armature"] * scale.get("armature", 1.0), friction=fr,
        stall_nm_ref=stall, stall_current_a=stall_i, rated_continuous_nm=entry["rated_continuous_nm"]["v"],
        noload_rad_s_ref=noload, mass_kg=entry["mass_kg"]["v"], rth_k_per_w=entry["thermal"]["rth_k_per_w"],
        tau_th_s=entry["thermal"]["tau_s"], uncertainty=dict(entry["uncertainty"]), notes=tuple(notes))
    return spec


def _generic(part: dict) -> ServoSpec:
    """Datasheet-only DC model for any other catalog actuator. Quality is poor on purpose; uncertainty is wide."""
    a = part["actuator"]
    vin_ref = float(np.mean(a["voltage_v"]))
    stall, noload = a["stall_torque_nm"], a["no_load_speed_rad_s"]
    i_stall = max(stall * noload / vin_ref, 0.1)           # ideal DC motor: P_stall = tau_s*w_nl (see docs)
    kt = vin_ref * 0.97 / noload
    return ServoSpec(
        key=part["id"], label=part["name"], quality="generic_datasheet", quality_score=0.15, vin_ref=vin_ref,
        voltage_rating_v=tuple(a["voltage_v"]), kt=kt, R_dc=vin_ref / i_stall, pwm_max=0.97, kp_fw=32, error_gain=0.166,
        error_gain_ratio=1.0, delay_s=0.005, rate_limit_rad_s=0.894 * noload, armature=a.get("armature_kg_m2", 0.01),
        friction={"model": "m1", "friction_base": 0.03 * stall, "friction_viscous": 0.02 * stall / noload},
        stall_nm_ref=stall, stall_current_a=i_stall, rated_continuous_nm=a.get("continuous_torque_nm", 0.33 * stall),
        noload_rad_s_ref=noload, mass_kg=part.get("mass_kg", 0.1), rth_k_per_w=3.0, tau_th_s=300.0,
        uncertainty={"stall": 0.3, "speed": 0.3, "friction": 0.5, "kt": 0.3, "rth": 0.5},
        notes=("generic datasheet model: no identification, current from ideal-DC assumption",))


def servo_spec(part_id: str, variant: str | None = None) -> ServoSpec:
    """Servo constants for a catalog actuator id (optionally an alternate model variant)."""
    models = _models_yaml()["models"]
    if part_id in models:
        return _resolve(models[part_id], part_id, None, variant)
    if variant not in (None, "default"):
        raise KeyError(f"actuator '{part_id}' has no model variant '{variant}'")
    return _generic(catalog.get(part_id))


def known_servo_ids() -> list[str]:
    return list(_models_yaml()["models"])


def bam_source() -> dict:
    return _models_yaml()["BAM_SOURCE"]


# ------------------------------------------------------------------------------------------------ friction
def friction_budget(fr: dict, tau_motor, tau_ext, dtheta):
    """BAM friction budget (frictionloss, damping) for models m1..m6, vectorised (arrays or floats in `fr` values).
    Port of bam/model.py Model.compute_frictions (Apache-2.0). tau_ext is the load torque the world applies at the output."""
    model = fr.get("model", "m4")
    load_dep = model in ("m3", "m4", "m5", "m6")
    stribeck = model in ("m2", "m4", "m5", "m6")
    directional = model in ("m5", "m6")
    quadratic = model == "m6"
    tau_motor, tau_ext, dtheta = np.asarray(tau_motor), np.asarray(tau_ext), np.asarray(dtheta)
    if directional:
        gear = np.abs(tau_ext * fr["load_friction_external"] - tau_motor * fr["load_friction_motor"])
        gear_s = np.abs(tau_ext * fr["load_friction_external_stribeck"] - tau_motor * fr["load_friction_motor_stribeck"])
    else:
        gear = np.abs(tau_ext - tau_motor)
        gear_s = gear
    if stribeck:
        coeff = np.exp(-(np.abs(dtheta / fr["dtheta_stribeck"]) ** fr["alpha"]))
    loss = np.full(np.broadcast(tau_motor, tau_ext, dtheta).shape, fr["friction_base"], dtype=float)
    if load_dep:
        loss = loss + (gear if directional else fr["load_friction_base"] * gear)
    if stribeck:
        loss = loss + coeff * fr["friction_stribeck"]
        if load_dep:
            loss = loss + (gear_s * coeff if directional else fr["load_friction_stribeck"] * gear * coeff)
            if quadratic:
                en = np.sign(tau_ext) != np.sign(tau_motor)
                by_motor = np.abs(tau_ext) < np.abs(tau_motor)
                by_ext = np.abs(tau_ext) > np.abs(tau_motor)
                q_m = fr["load_friction_external_quad"] * np.abs(tau_ext) ** 2
                q_e = fr["load_friction_motor_quad"] * np.abs(tau_motor) ** 2
                loss = loss + coeff * (by_motor * q_m + by_ext * q_e) * en
    return loss, np.full_like(loss, fr["friction_viscous"])


# ------------------------------------------------------------------------------------------------ bank
class ServoBank:
    """N servos driven together. All arguments/returns are in the servo domain (rad, rad/s, N*m)."""

    def __init__(self, specs: list[ServoSpec], dt: float, *, extra_latency_s: float = 0.0, backlash_rad=None,
                 torque_frac=None):
        self.specs = specs
        self.n = len(specs)
        self.dt = dt
        f = lambda attr: np.array([getattr(s, attr) for s in specs], dtype=float)  # noqa: E731
        self.kt, self.R, self.pwm = f("kt"), f("R_dc"), f("pwm_max")
        self.gain = f("kp_fw") * f("error_gain") * f("error_gain_ratio")
        self.rate = f("rate_limit_rad_s")
        self.stall_ref = f("stall_nm_ref")
        self.vin_ref = f("vin_ref")
        self.kt_cur, self.R_heat = f("kt_current"), f("R_heat")
        self.armature = f("armature")
        self.torque_frac = np.ones(self.n) if torque_frac is None else np.asarray(torque_frac, dtype=float)
        self.backlash = np.array([s.backlash_rad for s in specs]) if backlash_rad is None else np.broadcast_to(np.asarray(backlash_rad, float), (self.n,)).copy()
        self.delay_steps = (f("delay_s") + extra_latency_s) / dt
        self.fr_keys = sorted({k for s in specs for k in s.friction if k != "model"})
        self.fr = {k: np.array([s.friction.get(k, 0.0) for s in specs], dtype=float) for k in self.fr_keys}
        models = {s.friction.get("model", "m4") for s in specs}
        if len(models) != 1:
            raise ValueError(f"mixed friction models {models} in one bank are not supported")
        self.fr["model"] = models.pop()
        self._hist_len = int(np.ceil(self.delay_steps.max())) + 3
        self.vin = np.array([s.vin_ref for s in specs], dtype=float)
        self.reset(np.zeros(self.n))

    def reset(self, theta0):
        theta0 = np.asarray(theta0, dtype=float)
        self.hist = np.tile(theta0, (self._hist_len, 1))      # ring buffer of commanded targets
        self.head = 0
        self.q_ts = theta0.copy()                              # firmware's rate-limited internal target
        self.play = theta0.copy()                              # backlash play operator state (seen position)
        self.duty = np.zeros(self.n)
        self.tau_m = np.zeros(self.n)

    def _delayed(self, idx: np.ndarray) -> np.ndarray:
        # sample the command history `delay_steps` (fractional) ago
        d = self.delay_steps
        lo = np.floor(d).astype(int)
        w = d - lo
        L = self._hist_len
        a = self.hist[(self.head - lo) % L, np.arange(self.n)]
        b = self.hist[(self.head - lo - 1) % L, np.arange(self.n)]
        return (1 - w) * a + w * b

    def set_supply(self, vin) -> None:
        self.vin = np.broadcast_to(np.asarray(vin, dtype=float), (self.n,)).copy()

    def control(self, theta_cmd, theta, omega):
        """One firmware tick. Returns motor torque [N*m] at the output (clipped to the conservative stall cap)."""
        self.head = (self.head + 1) % self._hist_len
        self.hist[self.head] = theta_cmd
        tgt = self._delayed(None)
        step = self.rate * self.dt
        self.q_ts = np.clip(tgt, self.q_ts - step, self.q_ts + step)
        self.play = np.clip(self.play, theta - self.backlash / 2, theta + self.backlash / 2)
        duty = np.clip((self.q_ts - self.play) * self.gain, -self.pwm, self.pwm)
        volts = self.vin * duty
        tau = self.kt * (volts - self.kt * omega) / self.R
        cap = self.stall_ref * self.vin / self.vin_ref * self.torque_frac
        tau = np.clip(tau, -cap, cap)
        self.duty, self.tau_m = duty, tau
        return tau

    def frictions(self, tau_m, tau_ext, omega):
        return friction_budget(self.fr, tau_m, tau_ext, omega)

    # ---- electrical / thermal bookkeeping (not part of the dynamics) ---------------------------------------
    def current(self, tau_m) -> np.ndarray:
        """Motor current [A] estimated from torque with the datasheet stall-torque/stall-current ratio."""
        return np.abs(tau_m) / self.kt_cur

    def heat_w(self, tau_m, tau_friction_power) -> np.ndarray:
        """Heat dissipated in the servo: copper loss + gearbox friction + standby."""
        i = self.current(tau_m)
        return i * i * self.R_heat + np.abs(tau_friction_power) + IDLE_CURRENT_A * self.vin * 0.5

    def battery_w(self, tau_m, omega) -> np.ndarray:
        """Power drawn from the pack: I^2 R + mechanical power (no energy returned on regen) + standby."""
        i = self.current(tau_m)
        return np.maximum(i * i * self.R_heat + tau_m * omega, 0.0) + IDLE_CURRENT_A * self.vin


class ThermalBank:
    """First-order thermal node per servo: tau dT/dt = Rth*P - (T - T_amb). 70 C is the firmware protection default."""

    def __init__(self, specs: list[ServoSpec], ambient_c: float, t0_c: float | None = None):
        self.rth = np.array([s.rth_k_per_w for s in specs])
        self.tau = np.array([s.tau_th_s for s in specs])
        self.limit = np.array([s.max_temp_c for s in specs])
        self.ambient = ambient_c
        self.T = np.full(len(specs), ambient_c if t0_c is None else t0_c, dtype=float)

    def step(self, p_w, dt: float) -> np.ndarray:
        target = self.ambient + self.rth * p_w
        self.T += (target - self.T) * (1 - np.exp(-dt / self.tau))
        return self.T

    def steady_state(self, p_w) -> np.ndarray:
        return self.ambient + self.rth * np.asarray(p_w)
