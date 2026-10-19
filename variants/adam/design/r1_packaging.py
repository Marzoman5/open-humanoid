"""R1 packaging study: front + side hard-point layouts from catalog dimensions and the CAD-foundation facts, a profiles.yaml massing that
encloses them, and the design-metric verdicts (P1-P10, S3, HP) per height and layout. Answers challenge-1 row 1 (minimum height at which
"not a toy" proportions are achievable). Task T-20261019-36f9.

Run:  .venv/Scripts/python variants/adam/design/r1_packaging.py [--heights 0.50 0.55 ...] [--render CASE ...] [--quick]
Out:  variants/adam/design/r1_packaging/<case>/profiles.yaml + metrics.json, summary.{json,md};
      docs/design-method/R1/hardpoints_<case>.png (front + side) and docs/design-method/R1/studio_<case>/ (studio rig) for --render cases.

LAYOUTS (the question the challenge asked):
  chest : shoulder-pitch servos INSIDE the chest (back to back, horns out through the torso side), shoulder-roll servo in the shoulder cap.
  arm   : shoulder-pitch servo in the shoulder cap (horn inward onto a torso bracket), roll servo below it in the upper arm.
LEGS:   6dof (CAD-foundation leg: ankle-roll servo behind the ankle, ankle axis 66 mm) or 5dof (no ankle roll, Open Duck Mini style: ankle
        axis 40 mm, ODM's measured 38.9 mm in docs/concept-engine.md).

Every dimension is a named constant below with its source; the massing is the SMALLEST superellipse section family (n = 3.5) that encloses
the hard points with the shell gap + wall, starting from adult proportions (head 0.13 H, hip 0.50 H, knee 0.27 H, shoulder at the neck base).
Packaging choices made here (so the R1 reader can challenge them): hip-yaw servos with their long axis fore-aft so the waist-yaw servo sits
between them inside the pelvis (it then costs no torso height); compute, bus adapter, buck and IMU in the rear pelvis above the hip-roll
servos; the 3S pack across the upper back behind the shoulder servos; the neck-yaw servo in a front chest slot; the elbow servo in the upper arm
(long axis up); the arm rests at the smallest A-pose cant that clears the hips (arms otherwise collide with the 52 mm hip forks).
NOT checked here: cables, fasteners, ROM sweeps of the arms (the CAD geometry gate does those after R2a).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = HERE / "r1_packaging"
DOCS = REPO / "docs" / "design-method" / "R1"

# ------------------------------------------------------------------------------------------- constants (mm) and sources
S_L, S_W, S_H = 45.2, 24.7, 35.0      # STS3215 body: catalog/actuators/sts3215-12v.yaml dimensions_mm (verified)
AX = 12.0                            # output axis from the near end: openhumanoid/cad/components (sts3215 params axis_x, ESTIMATE)
BOSS = 2.0                           # output boss height: cad component sts3215 boss_h (ESTIMATE)
HOUS = 2.4 + 0.25                    # housing wall: dfm.yaml walls.load_path_mm 2.4 + sliding fit 0.25 per side
SHELL = 1.5 + 1.6                    # shell gap + shell wall: variants/adam/design-language.md (1.6 mm walls) and design-method D4 clearance 1.5 mm
MOVE = 1.0                           # moving gap between separately printed links: dfm.yaml moving_gap_min_mm
FORK = 52.0                          # pitch-joint fork width across (idler plate to horn plate): docs/cad-foundation.md section 9
PLATE = 4.3                          # horn plate thickness: docs/cad-foundation.md section 9 row 3
HORN = 3.0                           # horn thickness: cad component horn-25t
HIP_Y = 35.0                         # hip spacing 70 mm, servo-fixed floor (T-0004, openhumanoid/concept/thresholds.yaml packaging floors)
YAW_Z = (66.0, 101.0)                # hip-yaw servo body above the hip axis (variants/adam/cad/layout_v2.yaml horn_at 66 + 35 body)
PELVIS_TOP = 106.0                   # hip gimbal stack above the hip axis: docs/cad-foundation.md ("about 106 mm above")
ROLL_X = (-79.0, -44.0)              # hip-roll servo behind the hip axis (layout_v2 horn_at -44 + 35 body; "84 mm behind" incl. housing)
ROLL_Z = (-AX, S_L - AX)             # hip-roll servo long axis vertical, axis 12 mm from its near end
ANKLE = {"6dof": 66.0, "5dof": 40.0}  # ankle-pitch axis height: CAD foundation 66 mm (roll servo) / ODM 38.9 mm (no roll servo)
AROLL_X, AROLL_Z = (-61.5, -26.5), (26.0, 71.0)   # ankle-roll servo behind the ankle (layout_v2 interfaces.yaml, ankle_roll_l)
PACK = (22.0, 72.0, 36.0)            # 3S 1300 Tattu, x (depth) / y (across) / z: catalog lipo-3s-1300-tattu 72 x 36 x 22 (verified)
PI5 = (17.0, 85.0, 56.0)             # Raspberry Pi 5 85 x 56 x 17 (catalog rpi-5-4gb, verified): across the rear pelvis
CAM = (11.5, 25.0, 24.0)             # Camera Module 3 25 x 24 x 11.5 (catalog cam-rpi-v3, verified)
WAIST_RING = 10.0                    # waist-yaw output bearing ring between pelvis top and torso floor (ASSUMPTION)
N = 3.5                              # section squareness for every segment (design language: soft squircle; >6 reads boxy)
FA_WIDTH = 1.12                      # section width = 1.12 x the box half-width (+margin); depth solved so the box corner sits on the superellipse.
                                     # 1.12 balances front width (the gated view) against side depth (1.04 made the side view ~1.7x deeper than the box)

CANON = {"head": 0.13, "neck_hu": 0.30, "hip": 0.50, "knee": 0.27, "upper_arm": 0.19, "forearm": 0.21, "foot": 0.155, "foot_h": 20.0}


def _enclose(a: float, b: float, fa: float = 1.06, n: float = N) -> tuple[float, float]:
    """Superellipse half-axes (A, B) that contain the box half-extents (a, b): A = fa*a, B solved so the corner (a, b) lies on the curve."""
    A = fa * a
    r = 1.0 - (a / A) ** n
    B = b / r ** (1.0 / n)
    return A, B


def layout(H_m: float, arms: str, legs: str) -> dict:
    H = H_m * 1000.0
    notes = []
    # ---------------- vertical landmarks
    head_need = AX + (S_L - AX) + 2 * HOUS + 2 * SHELL                    # neck-pitch servo standing in the head
    head_h = max(CANON["head"] * H, head_need)
    chin = H - head_h
    neck_base = chin - CANON["neck_hu"] * head_h
    s = neck_base - (AX + HOUS + SHELL)                                     # shoulder axis: pitch servo long axis DOWN, its top 12 mm above
    a = ANKLE[legs]
    h = CANON["hip"] * H
    chest_floor = s - (S_L - AX) - HOUS                                     # bottom of the shoulder-servo housings
    need = h + PELVIS_TOP + WAIST_RING
    if chest_floor < need:
        h_new = max(0.46 * H, chest_floor - PELVIS_TOP - WAIST_RING)
        notes.append(f"torso too short at hip 0.50 H: hip lowered to {h_new / H:.3f} H")
        h = h_new
    torso_fits = chest_floor >= h + PELVIS_TOP + WAIST_RING - 1e-6
    if not torso_fits:
        notes.append(f"chest floor {chest_floor:.0f} mm below pelvis top + ring {h + PELVIS_TOP + WAIST_RING:.0f} mm even at hip 0.46 H")
    k = CANON["knee"] * H
    k_min = a + (S_L - AX) + AX + 2 * HOUS + MOVE                           # ankle servo top to knee servo bottom
    if k < k_min:
        notes.append(f"knee raised from {k / H:.3f} H to {k_min / H:.3f} H (ankle + knee servo stack)")
        k = k_min
    if h - k < k_min - a:
        notes.append("thigh shorter than the hip + knee servo stack")
    e = s - CANON["upper_arm"] * H                                          # elbow axis
    hand_end = e - CANON["forearm"] * H
    # ---------------- front (y) stack-up
    pack_w = PACK[1] + 2 * HOUS
    neck_slot_w = S_L + 2 * HOUS                                            # neck-yaw servo, long axis across y
    if arms == "chest":
        Tf = max(2 * (S_H + BOSS) + 2.4, pack_w, neck_slot_w)              # two pitch servos back to back + a 2.4 mm centre wall
        ya = Tf / 2 + SHELL + MOVE + SHELL + PLATE + HOUS + S_W / 2         # roll-servo centre: torso shell, gap, arm shell, horn plate, housing
        cap_half = S_W / 2 + HOUS + SHELL
        cap_depth = S_H / 2 + HOUS + SHELL                                  # roll axis fore-aft: 35 mm body thickness along x
    else:
        Tf = max(pack_w, neck_slot_w)
        ya = Tf / 2 + PLATE + SHELL + MOVE + SHELL + HORN + (S_H + BOSS) / 2   # pitch-servo body centre in the shoulder cap
        cap_half = (S_H + BOSS) / 2 + HOUS + SHELL
        cap_depth = S_W / 2 + HOUS + SHELL
    elbow_half = (S_H + BOSS) / 2 + HOUS + SHELL                            # elbow axis along y: 37 mm across
    fore_half = S_W / 2 + HOUS + SHELL                                      # gripper servo, 24.7 across
    hip_out = HIP_Y + FORK / 2 + SHELL                                      # thigh outer face
    yaw_half = HIP_Y + S_W / 2 + HOUS + SHELL                               # pelvis at the yaw-servo level
    # smallest A-pose cant: at every arm zone the arm's inner face must clear what is beside it by MOVE
    zones = [  # (z_top, z_bot, arm half width there)
        (s + AX + HOUS, s - (S_L - AX) - HOUS, cap_half),
        (e + (S_L - AX) + HOUS, e - AX - HOUS, elbow_half),
        (e - AX - HOUS, hand_end, fore_half)]
    body = [(h + PELVIS_TOP, h + YAW_Z[0] - HOUS, yaw_half), (h + YAW_Z[0], 0.0, hip_out)]   # (z_top, z_bot, body half width)
    tan_t = 0.0
    for zt, zb, wa in zones:
        for bt, bb, wb in body:
            lo, hi = max(zb, bb), min(zt, bt)
            if hi <= lo:
                continue
            d = s - hi                                                       # nearest-to-shoulder overlapping depth (worst)
            need_off = wb + MOVE + wa - ya
            if need_off > 0 and d > 1:
                tan_t = max(tan_t, need_off / d)
    cant = math.degrees(math.atan(tan_t))
    band_bot = neck_base - 0.14 * H
    arm_out_band = ya + cap_half + max(0.0, s - band_bot) * tan_t
    if arms == "chest" and (e + (S_L - AX) + HOUS + SHELL) > band_bot:
        arm_out_band = max(arm_out_band, ya + elbow_half + (s - band_bot) * tan_t)
    P3_est = 2 * arm_out_band / H
    # ---------------- side (x) stack-up of the chest: neck-yaw slot in front, shoulder servos, pack behind
    sv = S_W / 2 + HOUS
    chest_x = (-(sv + PACK[0] + 2 * HOUS), sv + S_W + 2 * HOUS)
    return dict(H=H, arms=arms, legs=legs, head_h=head_h, chin=chin, neck_base=neck_base, s=s, h=h, k=k, a=a, e=e, hand_end=hand_end,
                Tf=Tf, ya=ya, cap_half=cap_half, cap_depth=cap_depth, elbow_half=elbow_half, fore_half=fore_half, hip_out=hip_out, yaw_half=yaw_half,
                cant_deg=cant, tan_t=tan_t, P3_est=P3_est, shoulder_outer_est=2 * arm_out_band, chest_x=chest_x, chest_floor=chest_floor,
                torso_fits=torso_fits, notes=notes)


def _box(id_, seg, xr, yr, zr, m=SHELL / 1000.0):
    c = [(xr[0] + xr[1]) / 2000, (yr[0] + yr[1]) / 2000, (zr[0] + zr[1]) / 2000]
    sz = [abs(xr[1] - xr[0]) / 1000, abs(yr[1] - yr[0]) / 1000, abs(zr[1] - zr[0]) / 1000]
    return {"id": id_, "segment": seg, "center": [round(v, 5) for v in c], "size": [round(v, 5) for v in sz], "margin_m": round(m, 4)}


def hard_points(L: dict) -> list[dict]:
    h, k, a, s, e = L["h"], L["k"], L["a"], L["s"], L["e"]
    y, hs = HIP_Y, S_W / 2 + HOUS
    hp = []
    # legs (left)
    for nm, z in (("hip_pitch", h), ("knee", k), ("ankle_pitch", a)):
        hp.append(_box(f"{nm}_servo_l", "leg_l", (-hs, hs), (y - FORK / 2, y + FORK / 2), (z - AX - HOUS, z + S_L - AX + HOUS)))
    hp.append(_box("hip_roll_servo_l", "glute_l", (ROLL_X[0] - HOUS, ROLL_X[1] + HOUS), (y - hs, y + hs), (h + ROLL_Z[0] - HOUS, h + ROLL_Z[1] + HOUS)))
    if L["legs"] == "6dof":
        hp.append(_box("ankle_roll_servo_l", "heel_l", (AROLL_X[0] - HOUS, AROLL_X[1] + HOUS), (y - hs, y + hs), (AROLL_Z[0] - HOUS, AROLL_Z[1] + HOUS)))
    # pelvis: hip yaw x2 (long axis fore-aft), waist yaw between them, rear electronics bay
    for nm, yc in (("hip_yaw_servo_l", y), ("hip_yaw_servo_r", -y), ("waist_yaw_servo", 0.0)):
        hp.append(_box(nm, "torso", (-AX - HOUS, S_L - AX + HOUS), (yc - hs, yc + hs), (h + YAW_Z[0] - HOUS, h + YAW_Z[1] + HOUS)))
    hp.append(_box("pi5_adapter_buck_imu_bay", "torso", (-AX - HOUS - PI5[0] - 2 * HOUS, -AX - HOUS), (-PI5[1] / 2 - HOUS, PI5[1] / 2 + HOUS),
                   (h + ROLL_Z[1] + HOUS + 2, h + ROLL_Z[1] + HOUS + 2 + PI5[2] + 2 * HOUS)))
    # chest
    cx0, cx1 = L["chest_x"]
    sv = S_W / 2 + HOUS
    hp.append(_box("pack_3s1300", "torso", (cx0, -sv), (-PACK[1] / 2 - HOUS, PACK[1] / 2 + HOUS), (s + AX + HOUS - PACK[2] - 2 * HOUS, s + AX + HOUS)))
    hp.append(_box("neck_yaw_servo", "torso", (sv, cx1), (-S_L / 2 - HOUS, S_L / 2 + HOUS), (s + AX + HOUS - S_H - 2 * HOUS, s + AX + HOUS)))
    if L["arms"] == "chest":
        hp.append(_box("shoulder_pitch_servos", "torso", (-sv, sv), (-L["Tf"] / 2, L["Tf"] / 2), (s - (S_L - AX) - HOUS, s + AX + HOUS)))
    # arm (left), positions at the arm centre line with the cant applied at the box's mid height
    def ay(z):
        return L["ya"] + (s - z) * L["tan_t"]
    if L["arms"] == "arm":
        z0, z1 = s - (S_L - AX) - HOUS, s + AX + HOUS
        hp.append(_box("shoulder_pitch_servo_l", "arm_l", (-sv, sv), (ay((z0 + z1) / 2) - (S_H + BOSS) / 2 - HOUS, ay((z0 + z1) / 2) + (S_H + BOSS) / 2 + HOUS), (z0, z1)))
        rz0, rz1 = z0 - S_L - 2 * HOUS, z0
    else:
        rz0, rz1 = s - (S_L - AX) - HOUS, s + AX + HOUS
    hp.append(_box("shoulder_roll_servo_l", "arm_l", (-S_H / 2 - HOUS, S_H / 2 + HOUS), (ay((rz0 + rz1) / 2) - sv, ay((rz0 + rz1) / 2) + sv), (rz0, rz1)))
    ez0, ez1 = e - AX - HOUS, e + S_L - AX + HOUS
    hp.append(_box("elbow_servo_l", "arm_l", (-sv, sv), (ay((ez0 + ez1) / 2) - (S_H + BOSS) / 2 - HOUS, ay((ez0 + ez1) / 2) + (S_H + BOSS) / 2 + HOUS), (ez0, ez1)))
    gz1 = ez0 - 3
    hp.append(_box("gripper_servo_l", "arm_l", (-S_H / 2 - HOUS, S_H / 2 + HOUS), (ay(gz1 - 25) - sv, ay(gz1 - 25) + sv), (gz1 - S_L - 2 * HOUS, gz1)))
    # head: neck-pitch servo standing, camera in front of it
    np_ = L["chin"] + AX + HOUS + SHELL
    hp.append(_box("neck_pitch_servo", "head", (-sv, sv), (-(S_H + BOSS) / 2 - HOUS, (S_H + BOSS) / 2 + HOUS), (np_ - AX - HOUS, np_ + S_L - AX + HOUS)))
    hp.append(_box("camera", "head", (sv + 1, sv + 1 + CAM[0]), (-CAM[1] / 2, CAM[1] / 2), (np_ + 10, np_ + 10 + CAM[2])))
    return hp


HP_M = SHELL + 1.5        # section sizing margin: the HP check measures the box CORNERS against the surface, so the corner gets 1.5 mm extra


def _need(hps, seg, z, cy0=0.0, cx0=None):
    """Box half extents (about cy0, cx0) of every hard point of `seg` that spans height z, plus the sizing margin."""
    a = 0.0
    xs = []
    for hp in hps:
        if hp["segment"] != seg:
            continue
        cz, sz = hp["center"][2] * 1000, hp["size"][2] * 1000
        if not (cz - sz / 2 - HP_M - 0.6 <= z <= cz + sz / 2 + HP_M + 0.6):
            continue
        cx, cy = hp["center"][0] * 1000, hp["center"][1] * 1000
        sx, sy = hp["size"][0] * 1000, hp["size"][1] * 1000
        a = max(a, abs(cy - cy0) + sy / 2 + HP_M)
        xs += [cx - sx / 2 - HP_M, cx + sx / 2 + HP_M]
    if not xs:
        return 0.0, 0.0, (0.0 if cx0 is None else cx0)
    cxm = (min(xs) + max(xs)) / 2 if cx0 is None else cx0
    b = max(abs(v - cxm) for v in xs)
    return a, b, cxm


def _box_ends(hps, seg):
    out = []
    for hp in hps:
        if hp["segment"] == seg:
            cz, sz = hp["center"][2] * 1000, hp["size"][2] * 1000
            out += [cz - sz / 2 - HP_M, cz - sz / 2, cz, cz + sz / 2, cz + sz / 2 + HP_M]
    return out


def _st(z, A, B, cy=0.0, cx=0.0, n=N):
    d = {"z": round(z / 1000, 5), "w": round(2 * A / 1000, 5), "d": round(2 * B / 1000, 5), "n": n}
    if cy:
        d["cy"] = round(cy / 1000, 5)
    if cx:
        d["cx"] = round(cx / 1000, 5)
    return d


def _stations(hps, seg, zs, cy_fn=lambda z: 0.0, cx0=None, floor=None, fa=1.06, n=N, cx_default=0.0):
    """One section per z: the smallest superellipse that encloses every hard point of `seg` spanning z, never below floor(z) = (a, b)."""
    merged = []
    for z in sorted(zs):
        if merged and z - merged[-1] < 1.5:
            continue
        merged.append(z)
    out = []
    for z in merged:
        cy = cy_fn(z)
        aa, bb, cx = _need(hps, seg, z, cy0=cy, cx0=cx0)
        fa_, fb_ = floor(z) if floor else (0.0, 0.0)
        if aa == 0.0:
            cx = cx_default if cx0 is None else cx0
            A, B = fa_, fb_
        else:
            A, B = _enclose(max(aa, fa_ / fa), max(bb, fb_ * 0.8), fa, n)
            B = max(B, fb_)
        out.append(_st(z, A, B, cy=cy, cx=cx, n=n))
    return out


def profiles(L: dict, hps: list[dict], name: str) -> dict:
    H, h, k, a, s, e = L["H"], L["h"], L["k"], L["a"], L["s"], L["e"]
    segs = []
    waist_z = (h + PELVIS_TOP + L["chest_floor"]) / 2

    def ay(z):
        return L["ya"] + (s - z) * L["tan_t"]

    def afloor(z):
        if z < e - AX - HOUS - 4:
            return (L["fore_half"] * (0.5 if z < L["hand_end"] + 10 else 0.9), 14.0)
        return (L["fore_half"], 18.0)
    zs = _box_ends(hps, "arm_l") + [s + AX + HOUS + SHELL + 2, L["hand_end"] + 25, L["hand_end"] + 2]
    ar = _stations(hps, "arm_l", zs, cy_fn=ay, cx0=0.0, floor=afloor, fa=FA_WIDTH)
    band_bot = L["neck_base"] - 0.14 * H
    arm_outer = max(1000 * (st.get("cy", 0) + st["w"] / 2) for st in ar if band_bot / 1000 <= st["z"] <= L["neck_base"] / 1000 + 0.01)
    L["shoulder_outer_sections"] = 2 * arm_outer
    waist_half = 0.33 * 2 * arm_outer                                       # the waist is free (nothing in it but the waist-ring column): aim P4 ~0.6; the silhouette reads ~0.08 narrower than the floor

    def tfloor(z):
        if z <= h + PELVIS_TOP:
            return (L["yaw_half"] * 0.9, 30.0)
        if z < L["chest_floor"]:
            return (max(min(waist_half, L["Tf"] / 2 + SHELL), 30.0), 33.0)   # never wider than the chest (the arms sit beside it)
        return (L["Tf"] / 2 + SHELL, 30.0)
    zs = _box_ends(hps, "torso") + [h - 15, waist_z, L["neck_base"] - 2]
    zs = [z for z in zs if z <= L["neck_base"] + 2]
    t = _stations(hps, "torso", zs, floor=tfloor, fa=FA_WIDTH)
    t.append(_st(L["neck_base"] + 9, 26.0, 22.0, n=2.4))
    segs.append({"id": "torso", "role": "torso", "stations": t})
    # neck + head
    head_w = max(0.72 * L["head_h"], (S_H + BOSS) / 2 + HOUS + SHELL)
    aa, bb, cx = _need(hps, "head", L["chin"] + 25)
    A, B = _enclose(max(aa, head_w * 0.5), max(bb, head_w * 0.6), 1.05)
    hd = [_st(L["chin"] - 2, A * 0.85, B * 0.85, cx=cx, n=2.6)]
    for z in sorted(set(round(v, 1) for v in _box_ends(hps, "head"))):
        a2, b2, _ = _need(hps, "head", z, cx0=cx)
        A2, B2 = _enclose(max(a2, head_w * 0.5), max(b2, head_w * 0.6), 1.05)
        hd.append(_st(z, max(A, A2), max(B, B2), cx=cx, n=2.8))
    hd.append(_st(H - 1, A * 0.35, B * 0.35, cx=cx, n=2.2))
    hd = sorted({d["z"]: d for d in hd}.values(), key=lambda d: d["z"])
    hd = [d for i, d in enumerate(hd) if i == 0 or d["z"] - hd[i - 1]["z"] > 0.0015]
    segs.append({"id": "head", "role": "head", "stations": hd})
    nw = max(0.30 * 2 * A, 17.0)
    segs.append({"id": "neck", "role": "neck", "stations": [_st(L["neck_base"] - 4, nw, nw, n=2.0), _st(L["chin"] + 4, nw * 0.95, nw * 0.95, n=2.0)]})
    # legs (mirrored, cy = hip_y)
    beam = (FORK / 2 * 0.85 + SHELL, S_W / 2 + SHELL)
    zs = _box_ends(hps, "leg_l") + [(L["a"] + L["k"]) / 2 + 8, (L["k"] + L["h"]) / 2, L["h"] + 40]
    lg = _stations(hps, "leg_l", [z for z in zs if z > 10], cy_fn=lambda z: HIP_Y, cx0=0.0, floor=lambda z: beam, fa=FA_WIDTH)
    segs.append({"id": "leg", "role": "leg", "mirror": True, "k_m": 0.003, "stations": lg})
    gl = _stations(hps, "glute_l", _box_ends(hps, "glute_l"), cy_fn=lambda z: HIP_Y, fa=FA_WIDTH)
    segs.append({"id": "glute", "role": "torso", "mirror": True, "k_m": 0.004, "stations": gl})
    if L["legs"] == "6dof":
        he = _stations(hps, "heel_l", _box_ends(hps, "heel_l"), cy_fn=lambda z: HIP_Y, fa=FA_WIDTH)
        segs.append({"id": "heel", "role": "leg", "mirror": True, "k_m": 0.003, "stations": he})
    # foot (axis x)
    Lf, fh = CANON["foot"] * H, CANON["foot_h"]
    fw = max(0.09 * H, 50.0)
    x0 = -0.30 * Lf
    ft = []
    for f, wf, hf in ((0.0, 0.70, 0.8), (0.12, 0.95, 1.0), (0.55, 1.0, 1.0), (0.88, 0.85, 0.75), (1.0, 0.45, 0.45)):
        ft.append({"x": round((x0 + f * Lf) / 1000, 5), "w": round(fw * wf / 1000, 5), "d": round(fh * hf / 1000, 5), "n": 3.0, "cy": round(HIP_Y / 1000, 5), "cz": round(fh * hf / 2000, 5)})
    segs.append({"id": "foot", "role": "foot", "axis": "x", "mirror": True, "k_m": 0.002, "stations": ft})
    segs.append({"id": "arm", "role": "arm", "mirror": True, "k_m": 0.002, "stations": ar})
    joints = [{"id": "hip_l", "pos": [0, HIP_Y / 1000, round(h / 1000, 5)]}, {"id": "knee_l", "pos": [0, HIP_Y / 1000, round(k / 1000, 5)]},
              {"id": "ankle_l", "pos": [0, HIP_Y / 1000, round(a / 1000, 5)]}, {"id": "shoulder_l", "pos": [0, round(L["ya"] / 1000, 5), round(s / 1000, 5)]}]
    return {"schema": "design-profiles/0.1", "name": name, "kind": "design", "confidence": "approximate", "height_m": round(H / 1000, 4),
            "sources": ["variants/adam/design/r1_packaging.py (T-20261019-36f9): smallest shell family around catalog hard points; NOT a styled design"],
            "head_unit_m": round(L["head_h"] / 1000, 4), "segments": segs, "joints": joints, "hard_points": hps,
            "notes": f"arms={L['arms']} legs={L['legs']} cant={L['cant_deg']:.1f} deg; " + "; ".join(L["notes"])}


HARD = ["P1", "P2b", "P3", "P4", "P6", "P7", "P10a", "P10b", "S3a", "HP"]


def measure(prof_path: Path) -> dict:
    from openhumanoid.design import metrics
    from openhumanoid.design.meshio import load_subject
    subj = load_subject(prof_path, prof_path.parent.name)
    rep = metrics.write_report(subj, prof_path.parent / "metrics.json")
    crit = rep["evaluation"]["criteria"]
    return {"values": {k: (round(crit[k]["value"], 3) if isinstance(crit[k]["value"], (int, float)) else crit[k]["value"]) for k in crit},
            "verdicts": {k: crit[k]["verdict"] for k in crit}, "hard_failed": [k for k in HARD if crit.get(k, {}).get("verdict") == "FAIL"],
            "hp_failing": [x["id"] for x in rep["measured"].get("HP_hard_points", []) if not x.get("pass", True)]}


def draw_hardpoints(L: dict, prof: dict, out_png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, axs = plt.subplots(1, 2, figsize=(11, 8), dpi=110)
    H = L["H"]
    colors = {"leg_l": "#c0392b", "glute_l": "#c0392b", "heel_l": "#c0392b", "torso": "#2c3e50", "arm_l": "#2471a3", "head": "#7d3c98"}
    for ax, view in zip(axs, ("front", "side")):
        for hp in prof["hard_points"]:
            c, sz = [v * 1000 for v in hp["center"]], [v * 1000 for v in hp["size"]]
            u, w = (c[1], sz[1]) if view == "front" else (c[0], sz[0])
            col = colors.get(hp["segment"], "#555")
            ax.add_patch(Rectangle((u - w / 2, c[2] - sz[2] / 2), w, sz[2], fill=True, alpha=0.25, color=col, lw=0))
            ax.add_patch(Rectangle((u - w / 2, c[2] - sz[2] / 2), w, sz[2], fill=False, color=col, lw=1))
            if view == "front" and hp["segment"].endswith("_l"):
                ax.add_patch(Rectangle((-u - w / 2, c[2] - sz[2] / 2), w, sz[2], fill=True, alpha=0.12, color=col, lw=0))
        # section outlines from the profiles stations (half widths), both sides in front view
        for seg in prof["segments"]:
            if seg.get("axis", "z") != "z":
                continue
            zs = [st["z"] * 1000 for st in seg["stations"]]
            for sign in ((1, -1) if (view == "front" and seg.get("mirror")) else (1,)):
                if view == "front":
                    cy = [sign * st.get("cy", 0) * 1000 for st in seg["stations"]]
                    hw = [st["w"] * 500 for st in seg["stations"]]
                else:
                    cy = [st.get("cx", 0) * 1000 for st in seg["stations"]]
                    hw = [st["d"] * 500 for st in seg["stations"]]
                ax.plot([c - w for c, w in zip(cy, hw)], zs, color="#888", lw=0.8)
                ax.plot([c + w for c, w in zip(cy, hw)], zs, color="#888", lw=0.8)
                if not (view == "front" and seg.get("mirror")) and view == "front":
                    pass
        for zf, lab in ((L["s"], "shoulder axis"), (L["h"], "hip axis"), (L["k"], "knee"), (L["neck_base"], "neck base"), (L["neck_base"] - 0.14 * H, "P3 band bottom")):
            ax.axhline(zf, color="#bbb", lw=0.6, ls="--")
            ax.text(ax.get_xlim()[0] if False else (-170 if view == "front" else -150), zf + 2, lab, fontsize=7, color="#777")
        if view == "front":
            lim = 0.145 * H
            ax.axvline(lim, color="#e67e22", lw=1)
            ax.axvline(-lim, color="#e67e22", lw=1)
            ax.text(lim + 2, H * 0.95, "P3 0.29 H", fontsize=7, color="#e67e22")
        ax.set_aspect("equal")
        ax.set_xlim(-180, 180) if view == "front" else ax.set_xlim(-160, 160)
        ax.set_ylim(0, H + 10)
        ax.set_title(f"{view}: hard points (boxes incl. housing) and shell sections", fontsize=9)
        ax.set_xlabel("y (mm)" if view == "front" else "x (mm, forward +)")
        ax.set_ylabel("z (mm)")
    fig.suptitle(f"R1 packaging {prof['name']}: H {H / 1000:.3f} m, shoulders {L['arms']}, legs {L['legs']}, arm cant {L['cant_deg']:.1f} deg, "
                 f"shoulder outer {L['shoulder_outer_est']:.0f} mm = {L['P3_est']:.3f} H (est.)", fontsize=10)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png)
    plt.close(fig)


def case_name(H, arms, legs):
    return f"{arms}-{legs}-{int(round(H * 1000))}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heights", nargs="+", type=float, default=[0.50, 0.55, 0.575, 0.60, 0.625, 0.65, 0.70])
    ap.add_argument("--arms", nargs="+", default=["chest", "arm"])
    ap.add_argument("--legs", nargs="+", default=["6dof", "5dof"])
    ap.add_argument("--render", nargs="*", default=[], help="case names to render with the studio rig and draw hard points for")
    ap.add_argument("--no-metrics", action="store_true")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for arms in a.arms:
        for legs in a.legs:
            for H in a.heights:
                L = layout(H, arms, legs)
                name = case_name(H, arms, legs)
                hps = hard_points(L)
                prof = profiles(L, hps, name)
                d = OUT / name
                d.mkdir(parents=True, exist_ok=True)
                pp = d / "profiles.yaml"
                pp.write_text("# written by variants/adam/design/r1_packaging.py (T-20261019-36f9); re-run, do not edit\n" + yaml.safe_dump(prof, sort_keys=False, width=200), encoding="utf-8")
                row = {"case": name, "H_m": H, "arms": arms, "legs": legs, **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in L.items() if k in
                       ("Tf", "ya", "cant_deg", "P3_est", "shoulder_outer_est", "shoulder_outer_sections", "torso_fits", "notes", "h", "k", "s", "a", "head_h")}}
                if not a.no_metrics:
                    row["metrics"] = measure(pp)
                rows.append(row)
                m = row.get("metrics", {})
                print(f"{name}: cant {L['cant_deg']:.1f} deg, shoulder {L['shoulder_outer_est']:.0f} mm = {L['P3_est']:.3f} H (est), "
                      f"P3 {m.get('values', {}).get('P3')}, hard fails {m.get('hard_failed')}", flush=True)
                if name in a.render:
                    draw_hardpoints(L, prof, DOCS / f"hardpoints_{name}.png")
                    from openhumanoid.design.meshio import load_subject
                    from openhumanoid.design.studio import render_studio
                    refs = [str(REPO / "openhumanoid/design/references/optimus_like.yaml"), str(REPO / "openhumanoid/design/references/human_canon.yaml")]
                    render_studio(load_subject(pp, f"R1 {name}"), DOCS / f"studio_{name}", refs=refs)
    # minimum height per layout: lowest H from which every taller tested H passes all numeric hard gates
    summary = {}
    for arms in a.arms:
        for legs in a.legs:
            rs = sorted([r for r in rows if r["arms"] == arms and r["legs"] == legs], key=lambda r: r["H_m"])
            ok = [r["H_m"] for r in rs if r.get("metrics") and not r["metrics"]["hard_failed"]]
            ok_but_foot = [r["H_m"] for r in rs if r.get("metrics") and not [f for f in r["metrics"]["hard_failed"] if f not in ("P10a", "P10b")]]
            p3 = [r["H_m"] for r in rs if r.get("metrics") and r["metrics"]["values"].get("P3") is not None and r["metrics"]["values"]["P3"] <= 0.29]
            summary[f"{arms}-{legs}"] = {"all_hard_pass_heights": ok, "min_all_hard_pass": min(ok) if ok else None,
                                         "pass_except_foot_gates_heights": ok_but_foot, "P3_pass_heights": p3,
                                         "P3_est_by_height": {f"{r['H_m']:.3f}": r["P3_est"] for r in rs}}
    (OUT / "summary.json").write_text(json.dumps({"rows": rows, "min_height": summary}, indent=1, default=str), encoding="utf-8")
    md = ["<!-- written by variants/adam/design/r1_packaging.py; re-run, do not edit -->", "# R1 packaging study: minimum not-a-toy height per layout", "",
          "| case | arm cant deg | shoulder outer mm (stack-up / sections) | P3 est | P3 measured | P4 | P1 | P6 | P7 | P10a | P10b | HP | hard gates failed |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        v = r.get("metrics", {}).get("values", {})
        md.append(f"| {r['case']} | {r['cant_deg']} | {r['shoulder_outer_est']} / {r.get('shoulder_outer_sections')} | {r['P3_est']} | {v.get('P3')} | {v.get('P4')} | {v.get('P1')} | {v.get('P6')} | {v.get('P7')} | "
                  f"{v.get('P10a')} | {v.get('P10b')} | {v.get('HP')} | {', '.join(r.get('metrics', {}).get('hard_failed', [])) or '-'} |")
    md += ["", "| layout | heights passing every numeric hard gate | passing all but the foot gates (P10a/b) | P3 <= 0.29 measured |", "|---|---|---|---|"]
    for k, s_ in summary.items():
        md.append(f"| {k} | {s_['all_hard_pass_heights']} | {s_['pass_except_foot_gates_heights']} | {s_['P3_pass_heights']} |")
    (OUT / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
