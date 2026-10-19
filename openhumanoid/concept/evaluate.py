"""Concept evaluator: candidate YAML -> frozen motions -> demand envelopes -> gates, with bounds sweep, mass cases, a small
quasi-static Monte Carlo, stress walks, servo-in-the-loop tracking, thermal, power, cost.

    python -m openhumanoid.concept evaluate variants/adam/concepts/A-3s-12v-sts3215.yaml

Writes variants/<base>/generated/concept/<candidate>/report.{json,md}. It never picks a winner and never tunes anything:
thresholds are in thresholds.yaml, motions are frozen, uncertainty is bounded and listed.
"""
from __future__ import annotations

import copy
import json
import math
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from .. import catalog
from ..actuators import ServoBank
from ..paths import generated_header, variants_dir
from . import config, envelopes as E, provenance, pushcheck as PC, tradestudy as TS
from .kin import RobotKin
from .motions import push as PU
from .playback import PlayConfig, learn_offsets, play
from .power import Pack
from .robot import Robot, benchmark_mass_kg, build_robot, load_concept, mass_sanity
from .thermal_validation import replay as thermal_replay

SHOULD_MOTIONS = {"sit_to_stand_130"}
CORE_MOTIONS = ["stand", "walk_forward", "walk_backward", "turn", "squat_90", "squat_120", "wave", "dance", "pickup", "sit_to_stand_130"]


@dataclass
class Mods:
    structure: float = 1.0
    wiring: float = 1.0
    torque_model: str | None = None
    armature_dir: float = 0.0       # -1..+1 of each actuator's armature uncertainty
    armature_abs: float | None = None   # sensitivity row: set the armature (kg m^2) of every servo whose armature is borrowed (12 V STS3215, STS3250)
    stall_dir: float = 0.0
    rth_dir: float = 0.0
    ambient_c: float | None = None
    speed_factor: float = 1.0
    com_shift_frac: tuple | None = None    # (dx, dy) as fractions of height
    floor_friction: float | None = None
    label: str = "nominal"


def _apply_servo_mods(robot: Robot, m: Mods) -> None:
    for n, s in list(robot.servo.items()):
        u = s.uncertainty
        s2 = s.perturbed(stall=1 + m.stall_dir * u.get("stall", 0.0), armature=1 + m.armature_dir * u.get("armature", 0.0),
                         rth=1 + m.rth_dir * u.get("rth", 0.0))
        if m.torque_model:
            s2 = s2.with_model(m.torque_model)
        if m.armature_abs is not None and s.quality != "measured_7v4":
            s2 = replace(s2, armature=float(m.armature_abs))
        robot.servo[n] = s2


def _hook(robot: Robot, m: Mods):
    if m.com_shift_frac is None and m.floor_friction is None:
        return None
    h = robot.height

    def hook(model):
        import mujoco
        if m.com_shift_frac is not None:
            bid = model.body("torso").id
            model.body_ipos[bid][0] += m.com_shift_frac[0] * h
            model.body_ipos[bid][1] += m.com_shift_frac[1] * h
        if m.floor_friction is not None:
            for g in range(model.ngeom):
                if model.geom_contype[g] and model.geom_bodyid[g] in (0,) or model.geom(g).name.startswith("foot"):
                    model.geom_friction[g][0] = m.floor_friction
    return hook


@dataclass
class Bundle:
    robot: Robot
    kin: RobotKin
    refs: dict
    dem: dict
    metrics: dict
    rows: dict
    invalid: dict
    vin: float
    pack: Pack
    ms: dict | None
    thermal: dict | None
    stress_rows: dict = field(default_factory=dict)
    mods: Mods = field(default_factory=Mods)
    push_rows: dict = field(default_factory=dict)
    push_dem: dict = field(default_factory=dict)
    should: dict = field(default_factory=dict)      # SHOULD-level motions (sit-to-stand proxy): warnings, never blockers
    push_cases: dict = field(default_factory=dict)  # R10 scenario -> pushcheck.Case at the required impulse

    @property
    def worst(self) -> tuple[float, str]:
        if self.invalid:
            return 0.0, "invalid motion: " + ", ".join(self.invalid)
        j = min(self.rows.values(), key=lambda r: r["worst_margin"])
        return j["worst_margin"], j["joint"]

    @property
    def passes(self) -> bool:
        return (not self.invalid) and all(not r["fails"] for r in self.rows.values())

    def failing(self) -> list[str]:
        out = [f"{r['joint']}: {', '.join(r['fails'])}" for r in self.rows.values() if r["fails"]]
        return [f"INVALID {k}: {v}" for k, v in self.invalid.items()] + out


def run_bundle(concept: dict, mods: Mods | None = None, *, table_height: float | None = None, stress: bool = False,
               motions: list[str] | None = None, thermal: bool = True, pushes: bool = False) -> Bundle:
    mods = mods or Mods()
    robot = build_robot(concept, structure_scale=mods.structure, wiring_scale=mods.wiring)
    _apply_servo_mods(robot, mods)
    kin = RobotKin(robot)
    refs = E.build_motions(kin, table_height_m=table_height, stress=stress, walk_speed_factor=mods.speed_factor)
    want = motions or concept.get("evaluate", {}).get("motions") or CORE_MOTIONS
    pack = TS.pack_of(robot)
    vin = TS.v_nominal(pack)
    vin_arr = np.full(len(robot.names), vin)
    hook = _hook(robot, mods)
    cfg = PlayConfig(mode="ideal", model_hook=hook)
    dem, metrics, invalid, stress_rows, push_rows, push_dem, should = {}, {}, {}, {}, {}, {}, {}
    for name, ref in refs.items():
        if name in E.PUSH_NAMES:
            d = E.ideal_demand(robot, ref, cfg)
            push_dem[name] = d
            push_rows[name] = E.push_gate(robot, d, vin)
            push_rows[name]["meta"] = {k: v for k, v in ref.meta.items() if isinstance(v, (int, float, str, bool, list, dict))}
            push_rows[name]["notes"] = ref.notes[:3]
            continue
        if name.startswith("stress_"):
            d = E.ideal_demand(robot, ref, cfg)
            stress_rows[name] = {"valid": d.valid, "reason": d.invalid_reason,
                                 "metrics": E.joint_metrics(robot, d, vin_arr) if d.valid else None}
            continue
        if name not in want and name != "getup" and not (name.startswith("pickup_") and "pickup" in want):
            continue
        d = E.ideal_demand(robot, ref, cfg)
        dem[name] = d
        if name in SHOULD_MOTIONS:                       # R10: sit-to-stand is a SHOULD
            if d.valid:
                tab = E.gate_joint_table(robot, {name: E.joint_metrics(robot, d, vin_arr)})
                should[name] = {"valid": True, "fails": [f"{r['joint']}: {', '.join(r['fails'])}" for r in tab.values() if r["fails"]]}
            else:
                should[name] = {"valid": False, "fails": [d.invalid_reason]}
            continue
        if d.valid:
            metrics[name] = E.joint_metrics(robot, d, vin_arr)
        else:
            invalid[name] = d.invalid_reason
    push_cases = {}
    if pushes:                                    # R10: the required impulse, by the simplest strategy that recovers it (pushcheck)
        for sc in PU.SCENARIOS:
            case = PC.required_case(robot, kin, vin, sc, hook=hook)
            nm = f"push_{sc}"
            push_cases[nm] = case
            refs[nm] = case.ref
            push_dem[nm] = case.demand
            push_rows[nm] = {**case.row, "strategy": case.option.label if case.option else None,
                             "meta": {k: v for k, v in case.ref.meta.items() if isinstance(v, (int, float, str, bool, list, dict))}, "notes": case.ref.notes[:3]}
    rows = E.gate_joint_table(robot, metrics) if metrics else {}
    ms = th = None
    if thermal and metrics:
        sched = {k: v for k, v in dem.items() if v.valid and k in config.thresholds()["mixed_activity"]["schedule"]}
        ms = E.mixed_schedule(sched, robot, vin)
        amb = mods.ambient_c if mods.ambient_c is not None else config.value("thermal.ambient_c")
        th = E.thermal_report(robot, ms, ambient_c=amb, hot_ambient_c=40.0)
    return Bundle(robot, kin, refs, dem, metrics, rows, invalid, vin, pack, ms, th, stress_rows, mods, push_rows, push_dem, should, push_cases)


# ------------------------------------------------------------------------------------------------ pieces of the report
def _joint_rows(b: Bundle) -> list[dict]:
    rows = sorted(b.rows.values(), key=lambda r: r["worst_margin"])
    out = []
    for r in rows:
        out.append({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    return out


def _utilisation_ranking(b: Bundle) -> list[dict]:
    """Per base joint (both sides merged), ranked by the highest utilisation; the hint for where reinforcement helps."""
    best: dict[str, dict] = {}
    for r in b.rows.values():
        base = r["joint"].rsplit("_", 1)[0] if r["joint"].endswith(("_l", "_r")) else r["joint"]
        u = max(r["peak_frac_of_stall"] / config.gate("peak_torque_fraction_of_stall"), r["rms_over_rated"], r["util_max"] / config.gate("envelope_utilisation_max"))
        if base not in best or u > best[base]["utilisation"]:
            best[base] = {"joint": base, "actuator": r["actuator"], "utilisation": round(u, 3), "peak_frac_of_stall": round(r["peak_frac_of_stall"], 3),
                          "rms_over_rated": round(r["rms_over_rated"], 3), "envelope_util": round(r["util_max"], 3),
                          "driving_motion": r["peak_motion"] if r["peak_frac_of_stall"] / 0.7 >= r["rms_over_rated"] else r["rms_motion"]}
    return sorted(best.values(), key=lambda x: -x["utilisation"])


def _servo_runs(b: Bundle, pack_soc: float = 1.0) -> dict:
    """Servo-in-the-loop playback with learned feedforward: tracking error, saturation time, overload trips, grasp. NOT envelopes."""
    robot = b.robot
    load = TS.onboard_load_w(robot)
    reg = TS.regulator_for(robot)
    out = {}
    names = ["walk_forward", "turn", "squat_90", "wave", "pickup"] if len(b.dem) > 5 else [n for n in b.dem if b.dem[n].valid][:5]
    for nm in names:
        if nm not in b.refs or nm not in b.dem or not b.dem[nm].valid:
            continue
        ref = b.refs[nm]
        pk = TS.pack_of(robot, soc=pack_soc)
        cfg = PlayConfig(mode="servo", pack=pk, compute_w=load["total_w"], regulator_eff=reg["efficiency"])
        off, lg = learn_offsets(robot, ref, cfg, iters=3)
        sl = lg.sl()
        err = np.degrees(np.abs(lg.q - lg.q_ref)[sl])
        # gripper error is in metres: report separately
        gi = [i for i, n in enumerate(lg.names) if n.startswith("gripper")]
        mask = np.ones(err.shape[1], bool)
        mask[gi] = False
        rec = {"rms_err_deg": round(float(np.sqrt((err[:, mask] ** 2).mean())), 2), "max_err_deg": round(float(err[:, mask].max()), 2),
               "worst_joint": lg.names[int(np.argmax(np.where(mask, err.max(0), 0)))],
               "saturation_fraction_max": round(float(np.max(np.where(mask, lg.extras["sat_frac"], 0.0))), 3),
               "saturated_joint": lg.names[int(np.argmax(np.where(mask, lg.extras["sat_frac"], 0.0)))],
               "gripper_saturation_fraction(by design, torque-limited)": round(float(max([lg.extras["sat_frac"][i] for i in gi] or [0.0])), 3),
               "overload_trips": int(sum(lg.extras["protection_trips"])), "fell": bool(lg.fell),
               "min_bus_voltage_v": round(float(lg.vin[sl].min()), 2), "peak_total_current_a": round(float(lg.i_total[sl].max()), 2),
               "tether_mean_pct_bw": round(100 * lg.extras["assist_mean_bw"], 2)}
        if nm == "pickup" and "object_pos" in lg.extras:
            z0 = lg.extras["object_z_ref"]
            rec["object_lift_m"] = round(float(lg.extras["object_pos"][2] - z0), 4)
            rec["grasp_ok"] = bool(lg.extras["object_pos"][2] - z0 > 0.02)
        out[nm] = rec
    # push recovery: servo in the loop WITH the actuator delay; legs only (the gripper/arm are at rest)
    leg = [i for i, n in enumerate(robot.names) if n.split("_")[0] in ("hip", "knee", "ankle")]
    deliver = config.motions()["push"]["deliver"]
    for nm in E.PUSH_NAMES:
        d = b.push_dem.get(nm)
        if d is None or not d.valid or not b.push_rows.get(nm, {}).get("ok"):
            continue
        ref = b.refs[nm]
        pk = TS.pack_of(robot, soc=pack_soc)
        cfg = PlayConfig(mode="servo", pack=pk, compute_w=load["total_w"], regulator_eff=reg["efficiency"])
        off, lg = learn_offsets(robot, ref, cfg, iters=2)
        sl = lg.sl()
        err = np.degrees(np.abs(lg.q - lg.q_ref)[sl][:, leg])
        sat = np.array(lg.extras["sat_frac"])[leg]
        out[nm] = {"fell": bool(lg.fell), "leg_max_err_deg": round(float(err.max()), 2), "leg_rms_err_deg": round(float(np.sqrt((err ** 2).mean())), 2),
                   "saturation_fraction_max": round(float(sat.max()), 3), "saturated_joint": robot.names[leg[int(np.argmax(sat))]],
                   "overload_trips": int(sum(lg.extras["protection_trips"])), "min_bus_voltage_v": round(float(lg.vin[sl].min()), 2),
                   "delivered_in_time": bool((not lg.fell) and err.max() <= deliver["leg_tracking_error_deg_max"]),
                   "servo_delay_ms": round(1000 * max(s_.delay_s for s_ in robot.servo.values()), 1)}
    return out


def _closed_loop_sensitivity(b: Bundle) -> dict:
    """Latency / backlash / kp sensitivity on the walk, servo-in-the-loop. SENSITIVITY ONLY: 'needs closed loop (P5)'."""
    robot = b.robot
    if "walk_forward" not in b.refs or not b.dem.get("walk_forward") or not b.dem["walk_forward"].valid:
        return {}
    ref = b.refs["walk_forward"]
    base_cfg = PlayConfig(mode="servo")
    off, lg0 = learn_offsets(robot, ref, base_cfg, iters=3)
    out = {"label": "needs closed loop (P5): open-loop replay with frozen feedforward; not a gate"}
    cl = config.thresholds()["uncertainty"]["closed_loop_only"]
    cases = {"latency_40ms": dict(extra_latency_s=cl["latency_extra_ms"]["high"] / 1000), "backlash_1deg": dict(backlash_rad=math.radians(cl["backlash_deg"]["high"])),
             "kp_-10%": dict(kp_scale=cl["kp_scale"]["low"]), "kp_+10%": dict(kp_scale=cl["kp_scale"]["high"])}
    for k, kw in cases.items():
        lg = play(robot, ref, PlayConfig(**{**base_cfg.__dict__, "cmd_offset": off, **kw}))
        sl = lg.sl()
        err = np.degrees(np.abs(lg.q - lg.q_ref)[sl])
        out[k] = {"rms_err_deg": round(float(np.sqrt((err ** 2).mean())), 2), "max_err_deg": round(float(err.max()), 2), "fell": bool(lg.fell),
                  "tether_mean_pct_bw": round(100 * lg.extras["assist_mean_bw"], 2)}
    return out


def _power_block(b: Bundle) -> dict:
    robot = b.robot
    load = TS.onboard_load_w(robot)
    reg = TS.regulator_for(robot)
    pack = b.pack
    ms = b.ms
    if not ms:
        return {}
    rail_w = load["total_w"] / reg["efficiency"]
    avg_w = float(ms["batt_mean_w"].sum()) + rail_w
    usable_wh = pack.energy_wh * config.value("power.usable_battery_fraction")
    runtime = usable_wh / avg_w * 60.0
    branch = ms["branch_peak_w"]
    tr = _r10_transient(b)
    bus = TS.bus_analysis(robot, ms, branch, pack, rail_w, transient=tr)
    return {"pack": {"part": pack.part_id, "cells": pack.cells, "capacity_ah": pack.capacity_ah, "energy_wh": round(pack.energy_wh, 1),
                     "mass_kg": pack.mass_kg, "nominal_v": round(TS.v_nominal(pack), 2), "r_total_mohm": round(pack.r_total * 1000, 1),
                     "c_rating_limit_a": round(pack.max_discharge_a, 1)},
            "onboard_load": load, "regulator": TS.compute_check(robot, load),
            "average_power_w": round(avg_w, 2), "servo_average_w": round(float(ms["batt_mean_w"].sum()), 2), "rail_w": round(rail_w, 2),
            "runtime_min": round(runtime, 1), "runtime_requirement_min": config.gate("runtime_min_min"),
            "runtime_ok": bool(runtime >= config.gate("runtime_min_min")),
            "activity_power_w": {k: round(float(v.sum()) + rail_w, 1) for k, v in ms["batt_w"].items()},
            "bus": bus, "voltage_rating": TS.voltage_rating_report(robot, pack)}


def _thermal_block(b: Bundle, validation: dict) -> dict:
    if not b.thermal or not b.ms:
        return {}
    th, robot, ms = b.thermal, b.robot, b.ms
    limit = config.gate("thermal_limit_c")
    names = robot.names
    rated = np.array([robot.servo[n].rated_continuous_nm for n in names])
    rows = {}
    for i, n in enumerate(names):
        rows[n] = {"rms_mixed_nm": round(float(ms["rms_mixed_nm"][i]), 3), "rated_nm": round(float(rated[i]), 3),
                   "rms_mixed_over_rated": round(float(ms["rms_mixed_nm"][i] / rated[i]), 3),
                   "T_10min_c": round(float(th["T_end_c"][i]), 1), "steady_c": round(float(th["steady_c"][i]), 1),
                   "hot_steady_c": round(float(th["hot_steady_c"][i]), 1),
                   "minutes_to_70c": {str(t): (None if not np.isfinite(v[i]) else round(float(v[i]), 1)) for t, v in th["minutes_to_limit"].items()}}
    worst = max(rows, key=lambda n: rows[n]["hot_steady_c"])
    return {"primary_gate": "RMS torque (mixed schedule) <= vendor-rated continuous torque",
            "rms_gate_ok": all(r["rms_mixed_over_rated"] <= config.gate("rms_torque_vs_continuous") for r in rows.values()),
            "thermal_model_usable": bool(validation["thermal_numbers_usable"]), "thermal_model_validation": validation["verdict"],
            "limit_c": limit, "ambient_c": config.value("thermal.ambient_c"), "hot_case": "Rth x1.4 and 40 C in-shell ambient",
            "T_10min_max_c": round(float(th["T_end_c"].max()), 1), "steady_max_c": round(float(th["steady_c"].max()), 1),
            "hot_steady_max_c": round(float(th["hot_steady_c"].max()), 1), "hottest_joint": worst, "per_joint": rows}


def _bounds(concept: dict, table_height, nominal: Bundle) -> list[dict]:
    """Tornado: one unknown at a time at its low/high bound; report the worst margin and what fails."""
    t = config.thresholds()["uncertainty"]["tornado"]
    lo, hi = t["mass_structure"]["low"], t["mass_structure"]["high"]
    from ..actuators import bam_params
    st3025 = float(bam_params("bam_waveshare_st3025_m4.json")["armature"])
    variants = [
        Mods(structure=lo, label=f"structure mass x{lo:g}"), Mods(structure=hi, label=f"structure mass x{hi:g}"),
        Mods(wiring=t["mass_wiring_electronics"]["low"], label="wiring/electronics x0.8"), Mods(wiring=t["mass_wiring_electronics"]["high"], label="wiring/electronics x1.5"),
        Mods(torque_model="linear", label="pessimistic linear torque-speed"),
        Mods(armature_dir=-1.0, label="armature low"), Mods(armature_dir=1.0, label="armature high"),
        Mods(stall_dir=-1.0, label="stall low"), Mods(stall_dir=1.0, label="stall high"),
        Mods(rth_dir=1.0, ambient_c=40.0, label="Rth high + 40 C ambient"),
        Mods(speed_factor=1.5, label="walking speed x1.5"),
        # SENSITIVITY, not a bound (challenge-2 row 4): the only other 12 V-class armature in BAM's parameter files (Waveshare ST3025, m4 fit,
        # bam/params/waveshare_st3025/m4.json, commit e9a619d), 0.00399 kg m^2 = 17% of the borrowed 7.4 V value. A different gearbox: the bench settles it.
        Mods(armature_abs=st3025, label=f"SENSITIVITY armature = BAM ST3025 ({st3025:.5f}), not a bound"),
    ]
    out = []
    for m in variants:
        b = run_bundle(concept, m, table_height=table_height, thermal=True)
        w, j = b.worst
        row = {"label": m.label, "kind": "sensitivity" if m.label.startswith("SENSITIVITY") else "bound", "worst_margin": round(w, 3), "worst_joint": j, "passes": b.passes, "failing": b.failing()[:6]}
        if b.thermal:
            row["hot_steady_max_c"] = round(float(b.thermal["hot_steady_c"].max()), 1)
            row["rms_mixed_over_rated_max"] = round(float((b.ms["rms_mixed_nm"] / np.array([b.robot.servo[n].rated_continuous_nm for n in b.robot.names])).max()), 3)
        out.append(row)
    nom_w = nominal.worst[0]
    for r in out:
        r["delta_vs_nominal"] = round(r["worst_margin"] - nom_w, 3)
    return out


def _mass_cases(concept: dict, table_height, nominal: Bundle) -> dict:
    robot = nominal.robot
    struct = robot.body.breakdown["structure_kg"]
    other = robot.total_mass - struct
    bm = benchmark_mass_kg(robot.height)
    cases = {"nominal": nominal}
    s_bm = max((bm - other) / max(struct, 1e-6), 1.0)
    out = {"nominal_kg": round(robot.total_mass, 3), "benchmark_fit_kg": round(bm, 3), "structure_kg_nominal": round(struct, 3),
           "cases": {}, "note": "benchmark fit is a SANITY BOUND and a stress case, not an estimate"}
    hi_band = config.thresholds()["mass"]["structure_factor"]["high"]
    for label, s in ((f"structure x{hi_band:g}", hi_band), ("benchmark-fit mass", s_bm)):
        b = run_bundle(concept, Mods(structure=s, label=label), table_height=table_height, thermal=True)
        w, j = b.worst
        out["cases"][label] = {"structure_scale": round(s, 2), "total_kg": round(b.robot.total_mass, 3), "worst_margin": round(w, 3), "worst_joint": j,
                               "passes": b.passes, "failing": b.failing()[:6]}
    # mass to first gate failure: raise the structure mass until a gate fails
    ladder = [1.0, 1.4, 2.0, 3.0, 4.5]
    last_ok = None
    first_fail = None
    scan = []
    for s in ladder:
        b = nominal if s == 1.0 else run_bundle(concept, Mods(structure=s), table_height=table_height, thermal=False)
        scan.append({"structure_scale": s, "total_kg": round(b.robot.total_mass, 3), "worst_margin": round(b.worst[0], 3), "passes": b.passes})
        if b.passes:
            last_ok = (s, b)
        else:
            first_fail = (s, b)
            break
    if first_fail is None:
        out["mass_to_first_gate_failure_kg"] = f"> {scan[-1]['total_kg']} kg (no failure up to structure x{ladder[-1]})"
    elif last_ok is None:
        out["mass_to_first_gate_failure_kg"] = f"fails at the nominal mass ({nominal.robot.total_mass:.2f} kg)"
    else:
        (s0, b0), (s1, b1) = last_ok, first_fail
        m0, m1 = b0.robot.total_mass, b1.robot.total_mass
        w0, w1 = b0.worst[0], b1.worst[0] if not b1.invalid else 0.0
        frac = (w0 - 1.0) / max(w0 - min(w1, 0.999), 1e-6)
        out["mass_to_first_gate_failure_kg"] = round(m0 + frac * (m1 - m0), 3)
    out["scan"] = scan
    return out


def _monte_carlo(concept: dict, table_height, n: int, seed: int) -> dict:
    """Small Monte Carlo over QUASI-STATIC dimensions only (mass bands, COM shift, floor friction, stall/armature/Rth spread)."""
    rng = np.random.default_rng(seed)
    ut = config.thresholds()
    ms_ = ut["mass"]
    mc = ut["uncertainty"]["monte_carlo"]
    peaks, rms, ok, fails_all = [], [], [], []
    names = None
    for i in range(n):
        m = Mods(structure=float(rng.uniform(ms_["structure_factor"]["low"], ms_["structure_factor"]["high"])),
                 wiring=float(rng.uniform(ms_["wiring_electronics_factor"]["low"], ms_["wiring_electronics_factor"]["high"])),
                 armature_dir=float(rng.uniform(-1, 1)), stall_dir=float(rng.uniform(-1, 1)), rth_dir=float(rng.uniform(-1, 1)),
                 com_shift_frac=tuple(rng.uniform(-1, 1, 2) * mc["com_shift_frac_h"]["value"]),
                 floor_friction=float(rng.uniform(mc["floor_friction"]["low"], mc["floor_friction"]["high"])), label=f"mc{i}")
        b = run_bundle(concept, m, table_height=table_height, thermal=False)
        names = b.robot.names
        ok.append(b.passes)
        if b.rows:
            peaks.append([b.rows[n_]["peak_frac_of_stall"] for n_ in names])
            rms.append([b.rows[n_]["rms_over_rated"] for n_ in names])
        else:
            peaks.append([9.99] * len(names)); rms.append([9.99] * len(names))
        fails_all.append(b.failing()[:3])
    peaks, rms = np.array(peaks), np.array(rms)
    p95 = np.percentile(peaks, 95, axis=0)
    return {"quasi_static_only": True, "samples": n, "seed": seed, "pass_rate": round(float(np.mean(ok)), 3),
            "pass_rate_required": config.gate("mc_pass_rate_min") if "mc_pass_rate_min" in ut["gates"] else None,
            "p95_peak_frac_of_stall": {nm: round(float(v), 3) for nm, v in zip(names, p95)},
            "p95_rms_over_rated": {nm: round(float(v), 3) for nm, v in zip(names, np.percentile(rms, 95, axis=0))},
            "p95_peak_gate_ok": bool((p95 <= config.gate("peak_torque_fraction_of_stall")).all()),
            "worst_joint_p95_peak": names[int(np.argmax(p95))], "worst_p95_peak": round(float(p95.max()), 3),
            "note": "latency, backlash and kp are NOT sampled here: they need the closed loop (P5)"}


def _stress_block(b: Bundle) -> dict:
    out = {}
    g = config.gate("peak_torque_fraction_of_stall")
    for name, r in b.stress_rows.items():
        if not r["valid"]:
            out[name] = {"valid": False, "reason": r["reason"]}
            continue
        m = r["metrics"]
        j = int(np.argmax(m["peak_frac_stall"]))
        out[name] = {"valid": True, "worst_peak_frac_of_stall": round(float(m["peak_frac_stall"][j]), 3), "joint": b.robot.names[j],
                     "worst_rms_over_rated": round(float(m["rms_over_rated"].max()), 3), "worst_util": round(float(m["util_max"].max()), 3),
                     "peak_within_gate": bool(m["peak_frac_stall"][j] <= g)}
    return out


def _rms_denominators(b: Bundle) -> dict | None:
    """Challenge-2 row 2: the RMS verdict for servos whose 'rated continuous torque' is a contested retailer label, at every figure in
    circulation (7.4 V STS3215: 0.49 Seeed, 0.637 Evelta). Per-motion gate (worst motion) and the mixed-activity RMS, legs and all joints."""
    robot = b.robot
    idx = [i for i, n in enumerate(robot.names) if robot.servo[n].rated_alt_nm]
    if not idx or not b.metrics:
        return None
    primary = {robot.names[i]: robot.servo[robot.names[i]].rated_continuous_nm for i in idx}
    figs = sorted({round(v, 3) for v in primary.values()} | {round(a, 3) for i in idx for a in robot.servo[robot.names[i]].rated_alt_nm})
    rows = []
    for fig in figs:
        worst, wj, wm = 0.0, "", ""
        for mname, mt in b.metrics.items():
            r = mt["rms_nm"][idx] / fig
            k = int(np.argmax(r))
            if r[k] > worst:
                worst, wj, wm = float(r[k]), robot.names[idx[k]], mname
        row = {"rated_nm": fig, "per_motion_rms_gate_worst": round(worst, 3), "per_motion_rms_gate_ok": bool(worst <= config.gate("rms_torque_vs_continuous")), "worst_joint": wj, "worst_motion": wm}
        if b.ms is not None:
            rm = b.ms["rms_mixed_nm"][idx] / fig
            row["mixed_schedule_rms_worst"] = round(float(rm.max()), 3)
            row["mixed_schedule_ok"] = bool(rm.max() <= config.gate("rms_torque_vs_continuous"))
        rows.append(row)
    return {"joints": len(idx), "rows": rows, "note": "the PRIMARY gate uses the first figure; the others are a sensitivity until a bench thermal hold measures the real continuous torque"}


def _r10_transient(b: Bundle) -> dict | None:
    """Battery power during the R10 push cases at the required impulse (per scenario, total and per bus branch), from the demand."""
    from .tradestudy import branch_of
    robot = b.robot
    if not b.push_dem:
        return None
    specs = [robot.servo[n] for n in robot.names]
    bank = ServoBank(specs, 0.01)
    kt, rh = bank.kt_cur, bank.R_heat
    br = {}
    for i, n in enumerate(robot.names):
        br.setdefault(branch_of(n), []).append(i)
    best = {"total_w": 0.0, "scenario": None, "branch_w": {k: 0.0 for k in br}}
    for nm, d in b.push_dem.items():
        if not d.valid:
            continue
        sl = d.window
        tau, om = d.tau[sl], d.omega[sl]
        k_ = max(1, int(round(0.04 / float(d.t[1] - d.t[0]))))
        ker = np.ones(k_) / k_
        cur = np.abs(tau) / kt
        batt = np.maximum(cur ** 2 * rh + tau * om, 0.0) + 0.03 * b.vin
        batt = np.stack([np.convolve(np.pad(batt[:, j], (k_ // 2, k_ - 1 - k_ // 2), mode="edge"), ker, mode="valid") for j in range(batt.shape[1])], 1)
        tot = float(batt.sum(1).max())
        if tot > best["total_w"]:
            best["total_w"], best["scenario"] = tot, nm
        for k, idx in br.items():
            best["branch_w"][k] = max(best["branch_w"][k], float(batt[:, idx].sum(1).max()))
    return best


def _push_block(b: Bundle, sim: dict, quick: bool) -> dict:
    """R10 push recovery: ONE absolute impulse for every candidate, any combination of strategies, standing and at mid single support of
    walk_forward. Per scenario: recoverable at the required impulse (plan + Reference + actuator demand + servo in the loop), the strategy,
    and (full run) the largest recoverable impulse in N.s and m/s."""
    cfg = config.motions()["push"]
    robot = b.robot
    J = float(cfg["required_impulse_Ns"])
    M = robot.total_mass
    cap = PU.hip_speed_cap(b.kin, b.vin)
    out = {"requirement": "R10 (a MUST, PROVISIONAL value pending the maintainer): survive an absolute push, the same for every candidate, by any combination of "
                          "strategies, standing and at mid single support of walk_forward. Getting up after a face-plant is not required yet.",
           "required_impulse_Ns": J, "required_dv_mps": round(J / M, 3), "mass_kg": round(M, 3), "definition": cfg["source"],
           "hip_strategy": {"trunk_speed_limit_rad_s": round(cap, 2),
                            "note": "the hip strategy counts only up to 90% of the hip-pitch no-load speed; beyond it it is unavailable, and it is never a blocker by itself"},
           "cases": {}}
    for nm, row in b.push_rows.items():
        sc = nm[len("push_"):]
        m = row.get("meta", {})
        case = {"valid": row["valid"], "reason": row["reason"], "demand_ok": bool(row.get("ok")), "strategy": row.get("strategy"), "notes": row.get("notes", [])}
        case.update({k: row[k] for k in ("peak_frac_of_stall", "peak_joint", "peak_nm", "util_max", "util_joint", "omega_peak", "omega_peak_joint", "why") if k in row})
        case["plan"] = {"steps_taken": m.get("steps_taken"), "landings": m.get("landings"), "crouch_peak_mm": round(1000 * m.get("crouch_peak_m", 0), 1),
                        "reach_clipped": m.get("clipped"), "trunk_pitch_peak_deg": round(m.get("trunk_pitch_peak_deg", 0), 1),
                        "trunk_speed_peak_rad_s": round(m.get("trunk_speed_peak_rad_s", 0), 2), "capture_offset_mm": round(1000 * m.get("capture_offset_m", 0), 1),
                        "reaction_delay_ms": round(1000 * m.get("reaction_delay_s", 0), 1), "cop_peak_offset_mm": round(1000 * m.get("cop_peak_offset_m", 0), 1)}
        if nm in sim:
            case["servo_in_the_loop"] = sim[nm]
        delivered = case.get("servo_in_the_loop", {}).get("delivered_in_time", True)
        case["recoverable_at_required"] = bool(case["valid"] and case["demand_ok"] and delivered)
        if not quick:
            lr = PC.largest_recoverable(robot, b.kin, b.vin, sc, hook=_hook(robot, b.mods))
            case["largest_recoverable"] = lr
        out["cases"][nm] = case
    out["all_ok"] = all(c["recoverable_at_required"] for c in out["cases"].values())
    if not quick:
        lrs = {nm: c["largest_recoverable"]["largest_recoverable_Ns"] for nm, c in out["cases"].items()}
        out["largest_recoverable_Ns"] = lrs
        worst = min(lrs, key=lrs.get)
        out["largest_recoverable_min"] = {"scenario": worst, "impulse_Ns": lrs[worst], "dv_mps": round(lrs[worst] / M, 3)}
        out["gate"] = "largest recoverable impulse >= required in every scenario: " + ("MET" if lrs[worst] >= J - 1e-6 else "NOT MET")
    return out


def _height_floor_note(robot: Robot) -> list[str]:
    return list(robot.spec.get("_floor_notes", []))


# ------------------------------------------------------------------------------------------------ main entry
def gait_sweep(concept: dict, table_height: float | None = None) -> tuple[dict, list[dict]]:
    """Challenge-2 rows 12-13: stance knee flexion x step time, the SAME set for every candidate; the gates use the best feasible one
    (largest worst-joint margin among the combinations whose motions are all valid). Returns (best row, all rows)."""
    gs = config.thresholds()["gait_sweep"]
    rows = []
    for f in gs["stance_knee_flex_deg"]:
        for st in gs["step_time_s"]:
            c = copy.deepcopy(concept)
            c.setdefault("locomotion", {}).setdefault("walk", {})["stance_knee_flex_deg"] = float(f)
            c["gait"] = {"step_time_s": float(st)}
            b = run_bundle(c, Mods(), table_height=table_height, thermal=False)
            w, j = b.worst
            rows.append({"stance_knee_flex_deg": f, "step_time_s": st, "worst_margin": round(w, 3), "worst_joint": j, "passes": b.passes,
                         "invalid": dict(b.invalid), "failing": b.failing()[:3]})
    pool = [r for r in rows if not r["invalid"]] or rows
    best = max(pool, key=lambda r: r["worst_margin"])
    return best, rows


def apply_gait(concept: dict, row: dict) -> dict:
    c = copy.deepcopy(concept)
    c.setdefault("locomotion", {}).setdefault("walk", {})["stance_knee_flex_deg"] = float(row["stance_knee_flex_deg"])
    c["gait"] = {"step_time_s": float(row["step_time_s"])}
    return c


def evaluate(path_or_concept, *, out_root: Path | None = None, samples: int | None = None, quick: bool = False,
             table_height: float | None = None, write: bool = True, gait: bool | None = None) -> dict:
    t0 = time.time()
    concept = load_concept(path_or_concept)
    cid = concept["id"]
    gait_rows = None
    gait_chosen = None
    if (not quick) if gait is None else gait:
        gait_chosen, gait_rows = gait_sweep(concept, table_height)
        concept = apply_gait(concept, gait_chosen)
    nominal = run_bundle(concept, Mods(), table_height=table_height, stress=not quick, pushes=True)
    robot = nominal.robot
    validation = thermal_replay()
    gates = config.thresholds()["gates"]
    msan = mass_sanity(robot)

    rep: dict = {"generated_by": "python -m openhumanoid.concept evaluate", "candidate": cid, "description": concept.get("description", ""),
                 "source_file": concept.get("_path", ""), "thresholds_file": "openhumanoid/concept/thresholds.yaml"}
    rep["design"] = {"height_m": robot.height, "template": robot.spec["kinematics"]["template"], "dof": len(robot.names),
                     "joints": robot.names, "actuators": {a: sum(1 for x in robot.acts.values() if x == a) for a in sorted(set(robot.acts.values()))},
                     "transmissions": robot.transmissions,
                     "proportions_m": {k: round(v, 4) for k, v in robot.geom.items()}, "packaging_floors_applied": _height_floor_note(robot),
                     "ankle_pitch_range_deg": next((j["range"] for j in robot.joints if j["base"] == "ankle_pitch"), None)}
    if gait_rows is not None:
        d0 = next((r for r in gait_rows if r["stance_knee_flex_deg"] == 40.0 and r["step_time_s"] == config.walk_spec()["step_time_s"]), None)
        rep["gait"] = {"chosen": {"stance_knee_flex_deg": gait_chosen["stance_knee_flex_deg"], "step_time_s": gait_chosen["step_time_s"]},
                       "chosen_worst_margin": gait_chosen["worst_margin"], "at_the_old_default_40deg_0p5s": d0,
                       "rule": "same set for every candidate; the gates use the combination with the largest worst-joint margin among those whose motions are all valid",
                       "sweep": gait_rows}
    rep["mass"] = {"breakdown_kg": robot.mass_breakdown, "total_kg": round(robot.total_mass, 3), "sanity": msan,
                   "bands": {"structure": [config.thresholds()["mass"]["structure_factor"]["low"], config.thresholds()["mass"]["structure_factor"]["high"]],
                             "wiring_electronics": [config.thresholds()["mass"]["wiring_electronics_factor"]["low"], config.thresholds()["mass"]["wiring_electronics_factor"]["high"]]}}
    rep["motions"] = {n: {"valid": d.valid, "invalid_reason": d.invalid_reason, "tether_mean_pct_bw": round(100 * d.assist_mean, 2),
                          "notes": d.notes[:3], "meta": {k: v for k, v in nominal.refs[n].meta.items() if isinstance(v, (int, float, str, list)) and k not in ("gait",)}}
                     for n, d in nominal.dem.items()}
    rep["joints_ranked_by_margin"] = _joint_rows(nominal)
    rep["utilisation_ranking"] = _utilisation_ranking(nominal) if nominal.rows else []
    w, j = nominal.worst
    rep["nominal"] = {"passes": nominal.passes, "worst_margin": round(w, 3), "worst_joint": j, "failing": nominal.failing()}
    rep["power"] = _power_block(nominal)
    rep["rms_denominators"] = _rms_denominators(nominal)
    rep["thermal"] = _thermal_block(nominal, validation)
    rep["cost"] = TS.cost_report(robot)
    rep["model_quality"] = TS.model_quality(robot, nominal.vin)
    if not quick:
        rep["servo_in_the_loop"] = _servo_runs(nominal)
        rep["closed_loop_sensitivity"] = _closed_loop_sensitivity(nominal)
        rep["stress_walks"] = _stress_block(nominal)
        rep["bounds_sweep"] = _bounds(concept, table_height, nominal)
        rep["mass_cases"] = _mass_cases(concept, table_height, nominal)
        n = samples or config.thresholds()["uncertainty"]["monte_carlo"]["n_samples"]["value"]
        rep["monte_carlo"] = _monte_carlo(concept, table_height, int(n), config.thresholds()["uncertainty"]["monte_carlo"]["seed"])
    rep["push_recovery"] = _push_block(nominal, rep.get("servo_in_the_loop", {}), quick)
    # ---- verdict: blockers fail the candidate, warnings do not
    blockers = list(nominal.failing())
    for nm, c in rep["push_recovery"]["cases"].items():
        if not c["valid"]:
            blockers.append(f"R10 {nm}: no strategy recovers {rep['push_recovery']['required_impulse_Ns']} N.s ({c['reason'][:140]})")
        elif not c["demand_ok"]:
            blockers.append(f"R10 {nm}: actuators cannot deliver {rep['push_recovery']['required_impulse_Ns']} N.s by any strategy ({c.get('strategy')}: {'; '.join(c.get('why', []))})")
        elif c.get("servo_in_the_loop") and not c["servo_in_the_loop"]["delivered_in_time"]:
            blockers.append(f"R10 {nm}: servo in the loop with latency did not deliver (fell={c['servo_in_the_loop']['fell']}, leg error {c['servo_in_the_loop']['leg_max_err_deg']} deg)")
    warnings = []
    for nm, sh in nominal.should.items():
        if sh["fails"]:
            warnings.append(f"SHOULD {nm} (proxy for getting up, not required yet): " + "; ".join(sh["fails"][:3]))
    rep["should_checks"] = nominal.should
    p = rep.get("power", {})
    mc = rep.get("monte_carlo")
    if mc and not mc["p95_peak_gate_ok"]:
        blockers.append(f"Monte Carlo p95 peak above the gate at {mc['worst_joint_p95_peak']} ({mc['worst_p95_peak']:.2f} of stall)")
    th = rep.get("thermal", {})
    if th and not th["rms_gate_ok"]:
        blockers.append("mixed-schedule RMS torque above the vendor-rated continuous torque on at least one joint")
    sim = rep.get("servo_in_the_loop", {})
    if sim.get("pickup") is not None and sim["pickup"].get("grasp_ok") is False:
        blockers.append("pickup: the servo-in-the-loop grasp did not lift the 150 g object")
    bus = p.get("bus", {})
    if bus and not bus["min_voltage_ok"]:
        blockers.append(f"bus: {bus['min_voltage_at_far_servo_v']} V at the farthest servo is below the servo minimum {bus['servo_min_operating_v']} V")
    if bus and not bus["pack_c_ok"]:
        blockers.append("pack: peak current above the C-rating limit")
    if p and not p["regulator"]["ok_at_peak"]:
        blockers.append("regulator cannot carry the peak 5 V rail current")
    cost = rep["cost"]
    if not cost["within_cap_typical"]:
        warnings.append(f"cost ${cost['total_usd']['typical']} typical is above the ${cost['budget_cap_usd']} cap (high band ${cost['total_usd']['high']}); prices are unverified")
    for aid, vr in p.get("voltage_rating", {}).items():
        if vr["over_rating_at_full_v"] > 0:
            warnings.append(f"{aid}: full charge {vr['pack_full_v']} V is {vr['over_rating_at_full_v']} V over the rating for {100 * vr['soc_share_over']:.0f}% of the discharge ({vr['mitigation']['action'] if vr['mitigation'] else ''})")
    if p and not p["runtime_ok"]:
        warnings.append(f"runtime {p['runtime_min']} min is below the 15 min Should")
    if th and not th["thermal_model_usable"]:
        warnings.append("thermal model failed the Robonine replay: thermal temperatures are indicative only")
    rep["gate_results"] = {
        "motions_valid": not nominal.invalid, "joint_gates_nominal": nominal.passes,
        "p95_peak_ok": mc["p95_peak_gate_ok"] if mc else None, "rms_vs_rated_mixed_ok": th.get("rms_gate_ok"),
        "thermal_10min_below_70c(info)": bool(th["T_10min_max_c"] < config.gate("thermal_limit_c")) if th else None,
        "thermal_model_usable": th.get("thermal_model_usable"), "runtime_ok(info)": p.get("runtime_ok"),
        "bus_min_voltage_ok": bus.get("min_voltage_ok"), "pack_c_ok": bus.get("pack_c_ok"),
        "grasp_ok": sim.get("pickup", {}).get("grasp_ok"), "tracking_noted_rms_deg": {k: v["rms_err_deg"] for k, v in sim.items() if "rms_err_deg" in v}}
    ok = not blockers
    robust = None
    if not quick:
        robust = all(r["passes"] for r in rep["bounds_sweep"] if r["kind"] == "bound")
        rep["robust_to_all_bounds"] = robust
        rep["passes_at_benchmark_mass"] = rep["mass_cases"]["cases"]["benchmark-fit mass"]["passes"]
    rep["verdict"] = {"status": "PASS" if ok else "FAIL", "robust_to_all_bounds": robust,
                      "passes_at_benchmark_mass": rep.get("passes_at_benchmark_mass"), "reasons": blockers[:14], "warnings": warnings,
                      "meaning": "PASS = no blocker: every frozen motion valid, nominal joint gates met, Monte Carlo p95 peak and mixed RMS within the gates, grasp, bus and regulator OK. Warnings (cost, voltage rating, runtime, unusable thermal model) do not flip it. 'robust' and 'benchmark mass' are the decision-rule checks (challenge-1): a PASS that is not robust is not a decision."}
    rep["limitations"] = LIMITATIONS
    rep["provenance"] = provenance.collect(robot)
    rep["wall_seconds"] = round(time.time() - t0, 1)
    if write:
        out = (out_root or variants_dir() / robot.concept.get("base", "adam") / "generated" / "concept") / cid
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(rep, indent=1, default=_json), encoding="utf-8")
        (out / "report.md").write_text(to_markdown(rep), encoding="utf-8")
        rep["_out"] = str(out)
    return rep


def _json(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


LIMITATIONS = [
    "Open-loop reference replay: LIPM + analytic IK gait (no trajectory optimisation), so loads are a lower bound for a real balancing controller; stress walks bound some of the gap.",
    "Torque demand includes the servo's reflected rotor inertia (BAM armature 0.0234 kg m^2), which dominates dynamic loads; that value is a 7.4 V identification used for all servos.",
    "12 V STS3215 and STS3250 are datasheet-anchored with dynamics borrowed from the 7.4 V fit; the mid-speed torque curve is unverified (anchored vs pessimistic linear shown).",
    "Printed structure mass is a pre-CAD guess; shells and brackets are not modelled. The benchmark fit is only a sanity bound / stress case.",
    "Thermal: single lumped node, Rth/tau derived from one Robonine unit with assumed ambient; the model does not reproduce Robonine run 2, so thermal numbers are indicative and RMS <= rated is the thermal gate.",
    "Latency, backlash and kp need the closed loop (P5); here they are sensitivities on one walk, never gates.",
    "Leg-table / self-collision, cable routing and packaging are not checked (T-0004 floors are applied only as proportion minimums).",
    "Stand-up from a fall is not modelled; the quasi-static sit-to-stand at 130 deg knee is a proxy only.",
]


def to_markdown(r: dict) -> str:
    L = [generated_header("concept evaluate", "<!--").rstrip() + " -->", f"# Concept report: {r['candidate']}", "", r["description"], ""]
    v = r["verdict"]
    L += [f"**Verdict: {v['status']}** (robust to all bounds: {v['robust_to_all_bounds']}; passes at benchmark mass: {v['passes_at_benchmark_mass']})", ""]
    for x in v["reasons"][:14]:
        L.append(f"- BLOCKER: {x}")
    for x in v["warnings"]:
        L.append(f"- warning: {x}")
    d = r["design"]
    L += ["", "## Design", f"- {d['dof']} DOF, template `{d['template']}`, height {d['height_m']} m, actuators {d['actuators']}",
          f"- packaging floors applied: {d['packaging_floors_applied'] or 'none'}"]
    if d["transmissions"]:
        L.append(f"- transmissions: {d['transmissions']}")
    m = r["mass"]
    L += ["", "## Mass", f"- component sum {m['total_kg']} kg: {m['breakdown_kg']}",
          f"- benchmark fit {m['sanity']['benchmark_fit_kg']} kg ({m['sanity']['status']}). {m['sanity']['note']}"]
    if "mass_cases" in r:
        mc = r["mass_cases"]
        L.append(f"- mass to first gate failure: **{mc['mass_to_first_gate_failure_kg']}**; cases: " + "; ".join(f"{k}: {c['total_kg']} kg worst margin {c['worst_margin']} ({'pass' if c['passes'] else 'FAIL'})" for k, c in mc["cases"].items()))
    L += ["", "## Frozen motions (identical for every candidate)", "| motion | valid | tether % BW | note |", "|---|---|---|---|"]
    for n, x in r["motions"].items():
        L.append(f"| {n} | {x['valid']} | {x['tether_mean_pct_bw']} | {x['invalid_reason'] or '; '.join(x['notes'][:1])} |")
    L += ["", "## Joints, worst margin first (margin = gate / value, < 1 fails)", "| joint | actuator | worst | peak/stall | rms/rated | envelope | overload | fails |", "|---|---|---|---|---|---|---|---|"]
    for x in r["joints_ranked_by_margin"][:14]:
        L.append(f"| {x['joint']} | {x['actuator']} | {x['worst_margin']} | {x['peak_frac_of_stall']} ({x['peak_motion']}) | {x['rms_over_rated']} ({x['rms_motion']}) | {x['util_max']} | {x['overload_run_ratio']} | {', '.join(x['fails'])} |")
    L += ["", "## Where reinforcement would help (per-joint utilisation, 1.0 = at the gate)"]
    for x in r["utilisation_ranking"][:8]:
        L.append(f"- {x['joint']} ({x['actuator']}): {x['utilisation']} driven by {x['driving_motion']}")
    p = r.get("power")
    if p:
        L += ["", "## Power", f"- pack {p['pack']['part']} {p['pack']['cells']}S {p['pack']['capacity_ah']} Ah ({p['pack']['energy_wh']} Wh, {p['pack']['mass_kg']} kg)",
              f"- average {p['average_power_w']} W -> runtime {p['runtime_min']} min (requirement {p['runtime_requirement_min']} min, ok={p['runtime_ok']})",
              f"- peak bus {p['bus']['peak_total_a']} A, sag {p['bus']['sag_at_peak_v']} V, fuse {p['bus']['fuse_a']} A, min voltage at far servo {p['bus']['min_voltage_at_far_servo_v']} V (servo minimum {p['bus']['servo_min_operating_v']} V)",
              f"- regulator: {p['regulator']}", f"- voltage rating: {p['voltage_rating']}"]
    t = r.get("thermal")
    if t:
        L += ["", "## Thermal", f"- primary gate (RMS <= rated): {'ok' if t['rms_gate_ok'] else 'FAIL'}",
              f"- 10-min mixed: max {t['T_10min_max_c']} C; steady {t['steady_max_c']} C; hot case (Rth x1.4, 40 C) {t['hot_steady_max_c']} C at {t['hottest_joint']}",
              f"- model validation: {t['thermal_model_validation']}"]
    c = r["cost"]
    L += ["", "## Cost", f"- typical ${c['total_usd']['typical']}, low ${c['total_usd']['low']}, high ${c['total_usd']['high']} (cap ${c['budget_cap_usd']}; within cap at high price: {c['within_cap_at_high']}); {c['unverified_lines']} unverified lines"]
    pr = r.get("push_recovery")
    if pr:
        L += ["", "## Push recovery (R10, a MUST)",
              f"Required: an ABSOLUTE impulse of **{pr['required_impulse_Ns']} N.s** (= {pr['required_dv_mps']} m/s on this {pr['mass_kg']} kg robot), PROVISIONAL pending the maintainer, "
              "recovered by ANY combination of strategies (ankle, hip, up to two steps with 0.15-0.35 s swing), standing and at mid single support of walk_forward. "
              "One gate: the largest recoverable impulse must be at least the requirement. The emergency demand may use the whole stall torque.",
              f"Hip strategy: {pr['hip_strategy']['note']} (limit {pr['hip_strategy']['trunk_speed_limit_rad_s']} rad/s).", "",
              "| scenario | strategy at the requirement | recoverable | peak/stall | envelope | steps (crouch) | largest recoverable N.s (m/s) | by | limited by |", "|---|---|---|---|---|---|---|---|---|"]
        for nm, c in pr["cases"].items():
            lr = c.get("largest_recoverable", {})
            pl = c.get("plan", {})
            L.append(f"| {nm} | {c.get('strategy')} | {c['recoverable_at_required']} | {round(c['peak_frac_of_stall'], 2) if 'peak_frac_of_stall' in c else '-'} {c.get('peak_joint', '')} | "
                     f"{round(c['util_max'], 2) if 'util_max' in c else '-'} | {pl.get('steps_taken')} ({pl.get('crouch_peak_mm')} mm) | "
                     f"{lr.get('largest_recoverable_Ns', '-')} ({lr.get('dv_mps', '-')}) | {lr.get('best_strategy', '-')} | {lr.get('limited_by', '-')} |")
            if not c["valid"]:
                L.append(f"|  | reason: {c['reason'][:200]} | | | | | | | |")
            for w in c.get("why", []):
                L.append(f"|  | {w} | | | | | | | |")
        if "gate" in pr:
            L.append(f"\n{pr['gate']}; the weakest scenario is {pr['largest_recoverable_min']['scenario']} at {pr['largest_recoverable_min']['impulse_Ns']} N.s ({pr['largest_recoverable_min']['dv_mps']} m/s).")
    if "bounds_sweep" in r:
        L += ["", "## Bounds sweep (tornado)", "| unknown | worst margin | delta | passes | failing |", "|---|---|---|---|---|"]
        for b in r["bounds_sweep"]:
            L.append(f"| {b['label']} | {b['worst_margin']} ({b['worst_joint']}) | {b['delta_vs_nominal']} | {b['passes']} | {'; '.join(b['failing'][:2])} |")
    if "monte_carlo" in r:
        mc = r["monte_carlo"]
        L += ["", f"## Monte Carlo (quasi-static dimensions only, {mc['samples']} samples)", f"- pass rate {mc['pass_rate']}; worst p95 peak {mc['worst_p95_peak']} at {mc['worst_joint_p95_peak']}; {mc['note']}"]
    if "stress_walks" in r:
        L += ["", "## Walk stress variants (informational)"]
        for k, s in r["stress_walks"].items():
            L.append(f"- {k}: " + (f"peak {s['worst_peak_frac_of_stall']} of stall at {s['joint']}, within gate: {s['peak_within_gate']}" if s["valid"] else f"INVALID ({s['reason']})"))
    if "servo_in_the_loop" in r:
        L += ["", "## Servo-in-the-loop (tracking, saturation, overload trips; NOT envelopes)"]
        for k, s in r["servo_in_the_loop"].items():
            if "rms_err_deg" not in s:
                L.append(f"- {k}: fell={s['fell']}, leg tracking max {s['leg_max_err_deg']} deg (rms {s['leg_rms_err_deg']}), saturation {s['saturation_fraction_max']} at {s['saturated_joint']}, trips {s['overload_trips']}, delivered in time: {s['delivered_in_time']} (servo delay {s['servo_delay_ms']} ms)")
                continue
            L.append(f"- {k}: rms err {s['rms_err_deg']} deg, max {s['max_err_deg']} deg, saturation {s['saturation_fraction_max']} at {s['saturated_joint']}, trips {s['overload_trips']}, min bus {s['min_bus_voltage_v']} V" + (f", grasp ok {s['grasp_ok']}" if "grasp_ok" in s else ""))
        L.append(f"- closed-loop sensitivity (needs closed loop, P5): {r.get('closed_loop_sensitivity')}")
    L += ["", "## Model quality"]
    for a, q in r["model_quality"].items():
        L.append(f"- {a}: {q['quality']} (score {q['score']}), bus {q['bus_v']} V vs model {q['vin_ref']} V -> {q['voltage_note']}")
    L += ["", "## Limitations"] + [f"- {x}" for x in r["limitations"]]
    L += ["", "## Constants and their provenance class", "| constant | class | source |", "|---|---|---|"]
    for p_ in r["provenance"]:
        L.append(f"| {p_['constant']} | {p_['class']} | {str(p_['source'])[:140].replace('|', '/')} |")
    return "\n".join(L) + "\n"
