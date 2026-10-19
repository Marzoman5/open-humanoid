"""CAD foundation tests (T-20261019-2426): component library, DFM rules, guarded booleans, feature helpers, interfaces generator,
geometry gate, ROM sweep, assembly access, fit gauge, and the one-leg validation of the whole chain."""
import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

bd = pytest.importorskip("build123d")

from openhumanoid import catalog  # noqa: E402
from openhumanoid.cad import access, dfm, features as F, gauge, geometry_gate as gg, interfaces, rom  # noqa: E402
from openhumanoid.cad.assembly import Assembly  # noqa: E402
from openhumanoid.cad.components import get, list_components  # noqa: E402
from openhumanoid.cad.core import (CadOpError, apply, box_at, loc_from, min_distance, overlap_volume, safe_cut,  # noqa: E402
                                   safe_union)
from openhumanoid.cad.geom import Link, Part  # noqa: E402
from openhumanoid.cad.housing import servo_housing  # noqa: E402
from openhumanoid.paths import repo_root  # noqa: E402
from openhumanoid.spec import load_spec  # noqa: E402

ROOT = repo_root()


# --------------------------------------------------------------------------- component library


def test_every_component_builds_valid_with_provenance():
    for cid in list_components():
        c = get(cid.replace("x<len>", "x8"))
        assert c.shape.is_valid and c.shape.volume > 0, cid
        for k, v in c.provenance.items():
            assert v["conf"] in {"standard", "datasheet", "vendor", "derived", "estimate"}, (cid, k)
            assert v["src"], (cid, k)


def test_servo_dimensions_and_features():
    s = get("sts3215")
    P = s.params
    assert (P["L"], P["W"], P["H"]) == (45.2, 24.7, 35.0)
    assert P["spline_od"] == 5.9                      # vendor: 25T, OD 5.9 mm
    assert {"axis", "horn_seat", "back_axis", "cable_exit"} <= set(s.frames)
    assert len(s.holes) == 8 and s.keepout.volume > s.shape.volume
    # the back axis points away from the case, the horn seat sits above the boss plus the horn float
    assert s.frames["back_axis"].position.Z == pytest.approx(-P["H"])
    assert s.frames["horn_seat"].position.Z == pytest.approx(P["boss_h"] + P["horn_float"])
    assert s.estimates(), "unverified servo features must be flagged for the gauge"
    # the case/shaft split used by the ROM check keeps the shaft out of the static body
    case, (front, back) = P["case_shape"], P["shaft_shapes"]
    assert overlap_volume(case, front) < 1e-6 and overlap_volume(case, back) < 1e-6


def test_catalog_mechanical_blocks_consistent():
    a, b = catalog.get("sts3215-12v")["mechanical"], catalog.get("sts3215-7v4")["mechanical"]
    assert a == b                                      # same case, same data
    c = catalog.get("sts3250-12v")
    assert c["dimensions_mm"] == [45.22, 24.72, 35]
    assert catalog.validate_catalog() == []
    assert get("sts3250").params["L"] == pytest.approx(45.2)


def test_hardware_standards():
    m3 = get("screw:M3x8").params
    assert (m3["head_d"], m3["head_k"], m3["hex_key"]) == (5.5, 3.0, 2.5)
    assert get("screw:M3x8L").params["head_k"] == 2.0 and get("screw:M3x8L").params["low_head"]
    assert get("insert:M3").params["hole_d"] < get("insert:M3").params["od"]
    assert get("bearing:MR105ZZ").params["od"] == 10 and get("bearing:F688ZZ").params["flange_d"] == 18
    assert get("magnet:6x3").params["d"] == 6
    pi = get("rpi-zero-2w")
    assert pi.bbox_mm() == (65.0, 30.0, 5.0) and len(pi.holes) == 4
    xs = sorted({round(h.frame.position.X, 1) for h in pi.holes})
    assert xs == [3.5, 61.5]                           # Raspberry Pi mechanical drawing: 58 mm hole spacing
    assert len(get("rpi-5-4gb").holes) == 4 and get("lipo-3s-2200").shape.volume > 80000


# --------------------------------------------------------------------------- DFM


def test_dfm_rules():
    assert dfm.clearance("press") < dfm.clearance("slip") < dfm.clearance("sliding") < dfm.clearance("rotating") < dfm.clearance("loose")
    assert dfm.hole_d(3.0) > 3.0 and dfm.hole_d(3.0, "slip") == pytest.approx(3.0 + dfm.hole_comp(3.0) + 2 * dfm.clearance("slip"))
    assert dfm.bed_usable([220, 220, 250]) == (210.0, 210.0, 245.0)
    assert dfm.min_wall("load_path") > dfm.min_wall("structural") > dfm.min_wall("cosmetic")
    assert "clearance.slip" in dfm.tuned_rules()
    assert dfm.snap_strain(1.0, 1.2, 10.0) == pytest.approx(0.018)


def test_dfm_z_knockdown_matches_research_materials():
    mats = yaml.safe_load((ROOT / "research/methods/print_materials.yaml").read_text(encoding="utf-8"))["materials"]
    table = dfm.load_dfm()["orientation"]["z_over_xy_strength"]
    assert table["PLA"] == mats["PLA"]["z_over_xy_strength"]
    assert table["PLA_plus"] == mats["PLA_plus"]["z_over_xy_strength"]
    assert table["PETG"] == mats["PETG"]["z_over_xy_strength"]
    assert table["ASA"] == mats["ABS_ASA"]["ASA"]["z_over_xy_strength"]
    assert 0.5 < table["CF_nylon"] < 0.7


def test_thin_wall_detector():
    thin = bd.Box(40, 30, 1.0)
    ok = bd.Box(40, 30, 2.4)
    assert not dfm.thin_wall_report(thin, 1.6)["ok"]
    assert dfm.thin_wall_report(ok, 1.6)["ok"]
    hollow = bd.Box(40, 30, 20) - bd.Box(38.0, 28.0, 18.0)          # 1.0 mm walls
    assert dfm.thin_wall_report(bd.Box(40, 30, 20) - bd.Box(36.8, 26.8, 16.8), 1.6)["ok"]      # 1.6 mm walls pass
    assert not dfm.thin_wall_report(hollow, 1.6)["ok"]


# --------------------------------------------------------------------------- guarded booleans (research 01: silent failures)


def test_guarded_booleans_raise():
    base = bd.Box(20, 20, 20)
    with pytest.raises(CadOpError, match="one solid"):
        safe_union(base, bd.Pos(50, 0, 0) * bd.Box(5, 5, 5), "float")           # a feature that does not touch the part
    ok = safe_union(base, bd.Pos(10, 0, 0) * bd.Box(10, 5, 5), "touching")
    assert ok.volume > base.volume
    with pytest.raises(CadOpError, match="one solid"):
        safe_cut(base, bd.Box(30, 30, 2), "slice in two")                         # cuts the part in two
    out = safe_cut(base, bd.Pos(10, 0, 0) * bd.Cylinder(2, 10), "hole")
    assert out.volume < base.volume


# --------------------------------------------------------------------------- feature helpers


def test_insert_boss_and_floor_rule():
    ins = get("insert:M3").params
    plate = bd.Pos(0, 0, -6) * bd.Box(30, 30, 12)
    shape, sites = apply(plate, F.insert_boss("M3", at=loc_from((0, 0, 0), (0, 0, 1))), name="p")
    probe = lambda d: loc_from((0, 0, 0), (0, 0, -1)) * (bd.Pos(0, 0, ins["hole_depth"] / 2) * bd.Cylinder(d / 2, ins["hole_depth"]))   # noqa: E731
    assert overlap_volume(shape, probe(ins["hole_d"] - 0.1)) < 0.5
    assert overlap_volume(shape, probe(ins["hole_d"] + 0.6)) > 0.5
    assert sites[0].kind == "insert" and sites[0].thread == "M3"
    with pytest.raises(CadOpError, match="floor"):
        F.insert_boss("M3", boss_h=ins["hole_depth"] + 0.5)                     # leaves 0.5 mm under the pocket
    boss = F.insert_boss("M3", boss_h=9.0)
    assert boss.add and abs(boss.add[0].bounding_box().size.X - (ins["hole_d"] + 2 * dfm.load_dfm()["insert_boss"]["wall_mm"]["v"])) < 1e-6


def test_screw_clearance_counterbore_and_length_helper():
    plate = bd.Pos(0, 0, -5) * bd.Box(30, 30, 10)
    f = F.counterbore("M3", through=10, head="low", length=8, at=loc_from((0, 0, 0), (0, 0, 1)))
    shape, sites = apply(plate, f, name="cb")
    s = get("screw:M3x8L").params
    assert shape.volume < plate.volume - 3.14 * (1.5**2) * 10
    assert sites[0].kind == "screw" and sites[0].tool_len == dfm.load_dfm()["access"]["tool_len_mm"]["M3"]
    assert F.screw_length_for(6.0) == 12 and F.screw_length_for(2.0) == 8
    assert len(F.bolt_circle(4, 32)) == 4 and F.bolt_circle(4, 32)[0] == (16.0, 0.0)
    assert s["counterbore_depth"] < get("screw:M3x8").params["counterbore_depth"]


def test_magnet_idler_cable_keepout():
    blk = bd.Pos(0, 0, -6) * bd.Box(30, 30, 12)
    s1, _ = apply(blk, F.magnet_boss("6x3", at=loc_from((0, 0, 0), (0, 0, 1))), name="m")
    assert len(s1.solids()) == 1 and s1.volume < blk.volume - 80          # a closed void for the pause-print magnet
    plate = bd.Pos(0, 0, -2.8) * bd.Box(30, 30, 5.6)
    s2, _ = apply(plate, F.idler_seat("MR105ZZ", plate_t=5.6, boss=False, at=loc_from((0, 0, 0), (0, 0, 1))), name="idler")
    assert s2.volume < plate.volume
    with pytest.raises(CadOpError, match="shoulder"):
        F.idler_seat("MR105ZZ", plate_t=4.5)                                   # 4 mm seat + 1.6 mm shoulder needs 5.6
    cc = F.cable_channel([(0, 0, 0), (20, 0, 0), (20, 20, 10)], 3.0)
    s3, _ = apply(bd.Pos(10, 10, 0) * bd.Box(40, 40, 20), cc, name="cable")
    assert s3.is_valid and cc.keepouts
    ko = F.keepout(get("sts3215"), margin=1.0)
    assert ko.volume > get("sts3215").shape.volume
    with pytest.raises(CadOpError):
        F.cable_channel([(0, 0, 0)], 3.0)


def test_split_for_bed_pieces_fit_with_dowels():
    long = bd.Box(450, 60, 30)
    parts = F.split_for_bed(long, [220, 220, 250], part="beam")
    assert len(parts) == 3 and [i for i, _ in parts] == ["beam_a", "beam_b_a", "beam_b_b"]
    usable = dfm.bed_usable([220, 220, 250])
    for _, s in parts:
        ok, ext = gg.fits_bed(s, usable)
        assert ok, ext
    total = sum(s.volume for _, s in parts)
    assert total < long.volume and total > long.volume - 8 * 3.14 * 3.6**2 * 16      # only the dowel pockets are missing
    with pytest.raises(CadOpError):
        F.split_for_bed(bd.Box(450, 12, 6), [220, 220, 250])                     # nowhere to put the dowels


def test_loft_shell_checked():
    sh = F.loft_shell([{"z": 0, "a": 25, "b": 20}, {"z": 60, "a": 28, "b": 24}, {"z": 120, "a": 20, "b": 16}], 1.6)
    assert sh.is_valid and len(sh.solids()) == 1
    with pytest.raises(CadOpError):
        F.loft_shell([{"z": 0, "a": 2, "b": 2}, {"z": 10, "a": 2, "b": 2}], 1.6)


def test_servo_housing_fit_and_sites():
    h = servo_housing("sts3215-12v")
    servo = get("sts3215")
    assert overlap_volume(h.shape, servo.shape) < 0.5
    assert min_distance(h.shape, servo.params["case_shape"]) == pytest.approx(dfm.clearance("slip"), abs=0.02)
    assert min_distance(h.cover, servo.params["case_shape"]) >= dfm.clearance("slip") - 0.02
    kinds = [s.kind for s in h.sites + h.cover_sites]
    assert kinds.count("insert") == 2 and kinds.count("screw") == 2
    # the cover screws' counterbore keeps the structural wall to the cover's edge
    assert h.params["end_w"] >= 2 * (3.25 + dfm.min_wall("structural")) - 1e-6
    hi = servo_housing("sts3215-12v", cover_t=5.6, idler={"bearing": "MR105ZZ", "gap_mm": 1.5})
    assert hi.params["pin"]["d"] == pytest.approx(4.9)
    with pytest.raises(CadOpError, match="thicker cover"):
        servo_housing("sts3215-12v", cover_t=3.2, idler={"bearing": "MR105ZZ"})


def test_horn_mount_rules():
    f = F.horn_mount("sts3215-12v", mode="flat")
    ids = [s.id for s in f.sites]
    assert ids[0] == "horn_center" and len(ids) == 5
    with pytest.raises(CadOpError, match="plate_t"):
        F.horn_mount("sts3215-12v", plate_t=3.2)


# --------------------------------------------------------------------------- interfaces generator


@pytest.fixture(scope="module")
def adam():
    return load_spec("adam")


@pytest.fixture(scope="module")
def adam_ifs(adam):
    lay = interfaces.load_layout(adam)
    return interfaces.generate(adam, lay)


def test_interfaces_generated_and_consistent(adam, adam_ifs):
    d = adam_ifs
    assert len(d["joints"]) == 22 and not d["problems"]
    assert {j["limb"] for j in d["joints"].values()} == {"leg", "arm", "head"}
    kn = d["joints"]["knee_l"]
    assert kn["axis"]["direction"] == [0, 1, 0] and kn["actuator"]["id"] == "sts3215-12v"
    # horn seat recorded in interfaces.yaml = the component's frame (boss + horn float), not a stale number
    s = get("sts3215")
    z = kn["actuator"]["frame"]["z_dir"]
    o = kn["actuator"]["frame"]["origin_mm"]
    expect = [o[i] + z[i] * s.frames["horn_seat"].position.Z for i in range(3)]
    assert kn["horn"]["seat_origin_mm"] == pytest.approx(expect, abs=1e-3)
    # right side: geometry mirrored in y, roll ranges mirrored, pitch ranges identical
    r = d["joints"]["hip_roll_r"]
    l = d["joints"]["hip_roll_l"]
    assert r["rom_deg"] == [-l["rom_deg"][1], -l["rom_deg"][0]]
    assert d["joints"]["knee_r"]["rom_deg"] == kn["rom_deg"]
    assert r["axis"]["origin_mm"][1] == -l["axis"]["origin_mm"][1]
    # CAD-limited ranges are recorded next to the spec range
    assert kn["rom_spec_deg"] == [0, 130] and kn["rom_deg"][1] < 130 and kn["rom_note"]
    assert d["height_mm"] == 600.0 and d["bed_mm"] == [220, 220, 250]


def test_committed_interfaces_are_current(adam, adam_ifs):
    on_disk = yaml.safe_load((Path(adam["_dir"]) / "generated" / "interfaces.yaml").read_text(encoding="utf-8"))
    assert on_disk["layout_sha"] == adam_ifs["layout_sha"]
    assert on_disk["joints"]["knee_l"]["horn"] == adam_ifs["joints"]["knee_l"]["horn"]
    assert interfaces.load(adam).d["height_mm"] == 600.0


def test_interfaces_knee_override_and_precheck(adam):
    lay = interfaces.load_layout(adam)
    lay["actuators"] = {"default": "sts3215-12v", "overrides": {"knee": "sts3250-12v"}}
    d = interfaces.generate(adam, lay)
    assert d["joints"]["knee_l"]["actuator"]["id"] == "sts3250-12v" and d["joints"]["ankle_pitch_l"]["actuator"]["id"] == "sts3215-12v"
    # two servos at the same place must be reported before any geometry exists
    lay2 = interfaces.load_layout(adam)
    for j in lay2["limbs"]["leg"]["joints"]:
        if j["name"] == "hip_roll":
            j["servo"]["horn_at"] = 66
            j["servo"]["horn"] = [0, 0, -1]
            j["servo"]["long"] = [0, -1, 0]
            j["axis"] = "z"
    assert interfaces.generate(adam, lay2)["problems"]
    lay3 = interfaces.load_layout(adam)
    lay3["limbs"]["leg"]["joints"][0]["servo"]["horn"] = [1, 0, 0]
    with pytest.raises(ValueError, match="along the joint axis"):
        interfaces.generate(adam, lay3)


# --------------------------------------------------------------------------- geometry gate


def test_gate_part_checks_and_expectations():
    shape = bd.Box(40, 30, 6) - bd.Pos(10, 0, 0) * bd.Cylinder(1.7, 10)
    p = Part("plate", shape, "frame", "petg", meta={"wall_class": "structural", "expect": [
        {"kind": "size", "axis": "x", "value": 40, "tol": 0.1},
        {"kind": "void_cylinder", "origin": [10, 0, -3], "dir": [0, 0, 1], "d": 3.4, "length": 6, "tol": 0.1},
        {"kind": "solid_point", "point": [-10, 0, 0]},
        {"kind": "contains_bbox", "min": [-19, -14, -2], "max": [19, 14, 2]},
    ]})
    r = gg.check_part(p, bed_mm=[220, 220, 250])
    assert r["ok"], [c for c in r["checks"] if not c["ok"]]
    names = {c["check"] for c in r["checks"]}
    assert {"solid", "step_roundtrip", "stl", "bed", "min_wall"} <= names
    bad = Part("bad", shape, "frame", "petg", meta={"expect": [{"kind": "void_cylinder", "origin": [-10, 0, -3], "dir": [0, 0, 1], "d": 3.4, "length": 6}]})
    assert not gg.check_part(bad, bed_mm=[220, 220, 250], fast=True)["ok"]
    two = Part("two", bd.Compound(children=[bd.Box(5, 5, 5), bd.Pos(20, 0, 0) * bd.Box(5, 5, 5)]), "frame", "petg")
    assert not gg.check_part(two)["ok"]                                          # two solids
    big = Part("big", bd.Box(300, 20, 20), "frame", "petg")
    assert not gg.check_part(big, bed_mm=[220, 220, 250], fast=True)["ok"]
    thin = Part("thin", bd.Box(40, 30, 1.0), "frame", "petg")
    assert any(c["check"] == "min_wall" and not c["ok"] for c in gg.check_part(thin, bed_mm=[220, 220, 250])["checks"])


def _toy_arm(wall_x=(15, 40), wall_y=(10, 20), arm_len=40.0):
    base = Link("base", None, (0, 0, 0))
    arm = Link("arm", "base", (0, 0, 0), joints=[{"name": "j", "axis": "z", "range": [-90, 90]}])
    base.parts.append(Part("wall", box_at(bd.Location(), (wall_x[1] - wall_x[0], wall_y[1] - wall_y[0], 10),
                                          ((wall_x[0] + wall_x[1]) / 2, (wall_y[0] + wall_y[1]) / 2, 0)), "frame", "petg"))
    arm.parts.append(Part("bar", bd.Pos(arm_len / 2, 0, 0) * bd.Box(arm_len, 4, 6), "frame", "petg"))
    return Assembly("toy", {"base": base, "arm": arm})


def test_assembly_clash_and_clearance_check():
    asm = _toy_arm()
    r = gg.check_assembly(asm)
    assert r["ok"] and not r["clashes"]
    asm.stand_pose = {"j": math.radians(30)}                                      # the bar runs through the wall
    r = gg.check_assembly(asm)
    assert r["clashes"] and r["clashes"][0]["a"] in ("wall", "bar")
    asm.stand_pose = {"j": math.radians(10.3)}                                    # bar corner ~0.9 mm from the wall face: too close for parts that move
    t = gg.check_assembly(asm)
    assert t["ok"] and t["tight"] and t["tight"][0]["dist_mm"] < 1.0
    asm.fit("wall", "bar", 0.5)                                                   # a designed 0.5 mm clearance is accepted
    assert not gg.check_assembly(asm)["tight"]
    asm.stand_pose = {"j": math.radians(30)}
    asm.allow("wall", "bar")
    assert gg.check_assembly(asm)["ok"]                                           # designed contact is not a clash


def test_rom_sweep_finds_the_contact_angle():
    asm = _toy_arm()
    res = rom.sweep_joint(asm, "j", step_deg=10, refine_deg=0.25)
    # brute-force scan at 0.2 deg with the same overlap test
    first = None
    for i in range(0, 900):
        a = i * 0.1
        pl = {p.part.id: p for p in asm.placed({"j": math.radians(a)})}
        if overlap_volume(pl["wall"].shape, pl["bar"].shape) > 2.0:
            first = a
            break
    assert first is not None and res["limit_pos"] is not None
    assert abs(res["limit_pos"] - first) < 0.6
    assert res["limit_neg"] is None and res["within_spec"] is False
    assert res["collisions"][0]["pairs"][0]["a"] in ("wall", "bar")
    # the same sweep with the wall moved away is free over the whole range
    free = rom.sweep_joint(_toy_arm(wall_x=(60, 80)), "j", step_deg=15)
    assert free["within_spec"] and free["limit_pos"] is None
    q = rom.pose_angles(_leg_stub(), "squat", "l")
    assert q["knee_l"] > 0 and q["hip_pitch_l"] < 0 and q["ankle_pitch_l"] == pytest.approx(-(q["hip_pitch_l"] + q["knee_l"]))


def _leg_stub():
    links = {"pelvis": Link("pelvis", None, (0, 0, 0))}
    prev = "pelvis"
    for n, ax, rng in (("hip_pitch_l", "y", [-110, 60]), ("knee_l", "y", [0, 130]), ("ankle_pitch_l", "y", [-60, 60])):
        links[n + "_link"] = Link(n + "_link", prev, (0, 0, -100), joints=[{"name": n, "axis": ax, "range": rng}])
        prev = n + "_link"
    return Assembly("stub", links)


# --------------------------------------------------------------------------- assembly access


def _box_with_lid(lid_blocked=False):
    base = Link("base", None, (0, 0, 0))
    shell = bd.Pos(0, 0, 10) * bd.Box(40, 40, 20) - bd.Pos(0, 0, 12) * bd.Box(30, 30, 20)
    base.parts.append(Part("body", shell, "frame", "petg"))
    base.parts.append(Part("insidepart", bd.Pos(0, 0, 8) * bd.Box(10, 10, 6), "servo", "purchased", process="purchased"))
    lid = bd.Pos(0, 0, 21.5) * bd.Box(40, 40, 3)
    sites = [__import__("openhumanoid.cad.core", fromlist=["Site"]).Site("lid_screw", "screw", "lid", loc_from((15, 15, 23), (0, 0, 1)),
                                                                        thread="M3", mates="body", tool_d=8.0, tool_len=30.0)]
    base.parts.append(Part("lid", lid, "frame", "petg", sites=sites))
    if lid_blocked:
        base.parts.append(Part("hood", bd.Pos(15, 15, 40) * bd.Box(20, 20, 4) + bd.Pos(15, 15, 34) * bd.Box(2, 2, 10), "frame", "petg"))
    return Assembly("lidbox", {"base": base})


def test_access_order_and_screw_corridor():
    asm = _box_with_lid()
    plan = access.analyse(asm)
    names = [s["part"] for s in plan["order"]]
    assert plan["ok"], access.summarize(plan)
    assert names.index("body") < names.index("lid") and names.index("insidepart") < names.index("lid")   # part goes in before the lid
    lid = next(s for s in plan["order"] if s["part"] == "lid")
    assert "lid_screw" in lid["screws"] and not lid["blocked_screws"]
    plan2 = access.analyse(_box_with_lid(lid_blocked=True))
    order2 = [s["part"] for s in plan2["order"]]
    blocked = [s for s in plan2["order"] if s["blocked_screws"]]
    assert order2.index("lid") < order2.index("hood") or blocked        # the hood must come after the screw or the screw is flagged


def test_access_flags_part_trapped_in_closed_shell():
    base = Link("base", None, (0, 0, 0))
    shell = bd.Box(40, 40, 40) - bd.Box(30, 30, 30)                       # a sealed hollow cube
    base.parts.append(Part("shell", shell, "frame", "petg"))
    base.parts.append(Part("core", bd.Box(10, 10, 10), "frame", "petg"))
    plan = access.analyse(Assembly("sealed", {"base": base}))
    assert not plan["ok"] and (plan["cyclic_parts"] or plan["stuck_parts"])
    assert "NO VALID ORDER" in access.summarize(plan) or "STUCK" in access.summarize(plan)


def test_access_flags_screw_covered_by_its_own_part():
    base = Link("base", None, (0, 0, 0))
    from openhumanoid.cad.core import Site

    p = bd.Box(30, 30, 6) + bd.Pos(0, 0, 10) * bd.Box(30, 30, 4) + bd.Pos(0, 12, 6) * bd.Box(30, 4, 6)   # an overhang above the head
    site = Site("s", "screw", "bracket", loc_from((0, 0, 3), (0, 0, 1)), thread="M3", tool_d=8, tool_len=30)
    base.parts.append(Part("bracket", p, "frame", "petg", sites=[site]))
    plan = access.analyse(Assembly("own", {"base": base}))
    assert plan["unreachable_screws"] and plan["unreachable_screws"][0]["blocked_by"] == "bracket"


# --------------------------------------------------------------------------- fit gauge


def test_fit_gauge_builds_and_reads_results(tmp_path):
    shape, keys = gauge.build()
    assert [k["id"] for k in keys] == [f"G{i}" for i in range(1, 9)]
    assert all(s.is_valid for s in shape.solids())
    vol = gauge.volume_mm3(shape) / 1000
    assert 10 < vol < 40 and gauge.estimate_minutes(shape) < 40
    info = gauge.write(tmp_path / "g", "sts3215-12v", "MR105ZZ")
    for f in ("gauge.step", "gauge.stl", "gauge.json", "gauge_key.md"):
        assert (tmp_path / "g" / f).exists()
    # servo slice: its pocket outline is the real housing pocket
    g1 = next(k for k in info["tiles"] if k["id"] == "G1")
    assert g1["expect_mm"]["pocket_L"] == pytest.approx(45.2 + 2 * dfm.clearance("slip"))
    prop = gauge.read_results({"clearance_slip_index": 3, "insert_m3_hole_index": 4, "bearing_seat_index": 2, "horn_hole_radius_mm": 7.5})
    assert prop["clearance.slip.per_side_mm"] == gauge.LADDER_CLEAR[2]
    assert prop["components/data/hardware.yaml horns.round_25t.bolt_circle_d"] == 15.0
    # the clearance ladder holes are generated with the same recipe as the real parts
    assert gauge.LADDER_CLEAR[0] <= dfm.clearance("slip") <= gauge.LADDER_CLEAR[-1]


# --------------------------------------------------------------------------- the validation leg (everything together)


@pytest.fixture(scope="module")
def leg(adam):
    p = ROOT / "variants/adam/cad/leg_v2.py"
    sp = importlib.util.spec_from_file_location("leg_v2_test", p)
    m = importlib.util.module_from_spec(sp)
    sys.modules["leg_v2_test"] = m
    sp.loader.exec_module(m)
    ctx = SimpleNamespace(spec=adam, interfaces=interfaces.load(adam), variant_dir=Path(adam["_dir"]))
    return m.build(ctx)


def test_leg_parts_pass_geometry_gate(leg):
    rep = gg.run_gate(leg, fast=True)
    assert rep["ok"], gg.summarize(rep)
    printed = [p.id for _, p in leg.printed()]
    assert len(printed) == 17 and "thigh_idler_l" in printed and "roll_cradle_l" in printed
    # every part is checked against interfaces.yaml: horn holes on the axis, bearing seats, servo envelopes
    n_expect = sum(len(p.meta.get("expect", [])) for _, p in leg.parts())
    assert n_expect >= 20
    bom = leg.bom()
    assert bom["components"]["sts3215-12v"] == 6 and bom["fasteners"]["insert M3"] >= 12
    # no printed part exceeds the 220x220x250 bed
    for _, p in leg.printed():
        assert gg.check_bed(p.shape, leg.bed_mm)["ok"], p.id


def test_leg_rom_sweep_and_poses(leg):
    res = rom.sweep_all(leg, step_deg=15, gap_check=True)
    assert res["ok"], rom.summarize(res)
    for pose in ("squat", "step_forward", "split_stance"):
        assert rom.check_pose(leg, pose, "l")["ok"], pose
    # the sweep must really detect a collision: widen the knee ROM beyond the CAD limit
    leg.links["knee_l_link"].joints[0]["range"] = [0, 130]
    wide = rom.sweep_joint(leg, "knee_l", step_deg=10)
    leg.links["knee_l_link"].joints[0]["range"] = [0, 115]
    assert not wide["within_spec"] and 115 < wide["limit_pos"] < 125
    assert {wide["collisions"][0]["pairs"][0]["a"], wide["collisions"][0]["pairs"][0]["b"]} == {"cover_hip_roll_l", "cover_ankle_roll_l"}


def test_leg_access_order_and_subassemblies(leg):
    plan = access.analyse(leg)
    assert plan["ok"], access.summarize(plan)
    names = [s["part"] for s in plan["order"]]
    assert names.index("thigh_l") < names.index("thigh_idler_l")          # the idler plate goes on last
    assert names.index("roll_plate_l") < names.index("roll_cradle_l")      # horn screws before the cradle
    assert all(v.get("bench_assemblable") for v in plan["subassemblies"].values())
    assert sum(len(s["screws"]) for s in plan["order"]) >= 40
    # inserts are prep, not corridor-checked
    assert any(p["kind"] == "insert" for p in plan["prep"])


def test_split_for_bed_avoids_features():
    beam = bd.Box(450, 40, 30)
    beam, _ = apply(beam, F.insert_boss("M3", at=loc_from((0, 0, 15), (0, 0, 1))), name="beam")       # a hole right where a mid cut would go
    parts = F.split_for_bed(beam, [220, 220, 250], part="b")
    cuts = sorted(s.bounding_box().max.X for _, s in parts)[:-1]
    assert all(abs(c) > 3.0 for c in cuts)


def test_cheatsheet_golden_examples_run():
    """Every golden-example block in docs/cad-cheatsheet.md must run (research C5: examples that rot are worse than none)."""
    import re

    text = (ROOT / "docs" / "cad-cheatsheet.md").read_text(encoding="utf-8")
    fence = "`" * 3
    blocks = re.findall(fence + r"python golden\n(.*?)" + fence, text, flags=re.S)
    assert len(blocks) == 3
    for b in blocks:
        exec(compile(b, "<golden>", "exec"), {})
