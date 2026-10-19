"""Envelopes: per-joint demand (peak, RMS, torque-speed utilisation, overload-protection exposure), the 10-minute
mixed-activity thermal/battery simulation, and the gate evaluation.

DEMAND, NOT DELIVERY (challenge-1 row 7). Envelopes come from `ideal` playback: a stiff torque-source PD with no
voltage, stall cap, latency or tether-free assumption, so the torque it reports is what the *motion* needs (including the
servo's own reflected rotor inertia, which dominates the dynamic load). BAM friction is added on top as a motor-side
cost for moving joints (static friction is NOT credited as free holding torque: conservative). Servo-in-the-loop runs are
used only for tracking error, saturation time and overload trips. A motion whose ideal playback needed more than 1% of
body weight of tether force is INVALID.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import config
from .kin import Reference, RobotKin
from .motions import dance as dance_mod
from .motions import pickup as pickup_mod
from .motions import posture, walk as walk_mod
from .playback import Log, PlayConfig, play
from .power import Pack
from .robot import Robot
from ..actuators import ServoBank, ThermalBank, friction_budget

MOTION_ORDER = ["stand", "walk_forward", "walk_backward", "turn", "squat_90", "squat_120", "wave", "dance", "pickup", "sit_to_stand_130"]


# ------------------------------------------------------------------------------------------------ motion set
def build_motions(kin: RobotKin, *, table_height_m: float | None = None, stress: bool = False,
                  walk_speed_factor: float = 1.0) -> dict[str, Reference]:
    """The frozen motion set (identical for every candidate). Stress variants add the walk stress cases."""
    m = config.motions()
    refs: dict[str, Reference] = {}
    refs["stand"] = posture.stand(kin, 4.0)
    g0 = walk_mod.frozen_gait()
    ov = {"step_len": g0["step_len"] * walk_speed_factor} if walk_speed_factor != 1.0 else {}
    refs["walk_forward"] = walk_mod.walk(kin, "forward", **ov)
    refs["walk_backward"] = walk_mod.walk(kin, "backward", **ov)
    refs["turn"] = walk_mod.walk(kin, "turn")
    for d in m["squat"]["depths_deg"]:
        refs[f"squat_{int(d)}"] = posture.squat(kin, d, down_s=m["squat"]["down_s"], hold_s=m["squat"]["hold_s"])
    refs["wave"] = posture.wave(kin, "r", duration=m["wave"]["duration_s"], freq_hz=m["wave"]["freq_hz"], amp_deg=m["wave"]["amp_deg"])
    dn = m["dance"]
    refs["dance"] = dance_mod.dance(kin, bpm=dn["bpm"], n_phrases=dn["phrases"], v_limit=dn["v_limit_rad_s"],
                                    max_dev_deg=dn["smoother_max_deviation_deg"])
    pk = m["pickup"]
    refs["pickup"] = pickup_mod.pickup(kin, table_height_m=table_height_m or pk["table_height_m"])
    sts = m["sit_to_stand"]
    refs["sit_to_stand_130"] = posture.squat(kin, sts["knee_deg"], down_s=sts["down_s"], hold_s=sts["hold_s"])
    refs["sit_to_stand_130"].name = "sit_to_stand_130"
    if stress:
        s = m["stress"]
        g = walk_mod.frozen_gait()
        refs["stress_walk_speed_x1.5"] = walk_mod.walk(kin, "forward", step_len=g["step_len"] * s["walk_speed_factor"])
        refs["stress_walk_step_time_x0.8"] = walk_mod.walk(kin, "forward", step_time=g["step_time"] * s["walk_step_time_factor"])
        for sign, tag in ((1, "late"), (-1, "early")):
            r = walk_mod.walk(kin, "forward", landing_shift=int(sign * round(s["landing_timing_error_s"] / 0.01)))
            refs[f"stress_landing_{tag}_10ms"] = r
        refs["stress_capture_step"] = walk_mod.walk(kin, "forward", capture_n=3, capture_m=s["capture_step_lateral_m"])
        for k in list(refs):
            if k.startswith("stress_"):
                refs[k].name = k
    return refs


# ------------------------------------------------------------------------------------------------ demand
@dataclass
class Demand:
    name: str
    t: np.ndarray
    tau: np.ndarray            # (T, n) motor-torque demand (servo domain, friction added)
    tau_ideal: np.ndarray      # (T, n) before friction
    omega: np.ndarray
    names: list
    window: slice
    valid: bool
    invalid_reason: str
    assist_mean: float
    assist_peak: float
    fell: bool
    notes: list = field(default_factory=list)
    log: Log | None = None


def ideal_demand(robot: Robot, ref: Reference, cfg: PlayConfig | None = None) -> Demand:
    cfg = cfg or PlayConfig(mode="ideal")
    cfg = PlayConfig(**{**cfg.__dict__, "mode": "ideal"})
    lg = play(robot, ref, cfg)
    sl = lg.sl()
    specs = [robot.servo[n] for n in robot.names]
    bank = ServoBank(specs, 0.01)
    tau = lg.tau[sl]
    om = lg.omega[sl]
    fl, d = friction_budget(bank.fr, tau, -tau, om)
    moving = np.abs(om) > 0.05
    tau_dem = tau + np.sign(om) * (fl + d * np.abs(om)) * moving
    t = lg.t[sl]
    win = slice(0, len(t))
    if "walk_window" in ref.meta:
        a, b = ref.meta["walk_window"]
        i0, i1 = int(np.searchsorted(t, a)), int(np.searchsorted(t, b))
        win = slice(i0, max(i1, i0 + 2))
    limit = config.value("assist.mean_fraction_of_weight_max")
    notes = list(ref.notes)
    valid, why = True, ""
    if not ref.feasible:
        valid, why = False, "reference infeasible: " + "; ".join(ref.notes)
    elif lg.fell:
        valid, why = False, "ideal playback fell over"
    elif lg.extras["assist_mean_bw"] > limit:
        valid, why = False, f"tether supplied {lg.extras['assist_mean_bw'] * 100:.1f}% of body weight on average (limit {limit * 100:.0f}%)"
    elif ref.meta.get("max_smoother_dev_deg", 0.0) > config.motions()["dance"]["smoother_max_deviation_deg"]:
        valid, why = False, f"choreography needs {ref.meta['max_smoother_dev_deg']:.0f} deg more than the speed limit allows"
    return Demand(ref.name, t, tau_dem, tau, om, robot.names, win, valid, why, lg.extras["assist_mean_bw"],
                  lg.extras["assist_peak_bw"], lg.fell, notes, lg)


# ------------------------------------------------------------------------------------------------ metrics
def _runs(mask: np.ndarray, dt: float) -> float:
    """Longest continuous True run in seconds, per column of a (T,n) mask."""
    best = np.zeros(mask.shape[1])
    cur = np.zeros(mask.shape[1])
    for row in mask:
        cur = np.where(row, cur + dt, 0.0)
        best = np.maximum(best, cur)
    return best


def _protection_trips(over: np.ndarray, dt: float, prot: np.ndarray, rel: np.ndarray) -> np.ndarray:
    """Replay the firmware overload state machine on the demand: count trips per joint."""
    n = over.shape[1]
    timer = np.zeros(n)
    prot_on = np.zeros(n, bool)
    relt = np.zeros(n)
    trips = np.zeros(n, int)
    for row in over:
        timer = np.where(row, timer + dt, np.maximum(timer - dt, 0.0))
        new = (~prot_on) & (timer >= prot)
        trips += new
        prot_on |= new
        relt = np.where(prot_on & ~row, relt + dt, 0.0)
        r = prot_on & (relt >= rel)
        prot_on &= ~r
        timer = np.where(r | new, 0.0, timer)
    return trips


def joint_metrics(robot: Robot, dem: Demand, vin_op: np.ndarray, *, torque_model: str | None = None) -> dict:
    """Per-joint numbers for one motion. vin_op: operating bus voltage per joint (the pack's nominal voltage)."""
    sl = dem.window
    tau, om = dem.tau[sl], dem.omega[sl]
    dt = float(dem.t[1] - dem.t[0]) if len(dem.t) > 1 else 0.01
    specs = [robot.servo[n] for n in robot.names]
    k = max(1, int(round(config.gate("peak_window_s") / dt)))
    ker = np.ones(k) / k
    ma = lambda x: np.stack([np.convolve(np.pad(x[:, j], (k // 2, k - 1 - k // 2), mode="edge"), ker, mode="valid") for j in range(x.shape[1])], 1)  # noqa: E731
    tau_ma, om_ma = np.abs(ma(tau)), np.abs(ma(om))
    stall = np.array([float(s.stall_cap(v)) for s, v in zip(specs, vin_op)])
    rated = np.array([s.rated_continuous_nm for s in specs])
    avail = np.stack([s.tau_available(om_ma[:, j], vin_op[j], model=torque_model) for j, s in enumerate(specs)], 1)
    util = np.where(tau_ma > 0.02 * stall, tau_ma / np.maximum(avail, 1e-6), 0.0)
    prot = np.array([s.protection_time_s for s in specs])
    relt = np.array([s.release_time_s for s in specs])
    ovf = np.array([s.overload_fraction for s in specs])
    above70 = tau_ma > config.gate("peak_torque_fraction_of_stall") * stall
    over80 = tau_ma > ovf * stall
    return {
        "peak_nm": tau_ma.max(0), "peak_frac_stall": tau_ma.max(0) / stall, "stall_nm": stall,
        "rms_nm": np.sqrt((tau ** 2).mean(0)), "rated_nm": rated, "rms_over_rated": np.sqrt((tau ** 2).mean(0)) / rated,
        "util_max": np.minimum(util.max(0), 9.99), "omega_peak": om_ma.max(0),
        "run_above70_s": _runs(above70, dt), "time_above70_s": above70.sum(0) * dt,
        "run_above80_s": _runs(over80, dt), "trips": _protection_trips(over80, dt, prot, relt),
        "prot_time_s": prot,
    }


def gate_joint_table(robot: Robot, per_motion: dict[str, dict]) -> dict:
    """Worst case over the (valid) motions, per joint, vs the gates."""
    g = {k: config.gate(k) for k in ("peak_torque_fraction_of_stall", "rms_torque_vs_continuous", "envelope_utilisation_max")}
    half = config.value("overload_protection.gate_fraction_of_protection_time")
    names = robot.names
    n = len(names)
    out = {}
    for j in range(n):
        row = {"joint": names[j], "actuator": robot.acts[names[j]]}
        pk = [(m, v["peak_frac_stall"][j]) for m, v in per_motion.items()]
        rm = [(m, v["rms_over_rated"][j]) for m, v in per_motion.items()]
        ut = [(m, v["util_max"][j]) for m, v in per_motion.items()]
        ru = [(m, v["run_above70_s"][j] / (half * v["prot_time_s"][j])) for m, v in per_motion.items()]
        tr = [(m, int(v["trips"][j])) for m, v in per_motion.items()]
        w = lambda lst: max(lst, key=lambda x: x[1])  # noqa: E731
        row.update({
            "peak_frac_of_stall": w(pk)[1], "peak_motion": w(pk)[0],
            "rms_over_rated": w(rm)[1], "rms_motion": w(rm)[0],
            "util_max": w(ut)[1], "util_motion": w(ut)[0],
            "overload_run_ratio": w(ru)[1], "overload_motion": w(ru)[0],
            "trips": sum(x[1] for x in tr), "trip_motion": w(tr)[0] if any(x[1] for x in tr) else "",
            "stall_nm": float(per_motion[next(iter(per_motion))]["stall_nm"][j]),
        })
        row["margin_peak"] = g["peak_torque_fraction_of_stall"] / max(row["peak_frac_of_stall"], 1e-9)
        row["margin_rms"] = g["rms_torque_vs_continuous"] / max(row["rms_over_rated"], 1e-9)
        row["margin_util"] = g["envelope_utilisation_max"] / max(row["util_max"], 1e-9)
        row["margin_overload"] = 1.0 / max(row["overload_run_ratio"], 1e-9)
        row["fails"] = [name for name, m in (("peak", row["margin_peak"]), ("rms", row["margin_rms"]), ("envelope", row["margin_util"]),
                                             ("overload_time", row["margin_overload"])) if m < 1.0] + (["protection_trip"] if row["trips"] else [])
        row["worst_margin"] = min(row["margin_peak"], row["margin_rms"], row["margin_util"], row["margin_overload"])
        out[names[j]] = row
    return out


# ------------------------------------------------------------------------------------------------ mixed activity
def mixed_schedule(dem: dict[str, Demand], robot: Robot, vin: float) -> dict:
    """Mean per-joint heat and battery power in each activity, then the 100 s cycle weights."""
    specs = [robot.servo[n] for n in robot.names]
    bank = ServoBank(specs, 0.01)
    bank.set_supply(np.full(len(specs), vin))
    sched = config.thresholds()["mixed_activity"]["schedule"]
    cyc = float(config.thresholds()["mixed_activity"]["cycle_s"])
    from .tradestudy import branch_of
    br = {}
    for i, n in enumerate(robot.names):
        br.setdefault(branch_of(n), []).append(i)
    out = {"heat_w": {}, "batt_w": {}, "batt_w_peak_total": {}, "rms": {}, "branch_peak_w": {b: 0.0 for b in br}}
    for name, d in dem.items():
        if name not in sched:
            continue
        sl = d.window
        tau, om = d.tau[sl], d.omega[sl]
        fl, dm = friction_budget(bank.fr, tau, -tau, om)
        fp = np.abs(fl * om * (np.abs(om) > 0.05)) + dm * om ** 2
        cur = np.abs(tau) / bank.kt_cur
        heat = cur ** 2 * bank.R_heat + fp + 0.03 * vin * 0.5
        batt = np.maximum(cur ** 2 * bank.R_heat + tau * om, 0.0) + 0.03 * vin
        out["heat_w"][name] = heat.mean(0)
        out["batt_w"][name] = batt.mean(0)
        out["batt_w_peak_total"][name] = float(batt.sum(1).max())
        for b, idx in br.items():
            out["branch_peak_w"][b] = max(out["branch_peak_w"][b], float(batt[:, idx].sum(1).max()))
        out["rms"][name] = (tau ** 2).mean(0)
    weights = {k: v / cyc for k, v in sched.items() if k in out["heat_w"]}
    wsum = sum(weights.values())
    weights = {k: v / wsum for k, v in weights.items()}
    out["weights"] = weights
    out["heat_mean_w"] = sum(w * out["heat_w"][k] for k, w in weights.items())
    out["batt_mean_w"] = sum(w * out["batt_w"][k] for k, w in weights.items())
    out["rms_mixed_nm"] = np.sqrt(sum(w * out["rms"][k] for k, w in weights.items()))
    out["batt_total_peak_w"] = max(out["batt_w_peak_total"].values())
    return out


def thermal_series(robot: Robot, heat_by_activity: dict, weights: dict, *, ambient_c: float, rth_scale: float = 1.0,
                   tau_scale: float = 1.0, horizon_s: int = 600, dt: float = 1.0) -> np.ndarray:
    """Temperature (T_steps, n) over the 100 s activity cycle repeated for `horizon_s`."""
    specs = [robot.servo[n] for n in robot.names]
    cyc = float(config.thresholds()["mixed_activity"]["cycle_s"])
    sched = config.thresholds()["mixed_activity"]["schedule"]
    tb = ThermalBank(specs, ambient_c)
    tb.rth = tb.rth * rth_scale
    tb.tau = tb.tau * tau_scale
    seq = []
    for k, w in weights.items():
        seq.append((sched[k], heat_by_activity[k]))
    T = [tb.T.copy()]
    t = 0.0
    while t < horizon_s:
        for secs, p in seq:
            steps = int(round(secs / dt))
            for _ in range(steps):
                tb.step(p, dt)
                t += dt
                T.append(tb.T.copy())
                if t >= horizon_s:
                    return np.array(T)
    return np.array(T)


def thermal_report(robot: Robot, ms: dict, *, ambient_c: float, hot_ambient_c: float, hot_rth_scale: float = 1.4,
                   horizon_s: int = 600) -> dict:
    limit = np.array([robot.servo[n].max_temp_c for n in robot.names])
    heat, w = ms["heat_w"], ms["weights"]
    T600 = thermal_series(robot, heat, w, ambient_c=ambient_c, horizon_s=horizon_s)
    Tss = ambient_c + np.array([robot.servo[n].rth_k_per_w for n in robot.names]) * ms["heat_mean_w"]
    Thot = hot_ambient_c + hot_rth_scale * np.array([robot.servo[n].rth_k_per_w for n in robot.names]) * ms["heat_mean_w"]
    out = {"T_end_c": T600[-1], "T_max_c": T600.max(0), "steady_c": Tss, "hot_steady_c": Thot, "limit_c": limit,
           "minutes_to_limit": {}}
    for tau_s in (150, 300, 600, 1200):
        # time to reach the limit from ambient with first-order dynamics and the mean power
        rth = np.array([robot.servo[n].rth_k_per_w for n in robot.names])
        t_ss = ambient_c + rth * ms["heat_mean_w"]
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = (limit - ambient_c) / (t_ss - ambient_c)
            tm = np.where(t_ss <= limit, np.inf, -tau_s * np.log(1 - np.clip(ratio, 0, 0.9999)) / 60.0)
        out["minutes_to_limit"][tau_s] = tm
    return out
