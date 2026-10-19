"""Packaging-for-look study (T-20261019-c1aa): ENGINEERING side of every lever, with the concept engine's own functions.

Wraps variants/adam/design/r1_calibrated.py `run()` (strict, half-calibrated and ODM-calibrated gate sets, R10 at the required impulse,
optional bounds and the largest recoverable push). Thresholds are never changed. Two in-process patches, both stated in every output:

1. Rail servos (`x_rail_servos` in a concept): parts.yaml servos that run on a SECOND, regulated rail (Pololu D36V50F6, 6 V). The engine
   has one bus voltage for every servo and would scale a 6 V servo's stall to 11.1 V. Here each such servo is a datasheet-only ServoSpec
   (ideal DC motor, +-30% stall/speed bands, STS3215 BAM m4 friction scaled by the stall ratio) whose stall, no-load speed and torque-speed
   curve are PINNED to its rail voltage. The servo-in-the-loop bank is pinned the same way. The parts are registered in the in-memory
   catalog only (prices from parts.yaml); catalog/ is not edited.
2. Pack in the pelvis (`x_pack_host: pelvis`): the pack's catalog mass is moved from the torso segment to the pelvis segment after the
   body is built. The lumbar position (~40 mm lower than the chest pack) sits between the two, so this is the OPTIMISTIC end of the
   lever's COM effect; the chest position is the pessimistic end (= R1).

Run:  .venv/Scripts/python variants/adam/design/packaging/engine.py <concept.yaml ...> [--heights 0.55] [--bounds] [--pushmax] [--foot-frac 0.17]
Out:  variants/adam/design/packaging/results/engine_<id>.{json,md}
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(REPO))

import r1_calibrated as R1C  # noqa: E402
from openhumanoid import catalog  # noqa: E402
from openhumanoid.actuators import servo as SV  # noqa: E402
from openhumanoid.concept import robot as RB  # noqa: E402

PARTS = yaml.safe_load((HERE / "parts.yaml").read_text(encoding="utf-8"))
RES = HERE / "results"


@dataclass(frozen=True)
class RailServoSpec(SV.ServoSpec):
    """A servo on its own regulated rail: every supply-voltage argument is replaced by the rail voltage."""
    rail_v: float = 6.0

    def _v(self, vin):
        return np.full(np.shape(np.asarray(vin, dtype=float)), self.rail_v) if np.ndim(vin) else self.rail_v

    def stall_cap(self, vin):
        return super().stall_cap(self._v(vin))

    def stall_electrical(self, vin):
        return super().stall_electrical(self._v(vin))

    def noload(self, vin):
        return super().noload(self._v(vin))

    def tau_available(self, w, vin, *, optimistic: bool = False, model: str | None = None):
        return super().tau_available(w, self._v(vin), optimistic=optimistic, model=model)


def rail_spec(pid: str) -> RailServoSpec:
    p = PARTS["servos"][pid]
    v = float(p["rail_v"])
    stall, noload = float(p["stall_nm"]), float(p["noload_rad_s"])
    i_stall = max(stall * noload / v, 0.1)
    kt = v * 0.97 / noload
    # friction: the servo bank needs one friction model family, so take the STS3215 BAM m4 parameters with the torque terms scaled by
    # the stall ratio (the engine's own rule for the STS3250: dynamics_scale.torque); load-dependent coefficients are dimensionless
    ref = _ORIG_SPEC("sts3215-12v")
    sc = stall / ref.stall_nm_ref
    fr = {k: (val * sc if k in SV._FRICTION_TORQUE_KEYS else val) for k, val in ref.friction.items()}
    return RailServoSpec(
        key=pid, label=f"{pid} (generic datasheet model, {v:g} V rail)", quality="generic_datasheet", quality_score=0.15, vin_ref=v,
        voltage_rating_v=tuple(p["voltage_v"]), kt=kt, R_dc=v / i_stall, pwm_max=0.97, kp_fw=32, error_gain=0.166, error_gain_ratio=1.0,
        delay_s=0.005, rate_limit_rad_s=0.894 * noload, armature=float(p["armature_kg_m2"]),
        friction=fr,
        stall_nm_ref=stall, stall_current_a=i_stall, rated_continuous_nm=float(p["continuous_nm"]), noload_rad_s_ref=noload,
        mass_kg=float(p["mass_kg"]), rth_k_per_w=3.0, tau_th_s=300.0,
        uncertainty={"stall": 0.3, "speed": 0.3, "friction": 0.5, "kt": 0.3, "rth": 0.5, "armature": 0.5},
        notes=(f"packaging-look rail servo: datasheet-only, armature {p['armature_kg_m2']} kg m^2 is an ASSUMPTION", ), rail_v=v)


_ORIG_SPEC = RB.servo_spec
_ORIG_SUPPLY = SV.ServoBank.set_supply
_ORIG_BODY = RB.build_body
_STATE = {"armature_scale": 1.0, "pack_host": None, "pack_kg": 0.0}


def _servo_spec(pid, variant=None):
    if pid in PARTS["servos"] and PARTS["servos"][pid].get("rail_v"):
        s = rail_spec(pid)
        return replace(s, armature=s.armature * _STATE["armature_scale"])
    return _ORIG_SPEC(pid, variant)


def _set_supply(self, vin):
    _ORIG_SUPPLY(self, vin)
    for i, s in enumerate(self.specs):
        if isinstance(s, RailServoSpec):
            self.vin[i] = s.rail_v


def _build_body(spec, height, joints, actuator_mass, fixed_mass_kg):
    body = _ORIG_BODY(spec, height, joints, actuator_mass, fixed_mass_kg)
    if _STATE["pack_host"]:
        m = _STATE["pack_kg"]
        body.seg_mass["torso"] -= m
        body.seg_mass[_STATE["pack_host"]] += m
    return body


def install() -> None:
    cat = catalog.load_catalog()
    for pid, p in PARTS["servos"].items():
        if p.get("rail_v") and pid not in cat:
            cat[pid] = {"id": pid, "name": pid, "category": "actuator", "mass_kg": p["mass_kg"], "verified": False,
                        "price_usd": {"typical": p["price"], "low": p["price"], "high": p["price"], "unit": "each", "as_of": "2026-10-19"},
                        "actuator": {"type": "serial_bus_servo", "stall_torque_nm": p["stall_nm"], "no_load_speed_rad_s": p["noload_rad_s"],
                                     "voltage_v": p["voltage_v"], "continuous_torque_nm": p["continuous_nm"], "armature_kg_m2": p["armature_kg_m2"]},
                        "source": p["source"]}
    RB.servo_spec = _servo_spec
    SV.ServoBank.set_supply = _set_supply
    RB.build_body = _build_body


@contextlib.contextmanager
def concept_state(c: dict):
    old = dict(_STATE)
    if c.get("x_pack_host"):
        _STATE["pack_host"] = c["x_pack_host"]
        _STATE["pack_kg"] = float(catalog.get(c["power"]["pack"])["mass_kg"])
    _STATE["armature_scale"] = float(c.get("x_rail_armature_scale", 1.0))
    try:
        yield
    finally:
        _STATE.update(old)


def joint_table(res: dict) -> dict:
    rows = res["nominal"]["rows"]
    return {n: {"strict": r["strict_worst"], "half": r["half_worst"], "cal": r["cal_worst"], "peak_motion": r["peak_motion"]} for n, r in rows.items()}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "pickup":      # the engine's pickup reach scan with the same rail-servo patch: engine.py pickup <pickup args>
        install()
        from openhumanoid.concept.motions import pickup
        return pickup.main(argv[1:])
    ap = argparse.ArgumentParser()
    ap.add_argument("concepts", nargs="+")
    ap.add_argument("--heights", nargs="+", type=float, default=[0.55])
    ap.add_argument("--bounds", action="store_true")
    ap.add_argument("--pushmax", action="store_true")
    ap.add_argument("--foot-frac", type=float, default=None)
    ap.add_argument("--extra-latency-ms", type=float, default=0.0)
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    install()
    RES.mkdir(parents=True, exist_ok=True)
    if a.foot_frac is not None or a.extra_latency_ms:
        R1C.sensitivity_patch(a.foot_frac, a.extra_latency_ms / 1000.0)
    for cp in a.concepts:
        c = RB.load_concept(cp)
        rs = []
        with concept_state(c):
            for h in a.heights:
                r = R1C.run(cp, h, bounds=a.bounds, pushmax=a.pushmax, foot_frac=a.foot_frac)
                r["joints"] = joint_table(r)
                r["options"] = {"foot_frac": a.foot_frac, "extra_latency_ms": a.extra_latency_ms, "bounds": a.bounds,
                                "patches": {"rail_servos": c.get("x_rail_servos"), "pack_host": c.get("x_pack_host"),
                                            "rail_armature_scale": c.get("x_rail_armature_scale", 1.0)}}
                rs.append(r)
        cid = c["id"] + (f"-{a.tag}" if a.tag else "")
        (RES / f"engine_{cid}.json").write_text(json.dumps(rs, indent=1, default=R1C._js), encoding="utf-8")
        md = R1C.to_md(rs).replace("variants/adam/design/r1_calibrated.py (T-20261019-36f9)",
                                   "variants/adam/design/packaging/engine.py via r1_calibrated.py (T-20261019-c1aa)")
        (RES / f"engine_{cid}.md").write_text(md, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
