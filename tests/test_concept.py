"""Concept-engine tests (T-0017). Fast ones run in the default suite; multi-minute runs are marked slow
(`pytest -m "not slow"` skips them). Requires the `sim` and `concept` extras (mujoco, casadi)."""
from __future__ import annotations

import copy
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("mujoco")

from openhumanoid import catalog, simgen  # noqa: E402
from openhumanoid.actuators import ServoBank, bam_params, friction_budget, servo_spec  # noqa: E402
from openhumanoid.concept import config, envelopes as E, provenance  # noqa: E402
from openhumanoid.concept.kin import RobotKin, Reference, leg_ik, lower_body  # noqa: E402
from openhumanoid.concept.motions import posture, walk as W  # noqa: E402
from openhumanoid.concept.motions.lipm import PreviewController  # noqa: E402
from openhumanoid.concept.robot import build_robot, load_concept, mass_sanity  # noqa: E402
from openhumanoid.concept.thermal_validation import replay  # noqa: E402
from openhumanoid.spec import load_spec  # noqa: E402
from openhumanoid.templates import available, load_template, safe_eval  # noqa: E402

CONCEPTS = Path(__file__).resolve().parent.parent / "variants" / "adam" / "concepts"
A = CONCEPTS / "A-3s-12v-sts3215.yaml"


@pytest.fixture(scope="module")
def robot_a():
    return build_robot(A)


@pytest.fixture(scope="module")
def kin_a(robot_a):
    return RobotKin(robot_a)


# ----------------------------------------------------------------------------------------------- templates / simgen
def test_templates_are_data_and_expressions_are_safe():
    assert {"biped_v1", "humanoid_v2"} <= set(available())
    assert safe_eval("max(0.045, 0.09*h) + thigh/2", {"h": 0.5, "thigh": 0.1}) == pytest.approx(0.095)
    with pytest.raises(ValueError):
        safe_eval("__import__('os').system('x')", {})
    with pytest.raises(KeyError):
        safe_eval("nonsense*2", {})


def test_unknown_template_joint_is_an_error_not_skipped():
    c = load_concept(A)
    c["template"] = "biped_v1"       # biped_v1 has no waist_yaw / gripper
    with pytest.raises((ValueError, KeyError)):
        build_robot(c).make_xml()


def test_biped_v1_still_builds_from_the_template():
    import mujoco
    spec = load_spec("adam")
    s = simgen.load_sizing(spec)
    m = mujoco.MjModel.from_xml_string(simgen.build_mjcf(spec, s))
    assert m.nu == len([j for j in simgen.expand_joints(spec, s["joints_base"]) if simgen.JOINT_BODY.get(j["base"])])
    assert abs(sum(m.body_mass) - s["mass"]["total_kg"]) < 0.05 * s["mass"]["total_kg"]


def test_humanoid_v2_has_all_requested_joints(robot_a):
    names = set(robot_a.names)
    for need in ("hip_yaw_l", "ankle_roll_r", "waist_yaw", "neck_yaw", "neck_pitch", "shoulder_pitch_l", "shoulder_roll_r", "elbow_l", "gripper_l", "gripper_r"):
        assert need in names
    m = robot_a.build_model()
    assert m.joint("gripper_r").type == 2           # slide
    assert abs(m.jnt_axis[m.joint("gripper_r").id][1]) == 1.0
    assert m.jnt_axis[m.joint("gripper_l").id][1] == -m.jnt_axis[m.joint("gripper_r").id][1]   # mirrored jaws


def test_optional_hand_bodies_fold_their_mass_into_the_forearm():
    c = load_concept(A)
    c["joints"] = [j for j in c["joints"] if (j if isinstance(j, str) else j["name"]) != "gripper"]
    r = build_robot(c)
    m = r.build_model()
    assert "hand_l" not in [m.body(i).name for i in range(m.nbody)]
    assert float(sum(m.body_mass)) == pytest.approx(r.total_mass, rel=1e-3)


# ----------------------------------------------------------------------------------------------- mass, floors, transmissions
def test_mass_bands_touch_only_structure_and_wiring():
    base = build_robot(A)
    heavy = build_robot(A, structure_scale=1.8)
    assert heavy.total_mass - base.total_mass == pytest.approx(0.8 * base.body.breakdown["structure_kg"], rel=1e-3)
    wired = build_robot(A, wiring_scale=1.5)
    assert wired.mass_breakdown["wiring_kg"] == pytest.approx(1.5 * base.mass_breakdown["wiring_kg"], rel=1e-3)
    assert wired.mass_breakdown["actuators_kg"] == base.mass_breakdown["actuators_kg"]


def test_benchmark_fit_is_only_a_sanity_bound(robot_a):
    s = mass_sanity(robot_a)
    assert "SANITY BOUNDS ONLY" in s["note"] and s["benchmark_fit_kg"] == pytest.approx(18.5 * robot_a.height ** 2.28, abs=1e-3)


def test_packaging_floors_raise_low_proportions(robot_a):
    assert robot_a.spec["_floor_notes"]                       # the spec default ankle height 0.045 h is below 0.06 h
    assert robot_a.geom["ankle_height"] == pytest.approx(0.06 * robot_a.height, rel=1e-6)
    assert robot_a.geom["hip_width"] >= 0.0699
    assert robot_a.geom["foot_length"] >= 0.092 * robot_a.height / 0.5 - 1e-9


def test_transmission_representation_moves_mass_and_ratio():
    d = build_robot(CONCEPTS / "D-transmission-example.yaml")
    a = build_robot(A)
    assert d.transmissions["knee_l"]["efficiency"] == 0.85
    assert d.body.seg_mass["shank"] < a.body.seg_mass["shank"]            # ankle servo left the shank
    assert d.body.seg_mass["pelvis"] > a.body.seg_mass["pelvis"]          # knee servos arrived in the pelvis
    assert d.total_mass == pytest.approx(a.total_mass, rel=1e-6)
    i = d.names.index("ankle_pitch_l")
    assert d.eff[i] == pytest.approx(0.90) and d.ratio[i] == 1.0


# ----------------------------------------------------------------------------------------------- catalog
def test_new_catalog_parts_have_dims_mass_and_sources():
    assert catalog.validate_catalog() == []
    for pid in ("lipo-2s-1200-nanotech", "lipo-2s-2200-turnigy", "lipo-3s-1300-tattu", "lipo-3s-2300-tattu", "charger-skyrc-b6neo",
                "buck-pololu-d36v50f5", "psu-rpi5-27w", "rpi-zero-2w", "rpi-5-4gb", "lipo-3s-2200"):
        p = catalog.get(pid)
        assert p.get("dimensions_mm") and p.get("mass_kg") and "http" in p["source"], pid
        # T-0002 (2026-10-19) verified some of these; a verified part needs >= 2 vendor rows and a URL source
        assert isinstance(p["verified"], bool)
        if p["verified"]:
            assert len(p.get("vendors", [])) >= 2, pid
    for pid in ("lipo-2s-2200-turnigy", "lipo-3s-2300-tattu"):
        assert catalog.get(pid)["specs"]["cells"] in (2, 3)


# ----------------------------------------------------------------------------------------------- servo model
def test_servo_specs_and_provenance_classes():
    s74, s12, s50 = servo_spec("sts3215-7v4"), servo_spec("sts3215-12v"), servo_spec("sts3250-12v")
    assert s74.stall_cap(7.4) == pytest.approx(1.912, abs=1e-3) and s12.stall_cap(12.0) == pytest.approx(2.942, abs=1e-3)
    assert s74.noload(7.4) == pytest.approx(5.67, abs=0.02)
    assert s12.noload(12.0) == pytest.approx(4.78, abs=0.01)         # datasheet-anchored, NOT the 9.2 rad/s of 'kt same'
    assert servo_spec("sts3215-12v", "bam_scaled").noload(12.0) > 9.0
    assert s74.quality == "measured_7v4" and s12.quality == "extrapolated_12v" and s50.quality == "datasheet_only"
    assert s12.uncertainty["stall"] >= 0.25 and s12.uncertainty["speed"] >= 0.25
    assert s74.uncertainty["armature"] == 0.20 and s12.uncertainty["armature"] == 0.50 and s50.uncertainty["armature"] == 0.50
    assert s74.perturbed(armature=1.2).armature == pytest.approx(1.2 * s74.armature)
    assert s12.stall_cap(11.1) == pytest.approx(2.942 * 11.1 / 12)            # voltage scaling of the reference stall


def test_torque_speed_models_anchored_vs_pessimistic_linear():
    s = servo_spec("sts3215-12v")
    w = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    anch, lin = s.tau_available(w, 12.0), s.with_model("linear").tau_available(w, 12.0)
    assert np.all(lin <= anch + 1e-9) and lin[2] < 0.7 * anch[2]
    assert np.all(np.diff(anch) <= 1e-9)


def test_friction_is_not_subtracted_twice_after_the_cap():
    """The motor-side cap is stall + friction budget, so the NET shaft torque can still reach the datasheet stall."""
    s = servo_spec("sts3215-7v4")
    b = ServoBank([s], 0.002)
    b.set_supply(7.4)
    tau = 0.0
    for _ in range(50):
        tau = b.control(np.array([1.0]), np.array([0.0]), np.array([0.0]))[0]
        fl, d = b.frictions(np.array([tau]), np.array([-tau]), np.array([0.0]))
    net = tau - float(fl[0])
    assert net >= 0.98 * s.stall_cap(7.4) - 1e-6 and tau > s.stall_cap(7.4)


def test_overload_protection_trips_after_protection_time():
    s = servo_spec("sts3215-7v4")
    b = ServoBank([s], 0.002)
    b.set_supply(7.4)
    for k in range(int(3.0 / 0.002)):                      # a large step command saturates the servo for 3 s
        b.control(np.array([1.5]), np.array([0.0]), np.array([0.0]))
        b.frictions(np.array([b.tau_m[0]]), np.array([-b.tau_m[0]]), np.array([0.0]))
        if k == int(1.5 / 0.002):
            assert b.trips[0] == 0 and not b.protected[0]
    assert b.trips[0] == 1 and b.protected[0]
    assert abs(b.tau_m[0]) <= s.protective_fraction * s.stall_cap(7.4) + 1e-9


def test_friction_budget_matches_the_bam_files_shape():
    fr = servo_spec("sts3215-7v4").friction
    loss, damp = friction_budget(fr, np.array([1.0, 0.0]), np.array([-1.0, 0.0]), np.array([0.0, 3.0]))
    assert loss[0] > loss[1] and damp[0] == pytest.approx(bam_params("bam_feetech_sts3215_7_4V_m4.json")["friction_viscous"])


def _bam_importable():
    src = os.environ.get("BAM_SRC")
    if src and src not in sys.path:
        sys.path.insert(0, src)
    try:
        import bam  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _bam_importable(), reason="upstream BAM not importable: set BAM_SRC to a checkout of Rhoban/bam (needs numpy + colorama; the package itself wants Python >= 3.12)")
def test_bam_fidelity_against_upstream():
    """Our re-implementation vs upstream BAM (Apache-2.0, commit e9a619d) on a pendulum trajectory: identical to float precision."""
    from dataclasses import replace
    from bam.model import load_model
    from bam.simulate import Simulator

    m = load_model(motor_name="feetech_sts3215_7_4V", model="m4")
    sp = servo_spec("sts3215-7v4")
    rng = np.random.default_rng(0)
    for _ in range(100):
        tm, te, dq = rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-6, 6)
        a, b = m.compute_frictions(tm, te, dq), friction_budget(sp.friction, tm, te, dq)
        assert abs(a[0] - float(b[0])) < 1e-12 and abs(a[1] - float(b[1])) < 1e-12
    m.actuator.load_log({"mass": 0.15, "arm_mass": 0.03, "length": 0.10, "kp": 32, "vin": 7.4})
    m.q_offset.value = 0.0
    sim = Simulator(m)
    dt, n = 0.002, 1500
    qt = 0.8 * np.sin(2 * np.pi * 0.5 * np.arange(n) * dt)
    sim.reset(0.0, 0.0)
    qb = []
    for k in range(n):
        sim.step(m.actuator.compute_control(qt[k], sim.q, sim.dq, dt), True, dt)
        qb.append(sim.q)
    spec = replace(sp, delay_s=0.0, backlash_rad=0.0, stall_nm_ref=1e3)
    bank = ServoBank([spec], dt)
    bank.reset(np.array([0.0]))
    tb = m.actuator.testbench
    q = dq = 0.0
    qo = []
    for k in range(n):
        tau = bank.control(np.array([qt[k]]), np.array([q]), np.array([dq]))[0]
        bias = tb.compute_bias(q, dq)
        fl, d = bank.frictions(np.array([tau]), np.array([bias]), np.array([dq]))
        inertia = tb.compute_mass(q, dq) + spec.armature
        net = tau + bias
        stop = (inertia / dt) * dq + net
        net += -np.sign(stop) * min(abs(stop), float(fl[0]) + float(d[0]) * abs(dq))
        dq = float(np.clip(dq + net / inertia * dt, -100, 100))
        q += dq * dt
        qo.append(q)
    assert np.abs(np.array(qb) - np.array(qo)).max() < 1e-6


# ----------------------------------------------------------------------------------------------- kinematics, gait
def test_leg_ik_matches_mujoco_fk(kin_a):
    lg = kin_a.lg
    pel = np.array([[0.0, 0.0, 0.2], [0.01, 0.004, 0.19]])
    yaw, pitch = np.array([0.0, 0.25]), np.zeros(2)
    ank = np.array([[0.015, lg.hip_y, lg.ankle_h], [0.04, lg.hip_y + 0.005, lg.ankle_h + 0.01]])
    ankr = ank * np.array([1, -1, 1])
    out, ok = lower_body(kin_a, pel, yaw, pitch, ank, ankr, yaw, yaw)
    assert ok.all()
    Q = np.zeros((2, len(kin_a.names)))
    for n, v in out.items():
        Q[:, kin_a.index[n]] = v
    from openhumanoid.concept.kin import quat_from_yaw_pitch
    qu = quat_from_yaw_pitch(yaw, pitch)
    for i in range(2):
        site = kin_a.site("foot_l", Q[i], pel[i], qu[i])
        want = ank[i] + np.array([lg.foot_off * math.cos(yaw[i]), lg.foot_off * math.sin(yaw[i]), -lg.ankle_h])
        assert np.abs(site - want).max() < 1e-4


def test_preview_control_tracks_the_zmp():
    pc = PreviewController(0.23, 0.01)
    z = np.zeros(600)
    z[100:250], z[250:400] = 0.03, -0.03
    com, zmp = pc.run(z)
    assert np.abs(zmp[50:] - z[50:]).mean() < 1e-3 and np.abs(com).max() < 0.035


def test_walk_uses_the_frozen_spec_for_every_candidate(kin_a):
    w = config.walk_spec()
    ref = W.walk(kin_a, "forward")
    assert ref.feasible and ref.meta["speed_mps"] == pytest.approx(w["speed_mps"], rel=1e-6)
    assert ref.meta["step_time_s"] == w["step_time_s"]
    other = RobotKin(build_robot(CONCEPTS / "B-2s-7v4-sts3215.yaml"))
    assert W.walk(other, "forward").meta["speed_mps"] == ref.meta["speed_mps"]            # no per-candidate tempo
    back, turn = W.walk(kin_a, "backward"), W.walk(kin_a, "turn")
    assert back.meta["step_len_m"] < 0 and turn.meta["turn_rate_rad_s"] == pytest.approx(w["turn_rate_rad_s"], rel=1e-6)
    late = W.walk(kin_a, "forward", landing_shift=1)
    assert not np.allclose(late.q, ref.q)


def test_dance_is_frozen_30_to_60_seconds_within_the_smoother_limit(kin_a):
    from openhumanoid.concept.motions.dance import dance
    d = config.motions()["dance"]
    ref = dance(kin_a, bpm=d["bpm"], n_phrases=d["phrases"], v_limit=d["v_limit_rad_s"])
    assert 30 <= ref.duration <= 60 and ref.feasible
    assert ref.meta["max_smoother_dev_deg"] <= d["smoother_max_deviation_deg"]


# ----------------------------------------------------------------------------------------------- demand and gates
def test_static_stance_torque_against_hand_calculation(robot_a, kin_a):
    ref = posture.stand(kin_a, 3.0)
    d = E.ideal_demand(robot_a, ref)
    assert d.valid
    i = robot_a.names.index("knee_l")
    tau = float(np.abs(d.tau_ideal[:, i]).mean())
    g, m = robot_a.geom, robot_a.body.seg_mass
    flex = math.radians(robot_a.spec["locomotion"]["walk"]["stance_knee_flex_deg"])
    M = robot_a.total_mass
    m_low = m["shank"] + m["foot"]
    hand = ((M - 2 * m_low) / 2 + m_low * 0.5) * 9.81 * g["thigh"] * math.sin(flex / 2)    # knee ahead of the ankle-hip line
    assert tau == pytest.approx(hand, rel=0.45)


def test_depth_ordering_of_knee_torque(robot_a, kin_a):
    vals = []
    for ref in (posture.stand(kin_a, 3.0), posture.squat(kin_a, 90), posture.squat(kin_a, 120)):
        d = E.ideal_demand(robot_a, ref)
        assert d.valid, d.invalid_reason
        vals.append(float(np.abs(d.tau_ideal[:, robot_a.names.index("knee_l")]).max()))
    assert vals[0] < vals[1] < vals[2]


def test_tether_above_one_percent_invalidates_a_motion(robot_a, kin_a):
    ref = posture.stand(kin_a, 3.0)
    bad = Reference("stand_floating", ref.dt, ref.q, ref.base_pos.copy(), ref.base_quat)
    bad.base_pos[:, 2] += np.linspace(0.0, 0.10, len(bad.base_pos))     # the plan lifts the pelvis 10 cm while the legs stay put
    d = E.ideal_demand(robot_a, bad)
    assert not d.valid and "tether" in d.invalid_reason and d.assist_mean > 0.01


def test_gate_metrics_flag_sustained_overload():
    r = build_robot(A)
    n = len(r.names)
    t = np.arange(0, 6, 0.01)
    stall = np.array([float(r.servo[x].stall_cap(11.1)) for x in r.names])
    tau = np.zeros((len(t), n))
    tau[:, 6] = 0.75 * stall[6]                                  # knee_l held at 75% of stall for 6 s
    d = E.Demand("synthetic", t, tau, tau, np.zeros_like(tau), r.names, slice(0, len(t)), True, "", 0.0, 0.0, False)
    m = E.joint_metrics(r, d, np.full(n, 11.1))
    assert m["peak_frac_stall"][6] == pytest.approx(0.75, rel=1e-3) and m["run_above70_s"][6] > 5.5
    tab = E.gate_joint_table(r, {"synthetic": m})
    assert "peak" in tab["knee_l"]["fails"] and "overload_time" in tab["knee_l"]["fails"]
    tau[:, 6] = 0.85 * stall[6]
    m2 = E.joint_metrics(r, E.Demand("s2", t, tau, tau, np.zeros_like(tau), r.names, slice(0, len(t)), True, "", 0.0, 0.0, False), np.full(n, 11.1))
    assert m2["trips"][6] >= 1


# ----------------------------------------------------------------------------------------------- thermal, power, provenance
def test_robonine_replay_reports_honestly():
    r = replay()
    assert r["run1"]["ok"]                                       # circular by construction (Rth was derived from it)
    assert r["thermal_numbers_usable"] == r["reproduces_both"]
    assert not r["reproduces_both"] and "UNUSABLE" in r["verdict"]    # the model under-predicts run 2 (71 C): documented


def test_voltage_rating_report_flags_2s_over_rating():
    from openhumanoid.concept import tradestudy as TS
    b = build_robot(CONCEPTS / "B-2s-7v4-sts3215")  if False else build_robot(CONCEPTS / "B-2s-7v4-sts3215.yaml")
    rep = TS.voltage_rating_report(b, TS.pack_of(b))
    assert rep["sts3215-7v4"]["over_rating_at_full_v"] == pytest.approx(1.0, abs=1e-6) and rep["sts3215-7v4"]["mitigation"]
    c = build_robot(CONCEPTS / "C-3s-sts3250-knees.yaml")
    rc = TS.voltage_rating_report(c, TS.pack_of(c))
    assert rc["sts3215-12v"]["over_rating_at_full_v"] == 0.0 and rc["sts3250-12v"]["over_rating_at_full_v"] > 0.5


def test_every_reported_constant_has_a_provenance_class(robot_a):
    allowed = {"measured", "measured (single unit, third party)", "sourced_estimate", "extrapolated", "assumption", "gate"}
    rows = provenance.collect(robot_a)
    assert len(rows) > 40
    assert {r["class"] for r in rows} <= allowed
    th = config.thresholds()
    for k, v in th["gates"].items():
        assert "class" in v and "source" in v, k


# ----------------------------------------------------------------------------------------------- evaluator
def test_evaluate_quick_runs_end_to_end(tmp_path):
    from openhumanoid.concept.evaluate import evaluate
    rep = evaluate(A, out_root=tmp_path, quick=True)
    for k in ("verdict", "joints_ranked_by_margin", "power", "thermal", "cost", "provenance", "limitations", "motions", "utilisation_ranking", "model_quality"):
        assert k in rep
    assert (tmp_path / rep["candidate"] / "report.md").exists() and (tmp_path / rep["candidate"] / "report.json").exists()
    assert rep["cost"]["total_usd"]["low"] <= rep["cost"]["total_usd"]["typical"] <= rep["cost"]["total_usd"]["high"]
    assert rep["thermal"]["thermal_model_usable"] is False


@pytest.mark.slow
def test_pickup_grasps_the_150g_object_with_the_servo_in_the_loop(robot_a, kin_a):
    from openhumanoid.concept.evaluate import Mods, run_bundle, _servo_runs
    b = run_bundle(load_concept(A), Mods(), motions=["stand", "pickup"], thermal=False)
    assert b.dem["pickup"].valid, b.dem["pickup"].invalid_reason
    out = _servo_runs(b)
    assert out["pickup"]["grasp_ok"] and out["pickup"]["overload_trips"] == 0


@pytest.mark.slow
def test_full_evaluation_with_bounds_and_monte_carlo(tmp_path):
    from openhumanoid.concept.evaluate import evaluate
    rep = evaluate(A, out_root=tmp_path, samples=2)
    assert len(rep["bounds_sweep"]) >= 10 and rep["monte_carlo"]["samples"] == 2 and rep["monte_carlo"]["quasi_static_only"]
    assert "benchmark-fit mass" in rep["mass_cases"]["cases"] and "mass_to_first_gate_failure_kg" in rep["mass_cases"]
    assert rep["stress_walks"] and "needs closed loop" in rep["closed_loop_sensitivity"]["label"]


@pytest.mark.slow
def test_known_robot_check_runs_legs_only(tmp_path):
    from openhumanoid.concept.evaluate import evaluate
    rep = evaluate(CONCEPTS / "duck-like-0p42-2s-sts3215.yaml", out_root=tmp_path, quick=True)
    assert set(rep["motions"]) == {"stand", "walk_forward", "walk_backward", "turn", "squat_90"}


# ----------------------------------------------------------------------------------------------- push recovery (R10)
def test_push_is_defined_in_capture_point_units_and_scaled_to_mass(robot_a, kin_a):
    from openhumanoid.concept.motions import push as PU
    ref = PU.push_case(kin_a, "ankle_fwd")
    m = ref.meta
    cfg = config.motions()["push"]
    assert m["dv_mps"] == pytest.approx(cfg["ankle_k"] * (kin_a.lg.foot_len / 2) * math.sqrt(9.81 / m["zc_m"]), rel=1e-6)
    assert m["impulse_Ns"] == pytest.approx(m["mass_kg"] * m["dv_mps"], rel=1e-6)           # J = M dv
    assert m["mass_kg"] == pytest.approx(robot_a.total_mass, rel=1e-3)
    servo_delay = max(s.delay_s for s in robot_a.servo.values())
    assert m["reaction_delay_s"] == pytest.approx(servo_delay + cfg["control_period_s"] + cfg["sensing_latency_s"])
    assert ref.feasible and m["recovered_plan"] and m["cop_peak_offset_m"] <= kin_a.lg.foot_len / 2


def test_ankle_push_is_cheap(robot_a, kin_a):
    from openhumanoid.concept.motions import push as PU
    ank = E.push_gate(robot_a, E.ideal_demand(robot_a, PU.push_case(kin_a, "ankle_fwd")), 11.1)
    assert ank["valid"] and ank["ok"] and ank["peak_frac_of_stall"] < 0.5
    assert ank["peak_joint"].startswith("ankle")


def test_latency_makes_the_capture_point_grow_before_the_controller_acts(kin_a):
    from openhumanoid.concept.motions import push as PU
    base = PU.push_case(kin_a, "capture_fwd")
    node = config._load()["motions"]["push"]
    old = node["sensing_latency_s"]
    try:
        node["sensing_latency_s"] = old + 0.040             # 40 ms more latency
        slow = PU.push_case(kin_a, "capture_fwd")
    finally:
        node["sensing_latency_s"] = old
    assert slow.meta["capture_point_xy"][0] > base.meta["capture_point_xy"][0]          # the capture point runs further away


def test_largest_recoverable_push_is_reported(kin_a):
    from openhumanoid.concept.motions import push as PU
    r = PU.max_recoverable_scale(kin_a, "ankle_fwd", iters=4)
    assert r["scale"] > 1.0 and r["impulse_Ns"] > 0
