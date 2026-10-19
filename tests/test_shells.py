"""Smoke tests for the shell-method bake-off (T-20261019-9746): one per method plus the shared spec and the evaluator.

Fast on purpose (a coarse M2 voxel, a coarse ROM sweep); the full bake-off is `python -m openhumanoid.design.shells.bakeoff`.
Skipped when the optional design/cad extras (build123d, manifold3d, trimesh, scikit-image) are missing; the evaluator
also needs rtree + shapely, M3 needs the separate bpy virtualenv.
"""
import numpy as np
import pytest

pytest.importorskip("build123d")
pytest.importorskip("manifold3d")
pytest.importorskip("trimesh")
pytest.importorskip("skimage")

from openhumanoid.design.shells import spec as S  # noqa: E402
from openhumanoid.design.shells.spec import LegSpec  # noqa: E402

PANELS = {"thigh_front", "thigh_rear", "shank_front", "shank_rear"}


def test_spec_keepouts_fit_the_nominal_silhouette():
    f = S.feasibility(LegSpec())
    assert all(v["ok"] for v in f.values()), f


def test_knee_cutter_is_star_shaped_and_grows_with_flexion():
    a = S.knee_cutter_polygon(LegSpec(flex_max_deg=90.0), 3.0)
    b = S.knee_cutter_polygon(LegSpec(flex_max_deg=130.0), 3.0)
    assert len(a) > 20 and len(b) > 20
    ra = np.hypot(*a.T).max()
    # the swept region covers at least the thigh outline at every angle: radius never below the cap radius
    assert np.hypot(*b.T).min() > 20.0 and ra > 0
    reg90, reg130 = S.PolarRegion(a), S.PolarRegion(b)
    assert reg130.contains(np.array([-40.0]), np.array([-45.0]))      # behind and below the knee: inside the 130 deg sweep
    assert not reg90.contains(np.array([-40.0]), np.array([-45.0]))


def test_spec_scaling_moves_axes_not_servos():
    s = LegSpec(length_scale=1.1)
    ko = {k.name: k for k in s.keepouts()}
    assert ko["servo_hip_pitch"].center[2] > LegSpec().keepouts()[1].center[2]
    assert ko["servo_knee"].size == LegSpec().keepouts()[0].size


@pytest.fixture(scope="module")
def m1(tmp_path_factory):
    from openhumanoid.design.shells import m1_build123d

    step = tmp_path_factory.mktemp("m1") / "shells.step"
    ss = m1_build123d.build(LegSpec(), step_path=str(step))
    return ss, step


def test_m1_panels_watertight_and_step_exported(m1):
    ss, step = m1
    assert set(ss.parts) == PANELS
    assert all(m.is_watertight and m.volume > 5000 for m in ss.parts.values())
    assert step.exists() and step.stat().st_size > 10_000
    assert all(ss.notes["brep_valid"].values())


def test_m2_panels_watertight():
    from openhumanoid.design.shells import m2_sdf

    ss = m2_sdf.build(LegSpec(), voxel=1.0)
    assert set(ss.parts) == PANELS
    assert all(m.is_watertight for m in ss.parts.values())
    assert ss.step_path is None          # mesh only: this is the cosmetic-part case of ADR I5


def test_m3_panels_watertight():
    from openhumanoid.design.shells import m3_bpy

    if not m3_bpy.available():
        pytest.skip("bpy virtualenv not available (.venv-bpy or OH_BPY_PYTHON)")
    ss = m3_bpy.build(LegSpec(), calibrate_passes=1)
    assert set(ss.parts) == PANELS
    assert all(m.is_watertight for m in ss.parts.values())


def test_evaluator_on_m1(m1):
    pytest.importorskip("rtree")
    pytest.importorskip("shapely")
    from openhumanoid.design.shells import evaluate as ev

    ss, _ = m1
    look = ev.look_metrics(ss.parts, ss.spec)
    assert look["T1_iou_front"] > 0.9 and look["T1_iou_side"] > 0.9
    rom = ev.rom_sweep(ss.parts, ss.spec, step_deg=30.0)
    assert rom["collision_free"] and rom["gap_at_0deg_mm"] > 1.0
    pr = ev.printability(ss.parts, ss.spec, with_wall=False)
    assert pr["all_watertight"] and pr["all_fit_bed"] and pr["part_count"] == 4
