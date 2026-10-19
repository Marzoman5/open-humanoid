"""STRENGTH REDESIGN (T-20261019-a026) of leg_v2.py: thicker plates and webs, internal fillets by default (fillets.fillet_internal through
Housing.build), a ribbed foot printed on its side, CF-nylon structure. The geometry gate, ROM sweep and access check must still pass; the strength
check (python -m openhumanoid.cad strength variants/adam/cad/leg_v3.py) shows the margins. leg_v2.py stays as the "before".

One leg frame (hip-yaw bracket to foot) of the representative 22-DOF layout, built ONLY from the CAD foundation:
the component library, the helper primitives (servo_housing / servo_pocket / horn_mount / idler_seat / insert_boss / screw_clearance /
cable slot) and the frames in variants/adam/generated/interfaces.yaml. No raw servo dimensions appear here.

This is a validation of the tooling (T-20261019-2426), NOT Adam's final leg. Design freeze happens after the concept and silhouette
reviews. Left leg only (the right leg is its mirror image: shapes mirrored in y, same joint names with `_r`).

Run:  python -m openhumanoid.cad interfaces adam
      python -m openhumanoid.cad check variants/adam/cad/leg_v2.py --out variants/adam/cad/validation

Topology (and why; every item below was forced by a check, see docs/cad-foundation.md section "Validation leg"):
* pitch joints (hip pitch, knee, ankle pitch) are FORKS: horn plate on one side of the servo housing, an idler plate with a bearing on
  the other, a web joining them below the housing. The idler plate is a SEPARATE part bolted on last: with a printed pin on the cover and a
  closed bearing seat a one-piece fork cannot be assembled (access check: precedence cycle).
* roll joints (hip roll, ankle roll) are single-sided plates on the horn. At the hip the plate and the pitch servo's cradle are two parts:
  the horn screws face the cradle, so the plate goes on the horn first and the cradle is bolted on afterwards (access check).
"""
from __future__ import annotations

import build123d as bd

from openhumanoid.cad import dfm
from openhumanoid.cad.assembly import Assembly
from openhumanoid.cad.components import get as get_component
from openhumanoid.cad.core import FeatureResult, Site, apply, box_at, loc_from, safe_union
from openhumanoid.cad.features import horn_mount, idler_frame, idler_seat, insert_boss, screw_clearance
from openhumanoid.cad.geom import Link, Part
from openhumanoid.cad.housing import servo_housing

# ---- design parameters of this leg (everything dimensional that is not a catalog/DFM/interface number)
P = {
    "plate_t": 8.0,            # horn plate: low-head counterbore 1.8-2.3 + floor; was 4.3 (thin plates were the first strength failures)
    "idler_plate_t": 7.5,      # bearing seat 4 mm + shoulder; was 5.6
    "cover_t": 6.5,            # was 4.4: the rear covers are the first thing a backward fall touches (floor 4.2 mm under the low-head counterbore)
    "cover_t_idler": 6.5,      # blind relief for the servo's back stub (3.4) + the printed idler pin + >= 1.6 mm behind them; was 5.6
    "housing_wall": 3.2,       # servo pocket walls, was 2.4 (load-path minimum): the yaw column and housings carry torque as thin-walled sections
    "web_radius": {"hip_pitch": 24.0, "knee": 30.0},   # fork web distance from the pitch axis: knee needs >= 30 for 115+ deg of flexion
    "web_t": 10.0,             # was 3.2 (torsion of the web carries the pitch torque from the horn plate to the beam): the web carries the whole leg load from the beam to the plates (bending of a 3.2 mm web failed first)
    "fork_w": 36.0,            # plate width (fore-aft); was 28
    "idler_w": 36.0,           # idler plate/tongue width: screws at +-10 need 3.25 (counterbore) + 1.6 (wall) to the edge
    "corner_r": 9.0,           # rounded plate corners shrink the swept radius
    "corner_r_tongue": 3.0,    # idler tongue corners: small, the counterbores sit close to them
    "bridge_above_axis": 24.0, # roll bracket bridge starts this far above the hip axis (outside the fork sweep)
    "sole_t": 6.5,             # was 3.2 (the heel and sole behind the plate are the next weakest section)
    "foot_plate_t": 8.0,       # horn plate of the foot; was 4.3 (the thin 90 deg cantilever)
    "foot_plate_w": 44.0,      # was 28
    "foot_rib_t": 4.0,         # three ribs along the sole from the plate to the toe
    "foot_rib_h": 22.0,        # rib height at the plate (above the sole top), tapering to rib_h_end at the tip
    "foot_rib_h_end": 8.0,
    "foot_rib_len": 62.0,
    "foot_fillet": 4.0,        # cantilever root radius (dfm fillet.cantilever_root_mm)
    "horn_washer_od": 5.0,     # ISO 7089 M2 washers under the horn screw heads (bearing area under a low-head M2 is only 6.8 mm2)
    "join_washer_od": 7.0,     # ISO 7089 M3 washers under the roll-cradle screws (the low head alone bears on 14.7 mm2)
    "join_screw": "M3x35L",    # roll cradle to roll plate (through the 29.8 mm cradle into inserts in the bridge)
    "bearing": "MR105ZZ",
    "idler_gap": 1.5,
    "structure_material": "cf-nylon",    # PA12-CF10: brackets, plates, idler plates, foot; covers stay PETG
}
LEG = ["hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch", "ankle_roll"]


def wp(loc: bd.Location, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> bd.Vector:
    """World position of the point (x, y, z) given in the frame `loc`."""
    return (loc * bd.Location((x, y, z))).position


def tup(v) -> tuple[float, float, float]:
    return (v.X, v.Y, v.Z)


def build(ctx) -> Assembly:
    ifs = ctx.interfaces
    if ifs is None:
        raise RuntimeError("generate interfaces first: python -m openhumanoid.cad interfaces adam")
    side = "l"
    J = {n: f"{n}_{side}" for n in LEG}
    link_of = {n: f"{n}_{side}_link" for n in LEG}
    links: dict[str, Link] = {"pelvis": Link("pelvis", None, (0.0, 0.0, 0.0))}
    prev = "pelvis"
    for n in LEG:
        j = ifs.joint(J[n])
        o, po = ifs.link_origin(link_of[n]), ifs.link_origin(prev)
        lo, hi = j["rom_deg"]
        links[link_of[n]] = Link(link_of[n], prev, tuple(round(o[i] - po[i], 4) for i in range(3)),
                                 joints=[{"name": J[n], "axis": j["axis"]["name"], "range": [lo, hi]}])
        prev = link_of[n]
    lo_of = {name: ifs.link_origin(name) for name in links}

    def to_link(shape: bd.Shape, link: str) -> bd.Shape:
        o = lo_of[link]
        return bd.Pos(-o[0], -o[1], -o[2]) * shape

    def pt_link(p, link):
        o = lo_of[link]
        return [round(p[0] - o[0], 4), round(p[1] - o[1], 4), round(p[2] - o[2], 4)]

    def site_to_link(s: Site, link: str, part: str, rename: dict | None = None) -> Site:
        o = lo_of[link]
        mates = (rename or {}).get(s.mates, s.mates)
        own = part if s.part in ("", "housing", "cover") or s.part is None else s.part
        return Site(**{**s.__dict__, "frame": bd.Pos(-o[0], -o[1], -o[2]) * s.frame, "part": own, "mates": mates})

    asm = Assembly("adam_leg_v2_l", links, interfaces=ifs.d, bed_mm=tuple(ifs.d["bed_mm"]))
    S = {n: ifs.servo_loc(J[n]) for n in LEG}                   # servo frames, world
    A = {n: ifs.joint(J[n])["actuator"]["id"] for n in LEG}
    idl = {n: ifs.joint(J[n])["idler"] for n in LEG}
    host_link = {n: ifs.joint(J[n])["actuator"]["host_link"] for n in LEG}
    child_link = {n: ifs.joint(J[n])["child_link"] for n in LEG}
    HORN = get_component("horn-25t")
    zp0 = {n: get_component(A[n]).frames["horn_seat"].position.Z + HORN.params["thickness"] for n in LEG}   # servo-frame z of the plate underside
    hp = P["plate_t"]

    def add_part(link, part):
        links[link].parts.append(part)

    def printed(pid, shape_w, link, sites_w, rename=None, wall_class="structural", up=(0, 1, 0), expect=None, meta=None, material=None):
        sites = [site_to_link(s, link, pid, rename) for s in sites_w]
        pt = Part(pid, to_link(shape_w, link), "frame", material or P["structure_material"], color="frame", sites=sites, print_up=up,
                  meta={"wall_class": wall_class, "expect": expect or [], "horn_washer_od_mm": P["horn_washer_od"], "screw_washer_od_mm": {"M3": P["join_washer_od"]}, **(meta or {})})
        add_part(link, pt)
        return pt

    # ------------------------------------------------------------------ housings (one per servo), all from the helper
    H = {}
    for n in LEG:
        has_idler = idl[n] is not None
        H[n] = servo_housing(A[n], part=f"housing_{J[n]}", cover_part=f"cover_{J[n]}", wall=P["housing_wall"],
                             cover_t=P["cover_t_idler"] if has_idler else P["cover_t"],
                             idler={"bearing": idl[n]["bearing"], "gap_mm": idl[n]["gap_mm"]} if has_idler else None)

    def idler_zin(n):    # servo-frame z of the idler plate inner face
        return H[n].params["cover_back_z"] - idl[n]["gap_mm"]

    def box_s(n, x0, x1, y0, y1, z0, z1, r=0.0):
        """Box given in servo-frame coordinates of joint n (corners rounded by r around the servo z axis), in world coordinates."""
        b = box_at(bd.Location(), (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
        if r > 0:
            b = bd.fillet(b.edges().filter_by(bd.Axis.Z), min(r, 0.45 * min(x1 - x0, y1 - y0)))
        return S[n] * b

    # ------------------------------------------------------------------ purchased parts: servos, shafts, horns, bearings
    for n in LEG:
        sv = get_component(A[n])
        add_part(host_link[n], Part(f"servo_{J[n]}", to_link(S[n] * sv.params["case_shape"], host_link[n]), "servo", "purchased", color="servo",
                                    mass_kg=sv.mass_kg, catalog=A[n], process="purchased"))
        for tag, shp_ in zip(("", "b"), sv.params["shaft_shapes"]):      # front spline and back stub: two solids, both turn with the output
            add_part(child_link[n], Part(f"shaft{tag}_{J[n]}", to_link(S[n] * shp_, child_link[n]), "shaft", "purchased", color="horn",
                                         mass_kg=0.0, process="purchased"))
        add_part(child_link[n], Part(f"horn_{J[n]}", to_link(S[n] * sv.frames["horn_seat"] * HORN.shape, child_link[n]), "horn", "purchased",
                                     color="horn", mass_kg=HORN.mass_kg, catalog="horn-25t", process="purchased"))
        if idl[n]:
            b = get_component(f"bearing:{idl[n]['bearing']}")
            gap = -idler_zin(n) - sv.params["H"]
            add_part(child_link[n], Part(f"bearing_{J[n]}", to_link(idler_frame(A[n], gap, S[n]) * b.shape, child_link[n]), "purchased",
                                         "purchased", color="horn", mass_kg=b.mass_kg, catalog=f"bearing:{idl[n]['bearing']}", process="purchased"))

    # ------------------------------------------------------------------ expectations checked numerically against interfaces.yaml
    def horn_expect(n, link):
        """Centre screw hole on the interface axis; the horn seat recorded by the part equals interfaces.yaml."""
        sv = get_component(A[n])
        z0 = zp0[n]
        o = wp(S[n], 0, 0, z0)
        zd = wp(S[n], 0, 0, z0 + 1) - o
        cs = get_component("screw:" + HORN.params["center_screw"] + "x6L").params
        d = cs["clearance_medium"] + dfm.hole_comp(cs["clearance_medium"])
        seat = wp(S[n], *(sv.frames["horn_seat"].position.X, sv.frames["horn_seat"].position.Y, sv.frames["horn_seat"].position.Z))
        return [{"kind": "void_cylinder", "origin": pt_link((o.X, o.Y, o.Z), link), "dir": [zd.X, zd.Y, zd.Z], "d": round(d, 3), "length": hp,
                 "tol": 0.1, "label": f"{J[n]}: centre screw hole on the output axis"},
                {"kind": "interface", "joint": J[n], "key": "horn.seat_origin_mm", "value": [seat.X, seat.Y, seat.Z], "tol": 0.05,
                 "label": f"{J[n]}: horn seat equals interfaces.yaml"}]

    def pocket_expect(n, link):
        """The part's bounding box must enclose the servo case envelope (x' long, y' width, z' height) of its joint."""
        sv = get_component(A[n])
        Pm = sv.params
        c = [tup(wp(S[n], x, y, z)) for x in (-Pm["axis_x"], Pm["far_end_x"]) for y in (-Pm["W"] / 2, Pm["W"] / 2) for z in (-Pm["H"], 0.0)]
        lo = [min(p[i] for p in c) for i in range(3)]
        hi = [max(p[i] for p in c) for i in range(3)]
        return [{"kind": "contains_bbox", "min": pt_link(lo, link), "max": pt_link(hi, link), "tol": 0.3, "label": f"{J[n]}: encloses the servo envelope"}]

    def seat_expect(n, link):
        b = get_component(f"bearing:{idl[n]['bearing']}")
        zin = idler_zin(n)
        o = wp(S[n], 0, 0, zin)
        zd = wp(S[n], 0, 0, zin - 1) - o                   # into the plate = away from the servo
        seat = b.params["od"] + dfm.load_dfm()["bearing_seat"]["seat_d_over_od_mm"]["v"]
        return [{"kind": "void_cylinder", "origin": pt_link((o.X, o.Y, o.Z), link), "dir": [zd.X, zd.Y, zd.Z], "d": round(seat, 3),
                 "length": b.params["w"], "tol": 0.1, "label": f"{J[n]}: bearing seat on the back axis"}]

    # ------------------------------------------------------------------ covers (fixed with the servo's host)
    for n in LEG:
        c_shape, c_sites = H[n].placed_cover(S[n])
        printed(f"cover_{J[n]}", c_shape, host_link[n], c_sites, rename={"housing": f"housing_{J[n]}"}, up=(0, 0, 1), material="petg")

    def horn_plate_feat(n, mate):
        return horn_mount(A[n], plate_t=hp, mode="flat", part="", mates=mate, washer_od=P["horn_washer_od"]).placed(S[n] * get_component(A[n]).frames["horn_seat"])

    # ---- pelvis mount: the yaw servo's housing alone (pelvis design is out of scope)
    pid = f"housing_{J['hip_yaw']}"
    shp, st = H["hip_yaw"].build(S["hip_yaw"], name=pid)
    printed(pid, shp, "pelvis", st, rename={"cover": f"cover_{J['hip_yaw']}"}, expect=pocket_expect("hip_yaw", "pelvis"),
            meta={"role": "pelvis mount stand-in"})

    # ---- 1. yaw bracket: horn plate under S1 + column down to the roll servo's housing S2
    yaw_plate = box_s("hip_yaw", -14, 14, -14, 62.35 + 4, zp0["hip_yaw"], zp0["hip_yaw"] + hp)       # servo frame y' = -world x: positive y' reaches back
    pp = H["hip_roll"].params
    ob = S["hip_roll"]
    top_z = wp(ob, pp["outer_x"][1], 0, 0).Z
    plate_bot_z = wp(S["hip_yaw"], 0, 0, zp0["hip_yaw"] + hp).Z
    col_x = (wp(ob, 0, 0, pp["z_bot"]).X, wp(ob, 0, 0, pp["z_top"] + pp["lip_t"]).X)
    S2c = ifs.axis_origin(J["hip_roll"])
    col = box_at(bd.Location(), (abs(col_x[1] - col_x[0]), 2 * pp["outer_y"][1], abs(plate_bot_z - top_z) + 2.0),
                 ((col_x[0] + col_x[1]) / 2, S2c[1], (plate_bot_z + top_z) / 2))
    hm1 = horn_plate_feat("hip_yaw", mate=f"servo_{J['hip_yaw']}")
    shp, st = H["hip_roll"].build(S["hip_roll"], adds=[yaw_plate, col], extra=[hm1], name="yaw_bracket")
    printed(f"yaw_bracket_{side}", shp, child_link["hip_yaw"], st, rename={"housing": f"yaw_bracket_{side}", "cover": f"cover_{J['hip_roll']}"},
            expect=horn_expect("hip_yaw", child_link["hip_yaw"]) + pocket_expect("hip_roll", child_link["hip_yaw"]))

    # ---- 2. roll joint: plate on S2's horn (+ bridge, inserts) and, as a SEPARATE part, the cradle for S3 bolted on afterwards
    p3 = H["hip_pitch"].params
    s3 = S["hip_pitch"]
    wall_x = wp(s3, 0, p3["outer_y"][0], 0).X          # back wall (world x) of S3's housing
    y_lo = wp(s3, 0, 0, p3["z_bot"]).Y
    y_hi = wp(s3, 0, 0, p3["z_top"] + p3["lip_t"]).Y
    z_lo = wp(s3, p3["outer_x"][0], 0, 0).Z
    z_hi = wp(s3, p3["outer_x"][1], 0, 0).Z
    x_plate0 = wp(S["hip_roll"], 0, 0, zp0["hip_roll"]).X
    z_ax_hip = ifs.axis_origin(J["hip_pitch"])[2]
    z_bridge0 = z_ax_hip + P["bridge_above_axis"]
    plate2 = box_at(bd.Location(), (hp, y_hi - y_lo, z_hi - (z_ax_hip - 12.0)), (x_plate0 + hp / 2, (y_lo + y_hi) / 2, (z_hi + z_ax_hip - 12.0) / 2))
    bridge = box_at(bd.Location(), (wall_x - x_plate0, y_hi - y_lo, z_hi - z_bridge0), ((x_plate0 + wall_x) / 2, (y_lo + y_hi) / 2, (z_hi + z_bridge0) / 2))
    plate2 = safe_union(plate2, bridge, "roll plate+bridge")
    from openhumanoid.cad.fillets import fillet_internal

    plate2, rep_rp = fillet_internal(plate2, P["foot_fillet"], min_len=6.0, name="roll_plate")     # plate / bridge corner (4 mm: cantilever root)
    asm.notes.append(f"roll plate: {rep_rp['filleted']}/{rep_rp['candidates']} internal edges filleted r={rep_rp['radius_mm']:.1f}")
    # joining screws: along world x from the cradle's front face, through the 29.8 mm cradle, into inserts in the bridge's front face
    yaxis = s3.position.Y
    join_pts = [(z_ax_hip + p3["x_ins"] + 0.0, yaxis + zz) for zz in (-7.0, -17.0, -27.0)]            # (world z, world y)
    join_feats_plate = [insert_boss("M3", part="roll_plate", mates="roll_cradle", tag=f"join_insert_{i}",
                                    at=loc_from((wall_x, y, z), (1, 0, 0), (0, 1, 0))) for i, (z, y) in enumerate(join_pts)]
    hm2 = horn_plate_feat("hip_roll", mate=f"servo_{J['hip_roll']}")
    plate_pid, cradle_pid = f"roll_plate_{side}", f"roll_cradle_{side}"
    plate_shape, plate_sites = apply(plate2, hm2, *join_feats_plate, name=plate_pid)
    printed(plate_pid, plate_shape, child_link["hip_roll"], plate_sites, rename={"roll_cradle": cradle_pid},
            expect=horn_expect("hip_roll", child_link["hip_roll"]))
    front_x = wp(s3, 0, p3["outer_y"][1], 0).X
    cradle_feats = [screw_clearance("M3", through=front_x - wall_x + 0.4, counterbore=True, head="low", part=cradle_pid, mates=plate_pid,
                                    length=35, tag=f"join_screw_{i}", washer_od=P["join_washer_od"], at=loc_from((front_x, y, z), (1, 0, 0), (0, 1, 0)))
                    for i, (z, y) in enumerate(join_pts)]
    shp, st = H["hip_pitch"].build(S["hip_pitch"], extra=cradle_feats, name=cradle_pid)
    printed(cradle_pid, shp, child_link["hip_roll"], st, rename={"housing": cradle_pid, "cover": f"cover_{J['hip_pitch']}"},
            expect=pocket_expect("hip_pitch", child_link["hip_roll"]))

    # ---- pitch forks: thigh (S3 fork + S4 housing), shank (S4 fork + S5 housing). Main part + removable idler plate.
    def fork(n, nxt, pid, idler_pid):
        rho, tw, fw = P["web_radius"][n], P["web_t"], P["fork_w"]
        z_in = idler_zin(n)
        x_far = rho + tw
        tp = P["idler_plate_t"]
        horn_plate = box_s(n, -x_far, 14, -fw / 2, fw / 2, zp0[n], zp0[n] + hp, P["corner_r"])
        web = box_s(n, -x_far, -rho, -fw / 2, fw / 2, z_in, zp0[n] + hp, 0.0)
        hn = H[nxt].params
        ref = S[nxt]
        bx = [wp(ref, 0, hn["outer_y"][0], 0).X, wp(ref, 0, hn["outer_y"][1], 0).X]
        by = [wp(ref, 0, 0, hn["z_bot"]).Y, wp(ref, 0, 0, hn["z_top"]).Y]
        z_top_beam = wp(S[n], -rho, 0, 0).Z + 1.0
        z_bot_beam = wp(ref, hn["outer_x"][1] - 1.0, 0, 0).Z
        beam = box_at(bd.Location(), (max(bx) - min(bx), max(by) - min(by), z_top_beam - z_bot_beam),
                      ((min(bx) + max(bx)) / 2, (min(by) + max(by)) / 2, (z_top_beam + z_bot_beam) / 2))
        zf = hn["z_bot"]                                   # servo-frame z of the beam's idler-side face (both frames share orientation/origin y)
        tongue = [(-(x_far + 8.0), 10.0), (-(x_far + 8.0), -10.0), (-(x_far + 20.0), 10.0), (-(x_far + 20.0), -10.0)]
        ins = [insert_boss("M3", part=pid, mates=idler_pid, tag=f"idler_insert_{i}", at=S[n] * loc_from((r, yy, zf), (0, 0, -1), (1, 0, 0)))
               for i, (r, yy) in enumerate(tongue)]
        hm = horn_plate_feat(n, mate=f"servo_{J[n]}")
        main_shape, main_sites = H[nxt].build(S[nxt], adds=[horn_plate, web, beam], extra=[hm, *ins], name=pid)
        # ---- the removable idler plate: plate + tongue/spacer down to the beam face
        fi = P["idler_w"]            # wider than the horn plate so the counterbores keep the structural wall to the edge
        plate = box_s(n, -(x_far + 28.0), 14, -fi / 2, fi / 2, z_in - tp, z_in, P["corner_r_tongue"])
        spacer = box_s(n, -(x_far + 28.0), -(x_far + 1.0), -fi / 2, fi / 2, z_in - 0.5, zf, P["corner_r_tongue"])
        seat = idler_seat(idl[n]["bearing"], plate_t=tp, part=idler_pid, boss=False, at=S[n] * loc_from((0, 0, z_in), (0, 0, 1), (1, 0, 0)))
        screws = [screw_clearance("M3", through=tp + (zf - z_in) + 0.5, counterbore=True, head="low", part=idler_pid, mates=pid, length=20,
                                  tag=f"idler_screw_{i}", at=S[n] * loc_from((r, yy, z_in - tp), (0, 0, -1), (1, 0, 0)))
                  for i, (r, yy) in enumerate(tongue)]
        idler_shape, idler_sites = apply(safe_union(plate, spacer, idler_pid), seat, *screws, name=idler_pid)
        return main_shape, main_sites, idler_shape, idler_sites

    for n, nxt, nm in (("hip_pitch", "knee", "thigh"), ("knee", "ankle_pitch", "shank")):
        pid, ipid = f"{nm}_{side}", f"{nm}_idler_{side}"
        ms, mst, isn, ist = fork(n, nxt, pid, ipid)
        printed(pid, ms, child_link[n], mst, rename={"housing": pid, "cover": f"cover_{J[nxt]}"},
                expect=horn_expect(n, child_link[n]) + pocket_expect(nxt, child_link[n]), up=(1, 0, 0))     # standing on the front face: the lateral bending stays in-layer
        printed(ipid, isn, child_link[n], ist, expect=seat_expect(n, child_link[n]), wall_class="structural")

    # ---- 5. ankle bracket: horn plate + S6's widened housing (behind the ankle) + removable idler plate
    n = "ankle_pitch"
    z_in = idler_zin(n)
    h6 = H["ankle_roll"].params
    s6 = S["ankle_roll"]
    x_back = wp(s6, 0, 0, h6["cover_back_z"]).X - 1.0
    fw, tp = P["fork_w"], P["idler_plate_t"]
    ax_n = ifs.axis_origin(J[n])
    y0p = x_back - ax_n[0]
    horn_plate = box_s(n, -fw / 2, fw / 2, y0p, fw / 2, zp0[n], zp0[n] + hp, P["corner_r"])       # as wide as the fork: this strip carries the roll servo's torque to the horn
    inner_horn = wp(S[n], 0, 0, zp0[n]).Y
    inner_idl = wp(S[n], 0, 0, z_in).Y
    cy = ifs.axis_origin("ankle_roll_l")[1]
    hw6 = h6["outer_y"][1]
    h6w = servo_housing(A["ankle_roll"], part=f"housing_{J['ankle_roll']}", cover_part=f"cover_{J['ankle_roll']}", cover_t=P["cover_t"], wall=P["housing_wall"],
                        side_extra=(inner_horn - cy - hw6 + 0.5, cy - inner_idl - hw6))      # S6 y' = -world y: [0] -> +y (horn side), [1] -> -y (idler side)
    bpid, ipid = f"ankle_bracket_{side}", f"ankle_idler_{side}"
    pts = [(x, ax_n[2] + dz) for x in (-40.0, -54.0) for dz in (-7.0, 7.0)]          # (world x, world z) of the idler plate screws
    ins = [insert_boss("M3", part=bpid, mates=ipid, tag=f"idler_insert_{i}", at=loc_from((x, inner_idl, z), (0, -1, 0), (1, 0, 0)))
           for i, (x, z) in enumerate(pts)]
    hm = horn_plate_feat(n, mate=f"servo_{J[n]}")
    shp, st = h6w.build(s6, adds=[horn_plate], extra=[hm, *ins], name=bpid)
    printed(bpid, shp, child_link[n], st, rename={"housing": bpid, "cover": f"cover_{J['ankle_roll']}"},
            expect=horn_expect(n, child_link[n]) + pocket_expect("ankle_roll", child_link[n]))
    iplate = box_s(n, -14, 14, y0p, fw / 2, z_in - tp, z_in, P["corner_r"])
    seat = idler_seat(idl[n]["bearing"], plate_t=tp, part=ipid, boss=False, at=S[n] * loc_from((0, 0, z_in), (0, 0, 1), (1, 0, 0)))
    scr = [screw_clearance("M3", through=tp + 0.5, counterbore=True, head="low", part=ipid, mates=bpid, length=12, tag=f"idler_screw_{i}",
                           at=loc_from((x, inner_idl - tp, z), (0, -1, 0), (1, 0, 0))) for i, (x, z) in enumerate(pts)]
    ishape, isites = apply(iplate, seat, *scr, name=ipid)
    printed(ipid, ishape, child_link[n], isites, expect=seat_expect(n, child_link[n]))

    # ---- 6. foot: thick horn plate on S6's horn, 5 mm sole, three tapered ribs, 4 mm cantilever-root fillets; printed on its side (up = +y) so the
    #         bending stress of the plate (z) and of the sole/ribs (x) both run along the filaments.
    n = "ankle_roll"
    fl = ifs.d["proportions_mm"]["foot_length"]
    fwid = ifs.d["proportions_mm"]["foot_width"]
    ax = ifs.axis_origin(J[n])
    x_plate0 = wp(S[n], 0, 0, zp0[n]).X
    hpf, wf, st = P["foot_plate_t"], min(P["foot_plate_w"], fwid - 4.0), P["sole_t"]
    plate = box_at(bd.Location(), (hpf, wf, ax[2] + 14.0), (x_plate0 + hpf / 2, ax[1], (ax[2] + 14.0) / 2))
    sole = box_at(bd.Location(), (fl, fwid, st), (ax[0] - 0.33 * fl + fl / 2, ax[1], st / 2))
    body = safe_union(plate, sole, "foot")
    xr0 = x_plate0 + hpf - 0.5
    for yy in (-0.5 * (wf - P["foot_rib_t"] - 8.0), 0.0, 0.5 * (wf - P["foot_rib_t"] - 8.0)):
        pts = [(xr0, st - 0.5), (xr0 + P["foot_rib_len"], st - 0.5), (xr0 + P["foot_rib_len"], st + P["foot_rib_h_end"]), (xr0, st + P["foot_rib_h"])]
        wire = bd.Wire.make_polygon([bd.Vector(x, ax[1] + yy - P["foot_rib_t"] / 2, z) for x, z in pts], close=True)
        rib = bd.extrude(bd.Face(wire), amount=P["foot_rib_t"], dir=(0, 1, 0))
        body = safe_union(body, rib, "foot ribs")
    from openhumanoid.cad.fillets import fillet_internal

    body, frep = fillet_internal(body, P["foot_fillet"], min_len=6.0, name="foot")
    asm.notes.append(f"foot: {frep['filleted']}/{frep['candidates']} internal edges filleted r={frep['radius_mm']:.1f}")
    hmf = horn_mount("sts3215-12v", plate_t=hpf, mode="flat", part="", mates=f"servo_{J[n]}", washer_od=P["horn_washer_od"]).placed(S[n] * get_component(A[n]).frames["horn_seat"])
    shp, st_ = apply(body, hmf, name="foot")
    printed(f"foot_{side}", shp, child_link[n], st_, expect=horn_expect(n, child_link[n]), up=(0, 1, 0))

    # ---- designed contacts and fits (everything else must stay clear by the generic moving/static gap)
    brackets = {"hip_yaw": f"yaw_bracket_{side}", "hip_roll": f"roll_plate_{side}", "hip_pitch": f"thigh_{side}", "knee": f"shank_{side}",
                "ankle_pitch": f"ankle_bracket_{side}", "ankle_roll": f"foot_{side}"}
    host_part = {"hip_yaw": f"housing_{J['hip_yaw']}", "hip_roll": f"yaw_bracket_{side}", "hip_pitch": f"roll_cradle_{side}",
                 "knee": f"thigh_{side}", "ankle_pitch": f"shank_{side}", "ankle_roll": f"ankle_bracket_{side}"}
    idler_part = {"hip_pitch": f"thigh_idler_{side}", "knee": f"shank_idler_{side}", "ankle_pitch": f"ankle_idler_{side}"}
    slip = dfm.clearance("slip") - 0.05
    asm.allow(f"roll_plate_{side}", f"roll_cradle_{side}")             # cradle bolted to the plate's bridge
    asm.allow(f"cover_{J['hip_pitch']}", f"roll_plate_{side}")          # the cover seats against the bridge's side face
    for nm, nxt in (("thigh", "knee"), ("shank", "ankle_pitch")):
        asm.allow(f"{nm}_{side}", f"{nm}_idler_{side}")                # idler plate bolted to the beam / web
    asm.allow(f"ankle_bracket_{side}", f"ankle_idler_{side}")
    for n in LEG:
        sv, hn_, sh, sb, cv = f"servo_{J[n]}", f"horn_{J[n]}", f"shaft_{J[n]}", f"shaftb_{J[n]}", f"cover_{J[n]}"
        br, ho = brackets[n], host_part[n]
        for a, b in ((sv, sh), (sv, sb), (sv, hn_), (sh, hn_), (hn_, br)):
            asm.allow(a, b)                    # shaft out of the case; horn floats 0.3 above the boss; plate screwed onto the horn
        asm.fit(sv, ho, slip)                  # servo in its pocket (slip fit 0.15/side)
        asm.fit(sv, cv, slip)
        asm.fit(cv, ho, 0.0)                   # cover seated on the housing
        for s_ in (sh, sb):
            asm.fit(s_, br, 0.3)
            asm.fit(s_, ho, 0.3)
            asm.fit(s_, cv, 0.3)
        asm.fit(sv, br, 0.3)
        if idl[n]:
            bg, ip = f"bearing_{J[n]}", idler_part[n]
            asm.allow(bg, ip)                  # pressed into the idler plate
            asm.fit(bg, cv, 0.04)              # inner race on the printed pin (press fit 0.05/side)
            asm.fit(bg, ho, 0.3)
            asm.fit(cv, ip, dfm.clearance("rotating") - 0.05)       # pin through the plate's relief hole
            asm.fit(cv, br, 0.3)
            asm.fit(ho, ip, 0.3)
            asm.fit(sb, bg, 0.3)
            asm.fit(sh, bg, 0.3)
            asm.fit(sv, ip, 0.3)
            asm.fit(sh, ip, 0.3)
            asm.fit(sb, ip, 0.3)
    asm.notes.append("left leg only; right leg = mirror in y")
    return asm
