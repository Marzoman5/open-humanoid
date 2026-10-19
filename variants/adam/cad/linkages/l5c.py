"""Adam baseline v2, lever L5c in real CAD (T-20261019-4ab5): the knee servo moved up into the thigh and the ankle-pitch servo moved up
into the calf, each driving its joint through a 1:1 PARALLELOGRAM (two equal parallel cranks + a coupler bar).

Built ONLY from the CAD foundation (openhumanoid/cad): the component library (STS3250 / STS3215 cases and shafts, 25T horn, 623ZZ and MR105ZZ
bearings, ISO 4762 / DIN 7984 screws), the helpers (servo_housing, horn_mount, idler_seat, screw_clearance) and dfm.yaml. Left leg,
leg centre plane y = 0, +y = lateral, x forward, z up, mm, 0.55 m Adam (hip axis 275, knee 148.5, ankle pitch 66 mm: the R1/R2a
landmarks of variants/adam/design/packaging/layout.py).

Why the stack looks like this (each item is forced by geometry, see the R2a-v2 review section 3):
* The input crank sits ON THE SERVO HORN. Its pin sweeps over the servo body, so the coupler must run in a plane OUTSIDE the horn stack
  (servo face + 2.3 horn seat + 3.0 horn + crank). The output crank at the joint must be in the same plane, so the slim pin joint
  carries the coupler plane too: this is what sets the front-view joint width, not the 32 mm "slim joint" of the packaging estimate.
* Coupler force F = T / (r sin(theta)), theta = crank angle from the ground line; the window theta in [35, 145] deg keeps 35 deg away from
  the parallelogram change point (theta = 0 / 180, where it can flip into an anti-parallelogram).
* 623ZZ C0r = 218 N (NSK datasheet via vendor listings, 2026-10-19): one bearing per pin is below the stall coupler force at the end of the
  range, so every crank pin carries TWO 623ZZ (bore from both faces, 1.6 mm shoulder ring between them, inner-race spacer).
* A printed coupler buckles at stall (PETG E = 1.68 GPa), so the coupler is 6061-T6 flat bar 3 x 10 mm (machined: cut + 2 drilled holes).
* Pins: M3 x 16 low-head ISO 7984 class 12.9, clamping coupler + washer + inner races + spacer + washer + M3 DIN 439 thin nut (the screw does
  not turn in the printed part; it is clamped to the inner races). Joint axles: M3 through 2 x 623ZZ, clamped to the tongue.
"""
from __future__ import annotations

import math

import build123d as bd

from openhumanoid.cad import dfm
from openhumanoid.cad.assembly import Assembly
from openhumanoid.cad.components import get as get_component
from openhumanoid.cad.core import FeatureResult, Site, apply, box_at, cyl_along, loc_from, safe_union
from openhumanoid.cad.features import horn_mount, screw_clearance
from openhumanoid.cad.geom import Link, Part
from openhumanoid.cad.housing import servo_housing

# ------------------------------------------------------------------------------------------------ design parameters (mm, deg)
H_ROBOT = 550.0
Z_HIP, Z_KNEE, Z_ANK = 0.50 * H_ROBOT, 0.27 * H_ROBOT, 66.0          # layout.py landmarks (ankle 66 mm: CAD-foundation floor)
P = {
    "face_y": 13.0,          # servo horn-face plane (y). Puts the cover back at -26.55 = the R1 fork's medial limit (-26): no inner-gap penalty
    "hip_face_y": 17.5,      # hip-pitch servo centred on the leg plane (R1)
    "knee_servo_z": 221.0,   # knee servo axis: the input crank boss (pin r 22 at 35 deg + boss 7.4) must stay 1 mm under the hip fork web (24 + 3.2 below the hip axis)
    "calf_servo_z": 104.0,   # calf servo axis: between the knee bridge (above) and the ankle tongue (below); see review section 3
    "r_knee": 22.0,          # crank radius, knee (STS3250 stall 4.90 N.m)
    "r_ankle": 18.0,         # crank radius, ankle (STS3215 12 V stall 2.94 N.m)
    "theta0_knee": 35.0,     # crank angle from the ground line (+z) at q = 0; knee q in [0, 110] -> theta in [35, 145]
    "theta0_ankle": 97.5,    # ankle q in [-60, 25] -> theta in [37.5, 122.5]
    "plate_t": 4.3,          # crank plate on the horn (horn_mount rule: counterbore 2.6 + head gap 0.3 + 1.6 floor)
    "boss_t": 9.6,           # 2 x 623ZZ (4 + 4) + 1.6 shoulder ring
    "ring_hole_d": 7.0,      # shoulder ring hole: clears the inner race + spacer (3 x 6 x 1.6) so only the outer races sit on the ring
    "washer_t": 0.5,         # DIN 125 / 433 M3 washer
    "nut_t": 1.8, "nut_af": 5.5,              # DIN 439 M3 thin nut: a 2.4 mm DIN 934 nut sits 0.65 mm over the housing lip (moving gap 1.0)
    "coupler_t": 3.0, "coupler_w": 10.0,      # 6061-T6 flat bar
    "pin_boss_r": 7.4,       # seat 10.1 / 2 + 2.0 bearing-seat wall (dfm bearing_seat.wall) + 0.35
    "axle_boss_r": 9.0,
    "tongue_y": (-3.0, 13.15),                # thigh tongue (knee) / shank tongue (ankle): to the housing's lateral face
    "clevis_med_y": (-9.8, -4.2),             # medial clevis plate (5.6 = 623ZZ 4 + 1.6 shoulder), 1.2 mm from the tongue
    "lateral_axis_t": 5.6,                    # lateral crank plate at the axle (bearing seat)
    "hip_web_r": 24.0, "hip_web_t": 3.2,      # R1 thigh fork web (CAD-foundation leg)
    "foot_len": 0.17 * H_ROBOT, "foot_w": 60.0, "sole_t": 3.2,
    "roll_axis_dz": -28.0,                    # ankle-roll axis below the pitch axis (CAD-foundation leg)
}
BEARING = "623ZZ"
KNEE_SERVO, CALF_SERVO, HIP_SERVO, ROLL_SERVO = "sts3250-12v", "sts3215-12v", "sts3215-12v", "sts3215-12v"
RANGES = {"hip_pitch": (-110.0, 40.0), "knee": (0.0, 110.0), "ankle_pitch": (-60.0, 25.0)}


def u_dir(theta_deg: float) -> tuple[float, float]:
    """Crank direction in the x-z plane, theta measured from +z toward +x (positive rotation about +y increases theta)."""
    t = math.radians(theta_deg)
    return math.sin(t), math.cos(t)


def ycyl(x: float, z: float, y0: float, y1: float, d: float) -> bd.Shape:
    return cyl_along(loc_from((x, y0, z), (0, 1, 0), (1, 0, 0)), d, y1 - y0)


def slot(p1, r1, p2, r2, y0, y1) -> bd.Shape:
    """Rounded link in the x-z plane between (x,z) points p1 and p2 with end radii r1, r2, extruded y0..y1."""
    dx, dz = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dz)
    beta = math.degrees(math.atan2(-dz, dx))
    w = 2 * min(r1, r2)
    bar = bd.Pos((p1[0] + p2[0]) / 2, (y0 + y1) / 2, (p1[1] + p2[1]) / 2) * bd.Rot(0, beta, 0) * bd.Box(L, y1 - y0, w)
    s = safe_union(ycyl(p1[0], p1[1], y0, y1, 2 * r1), ycyl(p2[0], p2[1], y0, y1, 2 * r2), "slot ends", single=False)
    return safe_union(s, bar, "slot")


def taper(p1, r1, p2, r2, y0, y1) -> bd.Shape:
    """Tapered crank arm: convex hull of the discs (p1, r1) and (p2, r2) in the x-z plane, extruded y0..y1 (external tangent lines)."""
    dx, dz = p2[0] - p1[0], p2[1] - p1[1]
    d = math.hypot(dx, dz)
    ux, uz = dx / d, dz / d
    a = math.asin((r1 - r2) / d)
    pts = []
    for sgn in (1, -1):
        ang = sgn * (math.pi / 2 + a)
        nx, nz = ux * math.cos(ang) - uz * math.sin(ang), ux * math.sin(ang) + uz * math.cos(ang)
        pts.append(((p1[0] + r1 * nx, p1[1] + r1 * nz), (p2[0] + r2 * nx, p2[1] + r2 * nz)))
    poly = [pts[0][0], pts[0][1], pts[1][1], pts[1][0]]
    face = bd.Face(bd.Wire.make_polygon([bd.Vector(x, y0, z) for x, z in poly], close=True))
    body = bd.extrude(face, amount=y1 - y0, dir=(0, 1, 0))
    s = safe_union(ycyl(p1[0], p1[1], y0, y1, 2 * r1), ycyl(p2[0], p2[1], y0, y1, 2 * r2), "taper ends", single=False)
    return safe_union(s, body, "taper")


def ybox(x0, x1, y0, y1, z0, z1) -> bd.Shape:
    return box_at(bd.Location(), (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def bearing_bore(x: float, z: float, y_face: float, outward: int, n: int = 1, part: str = "") -> FeatureResult:
    """Press seats for 623ZZ bearings along y at (x, z), numbers from dfm.yaml bearing_seat (seat = OD + 0.1, depth = width, shoulder 1.6).
    n = 1: one bearing pressed from the face at y_face (outward = +1: that face looks toward +y), shoulder ring behind it.
    n = 2: a boss of thickness 2w + shoulder whose outer face is y_face: one bearing from each face, the ring between them.
    The ring hole P["ring_hole_d"] clears the inner race and its spacer, so only the outer races bear on the printed ring."""
    b = get_component(f"bearing:{BEARING}").params
    r = dfm.load_dfm()["bearing_seat"]
    seat_d = b["od"] + float(r["seat_d_over_od_mm"]["v"])
    sh = float(r["shoulder_mm"]["v"])
    w = b["w"]
    o = outward

    def span(a, c):
        return min(a, c), max(a, c)
    f = FeatureResult(name=f"bearing_bore_{n}")
    f.cut.append(ycyl(x, z, *span(y_face + 0.5 * o, y_face - w * o), seat_d))                    # seat A, open past the face
    ring = span(y_face - w * o + 0.1 * o, y_face - (w + sh) * o - (0.1 if n == 2 else 1.0) * o)
    f.cut.append(ycyl(x, z, *ring, P["ring_hole_d"]))
    if n == 2:
        f.cut.append(ycyl(x, z, *span(y_face - (w + sh) * o, y_face - (2 * w + sh) * o - 0.5 * o), seat_d))   # seat B from the other face
    f.sites.append(Site(id=f"bearing_{part}_{x:.0f}_{z:.0f}", kind="press", part=part, frame=loc_from((x, y_face, z), (0, o, 0), (1, 0, 0)),
                        thread="", length_mm=w, needs_access=False))
    return f


def build(ctx=None) -> Assembly:
    F = P["face_y"]
    horn = get_component("horn-25t")
    hseat = get_component(KNEE_SERVO).frames["horn_seat"].position.Z         # 2.3 (boss 2.0 + float 0.3)
    horn_top = F + hseat + horn.params["thickness"]                           # crank plate underside (y)
    y_plate = (horn_top, horn_top + P["plate_t"])
    y_boss = (horn_top, horn_top + P["boss_t"])
    y_cpl = (y_boss[1] + P["washer_t"], y_boss[1] + P["washer_t"] + P["coupler_t"])
    y_nut = (horn_top - P["washer_t"] - P["nut_t"], horn_top - P["washer_t"])
    Sk = loc_from((0.0, F, P["knee_servo_z"]), (0, 1, 0), (1, 0, 0))         # knee servo: body forward (thigh front)
    Sc = loc_from((0.0, F, P["calf_servo_z"]), (0, 1, 0), (1, 0, 0))         # calf servo: body FORWARD (shin): a backward body meets the heel block at plantarflexion
    Sh = loc_from((0.0, P["hip_face_y"], Z_HIP), (0, 1, 0), (0, 0, 1))       # hip-pitch servo: body up (R1)
    Sr = loc_from((-26.5, 0.0, Z_ANK + P["roll_axis_dz"]), (1, 0, 0), (0, 0, 1))   # ankle-roll servo behind the ankle, horn forward (R1 heel block)
    rk, ra = P["r_knee"], P["r_ankle"]
    uk, ua = u_dir(P["theta0_knee"]), u_dir(P["theta0_ankle"])
    zks, zcs = P["knee_servo_z"], P["calf_servo_z"]
    pin_k_in = (rk * uk[0], zks + rk * uk[1])
    pin_k_out = (rk * uk[0], Z_KNEE + rk * uk[1])
    pin_a_in = (ra * ua[0], zcs + ra * ua[1])
    pin_a_out = (ra * ua[0], Z_ANK + ra * ua[1])

    origin = {"hip": (0.0, 0.0, 0.0), "thigh": (0.0, 0.0, Z_HIP), "crank_k": (0.0, 0.0, zks), "coupler_k": (pin_k_in[0], 0.0, pin_k_in[1]),
              "shank": (0.0, 0.0, Z_KNEE), "crank_a": (0.0, 0.0, zcs), "coupler_a": (pin_a_in[0], 0.0, pin_a_in[1]), "foot": (0.0, 0.0, Z_ANK)}
    parent = {"hip": None, "thigh": "hip", "crank_k": "thigh", "coupler_k": "crank_k", "shank": "thigh", "crank_a": "shank", "coupler_a": "crank_a",
              "foot": "shank"}
    joints = {"thigh": ("hip_pitch_l", RANGES["hip_pitch"]), "crank_k": ("knee_drv_l", RANGES["knee"]),
              "coupler_k": ("knee_cpl_l", (-RANGES["knee"][1], -RANGES["knee"][0])), "shank": ("knee_l", RANGES["knee"]),
              "crank_a": ("ankle_drv_l", RANGES["ankle_pitch"]), "coupler_a": ("ankle_cpl_l", (-RANGES["ankle_pitch"][1], -RANGES["ankle_pitch"][0])),
              "foot": ("ankle_pitch_l", RANGES["ankle_pitch"])}
    links: dict[str, Link] = {}
    for n in origin:
        o, po = origin[n], origin[parent[n]] if parent[n] else (0.0, 0.0, 0.0)
        js = [{"name": joints[n][0], "axis": "y", "range": list(joints[n][1])}] if n in joints else []
        links[n] = Link(n, parent[n], tuple(round(o[i] - po[i], 4) for i in range(3)), joints=js)
    asm = Assembly("adam_v2_l5c_leg_l", links, bed_mm=(220.0, 220.0, 250.0))
    asm.notes.append("closed chains as tree links: knee_drv_l = knee_l, knee_cpl_l = -knee_l; ankle_drv_l = ankle_pitch_l, ankle_cpl_l = -ankle_pitch_l "
                     "(check.py drives them together)")

    def to_link(shape, link):
        o = origin[link]
        return bd.Pos(-o[0], -o[1], -o[2]) * shape

    def site_to_link(s: Site, link: str, part: str, rename=None) -> Site:
        o = origin[link]
        own = part if s.part in ("", "housing", "cover", None) else s.part
        mates = (rename or {}).get(s.mates, s.mates)
        return Site(**{**s.__dict__, "frame": bd.Pos(-o[0], -o[1], -o[2]) * s.frame, "part": own, "mates": mates})

    def add(link, part):
        links[link].parts.append(part)
        return part

    def printed(pid, shape_w, link, sites_w=(), rename=None, wall_class="structural", meta=None):
        return add(link, Part(pid, to_link(shape_w, link), "frame", "petg", color="frame",
                              sites=[site_to_link(s, link, pid, rename) for s in sites_w], meta={"wall_class": wall_class, "expect": [], **(meta or {})}))

    def purchased(pid, shape_w, link, catalog=None, mass=None, kind="purchased", color="horn", material="purchased"):
        return add(link, Part(pid, to_link(shape_w, link), kind, material, color=color, mass_kg=mass, catalog=catalog, process="purchased"))

    def servo_parts(tag, aid, S, host, child):
        sv = get_component(aid)
        purchased(f"servo_{tag}", S * sv.params["case_shape"], host, aid, sv.mass_kg, kind="servo", color="servo")
        for t, sh in zip(("", "b"), sv.params["shaft_shapes"]):
            purchased(f"shaft{t}_{tag}", S * sh, child, mass=0.0, kind="shaft")
        purchased(f"horn_{tag}", S * sv.frames["horn_seat"] * horn.shape, child, "horn-25t", horn.mass_kg, kind="horn")

    def bearings(tag, x, z, y_faces, link):
        b = get_component(f"bearing:{BEARING}")
        out = []
        for i, (yf, sgn) in enumerate(y_faces):        # bearing shape: seat frame at the face, body toward -z of the frame
            out.append(purchased(f"bearing_{tag}_{i}", loc_from((x, yf, z), (0, sgn, 0), (1, 0, 0)) * b.shape, link, f"bearing:{BEARING}", b.mass_kg))
        return out

    def pin_stack(tag, x, z, link):
        """Coupler-side hardware clamped to the coupler: low-head screw on the lateral face, nut on the medial side (moves with the coupler)."""
        scr = get_component("screw:M3x16L")
        head = ycyl(x, z, y_cpl[1], y_cpl[1] + 2.0, scr.params["head_d"])
        nut = bd.Pos(x, (y_nut[0] + y_nut[1]) / 2, z) * bd.Rot(-90, 0, 0) * bd.extrude(bd.RegularPolygon(P["nut_af"] / math.sqrt(3), 6), P["nut_t"] / 2, both=True)
        shank = ycyl(x, z, y_nut[0], y_cpl[1], 2.9)
        purchased(f"pin_screw_{tag}", safe_union(head, shank, "pin screw"), link, "screw:M3x16L", scr.mass_kg)
        purchased(f"pin_nut_{tag}", nut, link, "nut:M3", 0.0004)

    # ======================================================================== hip (static): R1 hip-pitch servo + housing, roll-servo keep-out
    Hh = servo_housing(HIP_SERVO, part="housing_hip_pitch", cover_part="cover_hip_pitch", cover_t=4.4)
    shp, st = Hh.build(Sh, name="housing_hip_pitch")
    printed("housing_hip_pitch", shp, "hip", st, rename={"cover": "cover_hip_pitch"}, meta={"role": "R1 hip cradle stand-in (static obstacle)"})
    c_shape, c_sites = Hh.placed_cover(Sh)
    printed("cover_hip_pitch", c_shape, "hip", c_sites, rename={"housing": "housing_hip_pitch"})
    servo_parts("hip_pitch", HIP_SERVO, Sh, "hip", "thigh")
    add("hip", Part("keepout_hip_roll_servo", ybox(-81.65, -41.35, -14.9, 14.9, Z_HIP - 14.65, Z_HIP + 30.35), "keepout", "purchased", keepout=True,
                    process="purchased"))

    # ======================================================================== thigh: hip fork (R1), knee servo housing, knee tongue
    hp_top = P["hip_face_y"] + hseat + horn.params["thickness"]
    hip_plate_y = (hp_top, hp_top + P["plate_t"])
    hip_cov = Hh.params["cover_back_z"]                     # servo-frame z of the cover back -> world y = face + z
    hip_idl_y = (P["hip_face_y"] + hip_cov - 1.5 - 5.6, P["hip_face_y"] + hip_cov - 1.5)
    rw, tw = P["hip_web_r"], P["hip_web_t"]
    fork_lat = safe_union(ycyl(0.0, Z_HIP, *hip_plate_y, 28.0), ybox(-14.0, 14.0, *hip_plate_y, Z_HIP - rw - tw, Z_HIP), "fork plate")
    fork_med = safe_union(ycyl(0.0, Z_HIP, *hip_idl_y, 28.0), ybox(-14.0, 14.0, *hip_idl_y, Z_HIP - rw - tw, Z_HIP), "idler plate")
    web = ybox(-14.0, 14.0, hip_idl_y[0], hip_plate_y[1], Z_HIP - rw - tw, Z_HIP - rw)
    Hk = servo_housing(KNEE_SERVO, part="thigh", cover_part="cover_knee", cover_t=4.4)
    hk = Hk.params
    z_hk_top = zks + hk["outer_y"][1]
    col = ybox(-14.0, 14.0, hip_idl_y[0] + 2.0, F + hk["z_top"], z_hk_top - 1.0, Z_HIP - rw - tw + 0.5)       # web -> knee housing
    ty = P["tongue_y"]
    z_hk_bot = zks + hk["outer_y"][0]
    beam = ybox(-4.0, 10.0, ty[0], ty[1], Z_KNEE, z_hk_bot + 1.0)
    tongue = ycyl(0.0, Z_KNEE, ty[0], ty[1], 2 * P["axle_boss_r"])
    hm_hip = horn_mount(HIP_SERVO, plate_t=P["plate_t"], mode="flat", part="thigh", mates="servo_hip_pitch").placed(Sh * get_component(HIP_SERVO).frames["horn_seat"])
    axle_hole = FeatureResult(cut=[ycyl(0.0, Z_KNEE, ty[0] - 1, ty[1] + 1, 3.0 + dfm.hole_comp(3.0) + 0.1)], name="knee_axle_hole")
    hip_seat = FeatureResult(cut=[ycyl(0.0, Z_HIP, hip_idl_y[0] - 1, hip_idl_y[1] + 1, get_component("bearing:MR105ZZ").params["od"] + 0.1)], name="hip_idler_seat_stub")
    shp, st = Hk.build(Sk, adds=[fork_lat, fork_med, web, col, beam, tongue], extra=[hm_hip, axle_hole, hip_seat], name="thigh")
    printed("thigh", shp, "thigh", st, rename={"cover": "cover_knee", "housing": "thigh"})
    c_shape, c_sites = Hk.placed_cover(Sk)
    printed("cover_knee", c_shape, "thigh", c_sites, rename={"housing": "thigh"})
    servo_parts("knee", KNEE_SERVO, Sk, "thigh", "crank_k")
    # knee axle (clamped to the tongue): low-head M3 on the lateral bearing, nut on the medial face
    y_ax_lat = (y_plate[0], y_plate[0] + P["lateral_axis_t"])
    cm = P["clevis_med_y"]
    ax_head = ycyl(0.0, Z_KNEE, y_ax_lat[1] + P["washer_t"], y_ax_lat[1] + P["washer_t"] + 2.0, 5.5)
    ax_nut = ycyl(0.0, Z_KNEE, cm[0] - P["washer_t"] - P["nut_t"], cm[0] - P["washer_t"], P["nut_af"] * 1.1547)
    ax_shank = ycyl(0.0, Z_KNEE, cm[0] - P["washer_t"] - P["nut_t"] - 1.0, y_ax_lat[1] + P["washer_t"], 2.9)
    purchased("axle_knee", safe_union(safe_union(ax_head, ax_shank, "axle"), ax_nut, "axle+nut"), "thigh", "screw:M3x45L", 0.004)

    # ======================================================================== knee input crank (on the knee servo horn) + coupler
    def crank(pid, S, aid, pin, axis_xz, r_axis, link, tag):
        arm = taper(axis_xz, r_axis, pin, P["pin_boss_r"], *y_plate)
        boss = ycyl(pin[0], pin[1], *y_boss, 2 * P["pin_boss_r"])
        hm = horn_mount(aid, plate_t=P["plate_t"], mode="flat", part=pid, mates=f"servo_{tag}").placed(S * get_component(aid).frames["horn_seat"])
        bb = bearing_bore(pin[0], pin[1], y_boss[1], +1, n=2, part=pid)
        shp_, st_ = apply(safe_union(arm, boss, pid), hm, bb, name=pid)
        printed(pid, shp_, link, st_)
        bearings(f"{tag}_pin_in", pin[0], pin[1], [(y_boss[1], 1), (y_boss[0], -1)], link)

    crank("crank_knee", Sk, KNEE_SERVO, pin_k_in, (0.0, zks), 12.0, "crank_k", "knee")

    def coupler(pid, p_top, p_bot, link, tag_top, tag_bot):
        bar = slot(p_top, P["coupler_w"] / 2, p_bot, P["coupler_w"] / 2, *y_cpl)
        holes = FeatureResult(cut=[ycyl(p[0], p[1], y_cpl[0] - 1, y_cpl[1] + 1, 3.2) for p in (p_top, p_bot)], name="pin_holes")
        shp_, _ = apply(bar, holes, name=pid)
        sites = [Site(id=f"pin_{t}", kind="screw", part=pid, frame=loc_from((p[0], y_cpl[1] + 2.0, p[1]), (0, 1, 0), (1, 0, 0)), thread="M3", length_mm=16,
                      mates=f"crank_{t}", tool_d=8.0, tool_len=30.0) for p, t in ((p_top, tag_top), (p_bot, tag_bot))]
        add(link, Part(pid, to_link(shp_, link), "purchased", "al6061", color="horn", mass_kg=round(2.7e-6 * shp_.volume, 4), process="purchased",
                       catalog="al6061-flat-3x10", sites=[site_to_link(s, link, pid) for s in sites]))
        pin_stack(f"{pid}_top", p_top[0], p_top[1], link)
        pin_stack(f"{pid}_bot", p_bot[0], p_bot[1], link)

    coupler("coupler_knee", pin_k_in, pin_k_out, "coupler_k", "knee_in", "knee_out")

    # ======================================================================== shank: knee clevis + output crank, bridge, calf housing, ankle tongue
    Hc = servo_housing(CALF_SERVO, part="shank", cover_part="cover_calf", cover_t=4.4)
    hc = Hc.params
    z_hc_top, z_hc_bot = zcs + hc["outer_y"][1], zcs + hc["outer_y"][0]
    med_plate = slot((0.0, Z_KNEE), P["axle_boss_r"], (0.0, Z_KNEE - 12.0), P["axle_boss_r"], *cm)
    lat_axis = ycyl(0.0, Z_KNEE, *y_ax_lat, 2 * P["axle_boss_r"])
    lat_arm = taper((0.0, Z_KNEE), P["axle_boss_r"], pin_k_out, P["pin_boss_r"], *y_plate)
    lat_down = slot((0.0, Z_KNEE), P["axle_boss_r"], (0.0, Z_KNEE - 12.0), P["axle_boss_r"], *y_plate)
    out_boss = ycyl(pin_k_out[0], pin_k_out[1], *y_boss, 2 * P["pin_boss_r"])
    z_br = (Z_KNEE - 21.5, Z_KNEE - 11.0)                           # bridge below the knee: outside the tongue's 9 mm radius, above the calf crank sweep
    bridge = ybox(-10.0, 10.0, cm[0], y_plate[1], *z_br)
    drop = ybox(-14.0, 10.0, cm[0], F + hc["z_top"], z_hc_top - 1.0, z_br[0] + 0.5)
    ank_tongue = ycyl(0.0, Z_ANK, ty[0], ty[1], 2 * P["axle_boss_r"])
    ank_beam = ybox(-8.0, 8.0, ty[0], ty[1], Z_ANK, z_hc_bot + 1.0)
    knee_bores = [bearing_bore(0.0, Z_KNEE, cm[0], -1, n=1, part="shank"), bearing_bore(0.0, Z_KNEE, y_ax_lat[1], +1, n=1, part="shank"),
                  bearing_bore(pin_k_out[0], pin_k_out[1], y_boss[1], +1, n=2, part="shank")]
    ank_hole = FeatureResult(cut=[ycyl(0.0, Z_ANK, ty[0] - 1, ty[1] + 1, 3.0 + dfm.hole_comp(3.0) + 0.1)], name="ankle_axle_hole")
    shp, st = Hc.build(Sc, adds=[med_plate, lat_axis, lat_arm, lat_down, out_boss, bridge, drop, ank_beam, ank_tongue], extra=[*knee_bores, ank_hole], name="shank")
    printed("shank", shp, "shank", st, rename={"cover": "cover_calf", "housing": "shank"})
    c_shape, c_sites = Hc.placed_cover(Sc)
    printed("cover_calf", c_shape, "shank", c_sites, rename={"housing": "shank"})
    servo_parts("calf", CALF_SERVO, Sc, "shank", "crank_a")
    bearings("knee_axle", 0.0, Z_KNEE, [(cm[0], -1), (y_ax_lat[1], 1)], "shank")
    bearings("knee_pin_out", pin_k_out[0], pin_k_out[1], [(y_boss[1], 1), (y_boss[0], -1)], "shank")
    a_head = ycyl(0.0, Z_ANK, y_ax_lat[1] + P["washer_t"], y_ax_lat[1] + P["washer_t"] + 2.0, 5.5)
    a_nut = ycyl(0.0, Z_ANK, cm[0] - P["washer_t"] - P["nut_t"], cm[0] - P["washer_t"], P["nut_af"] * 1.1547)
    a_shank = ycyl(0.0, Z_ANK, cm[0] - P["washer_t"] - P["nut_t"] - 1.0, y_ax_lat[1] + P["washer_t"], 2.9)
    purchased("axle_ankle", safe_union(safe_union(a_head, a_shank, "axle"), a_nut, "axle+nut"), "shank", "screw:M3x45L", 0.004)

    # ======================================================================== ankle input crank (calf servo horn) + coupler
    crank("crank_ankle", Sc, CALF_SERVO, pin_a_in, (0.0, zcs), 12.0, "crank_a", "calf")
    coupler("coupler_ankle", pin_a_in, pin_a_out, "coupler_a", "ankle_in", "ankle_out")

    # ======================================================================== foot: ankle clevis + output crank + ankle-roll servo housing (heel) + sole
    Hr = servo_housing(ROLL_SERVO, part="ankle_cradle", cover_part="cover_roll", cover_t=4.4)
    f_med = slot((0.0, Z_ANK), P["axle_boss_r"], (-20.0, Z_ANK - 4.0), P["axle_boss_r"], *cm)
    f_lat_ax = ycyl(0.0, Z_ANK, *y_ax_lat, 2 * P["axle_boss_r"])
    f_lat_arm = taper((0.0, Z_ANK), P["axle_boss_r"], pin_a_out, P["pin_boss_r"], *y_plate)
    f_lat_back = slot((0.0, Z_ANK), P["axle_boss_r"], (-20.0, Z_ANK - 4.0), P["axle_boss_r"], *y_plate)
    f_boss = ycyl(pin_a_out[0], pin_a_out[1], *y_boss, 2 * P["pin_boss_r"])
    hr = Hr.params
    x_cr_front = -26.5 + hr["z_top"]                                    # roll housing front (servo z = world x)
    f_bridge = ybox(x_cr_front - 1.0, -12.0, cm[0], y_plate[1], Z_ANK - 13.0, Z_ANK - 4.0)
    foot_bores = [bearing_bore(0.0, Z_ANK, cm[0], -1, n=1, part="ankle_cradle"), bearing_bore(0.0, Z_ANK, y_ax_lat[1], +1, n=1, part="ankle_cradle"),
                  bearing_bore(pin_a_out[0], pin_a_out[1], y_boss[1], +1, n=2, part="ankle_cradle")]
    shp, st = Hr.build(Sr, adds=[f_med, f_lat_ax, f_lat_arm, f_lat_back, f_boss, f_bridge], extra=foot_bores, name="ankle_cradle")
    printed("ankle_cradle", shp, "foot", st, rename={"cover": "cover_roll", "housing": "ankle_cradle"})
    c_shape, c_sites = Hr.placed_cover(Sr)
    printed("cover_roll", c_shape, "foot", c_sites, rename={"housing": "ankle_cradle"})
    servo_parts("ankle_roll", ROLL_SERVO, Sr, "foot", "foot")
    bearings("ankle_axle", 0.0, Z_ANK, [(cm[0], -1), (y_ax_lat[1], 1)], "foot")
    bearings("ankle_pin_out", pin_a_out[0], pin_a_out[1], [(y_boss[1], 1), (y_boss[0], -1)], "foot")
    fl = P["foot_len"]
    sole = ybox(-0.33 * fl, 0.67 * fl, -P["foot_w"] / 2, P["foot_w"] / 2, 0.0, P["sole_t"])
    add("foot", Part("sole_keepout", to_link(sole, "foot"), "keepout", "purchased", keepout=True, process="purchased"))

    # ======================================================================== designed contacts / fits
    slip = dfm.clearance("slip") - 0.05
    for tag, host, br in (("hip_pitch", "housing_hip_pitch", "thigh"), ("knee", "thigh", "crank_knee"), ("calf", "shank", "crank_ankle"),
                          ("ankle_roll", "ankle_cradle", None)):
        sv, hn, sh, sb = f"servo_{tag}", f"horn_{tag}", f"shaft_{tag}", f"shaftb_{tag}"
        cv = {"hip_pitch": "cover_hip_pitch", "knee": "cover_knee", "calf": "cover_calf", "ankle_roll": "cover_roll"}[tag]
        for a, b in ((sv, sh), (sv, sb), (sv, hn), (sh, hn)):
            asm.allow(a, b)
        asm.fit(sv, host, slip)
        asm.fit(sv, cv, slip)
        asm.fit(cv, host, 0.0)
        for s_ in (sh, sb):
            asm.fit(s_, host, 0.3)
            asm.fit(s_, cv, 0.3)
        if br:
            asm.allow(hn, br)
            asm.fit(sh, br, 0.3)
            asm.fit(sv, br, 0.3)
    asm.allow("horn_ankle_roll", "ankle_cradle")
    asm.allow("horn_hip_pitch", "thigh")
    asm.fit("shaft_hip_pitch", "thigh", 0.3)
    asm.fit("servo_hip_pitch", "thigh", 0.3)
    for pid in [p.id for _, p in asm.parts() if p.id.startswith("bearing_")]:
        host_part = {"knee_pin_in": "crank_knee", "calf_pin_in": "crank_ankle", "knee_axle": "shank", "knee_pin_out": "shank",
                     "ankle_axle": "ankle_cradle", "ankle_pin_out": "ankle_cradle"}[pid[len("bearing_"):-2]]
        asm.allow(pid, host_part)                     # pressed in
    # clamped stacks: inner race <-> pin screw / axle (designed contact), coupler on a 0.5 mm washer over the boss
    for cp, tags in (("coupler_knee", ("knee_pin_in", "knee_pin_out")), ("coupler_ankle", ("calf_pin_in", "ankle_pin_out"))):
        top, bot = f"pin_screw_{cp}_top", f"pin_screw_{cp}_bot"
        for i in (0, 1):
            asm.allow(top, f"bearing_{tags[0]}_{i}")
            asm.allow(bot, f"bearing_{tags[1]}_{i}")
            asm.fit(f"pin_nut_{cp}_top", f"bearing_{tags[0]}_{i}", P["washer_t"] - 0.1)
            asm.fit(f"pin_nut_{cp}_bot", f"bearing_{tags[1]}_{i}", P["washer_t"] - 0.1)
            asm.fit(cp, f"bearing_{tags[0]}_{i}", P["washer_t"] - 0.1)
            asm.fit(cp, f"bearing_{tags[1]}_{i}", P["washer_t"] - 0.1)
        asm.allow(top, cp)
        asm.allow(bot, cp)
        asm.allow(f"pin_nut_{cp}_top", top)
        asm.allow(f"pin_nut_{cp}_bot", bot)
        host_in = "crank_knee" if cp == "coupler_knee" else "crank_ankle"
        host_out = "shank" if cp == "coupler_knee" else "ankle_cradle"
        for h_, end in ((host_in, "top"), (host_out, "bot")):
            asm.fit(cp, h_, P["washer_t"] - 0.1)
            asm.fit(f"pin_screw_{cp}_{end}", h_, 0.3)          # screw through the 7 mm ring hole / 10.1 seats
            asm.fit(f"pin_nut_{cp}_{end}", h_, P["washer_t"] - 0.1)
    for ax, bb, host, tg in (("axle_knee", "knee_axle", "shank", "thigh"), ("axle_ankle", "ankle_axle", "ankle_cradle", "shank")):
        for i in (0, 1):
            asm.allow(ax, f"bearing_{bb}_{i}")
        asm.allow(ax, tg)                             # clamped through the tongue
        asm.fit(ax, host, 0.3)
    asm.notes.append(f"stack (y, mm): servo face {F}; crank plate {y_plate}; pin boss {y_boss}; coupler {y_cpl}; pin nut {y_nut}")
    asm.notes.append(f"pins (x, z): knee in {pin_k_in}, knee out {pin_k_out}, ankle in {pin_a_in}, ankle out {pin_a_out}")
    asm.meta = {"P": P, "y_plate": y_plate, "y_boss": y_boss, "y_cpl": y_cpl, "y_nut": y_nut, "pins": {"knee_in": pin_k_in, "knee_out": pin_k_out,
                "ankle_in": pin_a_in, "ankle_out": pin_a_out}, "d_knee": zks - Z_KNEE, "d_ankle": zcs - Z_ANK}
    return asm
