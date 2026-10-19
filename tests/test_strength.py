"""G-strength: material model, section engine, load chain, fillets, analytic checks against beam theory, policy provenance.

Fast tests build tiny build123d parts (a few seconds); the FEA cross-check meshes a bar with gmsh and solves with scikit-fem
(tests/test_strength_fea.py); the full leg run is marked slow.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

build123d = pytest.importorskip("build123d")
bd = build123d

from openhumanoid.cad import dfm  # noqa: E402
from openhumanoid.cad.core import box_at, mesh_of, safe_union  # noqa: E402
from openhumanoid.cad.fillets import concave_edges, fillet_internal  # noqa: E402
from openhumanoid.cad.strength import policy as pol  # noqa: E402
from openhumanoid.cad.strength.analytic import PartAnalyzer  # noqa: E402
from openhumanoid.cad.strength.loadpath import Load, PartLoads  # noqa: E402
from openhumanoid.cad.strength.model import PartRec  # noqa: E402
from openhumanoid.cad.strength.sections import slice_mesh, stress  # noqa: E402


# ------------------------------------------------------------------------------------------------------------------ helpers
def part_from_shape(pid: str, shape, material="petg", up=(0, 0, 1), corners=None, profile=None) -> PartRec:
    from openhumanoid.cad.strength.corners import corners as _corners

    m = mesh_of(shape, tol=0.03, ang=0.15)
    dens = pol.material(material).density
    return PartRec(pid, "link", "frame", "fdm", material, None, float(m.volume) * 1e-6 * dens * 0.45, np.array(up, float), m, float(m.volume),
                   np.array(m.center_mass), [], {}, profile or {}, _corners(shape) if corners is None else corners, None)


def l_foot(t_plate=4.3, w=28.0, t_sole=3.2, fillet=0.0, ribs=False):
    """The v2 foot in miniature: a vertical plate on a sole (plate x = [-22, -22 + t]), sole x = [-34, 68]."""
    plate = box_at(bd.Location(), (t_plate, w, 52.0), (-22.0 + t_plate / 2, 0, 26.0))
    sole = box_at(bd.Location(), (102.0, 45.0, t_sole), (17.0, 0, t_sole / 2))
    body = safe_union(plate, sole, "foot")
    if ribs:
        pts = [(-22 + t_plate - 0.5, t_sole - 0.5), (40.0, t_sole - 0.5), (40.0, t_sole + 8.0), (-22 + t_plate - 0.5, t_sole + 22.0)]
        for yy in (-12.0, 0.0, 12.0):
            wire = bd.Wire.make_polygon([bd.Vector(x, yy - 2.0, z) for x, z in pts], close=True)
            body = safe_union(body, bd.extrude(bd.Face(wire), amount=4.0, dir=(0, 1, 0)), "rib")
    if fillet > 0:
        body, _ = fillet_internal(body, fillet, 6.0, "foot", region=((-1e4, -1e4, -1e4), (1e4, 1e4, t_sole + 1.0)))
    return body


def toe_load(F=85.0, x_toe=68.0, x_horn=-22.0) -> PartLoads:
    """Ground reaction F at the toe, equal and opposite reaction at the horn (on the plate underside), self weight neglected."""
    pl = PartLoads("foot", "link", g_link=np.zeros(3))
    pl.loads = [Load(np.array([x_toe, 0, 0.0]), np.array([0, 0, F]), np.zeros(3), "toe"),
                Load(np.array([x_horn, 0, 38.0]), np.array([0, 0, -F]), np.array([0, F * (x_toe - x_horn), 0.0]), "horn")]
    return pl


# ------------------------------------------------------------------------------------------------------------------ materials
def test_material_directional_allowable_and_provenance():
    m = pol.material("petg")
    knock = float(pol.pv(pol.policy(), "knockdown", "process"))
    assert m.tensile(90.0) == pytest.approx(knock * 37.9, rel=1e-6)          # load in the layer plane: XY value
    assert m.tensile(0.0) == pytest.approx(knock * 29.4, rel=1e-6)           # layers pulled apart: Z value
    assert m.tensile(0.0) < m.tensile(45.0) < m.tensile(90.0)
    assert m.shear(0.0) == pytest.approx(0.5 * m.tensile(0.0))
    cf = pol.material("cf-nylon")
    assert cf.sigma_z / cf.sigma_xy < 0.7                                    # CF-nylon is the most anisotropic (print_materials.yaml)
    assert pol.material("PLA_plus").key == "PLA_plus" and pol.material("pla-plus").key == "PLA_plus"
    with pytest.raises(KeyError):
        pol.material("unobtainium")
    # endurance: S-N lift at the design life, sourced PLA fraction 10 %
    pla = pol.material("PLA")
    assert pla.endurance_fraction == pytest.approx(0.10)
    assert pla.endurance(90.0) > 0.10 * pla.tensile(90.0)


def test_material_table_matches_dfm_knockdowns():
    d = dfm.load_dfm()["orientation"]["z_over_xy_strength"]
    for k, v in d.items():
        if k in ("PLA", "PLA_plus", "PETG", "ASA", "CF_nylon"):
            m = pol.material(k)
            assert m.sigma_z / m.sigma_xy == pytest.approx(v, abs=0.01)


def test_policy_every_number_has_a_provenance_kind():
    p = pol.policy()
    allowed = {"sourced", "derived", "assumption", "policy"}
    missing = []

    def walk(node, path):
        if isinstance(node, dict):
            if "v" in node or any(k in node for k in ("M2", "M3")) and "kind" in node:
                kind = node.get("kind")
                if kind not in allowed:
                    missing.append("/".join(path))
                if kind == "assumption" and not (node.get("src") or node.get("test")):
                    missing.append("/".join(path) + " (assumption without src/test)")
            for k, v in node.items():
                walk(v, path + [str(k)])

    for sect in ("knockdown", "fatigue", "stress_concentration", "fall", "walking", "handling", "joint_torque", "print_profile"):
        walk(p[sect], [sect])
    assert not missing, missing
    sf = p["safety_factors"]
    assert sf["fall"]["sf"] >= 2.0 and sf["walk"]["sf"] >= 3.0 and sf["stall"]["sf"] >= 1.5          # the brief's floor values
    assert sf["fall_rigid"]["gate"] is False and sf["walk"]["gate"] is True


# ------------------------------------------------------------------------------------------------------------------ sections
def test_section_stress_matches_beam_theory_for_a_cantilever():
    b, h, L, F = 20.0, 10.0, 100.0, 50.0
    bar = box_at(bd.Location(), (L, b, h), (L / 2, 0, 0))               # x = 0..L, y +-10, z +-5
    mesh = mesh_of(bar)
    sec = slice_mesh(mesh, np.array([40.0, 0, 0]), np.array([1.0, 0, 0]), shell=0.0, fill=1.0)
    assert sec.A == pytest.approx(b * h, rel=1e-3)
    # tip load F down at x = L; the part beyond the plane carries it: internal wrench on the far body from the near body
    F_far, M_far = np.array([0, 0, -F]), np.cross(np.array([L, 0, 0]) - sec.c, np.array([0, 0, -F]))
    r = stress(sec, -F_far, -M_far)
    M = F * (L - 40.0)
    assert r.sigma == pytest.approx(M * (h / 2) / (b * h ** 3 / 12), rel=0.02)         # sigma = M c / I
    assert r.tau == pytest.approx(1.5 * F / (b * h), rel=0.05)                         # rectangle: 1.5 V / A


def test_torsion_of_a_thin_rectangle_uses_saint_venant():
    b, t, T = 30.0, 3.0, 1000.0
    bar = box_at(bd.Location(), (60.0, b, t), (30.0, 0, 0))
    sec = slice_mesh(mesh_of(bar), np.array([30.0, 0, 0]), np.array([1.0, 0, 0]), shell=0.0, fill=1.0)
    J = b * t ** 3 / 3.0 * (1 - 0.63 * t / b)
    assert sec.J == pytest.approx(J, rel=0.03)
    r = stress(sec, np.zeros(3), np.array([-T, 0, 0.0]))
    assert r.tau == pytest.approx(T * t / J, rel=0.03)


def test_infill_weighting_reduces_inertia_but_keeps_the_skin():
    bar = box_at(bd.Location(), (60.0, 30.0, 12.0), (30.0, 0, 0))
    solid = slice_mesh(mesh_of(bar), np.array([30.0, 0, 0]), np.array([1.0, 0, 0]), shell=0.0, fill=1.0)
    sparse = slice_mesh(mesh_of(bar), np.array([30.0, 0, 0]), np.array([1.0, 0, 0]), shell=1.8, fill=0.15)
    assert sparse.A < solid.A and sparse.Svv < solid.Svv
    assert sparse.Svv > 0.65 * solid.Svv                                   # the skin carries most of the bending stiffness


# ------------------------------------------------------------------------------------------------------------------ fillets / corners
def test_fillet_internal_rounds_the_sharp_cantilever_root_and_stays_watertight():
    sharp = l_foot(fillet=0.0)
    r = l_foot(fillet=4.0)
    assert len(concave_edges(sharp, 6.0)) >= 2
    c0 = [c for c in part_from_shape("s", sharp).corners if c["kind"] == "sharp"]
    c1 = part_from_shape("f", r).corners
    assert c0 and any(c["kind"] == "fillet" and c["r"] == pytest.approx(4.0, abs=0.1) for c in c1)
    assert r.volume > sharp.volume and r.is_valid and len(r.solids()) == 1
    assert mesh_of(r).is_watertight


def test_dfm_has_structural_rules():
    d = dfm.load_dfm()
    assert dfm.fillet_default() >= dfm.fillet_min() >= 2.0
    assert dfm.fillet_min(10.0) == pytest.approx(5.0)                       # r >= 0.5 t for thick plates
    assert "gusset" in d["cantilever_rules"] and d["structural_print"]["perimeters"]["load_path"] >= 6


# ------------------------------------------------------------------------------------------------------------------ analytic checks
def _worst(part: PartRec, loads: PartLoads, cls="fall", case="toe"):
    rows = PartAnalyzer(part).evaluate(loads, case, cls)
    return {r.check: r for r in rows}


def test_thin_cantilever_foot_fails_and_the_ribbed_filleted_foot_passes():
    before = part_from_shape("foot_v2", l_foot(), profile={"perimeters": 4, "infill_pct": 40})
    after = part_from_shape("foot_v3", l_foot(t_plate=8.0, t_sole=6.5, fillet=4.0, ribs=True), material="cf-nylon", up=(0, 1, 0),
                            profile={"perimeters": 6, "infill_pct": 60})
    rb = _worst(before, toe_load())["section"]
    ra = _worst(after, toe_load())["section"]
    assert rb.margin < 0.2, rb.margin                                       # the maintainer's thin 90-degree cantilever: far below 1
    assert ra.margin > 1.0, ra.margin
    assert ra.margin > 8 * rb.margin
    assert "delamination" in rb.mode                                        # plate printed standing: bending runs across the layers
    assert rb.info["kt"] > 2.0 and ra.info["kt"] < rb.info["kt"]           # sharp corner Kt vs the 4 mm fillet


def test_print_orientation_changes_the_allowable_not_the_stress():
    shp = l_foot(t_plate=8.0, t_sole=6.5, fillet=4.0)
    up_z = _worst(part_from_shape("a", shp, up=(0, 0, 1)), toe_load())["section"]
    up_y = _worst(part_from_shape("b", shp, up=(0, 1, 0)), toe_load())["section"]
    assert up_z.info["sigma_mpa"] == pytest.approx(up_y.info["sigma_mpa"], rel=1e-6)
    assert up_y.allowable > 1.2 * up_z.allowable                             # layers run along the bending stress when printed on its side


def test_material_change_to_cf_nylon_raises_the_margin():
    shp = l_foot(t_plate=8.0, t_sole=6.5, fillet=4.0)
    pet = _worst(part_from_shape("p", shp, "petg", up=(0, 1, 0)), toe_load(), cls="walk")
    cfn = _worst(part_from_shape("c", shp, "cf-nylon", up=(0, 1, 0)), toe_load(), cls="walk")
    assert cfn["fatigue"].margin > 2.0 * pet["fatigue"].margin               # endurance 0.17 vs 0.10 and XY 71.6 vs 37.9


def test_fatigue_check_exists_only_for_cyclic_classes():
    p = part_from_shape("f", l_foot(t_plate=8.0, t_sole=6.5, fillet=4.0), up=(0, 1, 0))
    assert "fatigue" in _worst(p, toe_load(30.0), cls="walk")
    assert "fatigue" not in _worst(p, toe_load(30.0), cls="fall")
    rows = PartAnalyzer(p).evaluate(toe_load(30.0), "x", "fall_rigid")
    assert rows and all(not r.gate for r in rows)                            # the unprotected bound is reported, never gated


# ------------------------------------------------------------------------------------------------------------------ load chain
def test_chain_wrench_of_a_two_link_leg_is_statically_exact():
    from openhumanoid.cad.strength.chain import Contact, Scenario, joint_wrenches
    from openhumanoid.cad.strength.model import JointRec, LinkRec, Model

    links = {"base": LinkRec("base", None, np.zeros(3), (0, 0, 0), []),
             "arm": LinkRec("arm", "base", np.zeros(3), (0, 0, 0), [{"name": "j1", "axis": "y", "range": [-90, 90]}]),
             "tip": LinkRec("tip", "arm", np.array([0.0, 0.0, -100.0]), (0, 0, 0), [{"name": "j2", "axis": "y", "range": [-90, 90]}])}
    jr = lambda n, c: JointRec(n, c, "base", "base", np.array([0, 1.0, 0]), np.zeros(3), "x", np.zeros(3), np.array([0, 1.0, 0]), np.array([1.0, 0, 0]), np.zeros(3),
                               14.0, 4, "M2", "M3", None, None)
    m = Model("t", links, {}, {"j1": jr("j1", "arm"), "j2": jr("j2", "tip")})
    # 10 N pushing +z at a point 100 mm in front of j2 and 100 mm below it: torque about y at j2 = r x F
    sc = Scenario("t", "walk", "", {}, g_eff=np.zeros(3), contacts=[Contact("tip", np.array([100.0, 0.0, -200.0]), np.array([0, 0, 10.0]))])
    w = joint_wrenches(m, sc)
    assert w["j2"]["F"][2] == pytest.approx(10.0)
    assert w["j2"]["tau"] == pytest.approx(-(100.0 * 10.0), rel=1e-9) or abs(w["j2"]["tau"]) == pytest.approx(1000.0, rel=1e-9)
    assert abs(w["j1"]["tau"]) == pytest.approx(abs(1000.0 + 0.0 * 1.0), rel=1e-9)       # the force line is x = 100 from both axes


def test_fall_energy_numbers_are_derived_from_the_robot_mass():
    f = pol.policy()["fall"]
    # E = m g dh: for 5.11 kg, CoM 0.33 m (0.55 x 0.60), lying 0.06 m
    E = 5.11 * 9.80665 * (0.55 * 0.60 - float(pol.pv(f, "lying_com_height_m")))
    Fp = float(pol.pv(f, "energy_fraction_leg_contact")) * E / (float(pol.pv(f, "stop_distance_protected_mm")) * 1e-3) * float(pol.pv(f, "peak_over_average"))
    assert 450 < Fp < 560                                                    # ~507 N: the protected contact force the report quotes


# ------------------------------------------------------------------------------------------------------------------ variant config
def test_variant_strength_config_is_complete():
    from pathlib import Path

    import yaml

    from openhumanoid.paths import repo_root

    p = Path(repo_root()) / "variants" / "adam" / "cad" / "strength.yaml"
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert cfg["robot"]["mass_kg"] > 3 and cfg["leg"]["foot"]["part"] and cfg["concept"]["report"]
    assert (Path(repo_root()) / cfg["concept"]["report"]).exists()
    assert set(cfg["actuators"]) == {"hip_roll", "knee"}                       # R1 Path 1: STS3250 at hip roll and knees


@pytest.mark.slow
def test_leg_v2_foot_fails_and_leg_v3_foot_passes():
    """Full run on the CAD-foundation leg (about 5 minutes: two CAD builds)."""
    from openhumanoid.cad.strength import loadcases, runner
    from openhumanoid.cad.strength.cli import build_model

    cfg = loadcases.load_config("variants/adam/strength_cfg_placeholder") if False else None
    from openhumanoid.paths import repo_root

    root = repo_root()
    cfg = loadcases.load_config(root / "variants" / "adam" / "cad" / "strength.yaml")
    r2 = runner.run(build_model(str(root / "variants/adam/cad/leg_v2.py"), "adam", None), cfg, only_parts=["foot_l"])
    r3 = runner.run(build_model(str(root / "variants/adam/cad/leg_v3.py"), "adam", None), cfg, only_parts=["foot_l"])
    assert not r2["parts"]["foot_l"]["ok"] and r2["parts"]["foot_l"]["worst"]["margin"] < 0.1
    assert r3["parts"]["foot_l"]["ok"]
