"""L5c parallelogram: play (backlash) model and ANALYTIC strength checks of the linkage parts (T-20261019-4ab5).

The full strength gate (FEA + print-orientation derating, task T-20261019-a026, openhumanoid/cad/strength/) had not merged when this ran;
these are hand checks in the research/methods/d method and are flagged for that gate.

Geometry comes from l5c.P; DFM numbers from openhumanoid/cad/dfm.yaml; materials from research/methods/print_materials.yaml (PETG
Polymaker PolyMax XY 37.9 / Z 29.4 MPa, E 1684 MPa). Other constants carry their source inline.

Run:  .venv/Scripts/python variants/adam/cad/linkages/analysis.py [--knee-peak 2.1 --ankle-peak 1.3]   (engine peak demands, N.m)
Out:  variants/adam/cad/linkages/results/analysis.{json,md}
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import l5c  # noqa: E402
from openhumanoid.cad import dfm  # noqa: E402

OUT = HERE / "results"
MAT = yaml.safe_load((REPO / "research/methods/print_materials.yaml").read_text(encoding="utf-8"))["materials"]
PETG = MAT["PETG"]
C = {
    "stall_knee_nm": (4.903, "catalog/actuators/sts3250-12v.yaml (50 kg.cm @ 12 V)"),
    "stall_ankle_nm": (2.94, "catalog/actuators/sts3215-12v.yaml datasheet 12 V model (concept engine)"),
    "bearing_C0r_n": (218.0, "NSK 623ZZ basic static load rating (vendor listings of the NSK datasheet, 2026-10-19; VXB 230, budget 180)"),
    "bearing_Cr_n": (695.0, "NSK 623ZZ basic dynamic load rating (same)"),
    "bearing_radial_play_mm": ((0.005, 0.010), "miniature ball bearing radial internal clearance, normal class MC3 5-10 um (miniature bearing catalogue class table; recalled, conf vendor)"),
    "al6061_sy_mpa": (276.0, "6061-T6 yield, ASM / MatWeb standard value"),
    "al6061_E_mpa": (68900.0, "6061-T6 modulus, ASM"),
    "screw_129_rm_mpa": (1220.0, "ISO 898-1 class 12.9 tensile strength"),
    "screw_shear_ratio": (0.6, "shear ~0.6 Rm (common design rule)"),
    "m3_minor_d_mm": (2.387, "ISO 724 M3 minor diameter d3"),
    "m3_major_mm": ((2.874, 2.980), "ISO 965 6g M3 major diameter range"),
    "bore_623_mm": ((2.992, 3.000), "ISO 492 normal tolerance, bore 3 mm: 0/-8 um"),
    "mu_clamp": (0.15, "steel-on-steel dry friction, conservative"),
    "preload_n": (1200.0, "M3 at ~0.9 N.m (K 0.2 -> 1.5 kN), derated for the DIN 439 thin nut (04 class); ESTIMATE, set the torque on the bench"),
    "fall_drop_m": (0.10, "fall case F1: step-down / stumble drop onto the feet (research/methods/d sec 3, h = 0.10 m)"),
    "fall_stop_mm": (5.0, "stopping distance (TPU sole + compliance) -> n = h/d (research/methods/d sec 3)"),
    "mass_kg": (4.0, "R1 / v2 nominal mass at 0.55 m (engine report)"),
    "sf_static": (3.0, "dfm.yaml orientation.safety_factor_on_z (applied to printed parts in the weakest direction)"),
    "cyclic_frac": (0.10, "dfm.yaml orientation.cyclic_stress_fraction_of_uts"),
}


def v(k):
    return C[k][0]


def crank_bending(T, r, r_hub, r_pin, t):
    """Max bending stress (MPa) in a tapered crank arm (convex hull of the hub disc r_hub and the pin disc r_pin, plate thickness t), torque T
    (N.m) at the joint, coupler force perpendicular component T/r. Section at distance s from the pin centre has width w(s) = 2 (r_pin +
    (r_hub - r_pin) s / r) and moment M = (T / r) s. Checked from the pin boss edge to the hub edge."""
    Fp = T / (r / 1000.0)
    worst = (0.0, 0.0)
    for i in range(201):
        s = r_pin + (r - r_hub - r_pin) * i / 200.0
        w = 2 * (r_pin + (r_hub - r_pin) * s / r)
        M = Fp * s                      # N.mm
        sig = 6 * M / (t * w * w)
        if sig > worst[0]:
            worst = (sig, s)
    return worst


def joint(name, T_stall, T_peak, r, th_lo, th_hi, L_coupler):
    P = l5c.P
    s_lo = min(math.sin(math.radians(th_lo)), math.sin(math.radians(th_hi)))
    out = {"joint": name, "r_mm": r, "theta_window_deg": [th_lo, th_hi], "min_sin_theta": round(s_lo, 3), "coupler_len_mm": L_coupler}
    # ---------------------------------------------------------------- loads
    m, g = v("mass_kg"), 9.81
    n_fall = v("fall_drop_m") / (v("fall_stop_mm") / 1000.0)
    # F1: drop onto both feet, stance knee 40 deg -> knee moment arm = shank-to-force-line offset ~ shank * sin(20 deg); ankle arm ~ foot COP offset 20 mm
    arm = {"knee": 0.0825 * math.sin(math.radians(20.0)), "ankle": 0.020}[name]
    T_fall = (m * g * n_fall / 2.0) * arm
    cases = {"stall at the window end": (T_stall, s_lo), "engine peak (walk/dance/push), at the window end": (T_peak, s_lo) if T_peak else None,
             "fall F1 (0.10 m drop, n = %.0f), stance theta" % n_fall: (T_fall, math.sin(math.radians({"knee": 75.0, "ankle": 97.5}[name])))}
    rows = {}
    for cname, cv in cases.items():
        if not cv:
            continue
        T, sn = cv
        F = T / (r / 1000.0 * sn)
        A_net = (P["coupler_w"] - 3.2) * P["coupler_t"]
        I_out = P["coupler_w"] * P["coupler_t"] ** 3 / 12.0
        P_euler = math.pi ** 2 * v("al6061_E_mpa") * I_out / L_coupler ** 2
        A_pin = math.pi / 4 * v("m3_minor_d_mm") ** 2
        b = {"F_coupler_n": round(F, 1),
             "coupler_net_tension_mpa": round(F / A_net, 1), "coupler_SF_yield_net": round(v("al6061_sy_mpa") / (F / A_net), 2),
             "coupler_bearing_mpa": round(F / (3.0 * P["coupler_t"]), 1), "coupler_SF_bearing (1.5 Sy)": round(1.5 * v("al6061_sy_mpa") / (F / (3.0 * P["coupler_t"])), 2),
             "coupler_euler_n (pinned, out of plane)": round(P_euler, 0), "coupler_SF_buckling": round(P_euler / F, 2),
             "pin_shear_mpa (single shear, minor d)": round(F / A_pin, 1), "pin_SF_shear": round(v("screw_129_rm_mpa") * v("screw_shear_ratio") / (F / A_pin), 2),
             "bearing_load_each_n (2 per pin)": round(F / 2, 1), "bearing_load_over_C0r": round(F / 2 / v("bearing_C0r_n"), 2),
             "seat_pressure_mpa (F/2 over OD x w)": round(F / 2 / (10.0 * 4.0), 2),
             "seat_SF_vs_PETG_xy/3": round(PETG["tensile_xy"] / v("sf_static") / (F / 2 / 40.0), 2),
             "clamp_slip": bool(F > v("mu_clamp") * v("preload_n") * 2)}
        sig = max(crank_bending(T, r, rh, P["pin_boss_r"], P["plate_t"])[0] for rh in (12.0, P["axle_boss_r"]))   # input (horn hub 12) and output (axle boss) cranks
        b["crank_bending_mpa (tapered arm, plate 4.3)"] = round(sig, 1)
        b["crank_SF_vs_PETG_xy"] = round(PETG["tensile_xy"] / sig, 2)
        rows[cname] = b
    out["cases"] = rows
    # ---------------------------------------------------------------- play: lost motion along the coupler -> output angle
    br_lo, br_hi = v("bearing_radial_play_mm")
    mj_lo, mj_hi = v("m3_major_mm")
    bo_lo, bo_hi = v("bore_623_mm")
    screw_bore = (max(bo_lo - mj_hi, 0.0), bo_hi - mj_lo)          # diametral, when the clamp slips
    seat_loose = 2 * dfm.clearance("press")                          # one press-fit step lost (seat creep / mis-tuned): 0.1 mm diametral
    k_seat = PETG["modulus_xy"] * 8.0                                 # N/mm, radial stiffness of two 4 mm PETG seats ~ E * total width (ESTIMATE)
    per_pin = {
        "best (clamped, tuned seats)": br_lo + 0.0,
        "nominal (clamped, bearing play mid, seat compliance at the engine peak)": (br_lo + br_hi) / 2 + (rows.get("engine peak (walk/dance/push), at the window end", rows["stall at the window end"])["F_coupler_n"] / k_seat),
        "worst (clamp slips: screw in bore, seat one press step loose)": br_hi + screw_bore[1] + seat_loose,
    }
    axle = {"best (clamped, tuned seats)": br_lo, "nominal (clamped, bearing play mid, seat compliance at the engine peak)": (br_lo + br_hi) / 2,
            "worst (clamp slips: screw in bore, seat one press step loose)": br_hi + screw_bore[1] + seat_loose}
    play = {}
    for k in per_pin:
        lost = 2 * per_pin[k] + axle[k]                               # two coupler pins + the joint axle (the servo's own output play is in the servo backlash)
        play[k] = {"lost_motion_mm": round(lost, 4), "deg_mid (sin 1)": round(math.degrees(lost / r), 3), "deg_window_end": round(math.degrees(lost / (r * s_lo)), 3)}
    out["play"] = play
    out["play_inputs"] = {"bearing_radial_play_mm": [br_lo, br_hi], "screw_in_bore_diametral_mm": [round(x, 3) for x in screw_bore],
                          "seat_loose_mm": seat_loose, "seat_stiffness_n_per_mm (ESTIMATE)": k_seat}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--knee-peak", type=float, default=None, help="engine peak knee demand, N.m")
    ap.add_argument("--ankle-peak", type=float, default=None, help="engine peak ankle-pitch demand, N.m")
    a = ap.parse_args(argv)
    P = l5c.P
    asm = l5c.build()
    res = {"constants": {k: {"value": x[0], "source": x[1]} for k, x in C.items()},
           "knee": joint("knee", v("stall_knee_nm"), a.knee_peak, P["r_knee"], P["theta0_knee"] + l5c.RANGES["knee"][0], P["theta0_knee"] + l5c.RANGES["knee"][1], asm.meta["d_knee"]),
           "ankle": joint("ankle", v("stall_ankle_nm"), a.ankle_peak, P["r_ankle"], P["theta0_ankle"] + l5c.RANGES["ankle_pitch"][0],
                          P["theta0_ankle"] + l5c.RANGES["ankle_pitch"][1], asm.meta["d_ankle"])}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "analysis.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    L = ["<!-- written by variants/adam/cad/linkages/analysis.py (T-20261019-4ab5); re-run, do not edit -->", "# L5c linkage: analytic strength and play", "",
         "Hand checks (research/methods/d); the FEA strength gate (T-20261019-a026) had not merged. SF targets: printed parts 3 on the weakest direction "
         "(the crank plates print flat, so the coupler load is in the XY plane), metal parts yield/shear SF >= 1.5, bearings static load <= C0r.", ""]
    for j in ("knee", "ankle"):
        r = res[j]
        L += [f"## {j}: r {r['r_mm']} mm, theta {r['theta_window_deg']} deg (min sin {r['min_sin_theta']}), coupler {r['coupler_len_mm']} mm", "",
              "| check | " + " | ".join(r["cases"]) + " |", "|---|" + "---|" * len(r["cases"])]
        keys = list(next(iter(r["cases"].values())).keys())
        for k in keys:
            L.append(f"| {k} | " + " | ".join(str(c[k]) for c in r["cases"].values()) + " |")
        L += ["", "| play case | lost motion mm | added backlash deg (mid range) | at the window end |", "|---|---|---|---|"]
        for k, p in r["play"].items():
            L.append(f"| {k} | {p['lost_motion_mm']} | {p['deg_mid (sin 1)']} | {p['deg_window_end']} |")
        L.append("")
    (OUT / "analysis.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
