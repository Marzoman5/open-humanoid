"""CAD framework tests (build123d). Variant-agnostic checks plus one end-to-end export of Adam."""
import copy

import pytest

bd = pytest.importorskip("build123d")

from openhumanoid import catalog  # noqa: E402
from openhumanoid.cad import biped, export, geom  # noqa: E402
from openhumanoid.simgen import load_sizing  # noqa: E402
from openhumanoid.spec import expand_joints, load_spec  # noqa: E402


@pytest.fixture(scope="module")
def adam():
    return load_spec("adam")


@pytest.fixture(scope="module")
def adam_links(adam):
    links, notes = biped.build(adam, load_sizing(adam))
    return links, notes


def test_servo_envelope_from_catalog():
    s = geom.ServoDims.from_catalog(catalog.get("sts3215-12v"))
    assert (round(s.L, 1), round(s.W, 1), round(s.H, 1)) == (45.2, 24.7, 35.0)
    body, horn = geom.servo_shapes(s, (0, 0, 0), (0, 1, 0), (0, 0, -1))
    (x0, x1), (y0, y1), (z0, z1) = geom.bbox_of(body)
    assert y1 == pytest.approx(0, abs=1e-6) and y0 == pytest.approx(-s.H, abs=1e-6)   # body behind the horn face
    assert z1 == pytest.approx(s.shaft_offset, abs=1e-6) and z0 == pytest.approx(s.shaft_offset - s.L, abs=1e-6)
    assert geom.bbox_of(horn)[1][0] == pytest.approx(0, abs=1e-6)


def test_mass_properties_cube():
    mp = geom.mass_properties(bd.Box(10, 10, 10), 1000.0)   # 1 cm³ of water
    assert mp["mass"] == pytest.approx(1e-3, rel=1e-6)
    assert mp["inertia"][0][0] == pytest.approx(1e-3 * (0.01**2 + 0.01**2) / 12, rel=1e-4)
    combo = geom.combine_mass([mp, {**mp, "com": [0.1, 0, 0]}])
    assert combo["com"][0] == pytest.approx(0.05)


def test_shell_clears_what_it_wraps():
    part = geom.box((-12, 12), (-20, 20), (-80, 0))
    st = geom.fit_stations([part], -5, -75, [(0, 1.0), (1, 0.8)], margin=3.0, n=3.0)
    shell = geom.hollow_loft(st, 1.6, 3.0)
    assert shell.is_valid
    assert geom.interference(shell, part) < 1.0


def test_links_match_spec_joints(adam, adam_links):
    links, _ = adam_links
    names = {j["name"] for L in links.values() for j in L.joints}
    expected = {j["name"] for j in expand_joints(adam, load_sizing(adam)["joints_base"])}
    assert names == expected
    seen = set()
    for n, L in links.items():          # parents first
        assert L.parent is None or L.parent in seen
        seen.add(n)


def test_template_scales_with_height(adam):
    """Same servos, taller robot: still builds, segments get longer, nothing hard-coded to 0.5 m."""
    sz = copy.deepcopy(load_sizing(adam))
    k = 0.62 / sz["height_m"]
    sz["height_m"] = 0.62
    sz["geometry_m"] = {key: v * k for key, v in sz["geometry_m"].items()}
    links, _ = biped.build(adam, sz)
    assert links["shank_l"].pos_mm[2] == pytest.approx(-sz["geometry_m"]["thigh"] * 1000)


def test_rejects_non_box_actuators(adam):
    sz = copy.deepcopy(load_sizing(adam))
    bldc = next(p["id"] for p in catalog.actuators() if p["actuator"]["type"] != "serial_bus_servo")
    sz["actuators"] = {k: bldc for k in sz["actuators"]}
    with pytest.raises(ValueError, match="box servos"):
        biped.build(adam, sz)


def test_export_contract_and_sim(adam, adam_links, tmp_path):
    mujoco = pytest.importorskip("mujoco")
    links, notes = adam_links
    sz = load_sizing(adam)
    r = export.export(adam, sz, links, biped.load_style(adam), tmp_path / "export", notes)
    out = tmp_path / "export"
    for f in ("manifest.yaml", "mass_properties.yaml", "robot.xml"):
        assert (out / f).exists()
    assert any((out / "parts").glob("*.step")) and any((out / "meshes").glob("*.stl"))
    m = mujoco.MjModel.from_xml_path(str(out / "robot.xml"))
    assert m.nu == len(sz["actuators"])
    assert abs(r["totals"]["total_kg"] - float(sum(m.body_mass))) < 0.01
