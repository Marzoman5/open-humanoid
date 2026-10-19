"""Control-loop compute budget (R8: everything runs on the onboard Pi 5, no PC).

Measures, per control cycle, the CPU time of estimator + safety + behaviour manager + gait planner + IK (everything except the HAL calls), for
standing, walking and the dance (the heaviest upper-body clip), then scales it to a Raspberry Pi 5.

The Pi 5 figure is an ESTIMATE, not a measurement (no Pi was available): the host/Pi single-thread ratio is taken from a user-set factor
(default 3.5: the Pi 5's Cortex-A76 at 2.4 GHz is roughly 3x slower than a current desktop core on Geekbench-6 single-core, 3-5x on small
numpy/Python loops where interpreter overhead dominates). It is a range, and it must be replaced by a measurement on the real board.
"""
from __future__ import annotations

import platform
import time

import numpy as np


def _cpu_name() -> str:
    try:
        if platform.system() == "Windows":
            import subprocess
            out = subprocess.run(["wmic", "cpu", "get", "name"], capture_output=True, text=True, timeout=10).stdout.split("\n")
            names = [x.strip() for x in out if x.strip() and x.strip() != "Name"]
            if names:
                return names[0]
    except Exception:  # noqa: BLE001
        pass
    return platform.processor() or platform.machine()


def _stats(rt) -> dict:
    a = np.array(rt.compute_ms[10:])
    return {"cycles": len(a), "mean_ms": round(float(a.mean()), 3), "p99_ms": round(float(np.percentile(a, 99)), 3), "max_ms": round(float(a.max()), 3)}


def bench(seconds: float = 20.0, pi_factor: float = 3.5, pi_factor_range: tuple = (3.0, 5.0)) -> dict:
    from .scenarios import make_sim
    out = {"host": {"cpu": _cpu_name(), "python": platform.python_version(), "machine": platform.machine()}, "pi5_factor_assumed": pi_factor,
           "pi5_factor_range": list(pi_factor_range), "cases": {}}
    cases = {}
    # standing
    rt, hal = make_sim()
    rt.compute_ms.clear()
    for _ in range(int(seconds * 100)):
        rt.step()
    cases["stand"] = _stats(rt)
    # walking
    rt, hal = make_sim()
    rt.compute_ms.clear()
    for _ in range(int(seconds * 100)):
        rt.client.velocity(0.1, 0, 0, ttl=0.3)
        rt.step()
    cases["walk"] = _stats(rt)
    # dance (pre-built clip: generation is offline work, cached in ClipStore)
    rt, hal = make_sim()
    rt.clips("dance")
    rt.client.behaviour("dance")
    rt.compute_ms.clear()
    for _ in range(int(min(seconds, 30) * 100)):
        rt.step()
    cases["dance"] = _stats(rt)
    for k, v in cases.items():
        v["pi5_est_mean_ms"] = round(v["mean_ms"] * pi_factor, 2)
        v["pi5_est_p99_ms"] = [round(v["p99_ms"] * f, 2) for f in pi_factor_range]
        v["pi5_est_load_100hz_pct"] = round(100 * v["mean_ms"] * pi_factor / 10.0, 1)
        v["pi5_est_load_100hz_p99_pct"] = [round(100 * v["p99_ms"] * f / 10.0, 1) for f in pi_factor_range]
    out["cases"] = cases
    out["note"] = ("Host numbers are measured (HAL calls excluded: on hardware they are bus transfers, ~6 ms of a 10 ms period at 1 Mbit, not CPU). "
                   "Pi 5 numbers are scaled by an assumed factor and are NOT measured. Clips (dance, pickup) are compiled offline; building the dance on the host takes ~10 s (casadi QP).")
    return out
