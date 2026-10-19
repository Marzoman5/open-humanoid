"""Replay the two published Robonine thermal runs of an STS3215 12 V (research/actuators/feetech-sts3215/measured.yaml) through
our first-order thermal model. If the model cannot reproduce them, its thermal numbers are marked UNUSABLE in every report
(challenge-1 row 10): the primary thermal gate is then RMS torque <= the vendor-rated continuous torque.

Run 1: 15 kg.cm static hold (1 kg on a 15 cm lever): 48 C after 10 min, stable for more than an hour.
Run 2: +-90 deg oscillation at 15 kg.cm: 60 C after 50 min (starting from 48 C), 71 C after about 110 min in total.
Ambient, supply impedance, oscillation period and duty were NOT recorded. We assume 22 C ambient and a 4 s oscillation period;
the tolerance is +-8 K. The Rth of the model was derived from run 1, so run 1 is close to circular; run 2 is the real test.
"""
from __future__ import annotations

import math

import numpy as np

from ..actuators import ServoBank, ThermalBank, servo_spec, friction_budget

KGCM = 0.0980665
AMBIENT_ASSUMED_C = 22.0
OSC_PERIOD_ASSUMED_S = 4.0
TOLERANCE_K = 8.0


def _power(spec, tau: float, mean_abs_omega: float, vin: float = 12.0) -> float:
    bank = ServoBank([spec], 0.01)
    i = tau / bank.kt_cur[0]
    fl, d = friction_budget(bank.fr, np.array([tau]), np.array([-tau]), np.array([max(mean_abs_omega, 1e-9)]))
    fric = (fl[0] + d[0] * mean_abs_omega) * mean_abs_omega if mean_abs_omega > 0.05 else 0.0
    return float(i * i * bank.R_heat[0] + fric + 0.03 * vin * 0.5)


def replay(actuator: str = "sts3215-12v") -> dict:
    spec = servo_spec(actuator)
    tau = 15 * KGCM
    p_hold = _power(spec, tau, 0.0)
    mean_w = 4 * (math.pi / 2) / OSC_PERIOD_ASSUMED_S      # mean |w| of a +-90 deg sinusoid-like sweep, rad/s
    p_osc = _power(spec, tau, mean_w)
    tb = ThermalBank([spec], AMBIENT_ASSUMED_C)
    out = {"assumptions": {"ambient_c": AMBIENT_ASSUMED_C, "oscillation_period_s": OSC_PERIOD_ASSUMED_S, "tolerance_k": TOLERANCE_K,
                           "rth_k_per_w": spec.rth_k_per_w, "tau_s": spec.tau_th_s},
           "run1": {}, "run2": {}}
    T10 = None
    for t in range(1, 3601):
        tb.step(np.array([p_hold]), 1.0)
        if t == 600:
            T10 = float(tb.T[0])
    T60 = float(tb.T[0])
    out["run1"] = {"power_w": round(p_hold, 2), "T_10min_c": round(T10, 1), "T_60min_c": round(T60, 1),
                   "observed": {"T_10min_c": 48.0, "stable_for_1h": True},
                   "ok": bool(abs(T10 - 48.0) <= TOLERANCE_K and abs(T60 - T10) <= 5.0)}
    tb = ThermalBank([spec], AMBIENT_ASSUMED_C, t0_c=48.0)
    t50 = t110 = None
    for t in range(1, 111 * 60 + 1):
        tb.step(np.array([p_osc]), 1.0)
        if t == 50 * 60:
            t50 = float(tb.T[0])
    t110 = float(tb.T[0]) if True else None
    # observed: 60 C after 50 min starting from 48 C; 71 C after ~110 min TOTAL (taken here as 110 min of oscillation, generous)
    out["run2"] = {"power_w": round(p_osc, 2), "T_50min_c": round(t50, 1), "T_110min_c": round(t110, 1),
                   "observed": {"T_50min_c": 60.0, "T_110min_c": 71.0},
                   "ok": bool(abs(t50 - 60.0) <= TOLERANCE_K and abs(t110 - 71.0) <= TOLERANCE_K)}
    out["reproduces_both"] = bool(out["run1"]["ok"] and out["run2"]["ok"])
    out["thermal_numbers_usable"] = out["reproduces_both"]
    out["verdict"] = ("The first-order model reproduces both Robonine runs: its thermal numbers are usable (still one unit, ambient assumed)."
                      if out["reproduces_both"] else
                      "The first-order model does NOT reproduce both Robonine runs "
                      f"(run 1 ok={out['run1']['ok']}, run 2 ok={out['run2']['ok']}). Its thermal numbers are UNUSABLE as predictions; "
                      "they are shown as indicative only. The primary thermal gate is RMS torque <= vendor-rated continuous torque.")
    return out
