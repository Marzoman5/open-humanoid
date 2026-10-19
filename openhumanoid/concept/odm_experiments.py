"""Open Duck Mini calibration experiments (a), (b), (c) and the structure-mass back-out. See `calibration.py` for the licence note.

Every experiment ends in the same per-gate numbers (worst joint over the walking window, legs only), so the three can be compared:

  peak/stall      100 ms moving-average |tau| over the 7.4 V datasheet stall (1.912 N.m)           gate <= 0.70
  rms/rated 0.49  RMS |tau| over the vendor rated continuous torque, 0.49 N.m (Seeed)               gate <= 1.0
  rms/rated 0.64  the same with the contested 0.637 N.m (Evelta)                                     gate <= 1.0
  envelope        |tau| over the torque available at the joint speed (DC law, 7.4 V)                gate <= 0.90
  overload        longest run above 70% of stall over half the protection time (1 s)               gate <= 1.0
  speed           peak joint speed over the 7.4 V no-load speed (not a gate; why the envelope fails)

Demand is the minimum-torque inverse dynamics of `mintorque.py` for all three (no tether, no stability needed) and, where the frozen gait
is playable on the model, the ideal-PD harness too. NO GATE THRESHOLD IS CHANGED: the factors are measurements for the commander's ADR.
"""
from __future__ import annotations

import copy
import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from . import calibration as C, config, envelopes as E
from .mintorque import min_torque_demand
from .motions import walk as W
from .odm_reference import OdmGround, OdmPoly, odm_reference
from .odm_walk import ExternalKin

VIN = 7.4
GATES = {"peak_frac_of_stall": 0.70, "rms_over_rated_0.49": 1.0, "rms_over_rated_0.64": 1.0, "envelope_util": 0.90, "overload_run_ratio": 1.0}
LEG_PREFIX = ("hip", "knee", "ankle")


def gate_values(robot, dem, window=None) -> dict:
    """Worst leg joint of each gate quantity for one motion's demand."""
    vin = np.full(len(robot.names), VIN)
    m = E.joint_metrics(robot, dem, vin)
    leg = [i for i, n in enumerate(robot.names) if n.split("_")[0] in LEG_PREFIX]
    half_prot = config.value("overload_protection.gate_fraction_of_protection_time")
    sp = robot.servo[robot.names[leg[0]]]
    out = {
        "peak_frac_of_stall": float(m["peak_frac_stall"][leg].max()),
        "rms_over_rated_0.49": float(m["rms_nm"][leg].max() / 0.49),
        "rms_over_rated_0.64": float(m["rms_nm"][leg].max() / 0.637),
        "envelope_util": float(m["util_max"][leg].max()),
        "overload_run_ratio": float((m["run_above70_s"][leg] / (half_prot * m["prot_time_s"][leg])).max()),
        "speed_over_noload": float(m["omega_peak"][leg].max() / float(sp.noload(VIN))),
        "peak_nm_max": float(m["peak_nm"][leg].max()),
        "rms_nm_max": float(m["rms_nm"][leg].max()),
        "worst_joint_peak": robot.names[leg[int(np.argmax(m["peak_frac_stall"][leg]))]],
    }
    return out


def _force_playable(ref):
    if not ref.feasible:
        ref.meta["forced_infeasible_notes"] = list(ref.notes)
        ref.feasible = True
    return ref


def frozen_walk(kin, step_time: float, zmp_inboard: float = 0.0):
    """The frozen walk (0.10 m/s, 15 mm clearance, 20% double support) at one step time of the frozen set."""
    return W.walk(kin, "forward", step_time=step_time, zmp_inboard=zmp_inboard)


def exp_a(odm_dir, commands=((0.148, 0.0, 0.0), (0.074, 0.0, 0.0)), harmonics: int = 6) -> dict:
    """(a) ODM's own model with ODM's own reference motion (smoothed to `harmonics` Fourier harmonics: the raw polynomial fit has end-point
    oscillation). Demand by minimum-torque inverse dynamics; the PD harness cannot hold this reference (it is an RL imitation target)."""
    robot = C.load_odm(odm_dir, relax_ranges=True)
    poly = OdmPoly(Path(odm_dir) / C.ODM_POLY)
    home = OdmGround(robot).home_q()
    out = {"model": "Open Duck Mini MJCF, its own armature 0.027, 7.4 V STS3215 servo model, ranges relaxed so the replay can follow the reference (its knee swings to ~115 deg, past the +-90 deg of the MJCF)",
           "reference": f"polynomial fit, period {poly.period} s, smoothed to {harmonics} harmonics", "commands": {}}
    for cmd in commands:
        ref = odm_reference(robot, poly, cmd, n_periods=8, harmonics=harmonics)
        dm = min_torque_demand(robot, ref, stand_pose=home)
        g = gate_values(robot, dm)
        raw = odm_reference(robot, poly, cmd, n_periods=8, harmonics=None)
        gr = gate_values(robot, min_torque_demand(robot, raw, stand_pose=home))
        out["commands"][f"dx={ref.meta['table_key'][0]}"] = {
            "table_key": ref.meta["table_key"], "mean_speed_mps": round(ref.meta["mean_speed_mps"], 3), "step_time_s": round(poly.period / 2, 3),
            "gates_smoothed": g, "gates_raw_polynomial": gr, "base_residual_bw_mean": round(dm.assist_mean, 4), "friction_cone_violations": round(dm.friction_cone_violations, 3)}
    return out


def exp_b(odm_dir, flexes=(77.0, 40.0), step_times=(0.25, 0.35, 0.5), inboards=(0.0, 0.03, 0.05)) -> dict:
    """(b) the frozen gait on ODM's MJCF with numerical IK. The ZMP target moves towards the midline by `inboard` (ODM's stance is 163 mm
    wide with the legs knock-kneed: the frozen foot-centre ZMP needs 25+ deg of hip roll, past its +-25 deg). Each combination is run; the
    best FEASIBLE one (fewest IK / range failures, then the smallest worst gate) is the answer."""
    base = C.load_odm(odm_dir)
    rows = []
    for fx in flexes:
        robot = replace(base, spec={"locomotion": {"walk": {"stance_knee_flex_deg": fx}}, "id": "odm"})
        kin = ExternalKin(robot)
        for st in step_times:
            for zi in inboards:
                t0 = time.time()
                ref = frozen_walk(kin, st, zi)
                bad = int(sum("unreachable" in n or "violation" in n for n in ref.notes))
                nbad_ik = 0
                for n in ref.notes:
                    if "unreachable at" in n:
                        nbad_ik = int(n.split("unreachable at ")[1].split(" of")[0])
                ranges = [n for n in ref.notes if "violation" in n]
                _force_playable(ref)
                dm = min_torque_demand(robot, ref, stand_pose=OdmGround(robot).home_q())
                row = {"stance_knee_flex_deg": fx, "step_time_s": st, "zmp_inboard_m": zi, "ik_failed_samples": nbad_ik, "range_violation": ranges[0][:160] if ranges else "",
                       "gates": gate_values(robot, dm), "base_residual_bw_mean": round(dm.assist_mean, 4), "seconds": round(time.time() - t0, 1)}
                rows.append(row)
    def key(r):
        return (r["ik_failed_samples"] > 0, bool(r["range_violation"]), r["gates"]["peak_frac_of_stall"])
    best = min(rows, key=key)
    return {"combos": rows, "best": best}


def odm_like_concept(path) -> dict:
    from .robot import load_concept
    return load_concept(path)


def exp_c(concept_path, flexes=(77.0, 40.0), step_times=(0.25, 0.35, 0.5), inboards=(0.0, 0.03)) -> dict:
    """(c) the frozen gait on the ODM-like concept built by OUR generator (ODM's leg lengths, foot, stance width, mass, 5-DOF legs)."""
    from .robot import build_robot
    from .kin import RobotKin
    rows = []
    c0 = odm_like_concept(concept_path)
    for fx in flexes:
        for st in step_times:
            for zi in inboards:
                c = copy.deepcopy(c0)
                c["locomotion"]["walk"]["stance_knee_flex_deg"] = fx
                c["gait"] = {"step_time_s": st}
                robot = build_robot(c)
                kin = RobotKin(robot)
                ref = frozen_walk(kin, st, zi)
                feas = ref.feasible
                notes = [n for n in ref.notes if "unreachable" in n or "violation" in n]
                _force_playable(ref)
                dm = min_torque_demand(robot, ref)
                pd = E.ideal_demand(robot, ref)
                rows.append({"stance_knee_flex_deg": fx, "step_time_s": st, "zmp_inboard_m": zi, "feasible": bool(feas), "notes": [n[:140] for n in notes],
                             "gates_mintorque": gate_values(robot, dm), "pd_harness": {"valid": pd.valid, "reason": pd.invalid_reason[:100], "tether_mean_bw": round(pd.assist_mean, 4),
                                                                                       "gates": gate_values(robot, pd) if pd.valid else None},
                             "base_residual_bw_mean": round(dm.assist_mean, 4), "total_mass_kg": round(robot.total_mass, 3)})
    def key(r):
        return (not r["feasible"], r["gates_mintorque"]["peak_frac_of_stall"])
    return {"combos": rows, "best": min(rows, key=key)}


def structure_backout(odm_dir, duck_concept_path) -> dict:
    """Row 11: ODM's non-servo structure mass, backed out of the MJCF total, against the engine's 6.4 kg/m^3 * h^3 at 0.42 m."""
    from .robot import build_robot
    robot = C.load_odm(odm_dir)
    total = robot.total_mass
    n_servo = 14
    servo_kg = n_servo * robot.servo["knee_l"].mass_kg
    duck = build_robot(duck_concept_path)
    mb = duck.mass_breakdown
    onboard, wiring, misc = mb["onboard_parts_kg"], mb["wiring_kg"], mb["electronics_misc_kg"]
    non_servo = total - servo_kg
    structure = non_servo - onboard - wiring - misc
    nominal = 6.4 * 0.42 ** 3                           # the engine nominal BEFORE the recentring (the concepts now carry the ODM-implied coefficient)
    coef = structure / 0.42 ** 3
    return {"odm_total_kg": round(total, 3), "servos": n_servo, "servo_kg_each": robot.servo["knee_l"].mass_kg, "servo_total_kg": round(servo_kg, 3), "non_servo_kg": round(non_servo, 3),
            "electronics_wiring_estimate_kg": round(onboard + wiring + misc, 3), "electronics_note": "catalog masses of the same parts as the duck-like concept (Pi Zero 2 W, microSD, bus adapter, IMU, 2S pack, buck, switch, wiring) + 0.12 kg misc: an ESTIMATE (ODM publishes no mass breakdown)",
            "structure_implied_kg": round(structure, 3), "engine_nominal_structure_kg_at_0.42m": round(nominal, 3), "engine_coefficient_kg_per_m3": 6.4,
            "implied_coefficient_kg_per_m3": round(coef, 2), "gap_factor": round(structure / nominal, 2),
            "duck_like_non_servo_kg_before": round(duck.total_mass - 14 * 0.055 - (duck.body.breakdown["structure_kg"] - nominal), 3), "recentre_if_gap_above": 1.5,
            "recentre": bool(structure / nominal > 1.5)}


def run_all(odm_dir, concepts_dir, out_dir=None, quick: bool = False) -> dict:
    concepts_dir = Path(concepts_dir)
    res = {"licence_note": "Open Duck Mini's Playground and reference-motion repositories have NO LICENSE: read from a scratch folder at run time, nothing copied or committed; only derived numbers are recorded here",
           "gates": GATES, "servo": C.ODM_SERVO}
    res["odm_facts"] = C.load_odm(odm_dir).facts
    res["structure_mass"] = structure_backout(odm_dir, concepts_dir / "duck-like-0p42-2s-sts3215.yaml")
    res["a_own_reference"] = exp_a(odm_dir)
    res["b_frozen_on_odm"] = exp_b(odm_dir, step_times=(0.25, 0.5), inboards=(0.0, 0.04)) if quick else exp_b(odm_dir)
    duck = concepts_dir / "duck-like-0p42-2s-sts3215.yaml"
    res["d_old_duck_like_check"] = exp_c(duck, flexes=(40.0, 30.0), step_times=(0.35, 0.5), inboards=(0.0,)) if quick else exp_c(duck, flexes=(45.0, 40.0, 30.0, 20.0), inboards=(0.0,))
    res["c_frozen_on_odm_like"] = exp_c(concepts_dir / "odm-like-0p42-5dof.yaml", step_times=(0.25, 0.5), inboards=(0.0,)) if quick else exp_c(concepts_dir / "odm-like-0p42-5dof.yaml")
    sts = C.servo_spec(C.ODM_SERVO)
    res["odm_sim_vs_datasheet"] = {"odm_sim_forcerange_nm": 3.23, "datasheet_stall_7v4_nm": float(sts.stall_nm_ref), "ratio": round(3.23 / float(sts.stall_nm_ref), 2),
                                   "note": "ODM's training sim lets each servo deliver 3.23 N.m (and kp 13.37 N.m/rad); the 7.4 V datasheet stall the gates use is 1.912 N.m"}
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "odm_calibration.json").write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
    return res


def to_markdown(res: dict) -> str:
    """The per-gate calibration table and the interpretation inputs."""
    a = res["a_own_reference"]["commands"]
    ka = next(k for k in a if "0.148" in k)
    a_fast = a[ka]["gates_smoothed"]
    b = res["b_frozen_on_odm"]["best"]
    c = res["c_frozen_on_odm_like"]["best"]
    d = res["d_old_duck_like_check"]["best"]
    cols = [("peak_frac_of_stall", "peak / stall (100 ms)"), ("rms_over_rated_0.49", "RMS / rated 0.49"), ("rms_over_rated_0.64", "RMS / rated 0.64"),
            ("envelope_util", "torque-speed envelope"), ("overload_run_ratio", "overload run (70% stall)"), ("speed_over_noload", "speed / no-load (not a gate)")]
    L = ["# Open Duck Mini calibration (challenge-2 rows 1 and 11)", "", res["licence_note"] + ".", "",
         "Walking gates, worst LEG joint, 7.4 V STS3215 model (stall 1.912 N.m, rated 0.49 / 0.637 N.m), ODM's own armature 0.027 where its MJCF is used. "
         "No gate threshold is changed. 'a/gate' = value / gate = how much looser the gate would have to be for that robot-and-gait to pass.", "",
         "| gate | threshold | (a) ODM own reference | (b) frozen gait on ODM MJCF | (c) frozen gait on ODM-like (our generator) | (d) old duck-like check | a/gate | b/gate | c/gate | b/a (gait) | c/b (model) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, nm in cols:
        thr = GATES.get(k)
        va, vb, vc, vd = a_fast[k], b["gates"][k], c["gates_mintorque"][k], d["gates_mintorque"][k]
        f = (lambda v: f"{v / thr:.2f}") if thr else (lambda v: "-")
        L.append(f"| {nm} | {thr if thr else '-'} | {va:.2f} | {vb:.2f} | {vc:.2f} | {vd:.2f} | {f(va)} | {f(vb)} | {f(vc)} | {vb / va:.2f} | {vc / vb:.2f} |")
    L += ["", "Chosen combinations (best feasible):",
          f"- (a) command dx=0.148 (snapped to {a[ka]['table_key']}), step time 0.27 s, mean speed {a[ka]['mean_speed_mps']} m/s, smoothed to 6 harmonics; knee flexion about 77 deg",
          f"- (b) flex {b['stance_knee_flex_deg']} deg, step time {b['step_time_s']} s, ZMP {b['zmp_inboard_m']} m inboard, IK failures {b['ik_failed_samples']}",
          f"- (c) flex {c['stance_knee_flex_deg']} deg, step time {c['step_time_s']} s, ZMP {c['zmp_inboard_m']} m inboard, feasible {c['feasible']}",
          f"- (d) flex {d['stance_knee_flex_deg']} deg, step time {d['step_time_s']} s, feasible {d['feasible']}", "",
          "ODM's training sim vs the gates: " + res["odm_sim_vs_datasheet"]["note"], "",
          "Structure mass back-out (row 11): " + json.dumps(res["structure_mass"]), "", "ODM facts measured from its MJCF: " + json.dumps(res["odm_facts"])]
    return "\n".join(L) + "\n"
