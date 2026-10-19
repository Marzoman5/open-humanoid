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


# ----------------------------------------------------------------------------------------------- push recovery (R10, absolute impulse)
def test_push_is_an_absolute_impulse_the_same_for_every_candidate(robot_a):
    from openhumanoid.concept.motions import push as PU
    robot_b = build_robot(CONCEPTS / "B-2s-7v4-sts3215.yaml")
    J = config.motions()["push"]["required_impulse_Ns"]
    for rb in (robot_a, robot_b):
        kin = RobotKin(rb)
        for sc in ("stand_fwd", "walk_lat_out"):
            ref = PU.push_case(kin, sc)
            m = ref.meta
            assert m["impulse_Ns"] == pytest.approx(J) and m["dv_mps"] == pytest.approx(J / rb.total_mass, rel=1e-6)    # J fixed, dv = J / M
            assert m["mass_kg"] == pytest.approx(rb.total_mass, rel=1e-3)
            assert m["reaction_delay_s"] == pytest.approx(max(s.delay_s for s in rb.servo.values()) + config.motions()["push"]["control_period_s"] + config.motions()["push"]["sensing_latency_s"])


def test_cop_is_referenced_to_the_foot_centre_not_the_initial_com(kin_a):
    from openhumanoid.concept.motions import push as PU
    S = PU.make_setup(kin_a, "stand_fwd")
    assert S.c0[0] == pytest.approx(kin_a.lg.foot_off)                         # challenge-2 row 9: the old plan started the COM 7 mm behind the foot centre
    plan = PU.simulate(S, 0.2, PU.Option(0))
    mx = config.motions()["push"]["cop_margin_frac"] * kin_a.lg.foot_len / 2
    assert plan.ok and plan.meta["cop_peak_offset_m"] <= mx + 1e-6              # the COP never leaves the shrunk foot, measured from the foot centre


def test_ankle_push_is_cheap_and_a_push_free_control_passes_every_scenario(robot_a, kin_a):
    from openhumanoid.concept.motions import push as PU
    from openhumanoid.concept import pushcheck as PC, tradestudy as TS
    vin = TS.v_nominal(TS.pack_of(robot_a))
    ank = E.push_gate(robot_a, E.ideal_demand(robot_a, PU.push_case(kin_a, "stand_fwd", 0.15, PU.Option(0))), vin)
    assert ank["valid"] and ank["ok"] and ank["peak_frac_of_stall"] < 0.5
    for sc in PU.SCENARIOS:                                                      # a ~zero push must pass the emergency limits, else the walk itself would be blamed on the push
        c = PC.required_case(robot_a, kin_a, vin, sc, J=0.02)
        assert c.ok, (sc, c.row)


def test_hip_strategy_is_never_a_blocker_by_itself(kin_a):
    from openhumanoid.concept.motions import push as PU
    S = PU.make_setup(kin_a, "stand_fwd")
    assert not PU.simulate(S, 0.2, PU.Option(0, None, True), hip_speed_cap=0.01).ok          # speed-limited: unavailable ...
    assert PU.simulate(S, 0.2, PU.Option(0), hip_speed_cap=0.01).ok                          # ... but the ankle strategy alone still recovers it
    assert not any(o.hip for o in PU.options_for("stand_lat")) and any(o.hip for o in PU.options_for("stand_fwd"))
    assert PU.hip_speed_cap(kin_a) < float(min(kin_a.robot.servo[n].noload(11.1) for n in kin_a.robot.names if n.startswith("hip_pitch")))


def test_step_options_sweep_swing_time_and_allow_two_steps():
    from openhumanoid.concept.motions import push as PU
    opts = PU.options_for("walk_fwd")
    assert {o.swing_s for o in opts if o.steps} == {0.15, 0.20, 0.25, 0.30, 0.35} and max(o.steps for o in opts) == 2
    assert set(PU.SCENARIOS) == {"stand_fwd", "stand_lat", "walk_fwd", "walk_lat_out", "walk_lat_in"}


def test_latency_shrinks_the_largest_ankle_push(kin_a):
    from openhumanoid.concept.motions import push as PU
    S = PU.make_setup(kin_a, "stand_fwd")
    base = PU.plan_bisect(S, PU.Option(0), None, 2.0, full=False)
    node = config._load()["motions"]["push"]
    old = node["sensing_latency_s"]
    try:
        node["sensing_latency_s"] = old + 0.040
        slow = PU.plan_bisect(PU.make_setup(kin_a, "stand_fwd"), PU.Option(0), None, 2.0, full=False)
    finally:
        node["sensing_latency_s"] = old
    assert slow < base


def test_largest_recoverable_push_is_reported_in_newton_seconds_and_m_per_s(robot_a, kin_a):
    from openhumanoid.concept import pushcheck as PC, tradestudy as TS
    r = PC.largest_recoverable(robot_a, kin_a, TS.v_nominal(TS.pack_of(robot_a)), "stand_lat", demand_iters=2)
    assert r["largest_recoverable_Ns"] > 0.3 and r["dv_mps"] == pytest.approx(r["largest_recoverable_Ns"] / robot_a.total_mass, abs=2e-3)
    assert r["best_strategy"] and r["limited_by"]


# ----------------------------------------------------------------------------------------------- challenge-2 calibration fixes
def test_static_knee_torque_scales_with_the_supported_mass(robot_a, kin_a):
    """Row 10: scale every body mass by 1.5 in the simulated model: the static knee torque must follow within 5%, and an independent hand
    calculation from the model's own kinematics (vertical load W/2 at the COM x, minus the lower leg's own weight) must agree within 5%."""
    from openhumanoid.concept.playback import PlayConfig
    ref = posture.stand(kin_a, 3.0)

    def knee(scale):
        def hook(model):
            model.body_mass[:] *= scale
            model.body_inertia[:] *= scale
        d = E.ideal_demand(robot_a, ref, PlayConfig(mode="ideal", model_hook=hook))
        return float(np.abs(d.tau_ideal[:, robot_a.names.index("knee_l")]).mean())
    t1, t15 = knee(1.0), knee(1.5)
    assert t15 / t1 == pytest.approx(1.5, rel=0.05)
    m = kin_a.model
    kin_a.set_state(ref.q[0], ref.base_pos[0], ref.base_quat[0])
    kin_a.mj.mj_kinematics(m, kin_a.data)
    kin_a.mj.mj_comPos(m, kin_a.data)
    d = kin_a.data
    com_x = float(d.subtree_com[1][0])
    knee_x = float(d.xanchor[m.joint("knee_l").id][0])
    low = [i for i in range(m.nbody) if m.body(i).name in ("shank_l", "foot_l")]
    m_low = float(sum(m.body_mass[i] for i in low))
    x_low = float(sum(m.body_mass[i] * d.xipos[i][0] for i in low) / m_low)
    hand = abs(0.5 * float(sum(m.body_mass)) * 9.81 * (com_x - knee_x) - m_low * 9.81 * (x_low - knee_x))
    assert t1 == pytest.approx(hand, rel=0.05)


def test_pd_demand_agrees_with_minimum_torque_inverse_dynamics(robot_a, kin_a):
    from openhumanoid.concept.mintorque import min_torque_demand
    for ref in (posture.stand(kin_a, 3.0), W.walk(kin_a, "forward")):
        pd = E.ideal_demand(robot_a, ref)
        mt = min_torque_demand(robot_a, ref)
        vin = np.full(len(robot_a.names), 11.1)
        a, b = E.joint_metrics(robot_a, pd, vin), E.joint_metrics(robot_a, mt, vin)
        leg = [i for i, n in enumerate(robot_a.names) if n.split("_")[0] in ("hip", "knee", "ankle")]
        sag = [i for i in leg if robot_a.names[i].split("_")[0] in ("hip", "knee", "ankle") and not robot_a.names[i].startswith(("hip_roll", "hip_yaw", "ankle_roll"))]
        assert np.allclose(b["rms_nm"][sag], a["rms_nm"][sag], rtol=0.12, atol=0.02)              # sagittal joints: the PD and the ideal contact split agree
        assert np.allclose(b["rms_nm"][leg], a["rms_nm"][leg], rtol=0.5, atol=0.03)                 # roll joints differ more: the contact split decides the lateral COP


def test_mj_inverse_bookkeeping_and_closed_chain_fighting(robot_a, kin_a):
    from openhumanoid.concept import invdyn
    st = invdyn.inverse_error(robot_a, posture.stand(kin_a, 3.0))
    assert st["inverse_error_max_over_pd_leg"] < 0.01 and st["vertical_share_left_mean_in_ds"] == pytest.approx(0.5, abs=0.01) and st["squeeze_bw_max_in_ds"] < 0.01
    wk = invdyn.inverse_error(robot_a, W.walk(kin_a, "forward"))
    assert wk["inverse_error_max_over_pd_leg"] < 0.10 and wk["squeeze_bw_mean_in_ds"] < 0.03          # no stiff-PD fighting through the floor in double support


def test_gait_sweep_is_the_frozen_set_and_step_time_scales_the_step():
    gs = config.thresholds()["gait_sweep"]
    assert gs["step_time_s"] == [0.25, 0.35, 0.5] and gs["stance_knee_flex_deg"][0] == 20 and gs["stance_knee_flex_deg"][-1] == 45
    g1, g2 = W.frozen_gait(0.5), W.frozen_gait(0.25)
    assert g2["step_len"] == pytest.approx(g1["step_len"] / 2) and g2["n_steps"] == 2 * g1["n_steps"]       # same speed, same walk duration


def test_rated_alternative_and_st3025_armature_come_from_the_data_files():
    sp = servo_spec("sts3215-7v4")
    assert sp.rated_continuous_nm == pytest.approx(0.49) and sp.rated_alt_nm == (0.637,)
    st = bam_params("bam_waveshare_st3025_m4.json")
    assert st["armature"] == pytest.approx(0.00399, rel=2e-3) and st["actuator"] == "waveshare_st3025"


def test_cad_foundation_packaging_keeps_the_height_and_limits_the_ranges():
    from openhumanoid.concept.robot import build_spec
    c = load_concept(A)
    c["packaging"] = ["t0004", "cad_foundation"]
    c["height_m"] = 0.5
    spec = build_spec(c)
    p = spec["body"]["proportions"]
    base = load_spec("adam")["body"]["proportions"]
    keys = ("ankle_height", "shank", "thigh", "pelvis", "torso", "neck", "head")
    assert p["ankle_height"] * 0.5 == pytest.approx(0.066)
    assert sum(p[k] for k in keys) == pytest.approx(sum(base[k] for k in keys))             # the standing height is kept
    rng = {j["name"]: j["range"] for j in spec["kinematics"]["joints"]}
    assert rng["knee"][1] == 115 and rng["hip_pitch"] == [-110, 40] and rng["ankle_pitch"] == [-60, 25]


def test_squat_deeper_than_the_knee_range_is_clamped_and_reported():
    c = load_concept(A)
    c["packaging"] = ["t0004", "cad_foundation"]
    kin = RobotKin(build_robot(c))
    refs = E.build_motions(kin)
    assert refs["squat_120"].meta["rom_clamped_from_deg"] == 120 and "ROM CLAMP" in " ".join(refs["squat_120"].notes)
    assert "rom_clamped_from_deg" not in refs["squat_90"].meta


def test_unsafe_pickles_are_refused_before_loading(tmp_path):
    import pickle
    from openhumanoid.concept.calibration import pickle_is_numpy_only

    class Evil:
        def __reduce__(self):
            return (os.system, ("echo no",))
    bad = tmp_path / "bad.pkl"
    bad.write_bytes(pickle.dumps(Evil()))
    good = tmp_path / "good.pkl"
    good.write_bytes(pickle.dumps({"a": np.zeros(3)}))
    assert pickle_is_numpy_only(bad)[0] is False and pickle_is_numpy_only(good)[0] is True


@pytest.mark.skipif(not os.environ.get("ODM_DIR"), reason="set ODM_DIR to a scratch clone of apirrone/Open_Duck_Playground (no licence: never inside this repo)")
@pytest.mark.slow
def test_open_duck_mini_calibration_runs(tmp_path):
    from openhumanoid.concept import odm_experiments as X
    assert os.path.abspath(os.environ["ODM_DIR"]).lower().startswith(str(CONCEPTS.parent.parent.parent).lower()) is False
    res = X.run_all(os.environ["ODM_DIR"], CONCEPTS, tmp_path, quick=True)
    assert res["structure_mass"]["gap_factor"] > 1.5 and res["b_frozen_on_odm"]["best"]["gates"]["peak_frac_of_stall"] > 0
    assert "| gate |" in X.to_markdown(res)


# ----------------------------------------------------------------------------------------------- whole-body pickup planner (T-20261019-a536)
R1P1R = CONCEPTS / "R1-P1r-0p55-3s-sts3250-knee-hiproll.yaml"


@pytest.fixture(scope="module")
def kin_r1():
    return RobotKin(build_robot(R1P1R))


def _table_distances(robot, ref):
    """Independent re-measurement: MuJoCo signed distance of EVERY robot geom to the table top in EVERY frame of the finished reference."""
    import mujoco
    m = robot.build_model(ref.scene["xml"])
    d = mujoco.MjData(m)
    tg = m.geom("table_top").id
    skip = {m.body("table").id, m.body("obj").id}
    geoms = [g for g in range(m.ngeom) if m.geom_bodyid[g] > 0 and int(m.geom_bodyid[g]) not in skip]
    qadr = np.array([m.joint(n).qposadr[0] for n in robot.names])
    ft = np.zeros(6)
    out = np.empty(len(ref.q))
    for i in range(len(ref.q)):
        d.qpos[:3], d.qpos[3:7], d.qpos[qadr] = ref.base_pos[i], ref.base_quat[i], ref.q[i]
        mujoco.mj_kinematics(m, d)
        out[i] = min(mujoco.mj_geomDistance(m, d, g, tg, 0.3, ft) for g in geoms)
    return out


def test_pickup_arm_ik_is_closed_form_and_exact(kin_r1):
    """The closed-form shoulder/elbow IK reproduces MuJoCo's forward kinematics, and unreachable targets are reported (not faked)."""
    from openhumanoid.concept.motions import pickup as P
    ctx = P._Ctx(kin_r1, "r", dict(P.PLAN))
    pose = P._pose(ctx, ctx.f0, 0.0, 0.0, 0.0)
    rng = np.random.default_rng(1)
    worst, n = 0.0, 0
    for _ in range(40):
        d = np.array([rng.uniform(0.02, 0.12), rng.uniform(-0.03, 0.004), -rng.uniform(0.05, 0.17)])
        if not (ctx.d_min + 0.004 < np.linalg.norm(d) < ctx.d_max - 0.004):
            continue
        Q, err = P._solve_arm(ctx, pose["Q"], pose["pel"], pose["quat"], pose["shoulder"] + d)
        worst, n = max(worst, err), n + 1
    assert n >= 10 and worst < 1e-4
    _, far = P._solve_arm(ctx, pose["Q"], pose["pel"], pose["quat"], pose["shoulder"] + np.array([0.0, 0.0, -0.40]))
    assert far > 0.15      # 40 cm below the shoulder is out of a 20 cm arm: the residual says so


def test_pickup_path_is_collision_free_and_table_height_is_a_parameter(kin_r1):
    from openhumanoid.concept.motions import pickup as P
    robot = kin_r1.robot
    seen = {}
    for z in (0.15, 0.30, 0.35):
        ref = P.pickup(kin_r1, table_height_m=z)
        assert ref.feasible and ref.meta["reachable"], ref.notes
        assert ref.meta["table_height_m"] == pytest.approx(z) and ref.scene["table_z"] == pytest.approx(z)
        dist = _table_distances(robot, ref)
        assert dist.min() > 0.0, f"{z} m: a robot geom comes {dist.min() * 1000:.1f} mm into the table at t={dist.argmin() * ref.dt:.2f} s"
        assert ref.meta["table_min_clearance_m"] >= P.PLAN["clearance_m"] - 1e-9
        assert ref.meta["standing_gap_m"] >= 0.0 and ref.meta["lift_m"] >= 0.03
        assert ref.meta["carried_object_clearance_min_m"] > 0.015      # the object stays off the table through the stand-up
        seen[z] = ref
    # the table height changes the posture: a low table needs the whole body (deep knee + hip hinge), a mid one only the arm
    assert seen[0.15].meta["squat_deg"] > seen[0.30].meta["squat_deg"] + 10 and seen[0.15].meta["hip_hinge_deg"] > 0
    assert seen[0.15].meta["squat_deg"] <= seen[0.15].meta["knee_range_max_deg"]
    from openhumanoid.concept.motions.common import check_ranges
    assert not check_ranges(kin_r1, seen[0.15].q)             # every joint stays inside its range (asserted independently of the planner)


def test_pickup_respects_the_knee_range_and_reports_why_it_fails(kin_r1):
    from openhumanoid.concept.motions import pickup as P
    c = load_concept(R1P1R)
    c["joints"] = [({"name": "knee", "range": [0, 60]} if (isinstance(j, dict) and j["name"] == "knee") else j) for j in c["joints"]]
    k60 = RobotKin(build_robot(c))
    ref = P.pickup(k60, table_height_m=0.15)
    knee_max = max(np.degrees(ref.q[:, k60.index["knee_l"]]).max(), np.degrees(ref.q[:, k60.index["knee_r"]]).max())
    assert knee_max <= 60.0 + 0.5
    if ref.feasible:
        assert ref.meta["squat_deg"] <= 60.0
    else:
        assert ref.meta["limit"] in ("arm reach", "table collision", "balance", "leg joint range", "path/IK") and "pickup at 0.15 m" in " ".join(ref.notes)


def test_pickup_out_of_reach_is_infeasible_and_says_why(kin_r1):
    from openhumanoid.concept.motions import pickup as P
    ref = P.pickup(kin_r1, table_height_m=0.60)         # above the shoulder of a 0.55 m robot
    assert not ref.feasible and ref.meta["reachable"] is False and ref.meta["limit"] == "arm reach"
    assert "pickup at 0.60 m" in " ".join(ref.notes) and "arm too short" in " ".join(ref.notes)


def test_pickup_balance_is_named_when_it_is_what_binds(kin_r1):
    from openhumanoid.concept.motions import pickup as P
    ok, info_ok = P.plan_pickup(kin_r1, 0.30)
    assert ok is not None
    assert info_ok["balance_margin_min_m"] >= P.PLAN["balance_margin_foot_lengths"] * kin_r1.lg.foot_len - 1e-4      # COM inside the foot polygon in every frame
    # force the COM to the toe edge (zero margin): the arm can reach, the legs can stand, only balance forbids it
    ref, info = P.plan_pickup(kin_r1, 0.30, plan={"com_fracs": (1.0,)})
    assert ref is None and info["limit"] == "balance"


def test_pickup_reach_range_reports_segments_and_limits(kin_r1):
    from openhumanoid.concept.motions import pickup as P
    r = P.reach_range(kin_r1, lo=0.30, hi=0.35, step=0.05, resolution=0.05)
    assert r["segments"] == [{"from_m": 0.30, "to_m": 0.35}] and r["max_reachable_m"] == 0.35 and r["min_reachable_m"] == 0.30
    assert all(x["reachable"] and x["table_clearance_mm"] >= 3.0 and x["balance_margin_mm"] > 0 for x in r["rows"])
    r2 = P.reach_range(kin_r1, lo=0.60, hi=0.60, step=0.05)
    assert r2["segments"] == [] and r2["rows"][0]["limit"] == "arm reach"


def test_pickup_lift_point_stays_on_the_arm_circle():
    from openhumanoid.concept.motions import pickup as P
    sh = np.array([0.0, -0.1, 0.4])
    G = sh + np.array([0.2, 0.0, -0.01])
    h = np.array([1.0, 0.0, 0.0])
    L = P._lift_point(sh, G, h, 0.04)
    assert L[2] - G[2] == pytest.approx(0.04) and np.linalg.norm(L - sh) == pytest.approx(np.linalg.norm(G - sh))
    assert P._lift_point(sh, sh + np.array([0.01, 0.0, 0.0]), h, 0.5)[2] == pytest.approx(sh[2] + 0.5)   # cannot rise on the circle: falls back to vertical


@pytest.mark.slow
def test_pickup_replay_has_no_table_spike_and_the_servo_grasp_lifts(kin_r1):
    """The R1 review's 131x-stall spike was the hand path colliding with the table. Replayed through the engine's own ideal playback the
    new path stays under the gate, and the servo-in-the-loop grasp lifts the 150 g object."""
    from openhumanoid.concept.motions import pickup as P
    d = P.demand_at(R1P1R, 0.35, servo=True)
    assert d["valid"], d.get("reason")
    assert d["worst_peak_frac"] < config.gate("peak_torque_fraction_of_stall") and d["tether_pct_bw"] < 1.0
    assert {"shoulder_pitch_r", "elbow_r", "waist_yaw"} <= set(d["arm_waist_gripper"])
    assert d["servo"]["grasp_ok"] and d["servo"]["overload_trips"] == 0 and not d["servo"]["fell"]


def test_pickup_works_with_the_left_hand_too(kin_r1):
    from openhumanoid.concept.motions import pickup as P
    ref = P.pickup(kin_r1, table_height_m=0.30, side="l")
    assert ref.feasible and ref.meta["reachable"], ref.notes
    assert _table_distances(kin_r1.robot, ref).min() > 0.0
    assert ref.q[:, kin_r1.index["gripper_l"]].max() > 0.05 and ref.q[:, kin_r1.index["gripper_r"]].max() < 0.01     # only the working hand opens


def test_pickup_uses_the_waist_and_the_hip_hinge_when_asked(kin_r1):
    """Both torso levers are in the planner and produce collision-free, in-range references (the cheapest posture does not need them at 0.35 m)."""
    from openhumanoid.concept.motions import pickup as P
    from openhumanoid.concept.motions.common import check_ranges
    twist = P.pickup(kin_r1, table_height_m=0.35, plan={"waist_deg": (30.0,), "hinge_deg": (0.0,)})
    assert twist.feasible and twist.meta["waist_yaw_deg"] == pytest.approx(30.0)
    assert np.degrees(twist.q[:, kin_r1.index["waist_yaw"]]).max() == pytest.approx(30.0, abs=0.5)
    hinge = P.pickup(kin_r1, table_height_m=0.35, plan={"waist_deg": (0.0,), "hinge_deg": (20.0,)})
    assert hinge.feasible and hinge.meta["hip_hinge_deg"] == pytest.approx(20.0)
    for ref in (twist, hinge):
        assert _table_distances(kin_r1.robot, ref).min() > 0.0 and not check_ranges(kin_r1, ref.q)
        assert ref.meta["balance_margin_min_m"] >= P.PLAN["balance_margin_foot_lengths"] * kin_r1.lg.foot_len - 1e-4
