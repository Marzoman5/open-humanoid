"""One leg frame (hip-yaw bracket to foot) of the representative 22-DOF layout, built ONLY from the CAD foundation:
the component library, the helper primitives (servo_housing / servo_pocket / horn_mount / idler_seat / insert_boss / screw_clearance /
cable slots) and the frames in variants/adam/generated/interfaces.yaml. No raw servo dimensions appear here.

This is a validation of the tooling (T-20261019-2426), NOT Adam's final leg. Design freeze happens after the concept and silhouette
reviews. Left leg only (the right leg is its mirror image: shapes mirrored in y, same joint names with `_r`).

Run:  python -m openhumanoid.cad check variants/adam/cad/leg_v2.py --out variants/adam/cad/validation
"""
from __future__ import annotations

import build123d as bd

from openhumanoid.cad import dfm
from openhumanoid.cad.assembly import Assembly
from openhumanoid.cad.components import get as get_component
from openhumanoid.cad.core import FeatureResult, Site, apply, box_at, loc_from, safe_union, union_all
from openhumanoid.cad.features import horn_mount, idler_frame, idler_seat
from openhumanoid.cad.geom import Link, Part
from openhumanoid.cad.housing import servo_housing

# ---- design parameters of this leg (everything dimensional that is not a catalog/DFM/interface number)
P = {
    "plate_t": 3.2,            # horn plate (screws are low-head counterbored: min 3.1 mm)
    "idler_plate_t": 5.0,      # bearing seat 4 mm + 1 mm shoulder
    "cover_t": 4.4,            # 2.6 mm low-head counterbore + 1.8 mm floor (the gate found 3.2 leaves 0.6 mm under the head)
    "cover_t_idler": 5.6,      # blind relief for the servo's back stub (3.4) + the printed idler pin + >= 1.6 mm behind them, 3.0 under the screws
    "web_radius": 24.0,        # fork web distance from the pitch axis: clears the housing near-end corner (20.8) by >= 3 mm
    "web_t": 3.2,
    "fork_w": 28.0,            # plate width (fore-aft)
    "sole_t": 3.2,
    "bearing": "MR105ZZ",
    "idler_gap": 1.5,
}
def wp(loc: bd.Location, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> bd.Vector:
    """World position of the point (x, y, z) given in the frame `loc`."""
    return (loc * bd.Location((x, y, z))).position


LEG = ["hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch", "ankle_roll"]


def build(ctx) -> Assembly:
    ifs = ctx.interfaces
    if ifs is None:
        raise RuntimeError("generate interfaces first: python -m openhumanoid.cad interfaces adam")
    side = "l"
    J = {n: f"{n}_{side}" for n in LEG}
    link_of = {n: f"{n}_{side}_link" for n in LEG}
    links: dict[str, Link] = {}
    root = Link("pelvis", None, (0.0, 0.0, 0.0))
    links["pelvis"] = root
    prev = "pelvis"
    for n in LEG:
        j = ifs.joint(J[n])
        o = ifs.link_origin(link_of[n])
        po = ifs.link_origin(prev)
        axis = j["axis"]["name"]
        lo, hi = j["rom_deg"]
        links[link_of[n]] = Link(link_of[n], prev, tuple(round(o[i] - po[i], 4) for i in range(3)),
                                 joints=[{"name": J[n], "axis": axis, "range": [lo, hi]}])
        prev = link_of[n]
    lo_of = {name: ifs.link_origin(name) for name in links}

    def to_link(shape: bd.Shape, link: str) -> bd.Shape:
        o = lo_of[link]
        return bd.Pos(-o[0], -o[1], -o[2]) * shape

    def site_to_link(s: Site, link: str, part: str, rename: dict | None = None) -> Site:
        o = lo_of[link]
        mates = (rename or {}).get(s.mates, s.mates)
        return Site(**{**s.__dict__, "frame": bd.Pos(-o[0], -o[1], -o[2]) * s.frame, "part": part, "mates": mates})

    asm = Assembly("adam_leg_v2_l", links, interfaces=ifs.d, bed_mm=tuple(ifs.d["bed_mm"]))
    S = {n: ifs.servo_loc(J[n]) for n in LEG}                   # servo frames, world
    A = {n: ifs.joint(J[n])["actuator"]["id"] for n in LEG}
    idl = {n: ifs.joint(J[n])["idler"] for n in LEG}
    host_link = {n: ifs.joint(J[n])["actuator"]["host_link"] for n in LEG}
    child_link = {n: ifs.joint(J[n])["child_link"] for n in LEG}
    HORN_T = get_component("horn-25t").params["thickness"]
    zp0 = {n: get_component(A[n]).frames["horn_seat"].position.Z + HORN_T for n in LEG}   # servo-frame z of the plate underside on the horn

    def add_part(link, part):
        links[link].parts.append(part)

    def printed(pid, shape_w, link, sites_w, rename=None, wall_class="structural", up=(0, 0, 1), meta=None):
        sites = [site_to_link(s, link, pid, rename) for s in sites_w]
        pt = Part(pid, to_link(shape_w, link), "frame", "petg", color="frame", sites=sites, print_up=up,
                  meta={"wall_class": wall_class, **(meta or {})})
        add_part(link, pt)
        return pt

    # ------------------------------------------------------------------ housings (one per servo), all from the helper
    H = {}
    for n in LEG:
        has_idler = idl[n] is not None
        H[n] = servo_housing(A[n], part=f"housing_{J[n]}", cover_part=f"cover_{J[n]}",
                             cover_t=P["cover_t_idler"] if has_idler else P["cover_t"],
                             idler={"bearing": idl[n]["bearing"], "gap_mm": idl[n]["gap_mm"]} if has_idler else None)

    def idler_zin(n):    # servo-frame z of the idler plate inner face
        return H[n].params["cover_back_z"] - idl[n]["gap_mm"]

    def box_s(n, x0, x1, y0, y1, z0, z1):
        """Box given in servo-frame coordinates of joint n, returned in world coordinates."""
        return S[n] * box_at(bd.Location(), (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))

    # ------------------------------------------------------------------ purchased parts: servos, horns, bearings
    for n in LEG:
        sv = get_component(A[n])
        add_part(host_link[n], Part(f"servo_{J[n]}", to_link(S[n] * sv.params["case_shape"], host_link[n]), "servo", "purchased", color="servo",
                                    mass_kg=sv.mass_kg, catalog=A[n], process="purchased"))
        for tag, shp_ in zip(("", "b"), sv.params["shaft_shapes"]):      # front spline and back stub: two solids, both turn with the output
            add_part(child_link[n], Part(f"shaft{tag}_{J[n]}", to_link(S[n] * shp_, child_link[n]), "shaft", "purchased", color="horn",
                                         mass_kg=0.0, process="purchased"))
        hz = get_component("horn-25t")
        add_part(child_link[n], Part(f"horn_{J[n]}", to_link(S[n] * sv.frames["horn_seat"] * hz.shape, child_link[n]), "horn", "purchased",
                                     color="horn", mass_kg=hz.mass_kg, catalog="horn-25t", process="purchased"))
        if idl[n]:
            b = get_component(f"bearing:{idl[n]['bearing']}")
            gap = -idler_zin(n) - sv.params["H"]
            add_part(child_link[n], Part(f"bearing_{J[n]}", to_link(idler_frame(A[n], gap, S[n]) * b.shape, child_link[n]), "purchased",
                                         "purchased", color="horn", mass_kg=b.mass_kg, catalog=f"bearing:{idl[n]['bearing']}", process="purchased"))

    # ------------------------------------------------------------------ covers (fixed with the servo's host)
    for n in LEG:
        c_shape, c_sites = H[n].placed_cover(S[n])
        cid = f"cover_{J[n]}"
        printed(cid, c_shape, host_link[n], c_sites, rename={"housing": f"housing_{J[n]}"}, up=(0, 0, 1))
    # ------------------------------------------------------------------ plates on horns
    def horn_plate_feat(n, plate_t=None, mate=None):
        return horn_mount(A[n], plate_t=plate_t or P["plate_t"], mode="flat", part="", mates=mate).placed(S[n] * get_component(A[n]).frames["horn_seat"])

    # ---- pelvis mount: the yaw servo's housing alone (pelvis design is out of scope)
    pid = f"housing_{J['hip_yaw']}"
    shp, st = H["hip_yaw"].build(S["hip_yaw"], name=pid)
    printed(pid, shp, "pelvis", st, rename={"cover": f"cover_{J['hip_yaw']}"}, meta={"role": "pelvis mount stand-in"})

    # ---- 1. yaw bracket: horn plate under S1 + column down to the roll servo's housing S2
    y1 = H["hip_roll"]
    hp = P["plate_t"]
    yaw_plate = box_s("hip_yaw", -14, 14, -14, 62.35 + 4, zp0["hip_yaw"], zp0["hip_yaw"] + hp)       # servo frame y' = -world x: positive y' reaches back (-x)
    pp = H["hip_roll"].params
    # column from the roll housing's top (its far end, world z) up to the plate underside; spans the housing footprint
    ob = S["hip_roll"]
    top_pt = wp(ob, pp["outer_x"][1], 0, 0)      # servo-frame far end point -> world
    plate_bot_z = (wp(S["hip_yaw"], 0, 0, zp0["hip_yaw"] + hp)).Z
    col_x = (wp(ob, 0, 0, pp["z_bot"])).X, (wp(ob, 0, 0, pp["z_top"] + pp["lip_t"])).X
    hw2 = pp["outer_y"][1]
    S2c = ifs.axis_origin(J["hip_roll"])
    col = box_at(bd.Location(), (abs(col_x[1] - col_x[0]), 2 * hw2, abs(plate_bot_z - top_pt.Z) + 2.0),
                 ((col_x[0] + col_x[1]) / 2, S2c[1], (plate_bot_z + top_pt.Z) / 2))
    hm1 = horn_plate_feat("hip_yaw", mate=f"servo_{J['hip_yaw']}")
    shp, st = H["hip_roll"].build(S["hip_roll"], adds=[yaw_plate, col], extra=[hm1], name="yaw_bracket")
    printed(f"yaw_bracket_{side}", shp, child_link["hip_yaw"], st, rename={"housing": f"yaw_bracket_{side}", "cover": f"cover_{J['hip_roll']}"})

    # ---- 2. roll bracket: plate on S2's horn merged into S3's housing back wall
    p3 = H["hip_pitch"].params
    # footprint of the S3 housing back wall in world (y, z); S3 frame: z' = +y, x' = +z, y' = +x
    s3 = S["hip_pitch"]
    wall_x = (wp(s3, 0, p3["outer_y"][0], 0)).X          # back wall (world x) of S3's housing
    y_lo = (wp(s3, 0, 0, p3["z_bot"])).Y
    y_hi = (wp(s3, 0, 0, p3["z_top"] + p3["lip_t"])).Y
    z_lo = (wp(s3, p3["outer_x"][0], 0, 0)).Z
    z_hi = (wp(s3, p3["outer_x"][1], 0, 0)).Z
    x_plate0 = (wp(S["hip_roll"], 0, 0, zp0["hip_roll"])).X
    plate2 = box_at(bd.Location(), (wall_x + 1.0 - x_plate0, y_hi - y_lo, z_hi - z_lo), ((x_plate0 + wall_x + 1.0) / 2, (y_lo + y_hi) / 2, (z_lo + z_hi) / 2))
    hm2 = horn_plate_feat("hip_roll", mate=f"servo_{J['hip_roll']}")
    shp, st = H["hip_pitch"].build(S["hip_pitch"], adds=[plate2], extra=[hm2], name="roll_bracket")
    printed(f"roll_bracket_{side}", shp, child_link["hip_roll"], st, rename={"housing": f"roll_bracket_{side}", "cover": f"cover_{J['hip_pitch']}"})

    # ---- pitch forks: thigh (S3 fork + S4 housing), shank (S4 fork + S5 housing)
    def fork(n, nxt, pid):
        """Fork around joint n's housing (plates on the horn side and the idler side + web) carrying joint nxt's housing at its end."""
        rho, tw, fw = P["web_radius"], P["web_t"], P["fork_w"]
        z_in = idler_zin(n)
        x_far = rho + tw
        horn_plate = box_s(n, -x_far, 14, -fw / 2, fw / 2, zp0[n], zp0[n] + hp)
        idler_plate = box_s(n, -x_far, 14, -fw / 2, fw / 2, z_in - P["idler_plate_t"], z_in)
        web = box_s(n, -x_far, -rho, -fw / 2, fw / 2, z_in - P["idler_plate_t"], zp0[n] + hp)
        # beam down to the next housing's top: spans its block footprint
        hn = H[nxt].params
        ref = S[nxt]
        bx = [wp(ref, 0, hn["outer_y"][0], 0).X, wp(ref, 0, hn["outer_y"][1], 0).X]
        by = [(wp(ref, 0, 0, hn["z_bot"])).Y, (wp(ref, 0, 0, hn["z_top"])).Y]
        z_top_beam = (wp(S[n], -rho, 0, 0)).Z + 1.0
        z_bot_beam = (wp(ref, hn["outer_x"][1] - 1.0, 0, 0)).Z
        beam = box_at(bd.Location(), (max(bx) - min(bx), max(by) - min(by), z_top_beam - z_bot_beam),
                      ((min(bx) + max(bx)) / 2, (min(by) + max(by)) / 2, (z_top_beam + z_bot_beam) / 2))
        hm = horn_plate_feat(n, mate=f"servo_{J[n]}")
        seat = idler_seat(idl[n]["bearing"], plate_t=P["idler_plate_t"], part=pid, boss=False,
                          at=S[n] * loc_from((0, 0, z_in), (0, 0, 1), (1, 0, 0)))
        return H[nxt].build(S[nxt], adds=[horn_plate, idler_plate, web, beam], extra=[hm, seat], name=pid)

    shp, st = fork("hip_pitch", "knee", f"thigh_{side}")
    printed(f"thigh_{side}", shp, child_link["hip_pitch"], st, rename={"housing": f"thigh_{side}", "cover": f"cover_{J['knee']}"})
    shp, st = fork("knee", "ankle_pitch", f"shank_{side}")
    printed(f"shank_{side}", shp, child_link["knee"], st, rename={"housing": f"shank_{side}", "cover": f"cover_{J['ankle_pitch']}"})

    # ---- 5. ankle bracket: fork around S5 (plates only) cross-linked by S6's widened housing, which sits behind the ankle
    n = "ankle_pitch"
    z_in = idler_zin(n)
    rho_back = 14.0
    h6 = H["ankle_roll"].params
    s6 = S["ankle_roll"]
    x_back = (wp(s6, 0, 0, h6["cover_back_z"])).X - 1.0           # rearmost point of S6's cover, world x
    z_ax = ifs.axis_origin(J[n])[2]
    fw = P["fork_w"]
    zlo, zhi = z_ax - 14.0, z_ax + 14.0
    # extend the plates backwards (world -x) to the S6 housing: servo-frame y' = world +x, so the back direction is -y'
    horn_plate = box_s(n, -14, 14, x_back - ifs.axis_origin(J[n])[0] - 0.0, fw / 2, zp0[n], zp0[n] + hp)
    idler_plate = box_s(n, -14, 14, x_back - ifs.axis_origin(J[n])[0] - 0.0, fw / 2, z_in - P["idler_plate_t"], z_in)
    # S6 housing widened so its sides meet the two plates
    inner_horn = (wp(S[n], 0, 0, zp0[n])).Y
    inner_idl = (wp(S[n], 0, 0, z_in)).Y
    cy = ifs.axis_origin(J["ankle_roll"])[1]
    wid = (max(inner_horn, inner_idl) - cy, cy - min(inner_horn, inner_idl))
    h6w = servo_housing(A["ankle_roll"], part=f"housing_{J['ankle_roll']}", cover_part=f"cover_{J['ankle_roll']}",
                        side_extra=(wid[0] - h6["outer_y"][1] + 0.5, wid[1] - h6["outer_y"][1] + 0.5))   # S6 y' = -world y
    hm = horn_plate_feat(n, mate=f"servo_{J[n]}")
    seat = idler_seat(idl[n]["bearing"], plate_t=P["idler_plate_t"], part=f"ankle_bracket_{side}", boss=False,
                      at=S[n] * loc_from((0, 0, z_in), (0, 0, 1), (1, 0, 0)))
    shp, st = h6w.build(S["ankle_roll"], adds=[horn_plate, idler_plate], extra=[hm, seat], name=f"ankle_bracket_{side}")
    printed(f"ankle_bracket_{side}", shp, child_link[n], st, rename={"housing": f"ankle_bracket_{side}", "cover": f"cover_{J['ankle_roll']}"})

    # ---- 6. foot: plate on S6's horn + sole
    n = "ankle_roll"
    fl = ifs.d["proportions_mm"]["foot_length"]
    fwid = ifs.d["proportions_mm"]["foot_width"]
    ax = ifs.axis_origin(J[n])
    x_plate0 = (wp(S[n], 0, 0, zp0[n])).X
    plate = box_at(bd.Location(), (hp + 1.0, 28.0, ax[2] + 14.0), (x_plate0 + hp / 2 + 0.5, ax[1], (ax[2] + 14.0) / 2))
    sole = box_at(bd.Location(), (fl, fwid, P["sole_t"]), (ax[0] - 0.33 * fl + fl / 2 - 0.0, ax[1], P["sole_t"] / 2))
    hmf = horn_plate_feat(n, mate=f"servo_{J[n]}")
    base = safe_union(plate, sole, "foot")
    shp, st = apply(base, hmf, name="foot")
    printed(f"foot_{side}", shp, child_link[n], st)

    # ---- designed contacts and fits (everything else must stay clear by the generic moving/static gap)
    brackets = {"hip_yaw": f"yaw_bracket_{side}", "hip_roll": f"roll_bracket_{side}", "hip_pitch": f"thigh_{side}", "knee": f"shank_{side}",
                "ankle_pitch": f"ankle_bracket_{side}", "ankle_roll": f"foot_{side}"}
    host_part = {"hip_yaw": f"housing_{J['hip_yaw']}", "hip_roll": f"yaw_bracket_{side}", "hip_pitch": f"roll_bracket_{side}",
                 "knee": f"thigh_{side}", "ankle_pitch": f"shank_{side}", "ankle_roll": f"ankle_bracket_{side}"}
    slip = dfm.clearance("slip") - 0.05
    for n in LEG:
        sv, hn_, sh, cv = f"servo_{J[n]}", f"horn_{J[n]}", f"shaft_{J[n]}", f"cover_{J[n]}"
        sb = f"shaftb_{J[n]}"
        asm.allow(sv, sh)                      # the shaft grows out of the case
        asm.allow(sv, sb)
        asm.allow(sv, hn_)                     # horn floats 0.3 mm above the boss: touching in the model, free in reality
        asm.allow(sh, hn_)                     # horn on the spline
        asm.allow(hn_, brackets[n])            # plate screwed onto the horn
        asm.fit(sv, host_part[n], slip)        # servo in its pocket (slip fit 0.15/side)
        asm.fit(sv, cv, slip)
        asm.fit(cv, host_part[n], 0.0)         # cover seated on the housing
        asm.fit(sh, brackets[n], 0.3)
        asm.fit(sh, host_part[n], 0.3)
        asm.fit(sh, cv, 0.3)
        asm.fit(sb, cv, 0.3)
        asm.fit(sb, host_part[n], 0.3)
        asm.fit(sb, brackets[n], 0.3)
        asm.fit(sv, brackets[n], 0.3)
        if idl[n]:
            bg = f"bearing_{J[n]}"
            asm.allow(bg, brackets[n])         # pressed into the idler plate
            asm.fit(bg, cv, 0.04)              # inner race on the printed pin (press fit 0.05/side)
            asm.fit(bg, host_part[n], 0.3)
            asm.fit(cv, brackets[n], dfm.clearance("rotating") - 0.05)    # pin through the plate's relief hole
            asm.fit(sb, bg, 0.3)
            asm.fit(sh, bg, 0.3)
    asm.notes.append("left leg only; right leg = mirror in y")
    return asm
