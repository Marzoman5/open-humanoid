"""Framework tests. Includes a synthetic large/expensive variant to catch Adam-only assumptions."""
import copy

import pytest

from openhumanoid import catalog, coord
from openhumanoid.sizing import evaluate, size
from openhumanoid.spec import DEFAULTS, deep_merge, expand_joints, load_spec, validate, load_raw


@pytest.fixture(scope="module")
def adam():
    return load_spec("adam")


def big_variant(adam):
    """A 1.2 m (G1-class), $20k, 48 V robot with a straighter-legged gait: must NOT land on hobby servos."""
    s = copy.deepcopy(adam)
    s["body"]["height_m"] = 1.2
    s["locomotion"] = {"walk": {"required": True, "step_freq_hz": 1.2, "knee_amplitude_rad": 0.6, "stance_knee_flex_deg": 20}}
    s["goals"]["budget_usd"] = {"target": 20000, "hard_cap": 20000}
    s["actuation"]["supply_voltage_v"] = [44, 50]
    s["actuation"]["require_feedback"] = "torque"
    s["actuation"]["uniform"] = False
    s["mass_model"]["structure_kg_at_1m"] = 9.0
    return s


def test_adam_spec_and_catalog_valid():
    assert validate(load_raw("adam")) == []
    assert catalog.validate_catalog() == []


def test_deep_merge_lists_replace():
    assert deep_merge({"a": {"b": 1, "c": [1, 2]}}, {"a": {"c": [3]}}) == {"a": {"b": 1, "c": [3]}}


def test_mirroring(adam):
    j = {x["name"]: x for x in expand_joints(adam)}
    assert j["hip_roll_l"]["range"] == [-30, 45]
    assert j["hip_roll_r"]["range"] == [-45, 30]
    assert j["knee_l"]["range"] == j["knee_r"]["range"]


def test_adam_feasible_and_walks(adam):
    r = size(adam)
    b = r["best"]
    assert b.feasible
    assert 0.40 <= b.height <= 0.75
    assert b.gait_checks["walk"]["ok"]
    assert b.cost["total"] <= adam["goals"]["budget_usd"]["hard_cap"]


def test_big_variant_selects_bldc(adam):
    s = big_variant(adam)
    ev = evaluate(s, 1.2, [j["name"] for j in s["kinematics"]["joints"] if j.get("priority") == "required"])
    assert ev.selection, ev.reason
    types = {catalog.get(a)["actuator"]["type"] for a in ev.selection.values()}
    assert types <= {"bldc_qdd", "bldc_planetary", "bldc_harmonic"}


def test_pwm_servo_rejected_for_feedback(adam):
    from openhumanoid.sizing import candidates
    _, rejected = candidates(adam)
    assert "mg996r" in rejected


def test_paths_overlap():
    assert coord.paths_overlap("modules/", "modules/joints/knee/")
    assert coord.paths_overlap("variants/*/cad/", "variants/adam/cad/leg.py")
    assert not coord.paths_overlap("sim/", "software/")


def test_sim_smoke(adam):
    pytest.importorskip("mujoco")
    from openhumanoid import reports, simgen
    reports.write_sizing(adam, size(adam))
    r = simgen.smoke_test(adam, seconds=1.0)
    assert r["ok"], r


def test_repo_root_prefers_package_checkout(tmp_path, monkeypatch):
    """Lesson 2026-10-19: running from another checkout's cwd must not switch repos."""
    from pathlib import Path
    from openhumanoid import paths
    fake = tmp_path / "other_checkout"
    (fake / "schemas").mkdir(parents=True)
    (fake / "AGENTS.md").write_text("x")
    monkeypatch.chdir(fake)
    monkeypatch.delenv("OPENHUMANOID_ROOT", raising=False)
    assert paths.repo_root() == Path(paths.__file__).resolve().parents[1]
