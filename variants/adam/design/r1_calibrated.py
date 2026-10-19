"""R1 feasibility on BOTH gate sets (ADR 0014): strict (datasheet, thresholds.yaml unchanged) and ODM-calibrated, per height, with the
tornado bounds and the benchmark-fit mass, for one or more concept candidates. Task T-20261019-36f9.

Run:  .venv/Scripts/python variants/adam/design/r1_calibrated.py variants/adam/concepts/R1-*.yaml --heights 0.55 0.60 [--no-bounds] [--pushmax]
Writes variants/adam/design/r1_results/<candidate>.json and .md (this script's own outputs; nothing under generated/ is touched).

What it does per (candidate, height), using ONLY the concept engine's own functions (openhumanoid.concept.evaluate / pushcheck):
  1. the height and the packaging floors [t0004, cad_foundation] (ankle 66 mm, knee 0-115, hip pitch -110/+40, ankle pitch -60/+25) are applied,
  2. the frozen gait set is swept (`evaluate.gait_sweep`, best strict worst-joint margin) and applied,
  3. nominal + every tornado bound of `evaluate._bounds` + the benchmark-fit mass are run with `run_bundle(..., pushes=True)`,
  4. per joint the strict margins come straight from the engine (`gate_joint_table`); the CALIBRATED margins relax ONLY the three ADR 0014
     categories by the measured Open Duck Mini factors (peak x1.52, RMS x1.94 against the 0.637 N.m label for the 7.4 V part / against the
     catalog rated figure for the others, envelope x1.18); overload time, motion validity, tether and R10 are NOT relaxed (same rule as
     `sweep.relaxed_feasibility`),
  5. R10: every scenario at the required impulse (the engine's one gate), plus the largest recoverable impulse at nominal with --pushmax.
Thresholds are not changed anywhere; the calibrated set is computed beside the strict one, as ADR 0014 section 2 requires.

CAVEAT (stated in every output): the ODM factors were measured on the 7.4 V STS3215 model; applying them to the 12 V STS3215 and to the
STS3250 assumes their real-vs-datasheet gaps are similar. Only the bench test (one 12 V + one 7.4 V STS3215) can confirm that.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np

from openhumanoid.concept import config, pushcheck as PC
from openhumanoid.concept import evaluate as EV
from openhumanoid.concept.robot import benchmark_mass_kg, load_concept

HERE = Path(__file__).resolve().parent
OUT = HERE / "r1_results"
# ADR 0014 section 2 (docs/decisions/0014-gate-calibration-known-robots.md); measured in variants/adam/generated/concept/calibration/odm_calibration.json
FACTORS = {"peak": 1.52, "rms": 1.94, "envelope": 1.18}
RMS_LABEL_7V4 = 0.637      # N.m, the label the ADR's 1.94 factor is measured against (Evelta); the catalog rated figure for the 7.4 V part is 0.49


def _cal_rows(b) -> dict:
    g_peak = config.gate("peak_torque_fraction_of_stall")
    g_rms = config.gate("rms_torque_vs_continuous")
    g_env = config.gate("envelope_utilisation_max")
    out = {}
    for n, r in b.rows.items():
        s = b.robot.servo[n]
        rated = float(s.rated_continuous_nm)
        rms_nm = r["rms_over_rated"] * rated
        base = RMS_LABEL_7V4 if b.robot.acts[n] == "sts3215-7v4" else rated
        m_peak = g_peak * FACTORS["peak"] / max(r["peak_frac_of_stall"], 1e-9)
        m_rms = g_rms * FACTORS["rms"] * base / max(rms_nm, 1e-9)
        m_env = g_env * FACTORS["envelope"] / max(r["util_max"], 1e-9)
        m_ovl = r["margin_overload"]
        fails = [k for k, m in (("peak", m_peak), ("rms", m_rms), ("envelope", m_env), ("overload_time", m_ovl)) if m < 1.0] + (["protection_trip"] if r["trips"] else [])
        out[n] = {"strict_worst": round(r["worst_margin"], 3), "strict_fails": r["fails"], "cal_peak": round(m_peak, 3), "cal_rms": round(m_rms, 3),
                  "cal_env": round(m_env, 3), "cal_overload": round(m_ovl, 3), "cal_worst": round(min(m_peak, m_rms, m_env, m_ovl), 3), "cal_fails": fails,
                  "peak_motion": r["peak_motion"], "rms_motion": r["rms_motion"]}
    return out


def _summ(b, label: str) -> dict:
    rows = _cal_rows(b) if b.rows else {}
    sw = min(rows.items(), key=lambda kv: kv[1]["strict_worst"]) if rows else (None, {"strict_worst": 0.0})
    cw = min(rows.items(), key=lambda kv: kv[1]["cal_worst"]) if rows else (None, {"cal_worst": 0.0})
    push = {k[len("push_"):]: bool(v.get("valid") and v.get("ok")) for k, v in b.push_rows.items()}
    inv = dict(b.invalid)
    inv_core = {k: v for k, v in inv.items() if not k.startswith("pickup_")}       # the 0.45 m-table pickup is a known planner gap (concept-engine.md)
    strict_ok = bool(rows) and not inv_core and all(not r["strict_fails"] for r in rows.values())
    cal_ok = bool(rows) and not inv_core and all(not r["cal_fails"] for r in rows.values())
    r10_ok = bool(push) and all(push.values())
    return {"label": label, "mass_kg": round(b.robot.total_mass, 3), "strict_worst": sw[1]["strict_worst"], "strict_worst_joint": sw[0],
            "cal_worst": cw[1]["cal_worst"], "cal_worst_joint": cw[0], "strict_joint_gates_pass": strict_ok, "cal_joint_gates_pass": cal_ok,
            "r10_at_required": push, "r10_pass": r10_ok, "invalid": {k: v[:100] for k, v in inv.items()},
            "strict_pass": strict_ok and r10_ok, "cal_pass": cal_ok and r10_ok,
            "cal_fails": {n: r["cal_fails"] for n, r in rows.items() if r["cal_fails"]}, "strict_fails": {n: r["strict_fails"] for n, r in rows.items() if r["strict_fails"]},
            "rows": rows}


def bounds_mods() -> list:
    t = config.thresholds()["uncertainty"]["tornado"]
    lo, hi = t["mass_structure"]["low"], t["mass_structure"]["high"]
    M = EV.Mods
    return [M(structure=lo, label=f"structure mass x{lo:g}"), M(structure=hi, label=f"structure mass x{hi:g}"),
            M(wiring=t["mass_wiring_electronics"]["low"], label="wiring/electronics x0.8"), M(wiring=t["mass_wiring_electronics"]["high"], label="wiring/electronics x1.5"),
            M(torque_model="linear", label="pessimistic linear torque-speed"), M(armature_dir=-1.0, label="armature low"), M(armature_dir=1.0, label="armature high"),
            M(stall_dir=-1.0, label="stall low"), M(stall_dir=1.0, label="stall high"), M(speed_factor=1.5, label="walking speed x1.5")]


def run(concept_path: str, h: float, *, bounds: bool = True, pushmax: bool = False, verbose: bool = True) -> dict:
    t0 = time.time()
    c = load_concept(concept_path)
    c = copy.deepcopy(c)
    c["height_m"] = float(h)
    c["packaging"] = ["t0004", "cad_foundation"]
    best, grows = EV.gait_sweep(c)
    c = EV.apply_gait(c, best)
    nom = EV.run_bundle(c, EV.Mods(), thermal=False, pushes=True)
    res = {"candidate": c["id"], "height_m": h, "gait": {k: best[k] for k in ("stance_knee_flex_deg", "step_time_s", "worst_margin")},
           "nominal": _summ(nom, "nominal"), "packaging_notes": nom.robot.spec.get("_floor_notes", []),
           "rom_clamps": [n for n, r in nom.refs.items() if r.meta.get("rom_clamped_from_deg")], "should": nom.should}
    if pushmax:
        res["largest_recoverable_Ns"] = {}
        for sc in [k[len("push_"):] for k in nom.push_rows]:
            lr = PC.largest_recoverable(nom.robot, nom.kin, nom.vin, sc, demand_iters=3)
            res["largest_recoverable_Ns"][sc] = {"Ns": lr.get("largest_recoverable_Ns"), "by": lr.get("best_strategy"), "limited_by": lr.get("limited_by")}
    if bounds:
        rows = []
        for m in bounds_mods():
            b = EV.run_bundle(c, m, thermal=False, pushes=True)
            s = _summ(b, m.label)
            s.pop("rows")
            rows.append(s)
        robot = nom.robot
        struct = robot.body.breakdown["structure_kg"]
        s_bm = max((benchmark_mass_kg(robot.height) - (robot.total_mass - struct)) / max(struct, 1e-6), 1.0)
        b = EV.run_bundle(c, EV.Mods(structure=s_bm, label="benchmark-fit mass"), thermal=False, pushes=True)
        s = _summ(b, f"benchmark-fit mass (structure x{s_bm:.2f})")
        s.pop("rows")
        rows.append(s)
        res["bounds"] = rows
        res["robust_strict"] = bool(res["nominal"]["strict_pass"] and all(r["strict_pass"] for r in rows))
        res["robust_cal"] = bool(res["nominal"]["cal_pass"] and all(r["cal_pass"] for r in rows))
        res["bounds_failing_cal"] = [r["label"] for r in rows if not r["cal_pass"]]
        res["bounds_failing_strict"] = [r["label"] for r in rows if not r["strict_pass"]]
        res["min_cal_worst_over_bounds"] = round(min([res["nominal"]["cal_worst"]] + [r["cal_worst"] for r in rows]), 3)
    res["seconds"] = round(time.time() - t0, 1)
    if verbose:
        n = res["nominal"]
        print(f"{c['id']} {h:.2f} m  {n['mass_kg']} kg  gait {best['stance_knee_flex_deg']}/{best['step_time_s']}  strict {n['strict_worst']} ({n['strict_worst_joint']})  "
              f"cal {n['cal_worst']} ({n['cal_worst_joint']})  R10 {n['r10_at_required']}  strict_pass {n['strict_pass']}  cal_pass {n['cal_pass']}  "
              f"robust_cal {res.get('robust_cal')}  failing_cal {res.get('bounds_failing_cal')}  [{res['seconds']} s]", flush=True)
    return res


def _js(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def to_md(rs: list[dict]) -> str:
    L = ["<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->",
         f"# R1 feasibility, strict vs ODM-calibrated gates: {rs[0]['candidate']}", "",
         "Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. "
         "The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.", "",
         "| height | mass kg | gait | strict worst (joint) | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | calibrated PASS | robust (cal) across bounds | bounds failing (cal) | min cal margin over bounds |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rs:
        n = r["nominal"]
        p = n["r10_at_required"]
        ps = "/".join("ok" if p.get(k) else "FAIL" for k in ("stand_fwd", "stand_lat", "walk_fwd", "walk_lat_out", "walk_lat_in"))
        L.append(f"| {r['height_m']:.2f} | {n['mass_kg']} | {r['gait']['stance_knee_flex_deg']:.0f} deg / {r['gait']['step_time_s']} s | {n['strict_worst']} ({n['strict_worst_joint']}) | "
                 f"{n['cal_worst']} ({n['cal_worst_joint']}) | {ps} | {n['strict_pass']} | {n['cal_pass']} | {r.get('robust_cal')} | {'; '.join(r.get('bounds_failing_cal', [])) or '-'} | {r.get('min_cal_worst_over_bounds')} |")
    for r in rs:
        L += ["", f"## {r['height_m']:.2f} m", ""]
        if r.get("largest_recoverable_Ns"):
            L.append("Largest recoverable impulse at nominal (N.s): " + ", ".join(f"{k} {v['Ns']}" for k, v in r["largest_recoverable_Ns"].items()))
            L.append("")
        if r["nominal"]["invalid"]:
            L.append("Invalid motions: " + "; ".join(f"{k}: {v}" for k, v in r["nominal"]["invalid"].items()))
            L.append("")
        L.append("| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |")
        L.append("|---|---|---|---|---|---|---|---|")
        for b in [r["nominal"]] + r.get("bounds", []):
            L.append(f"| {b['label']} | {b['mass_kg']} | {b['strict_worst']} | {b['cal_worst']} ({b['cal_worst_joint']}) | {b['r10_pass']} | {b['strict_pass']} | {b['cal_pass']} | "
                     f"{'; '.join(f'{k}: {v}' for k, v in list(b['cal_fails'].items())[:3]) or '-'}{' R10: ' + ','.join(k for k, v in b['r10_at_required'].items() if not v) if not b['r10_pass'] else ''} |")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("concepts", nargs="+")
    ap.add_argument("--heights", nargs="+", type=float, default=[0.55, 0.60])
    ap.add_argument("--no-bounds", action="store_true")
    ap.add_argument("--pushmax", action="store_true")
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    for cp in a.concepts:
        rs = [run(cp, h, bounds=not a.no_bounds, pushmax=a.pushmax) for h in a.heights]
        cid = rs[0]["candidate"] + (f"-{a.tag}" if a.tag else "")
        (OUT / f"{cid}.json").write_text(json.dumps(rs, indent=1, default=_js), encoding="utf-8")
        (OUT / f"{cid}.md").write_text(to_md(rs), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
