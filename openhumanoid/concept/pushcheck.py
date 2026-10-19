"""R10 push-recovery evaluation: the requirement-level check and the largest recoverable impulse, per scenario.

A scenario is RECOVERABLE at impulse J when some combination of strategies (`motions/push.py`) has a plan that recovers AND a
kinematically feasible Reference (leg reach, CAD-limited joint ranges) AND an actuator demand inside the emergency limits (peak
<= the whole stall torque, torque-speed utilisation <= 1.0, no fall, tether < 1%). The gate is one number per scenario:
largest recoverable impulse >= required impulse.  The largest recoverable impulse is found by scanning/bisecting on J over every
strategy (monotone in J per strategy), plan level first and the (expensive) MuJoCo demand only where it can change the answer.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config, envelopes as E
from .kin import Reference, RobotKin
from .motions import push as PU
from .playback import PlayConfig
from .robot import Robot

J_CAP_NS = 3.0                      # search ceiling; a result at the ceiling is reported as ">= 3.0"


@dataclass
class Case:
    scenario: str
    option: PU.Option | None
    impulse_Ns: float
    ref: Reference
    demand: E.Demand | None
    row: dict
    ok: bool


def _demand(robot: Robot, ref: Reference, vin: float, hook=None) -> tuple[E.Demand, dict]:
    d = E.ideal_demand(robot, ref, PlayConfig(mode="ideal", model_hook=hook))
    return d, E.push_gate(robot, d, vin)


def _row_meta(ref: Reference) -> dict:
    return {k: v for k, v in ref.meta.items() if isinstance(v, (int, float, str, bool, list, dict))}


def required_case(robot: Robot, kin: RobotKin, vin: float, scenario: str, J: float | None = None, hook=None, setup=None, max_demands: int = 8) -> Case:
    """The scenario at the required impulse: the first strategy (simplest first) whose plan, Reference and demand all pass; if none
    passes, the strategy with the smallest peak torque among the (up to `max_demands`) plan-feasible ones; if none is plan-feasible, the
    ankle-strategy plan marked as not recovered (so the failure carries a reason)."""
    S = setup or PU.make_setup(kin, scenario)
    J = J if J is not None else PU.required_impulse()
    cap = PU.hip_speed_cap(kin, vin)
    tried: list[Case] = []
    for opt in PU.options_for(scenario):
        ok, plan, ref = PU.plan_feasible(S, J, opt, cap, full=True)
        if not ok:
            continue
        d, row = _demand(robot, ref, vin, hook)
        case = Case(scenario, opt, J, ref, d, row, bool(row["valid"] and row.get("ok")))
        if case.ok:
            return case
        tried.append(case)
        if len(tried) >= max_demands:
            break
    if tried:
        best = min(tried, key=lambda c: c.row.get("peak_frac_of_stall", 9.9) if c.row["valid"] else 9.9)
        return best
    plan = PU.simulate(S, J, PU.Option(0), cap)
    ref = PU.build_reference(S, plan)
    d, row = _demand(robot, ref, vin, hook)
    return Case(scenario, None, J, ref, d, row, False)


def largest_recoverable(robot: Robot, kin: RobotKin, vin: float, scenario: str, hook=None, setup=None, j_hi: float = J_CAP_NS,
                        demand_iters: int = 4) -> dict:
    """Largest impulse (N.s) any strategy recovers, with the strategy, what limits it, and the per-strategy plan-level limits."""
    S = setup or PU.make_setup(kin, scenario)
    cap = PU.hip_speed_cap(kin, vin)
    per = []
    for opt in PU.options_for(scenario):
        jp = PU.plan_bisect(S, opt, cap, j_hi, iters=6, full=True)
        per.append({"option": opt.label, "plan_limit_Ns": round(jp, 3), "_opt": opt})
    order = sorted(per, key=lambda r: -r["plan_limit_Ns"])
    best = {"J": 0.0, "option": None, "limit": "no strategy recovers even a small push", "demand_row": None}
    n_demand = 0

    def pred_for(opt):
        def pred(J):
            nonlocal n_demand
            ok, plan, ref = PU.plan_feasible(S, J, opt, cap, full=True)
            if not ok:
                return False
            n_demand += 1
            d, row = _demand(robot, ref, vin, hook)
            return bool(row["valid"] and row.get("ok"))
        return pred

    for r in order:
        jp = r["plan_limit_Ns"]
        if jp <= best["J"] + 1e-6:
            break
        pred = pred_for(r["_opt"])
        if pred(jp):
            j = jp
        else:
            lo, hi = best["J"], jp                       # bisect the torque-feasible limit above what is already achieved
            if hi - lo < 0.02:
                continue
            for _ in range(demand_iters):
                mid = 0.5 * (lo + hi)
                if pred(mid):
                    lo = mid
                else:
                    hi = mid
            j = lo
            if j <= best["J"] + 1e-6:
                continue
        if j > best["J"]:
            best = {"J": j, "option": r["option"], "plan_limit_Ns": jp}
            best["limit"] = ("plan: " + "reach / capture point" if j >= jp - 0.02 else "actuators (torque / speed demand)")
    out = {"scenario": scenario, "largest_recoverable_Ns": round(best["J"], 3), "dv_mps": round(best["J"] / S.M, 3), "mass_kg": round(S.M, 3),
           "best_strategy": best["option"], "limited_by": best["limit"], "at_search_ceiling": bool(best["J"] >= j_hi - 1e-6),
           "strategies": [{"option": r["option"], "plan_limit_Ns": r["plan_limit_Ns"]} for r in order]}
    if best["J"] > 0:
        opt = next(r["_opt"] for r in per if r["option"] == best["option"])
        _, plan, ref = PU.plan_feasible(S, best["J"], opt, cap, full=True)
        d, row = _demand(robot, ref, vin, hook)
        out["at_largest"] = {k: row[k] for k in ("peak_frac_of_stall", "peak_joint", "util_max", "omega_peak", "ok") if k in row}
    return out


def summarize_case(c: Case, robot: Robot) -> dict:
    m = _row_meta(c.ref)
    out = {"valid": c.row["valid"], "reason": c.row["reason"], "demand_ok": bool(c.row.get("ok")), "strategy": c.option.label if c.option else None,
           "impulse_Ns": c.impulse_Ns, "dv_mps": m.get("dv_mps"), "notes": c.ref.notes[:3]}
    for k in ("peak_frac_of_stall", "peak_joint", "peak_nm", "util_max", "util_joint", "omega_peak", "omega_peak_joint", "why"):
        if k in c.row:
            out[k] = c.row[k]
    out["plan"] = {k: m.get(k) for k in ("steps_taken", "landings", "crouch_peak_m", "clipped", "trunk_pitch_peak_deg", "trunk_speed_peak_rad_s",
                                         "capture_offset_m", "reaction_delay_s", "cop_peak_offset_m")}
    return out
