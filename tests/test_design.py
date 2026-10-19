"""Design tooling (ADR 0010): profiles, massing, silhouettes, metrics, calibration, critic rules, doc/agent sync."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
import yaml

pytest.importorskip("skimage")
pytest.importorskip("trimesh")

from openhumanoid.design import calibrate, critic, metrics, silhouette as sil  # noqa: E402
from openhumanoid.design.cli import main as design_main  # noqa: E402
from openhumanoid.design.massing import build_massing, hard_point_margins  # noqa: E402
from openhumanoid.design.meshio import load_subject  # noqa: E402
from openhumanoid.design.profiles import ProfilesError, load_profiles, validate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "openhumanoid" / "design"
SAMPLE = DESIGN / "sample" / "sample_sleek_050.yaml"
REFS = DESIGN / "references"


@pytest.fixture(scope="module")
def sleek():
    return load_subject(SAMPLE)


@pytest.fixture(scope="module")
def toy():
    return load_subject(REFS / "toy_chibi.yaml")


# ----------------------------------------------------------------------------------------------------- profiles
def test_all_shipped_profiles_validate():
    for p in [SAMPLE, *REFS.glob("*.yaml")]:
        assert load_profiles(p)["height_m"] > 0, p


def test_profiles_mirror_and_defaults():
    prof = load_profiles(SAMPLE)
    ids = [s["id"] for s in prof["segments"]]
    assert "leg_l" in ids and "leg_r" in ids and "leg" not in ids
    left = next(s for s in prof["segments"] if s["id"] == "arm_l")
    right = next(s for s in prof["segments"] if s["id"] == "arm_r")
    assert left["stations"][0]["cy"] == pytest.approx(-right["stations"][0]["cy"])
    assert all("n" in st for st in left["stations"])
    assert any(j["id"] == "hip_r" for j in prof["joints"])
    assert prof["head_unit_m"] > 0


def test_profiles_reject_bad_input():
    data = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    bad = copy.deepcopy(data)
    bad["segments"][0]["stations"].reverse()
    assert any("increasing" in e for e in validate(bad))
    bad = copy.deepcopy(data)
    bad["segments"][0]["stations"][0]["w"] = -1
    assert validate(bad)
    bad = copy.deepcopy(data)
    bad["segments"].append(copy.deepcopy(bad["segments"][0]))
    assert any("duplicate" in e for e in validate(bad))
    bad = copy.deepcopy(data)
    bad["surprise"] = 1
    assert validate(bad)


def test_load_profiles_raises_with_all_problems(tmp_path):
    data = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    data["height_m"] = -1
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ProfilesError):
        load_profiles(p)


# ------------------------------------------------------------------------------------------------------ massing
def test_massing_is_smooth_watertight_and_right_size(sleek):
    m = sleek.whole
    assert m.is_watertight
    assert m.bounds[1][2] == pytest.approx(0.5, abs=0.006)
    assert m.bounds[0][2] == pytest.approx(0.0, abs=0.006)
    assert m.volume > 0
    # smooth, not boxy: no big planar facets
    assert metrics.compute(sleek)["S4_flat_area_fraction"] < 0.15


def test_massing_labels_cover_the_segments(sleek):
    assert {"head", "torso", "leg_l", "leg_r", "arm_l", "arm_r", "foot_l", "foot_r"} <= set(sleek.parts)


def test_hard_points_enclosed_in_sample_and_detect_violation():
    prof = load_profiles(SAMPLE)
    assert all(h["pass"] for h in hard_point_margins(prof))
    bad = copy.deepcopy(prof)
    bad["hard_points"][0]["size"] = [0.2, 0.2, 0.2]
    assert not all(h["pass"] for h in hard_point_margins(bad))


# --------------------------------------------------------------------------------------------------- silhouettes
def test_silhouette_framing_is_height_normalised(sleek):
    f = sil.rasterise(list(sleek.render_meshes.values()), "front", sleek.height_m)
    ys = __import__("numpy").flatnonzero(f.mask.any(axis=1))
    assert ys.max() - ys.min() + 1 == pytest.approx(sil.H_PX, abs=3)
    assert ys.max() == pytest.approx(sil.GROUND_ROW, abs=3)
    n = sil.normalise_mask(f.mask)
    assert sil.iou(n, n) == 1.0
    assert sil.iou(n, sil.normalise_mask(sil.rasterise(list(load_subject(REFS / "toy_chibi.yaml").render_meshes.values()), "front").mask)) < 0.7


def test_mask_from_image_round_trip(tmp_path, sleek):
    f = sil.rasterise(list(sleek.render_meshes.values()), "front", sleek.height_m)
    p = tmp_path / "ref.png"
    sil.save_mask(f.mask, p)
    assert sil.iou(sil.from_image(p), sil.normalise_mask(f.mask)) > 0.97


# ----------------------------------------------------------------------------------------------------- metrics
def test_metrics_land_on_known_proportions():
    # human canon built from Drillis-Contini-like numbers: head ~0.125-0.13 H, knee 0.285, shoulder ~0.27-0.28
    m = metrics.compute(load_subject(REFS / "human_canon.yaml"))
    assert 0.11 < m["P1_head_height_f"] < 0.14
    assert 0.25 < m["P3_shoulder_width_f"] < 0.30
    assert m["P7_knee_height_f"] == pytest.approx(0.285, abs=0.005)
    assert m["P8_thigh_taper_area"] < 0.65


def test_metrics_pass_sleek_and_fail_toy(sleek, toy):
    ev_s = metrics.evaluate(metrics.compute(sleek))
    ev_t = metrics.evaluate(metrics.compute(toy))
    assert ev_s["failed"] == []
    assert {"P1", "P3", "P6", "P10a", "S4a"} <= set(ev_t["failed"])
    assert ev_s["pass_fraction"] > ev_t["pass_fraction"] + 0.4


def test_s1_iou_against_approved(sleek):
    m = metrics.compute(sleek, approved=sleek)
    assert m["S1_iou_front"] == pytest.approx(1.0) and m["S1_iou_side"] == pytest.approx(1.0)
    ev = metrics.evaluate(m)
    assert ev["criteria"]["S1a"]["verdict"] == "PASS"


def test_calibration_separates_sleek_from_toy():
    rep = calibrate.run(None)
    assert rep["gap"]["separates"], rep["summary"]
    refs = [n for n, s in rep["summary"].items() if s["kind"] == "reference"]
    assert len(refs) >= 3 and all(rep["summary"][n]["failed"] == [] for n in refs)


def test_adam_cad_roblox_look_is_flagged():
    pytest.importorskip("mujoco")
    xml = ROOT / "variants" / "adam" / "cad" / "export" / "robot.xml"
    if not xml.exists():
        pytest.skip("run `oh cad build adam` to regenerate variants/adam/cad/export")
    m = metrics.compute(load_subject(xml, "adam_cad_v0"))
    ev = metrics.evaluate(m)
    assert m["P3_shoulder_width_f"] > 0.40          # research 07 §4 measured ~0.45 by pixel analysis
    assert {"P3", "S3a", "S4a", "S5a"} <= set(ev["failed"])
    assert ev["pass_fraction"] < 0.5


def test_cli_metrics_writes_json(tmp_path):
    out = tmp_path / "m.json"
    assert design_main(["metrics", str(SAMPLE), "--out", str(out), "--name", "x"]) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["evaluation"]["n_scored"] > 10 and rep["subject"] == "x"


# ------------------------------------------------------------------------------------------------- studio render
def test_studio_silhouette_set_and_sheet(tmp_path, sleek):
    from openhumanoid.design.studio import render_studio

    res = render_studio(sleek, tmp_path, refs=[f"opt={REFS / 'optimus_like.yaml'}"], clay=False)
    for k in ("silhouette_front", "silhouette_side", "overlay_front", "lineup_front", "sheet"):
        assert res["files"][k].exists(), k
    meta = json.loads((tmp_path / "studio.json").read_text(encoding="utf-8"))
    assert meta["rig_version"] == 1 and meta["refs"] == ["opt"]


def test_studio_clay_render_smoke(tmp_path, sleek):
    pv = pytest.importorskip("pyvista")
    from openhumanoid.design.studio import render_clay

    try:
        f = render_clay(sleek, "front", tmp_path / "clay.png", size=(200, 300))
    except Exception as e:  # headless CI without a GL context
        pytest.skip(f"offscreen GL unavailable: {e}")
    from PIL import Image
    im = Image.open(f)
    assert im.size == (200, 300)


# ------------------------------------------------------------------------------------------------- critic rules
def _rep(order, verdict="PASS", pref="candidate", reads="product", change=None):
    return {"order": order, "reads_as": reads,
            "criteria": {g: {"verdict": verdict, "evidence": "e"} for g in critic.GESTALT},
            "pairwise": {"preferred": pref}, "top_changes": change or []}


def test_critic_passes_only_when_everything_consistent():
    r = critic.combine([_rep("cand_first"), _rep("cand_second")])
    assert r["pass"] and r["criteria"]["G5"]["verdict"] == "PASS"


def test_critic_uncertain_is_no_pass():
    r = critic.combine([_rep("cand_first"), _rep("cand_second", verdict="UNCERTAIN")])
    assert not r["pass"] and r["criteria"]["G1"]["verdict"] == "UNCERTAIN"


def test_critic_position_bias_is_no_pass():
    r = critic.combine([_rep("cand_first", pref="candidate"), _rep("cand_second", pref="baseline")])
    assert not r["pass"] and r["criteria"]["G5"]["verdict"] != "PASS"
    r = critic.combine([_rep("cand_first", pref="candidate")])      # single order is not enough either
    assert not r["pass"]


def test_critic_toy_reading_fails_and_changes_are_capped():
    ch = [{"criterion": "G1", "change": str(i), "profile_param": "p"} for i in range(5)]
    r = critic.combine([_rep("single", verdict="FAIL", reads="toy", change=ch)])
    assert not r["pass"] and len(r["top_changes"]) == 3


def test_critic_round_cap_and_numeric_override(tmp_path, sleek):
    state = tmp_path / "s.json"
    for i in range(3):
        r = critic.combine([_rep("single", verdict="FAIL")], state_path=state)
    assert r["round"] == 3 and "escalate" in r["next"]
    mpath = tmp_path / "m.json"
    metrics.write_report(load_subject(REFS / "toy_chibi.yaml"), mpath)
    r = critic.combine([_rep("cand_first"), _rep("cand_second")], metrics_path=mpath)
    assert not r["pass"] and r["numeric_hard_failures"]


def test_extract_json_from_reply():
    txt = 'thinking...\n```json\n{"reads_as": "toy", "criteria": {}}\n```\n'
    assert critic.extract_json(txt)["reads_as"] == "toy"


# ------------------------------------------------------------------------------- docs / agent / rubric in sync
def test_rubric_ids_documented_and_critic_prompt_in_sync():
    rubric = yaml.safe_load((DESIGN / "rubric.yaml").read_text(encoding="utf-8"))
    doc = (ROOT / "docs" / "design-method.md").read_text(encoding="utf-8")
    agent = (ROOT / ".claude" / "agents" / "design-critic.md").read_text(encoding="utf-8")
    for item in rubric["metrics"] + rubric["informational"]:
        assert re.search(rf"\b{item['id']}\b", doc), f"{item['id']} missing from docs/design-method.md"
    for g in rubric["gestalt"]:
        assert re.search(rf"\b{g['id']}\b", doc), f"{g['id']} missing from docs"
        assert re.search(rf"\b{g['id']}\b", agent), f"{g['id']} missing from the critic prompt"
        assert g["name"].split(":")[0][:30] in agent or g["id"] == "G5", f"{g['id']} wording drifted from the critic prompt"
    for band in ("0.11", "0.29", "0.30"):  # a few calibrated numbers must appear in the doc
        assert band in doc
    assert "UNCERTAIN" in agent and "profile_param" in agent and "cand_second" in agent


def test_critic_agent_is_read_only_sonnet():
    agent = (ROOT / ".claude" / "agents" / "design-critic.md").read_text(encoding="utf-8")
    head = yaml.safe_load(agent.split("---")[1])
    assert head["name"] == "design-critic" and head["model"] == "sonnet"
    assert [t.strip() for t in str(head["tools"]).split(",")] == ["Read"]


def test_rig_is_committed_and_matches_silhouette_constants():
    rig = yaml.safe_load((DESIGN / "rig.yaml").read_text(encoding="utf-8"))
    assert rig["silhouette"]["canvas_px"] == sil.CANVAS
    assert rig["silhouette"]["height_px"] == sil.H_PX
    assert rig["silhouette"]["ground_row"] == sil.GROUND_ROW
    assert set(rig["clay"]["views"]) >= {"front", "side", "back", "three_quarter"}
