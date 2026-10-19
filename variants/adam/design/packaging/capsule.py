"""Packaging-for-look study (T-20261019-c1aa): the R2a direction-B ("Atlas-capsule", B4) styling rules made PARAMETRIC, so one
station family can be wrapped around any hard-point layout from layout.py.

B4 (variants/adam/design/silhouette/directions.py) writes its stations at fixed heights for the R1 0.55 m layout. Here every height is
written relative to the landmark or hard-point box it sits on in B4 (chin, chest housing bottom, pack bottom, yaw-servo top, hip-roll
servo, leg-servo box ends, arm-servo zones), and every hand-set width next to a fitted one keeps its B4 ratio or offset. With the
default levers the result is "B4-generic": not byte-identical to B4 (the leg covers use one generic rule instead of B4's hand-set
thigh/shank widths) but the same family; its metrics are reported beside B4's so the lever deltas are read inside one family.

Display cant: the smallest cant at which the arm shells keep the same front-view clearance to the body that B4 has at 21 deg
(`gap_rule`), so a slimmer arm or a narrower body earns a smaller cant by the same visual rule R2a used. Never below the R1 hip-fork
clearance rule (13.8 deg) unless the boxes themselves allow it (the clearance is measured on the shells, which enclose the boxes).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "silhouette"))
sys.path.insert(0, str(REPO))

import layout as LY  # noqa: E402
from build import _fit_dim  # noqa: E402
from openhumanoid.design.massing import hard_point_margins  # noqa: E402
from openhumanoid.design.profiles import expand, validate  # noqa: E402

N, K = 2.5, 9.0                 # B4 section family and blend
KL = max(3.0, K * 0.5)
ARM_N, ARM_WIN = 2.8, 3.2
REFINE: dict = {}              # styling refinements from critic rounds (set by build(refine=...)); empty = the plain B4 rules


def S(z, w, d, n=N, cx=0.0, cy=0.0):
    return {"z": z, "w": w, "d": d, "n": n, "cx": cx, "cy": cy}


def F(x, w, d, n=N, cy=0.0, cz=0.0):
    return {"x": x, "w": w, "d": d, "n": n, "cy": cy, "cz": cz}


class Ctx:
    def __init__(self, lay: dict):
        self.L = lay["L"]
        self.lv = lay["levers"]
        self.hps = lay["hard_points"]
        self.boxes = LY_boxes(self.hps)

    def seg(self, s):
        return [b for b in self.boxes if b["segment"] == s]

    def fw(self, seg, z, d, n=N, cx=0.0, cy=0.0, extra=0.0, win=8.0, floor=0.0):
        """Fitted width (smallest w enclosing seg's boxes at z with their margin) + extra, never below floor."""
        r = _fit_dim(self.seg(seg), z, cx, cy, n, d=d, win=win)
        if r is None:
            if floor:
                return floor
            raise ValueError(f"no hard point of {seg} spans z={z:.1f}")
        return max(r + extra, floor)

    def ay(self, z):
        return self.L["ya"] + (self.L["s"] - z) * self.L["tan_t"]

    def zr(self, id_):
        b = next(b for b in self.boxes if b["id"] == id_)
        return b["z"]

    def xr(self, id_):
        b = next(b for b in self.boxes if b["id"] == id_)
        return b["x"]


def LY_boxes(hps):
    out = []
    for hp in hps:
        c = [v * 1000 for v in hp["center"]]
        s = [v * 1000 for v in hp["size"]]
        out.append({"id": hp["id"], "segment": hp["segment"], "m": hp["margin_m"] * 1000,
                    "x": (c[0] - s[0] / 2, c[0] + s[0] / 2), "y": (c[1] - s[1] / 2, c[1] + s[1] / 2), "z": (c[2] - s[2] / 2, c[2] + s[2] / 2)})
    return out


def ends(st, z0, z1, frac):
    """B4 `_ends`: roll a shell in beyond each end at `frac` of the end station's size."""
    a, b = dict(st[0]), dict(st[-1])
    for q, z in ((a, z0), (b, z1)):
        q["z"] = z
        q["w"] *= frac
        q["d"] *= frac
    return [a, *st, b]


def dense(z0, z1, step=10.0):
    k = max(1, round((z1 - z0) / step))
    return [z0 + (z1 - z0) * i / k for i in range(k + 1)]


# --------------------------------------------------------------------------------------------------------------------- parts
def head_parts(c: Ctx, style: dict) -> list[dict]:
    L = c.L
    ch, H = L["chin"], L["H"]
    w, d, n, cx = style["head_w"], style["head_d"], style["head_n"], 5.0
    head = [S(ch - 6, 0.40 * w, 0.40 * d, 2.2, 3.0), S(ch - 3, 0.76 * w, 0.70 * d, 2.5, 3.0), S(ch - 0.1, 0.92 * w, 0.86 * d, 2.8, 3.5),
            S(ch + 13.5, w, d, n, cx), S(H - 20, w, d, n, cx), S(H - 11, 0.93 * w, 0.93 * d, n, cx), S(H - 4.5, 0.74 * w, 0.76 * d, 2.4, cx),
            S(H - 0.4, 0.32 * w, 0.36 * d, 2.2, cx)]
    if REFINE.get("head_ovoid"):     # critic r1 (G1/G4): an ovoid head, narrower chin and crown, rounder sections
        head = [S(ch - 6, 0.36 * w, 0.38 * d, 2.1, 3.0), S(ch - 3, 0.66 * w, 0.66 * d, 2.2, 3.0), S(ch - 0.1, 0.84 * w, 0.84 * d, 2.3, 3.5),
                S(ch + 13.5, 0.98 * w, d, 2.05, cx), S(H - 22, w, d, 2.05, cx), S(H - 11, 0.86 * w, 0.90 * d, 2.05, cx),
                S(H - 4.5, 0.66 * w, 0.72 * d, 2.1, cx), S(H - 0.4, 0.28 * w, 0.32 * d, 2.0, cx)]
        n = 2.05
    vz0, vz1 = ch + 8.5, H - 19
    zc, r, sh = (vz0 + vz1) / 2, (vz1 - vz0) / 2, 2.5
    vis = [S(zc + r * t, w, d, n, cx + 0.3 + sh * (1 - t * t) ** 0.5) for t in (-0.99, -0.85, -0.6, -0.3, 0.0, 0.3, 0.6, 0.85, 0.99)]
    out = [{"id": "head", "role": "shell", "k": 2.0, "stations": head}, {"id": "visor", "role": "dark", "k": 1.0, "stations": vis}]
    nb = L["chest_top"] - 1.95
    if c.seg("neck"):            # neck-yaw servo standing in the neck: fit the neck round it
        xr = c.xr("neck_yaw_servo")
        ncx, nd = (xr[0] + xr[1]) / 2, style.get("neck_d", 38.0)
        nb = min(nb, c.zr("neck_yaw_servo")[0] - 3.4)     # the neck root runs down into the chest far enough to hold the servo
        w0 = c.fw("neck", nb + 2, nd, 2.6, ncx, extra=1.0, floor=style["neck_w"][0])
        w1 = c.fw("neck", ch - 2, nd, 2.6, ncx, extra=1.0, floor=style["neck_w"][1])
        neck = [S(nb, w0, nd, 2.6, ncx), S(max(ch - 0.5, c.zr("neck_yaw_servo")[1] + 4.0), w1, nd, 2.6, ncx)]   # top tucked into the head
    else:
        neck = [S(nb, style["neck_w"][0], style["neck_w"][0], 2.0, 2.0), S(ch - 0.5, style["neck_w"][1], style["neck_w"][1], 2.0, 3.0)]
    out.append({"id": "neck", "role": "dark", "k": 3.0, "stations": neck})
    return out


def torso_parts(c: Ctx) -> list[dict]:
    L, lv = c.L, c.lv
    s, h, top = L["s"], L["h"], L["chest_top"]
    zb = L["chest_floor"]
    # chest x extent from its content: B4 = [-38, 58] around shoulder servos (x +-15) and the neck-yaw slot (to 45)
    ch_boxes = c.seg("chest")
    x_front = max(b["x"][1] for b in ch_boxes)
    x_back = min(b["x"][0] for b in ch_boxes if b["id"] == "shoulder_pitch_servos")
    x0, x1 = x_back - 23.0, x_front + 13.0
    cx, dc = (x0 + x1) / 2, x1 - x0
    cn = REFINE.get("chest_n", N)
    Wc = c.fw("chest", zb - 3.05 + 6, dc, cn, cx, extra=1.0)
    chest = [S(zb - 9.45, 0.793 * Wc, dc - 26, cn, cx - 4), S(zb - 5.45, 0.922 * Wc, dc - 12, cn, cx - 1),
             S(zb - 3.05, Wc, dc, cn, cx), S(s - 9.3, c.fw("chest", s - 9.3, dc + 2, cn, cx, extra=1.0), dc + 2, cn, cx),
             S(top + 3.15, Wc, dc, cn, cx), S(top + 5.35, 0.772 * Wc, 0.75 * dc, cn - 0.2, cx - 4), S(top + 7.85, 38, 40, 2.5, cx - 7)]
    if REFINE.get("chest_blend"):    # critic r1 (G2): no bib ledge; the chest tapers down into the waist ring
        chest = [S(zb - 20.0, 0.60 * Wc, dc - 42, cn, cx - 6), S(zb - 12.0, 0.80 * Wc, dc - 24, cn, cx - 4)] + chest[2:]
    if REFINE.get("chest_blend_strong"):   # critic r2 (G2): a long, soft taper from the chest into the waist ring, rounder at the bottom
        chest = [S(zb - 30.0, 0.50 * Wc, dc - 50, 2.2, cx - 7), S(zb - 21.0, 0.68 * Wc, dc - 36, 2.2, cx - 6),
                 S(zb - 12.0, 0.86 * Wc, dc - 18, cn, cx - 3)] + [q for q in chest if q["z"] >= zb - 3.1]
    if REFINE.get("low_roll"):       # critic r1 (P2a): the chest top rolls over lower and faster, so more neck shows
        chest = chest[:-2] + [S(top + 4.0, 0.70 * Wc, 0.70 * dc, cn - 0.2, cx - 5), S(top + 5.6, 34, 36, 2.4, cx - 7)]
    segs = [{"id": "chest", "role": "shell", "k": K + 4.0, "stations": chest}]
    bk = c.seg("back")
    if bk:
        b = bk[0]
        p0, p1 = b["z"]
        pcx = (b["x"][0] + b["x"][1]) / 2 + 8.15
        pd = (b["x"][1] - b["x"][0]) + 41.7
        bn = REFINE.get("back_n", N)
        Wb = c.fw("back", (p0 + p1) / 2, pd, bn, pcx, extra=1.0)
        back = [S(p0 - 18.65, 0.70 * Wb, 50 * pd / 76, bn, pcx + 10), S(p0 - 10.65, 0.81 * Wb, 66 * pd / 76, bn, pcx + 4),
                S(p0 - 3.05, Wb, pd, bn, pcx), S(p1 + 3.15, Wb, pd, bn, pcx), S(p1 + 6.55, 0.64 * Wb, 58 * pd / 76, bn - 0.2, pcx + 5),
                S(p1 + 9.05, 0.37 * Wb, 36 * pd / 76, 2.6, pcx + 14)]
        if p1 + 9.05 > top + 9:          # never above the chest roll-over (a pack lower in the back simply ends lower)
            back = [st for st in back if st["z"] <= top + 9.1]
        segs.append({"id": "back", "role": "shell", "k": K + 4.0, "stations": back})
    # pelvis capsule
    pn = REFINE.get("pelvis_n", N + 1.0)
    yz0, yz1 = c.zr("hip_yaw_servo_l")
    pz0 = c.zr("pi5_adapter_buck_imu_bay")[0]
    Wp = c.fw("pelvis", (yz0 + yz1) / 2, 100, pn, 3.0, extra=0.5)
    pel = [S(h + 15, 0.663 * Wp, 62, N, -2), S(h + 23, 0.829 * Wp, 80, N, -1),
           S(pz0 - 3.05, c.fw("pelvis", pz0 - 3.05, 94, pn, -1, extra=0.5), 94, pn, -1),
           S(yz0 - 3.05, Wp, 100, pn, 3), S(yz1 + 3.05, Wp, 100, pn, 3), S(yz1 + 5.85, 0.795 * Wp, 80, N, 3), S(yz1 + 8.85, 0.646 * Wp, 62, N, 3)]
    segs.append({"id": "pelvis", "role": "shell", "k": K + 4.0, "stations": pel})
    # graphite waist ring (B4: the waist-yaw gap). Without waist yaw it stays as the styling band between the two capsules.
    segs.append({"id": "waist", "role": "dark", "k": 3.0, "stations": [S(yz1 - 2.65, 0.729 * Wp, 70, 2.6, 2), S(zb - 1.45, 0.712 * Wp, 70, 2.6, 3)]})
    # glutes over the hip-roll servos
    r0, r1 = c.zr("hip_roll_servo_l")
    cy = L["hip_y"]
    gw = c.fw("glute_l", (r0 + r1) / 2, 62, 2.4, -61, cy, extra=1.5)
    segs.append({"id": "glute", "role": "shell", "mirror": True, "k": 10.0, "stations": [
        S(h - 37, 26, 26, 2.3, -48, cy), S(h - 26, 46, 50, 2.4, -58, cy), S(r0 - 3.05, gw, 62, 2.4, -61, cy), S(r1 + 3.15, gw, 62, 2.4, -61, cy),
        S(h + 57, 46, 48, 2.4, -52, cy), S(h + 77, 30, 30, 2.3, -40, cy)]})
    return segs


def leg_parts(c: Ctx) -> list[dict]:
    """Dark leg core fitted at every leg box end (B4 rule), white thigh/shank covers 3 mm proud of the boxes with a hip flare, a calf
    station between the calf boxes, rolled ends. The same rule for every layout (fork servos, fore-aft servos, slim joints)."""
    L, lv = c.L, c.lv
    cy, a, k, h = L["hip_y"], L["a"], L["k"], L["h"]
    n = 3.0
    bx = sorted(c.seg("leg_core_l"), key=lambda b: b["z"][0])

    def active(z, m0=3.15, m1=3.05):
        return [b for b in bx if b["z"][0] - m0 - 0.01 <= z <= b["z"][1] + m1 + 0.01]

    def xsec(z, pad=0.0):
        """cx and depth of the section that encloses every box spanning z (B4: depth 54 for the 30 mm-deep fork servos)."""
        act = active(z)
        x0, x1 = min(b["x"][0] for b in act), max(b["x"][1] for b in act)
        if (x1 - x0) > 40.0:      # a servo laid fore-aft (relocated): squarer, deeper section so its corners do not widen the leg past the mid-plane
            return (x0 + x1) / 2, ((x1 - x0) + 6.7) * 1.4 + pad, 3.6
        return (x0 + x1) / 2, max(54.0, ((x1 - x0) + 6.7) * 1.25) + pad, n
    zs = sorted({round(z, 2) for b in bx for z in (b["z"][0] - 3.15, b["z"][1] + 3.05)})
    core = [S(a - 26, 50, 42, n, 0, cy)]
    prev = None
    for z in zs:
        bcx, bd, nn = xsec(z)
        w = max(c.fw("leg_core_l", zz, bd, nn, bcx, cy, extra=0.2) for zz in (z, min(max(z, active(z)[0]["z"][0]), active(z)[0]["z"][1])))
        if prev is not None and z - prev["z"] > 6 and not [b for b in bx if prev["z"] < b["z"][0] and b["z"][1] < z] \
                and not active((prev["z"] + z) / 2):
            core.append(S((prev["z"] + z) / 2, min(prev["w"], w) - 7.4, min(prev["d"], bd) - 8, n, (prev["cx"] + bcx) / 2, cy))
        q = S(z, w, bd, nn, bcx, cy)
        core.append(q)
        prev = q
    core.append(S(prev["z"] + 8, 48, 40, n, 0, cy))
    core.sort(key=lambda q: q["z"])
    segs = [{"id": "leg_core", "role": "dark", "mirror": True, "k": 3.0, "stations": core}]

    def inner(w):
        return max(cy, 2.0 + w / 2)

    def cover(z_lo, z_hi, flare_z=None):
        sts = []
        for b in bx:
            if b["z"][1] < z_lo or b["z"][0] > z_hi:
                continue
            for z in (max(b["z"][0], z_lo + 4), min(b["z"][1], z_hi - 4)):
                bcx, bd, nn = xsec(z, 6.0)
                w = c.fw("leg_core_l", z, bd, nn, bcx, cy, extra=3.0, win=3.2)
                while w > 100.0 and bd < 200.0:      # the fit has no solution at this depth (two boxes of different depth meet): deepen
                    bd *= 1.1
                    w = c.fw("leg_core_l", z, bd, nn, bcx, cy, extra=3.0, win=3.2)
                sts.append(S(z, w, bd, nn, bcx, inner(w)))
        sts.sort(key=lambda q: q["z"])
        out = [sts[0]]
        for q in sts[1:]:                 # a station between two boxes: the mean of its neighbours (no waist between them)
            if q["z"] - out[-1]["z"] > 14:
                m = out[-1]
                wm = (m["w"] + q["w"]) / 2
                out.append(S((m["z"] + q["z"]) / 2, wm, (m["d"] + q["d"]) / 2, n, (m["cx"] + q["cx"]) / 2, inner(wm)))
            out.append(q)
        if flare_z is not None:          # the thigh is widest at the hip (design language rule 4)
            f = max(out, key=lambda q: q["z"])
            out.append(S(flare_z, f["w"] + 5.6, f["d"] - 2, n, f["cx"], inner(f["w"] + 5.6)))
        out = sorted(out, key=lambda q: q["z"])
        if REFINE.get("leg_smooth"):     # critic r1 (G2, S3b, P8b): one monotonic taper; only WIDENS stations, so every box stays enclosed
            top_i = max(range(len(out)), key=lambda i: (out[i]["w"], -out[i]["z"] if flare_z is None else out[i]["z"]))
            for i in range(1, top_i + 1):          # from the narrow lower end up to the widest station: never narrower going up
                if out[i]["w"] < out[i - 1]["w"]:
                    out[i] = S(out[i]["z"], out[i - 1]["w"], max(out[i]["d"], out[i - 1]["d"]), out[i]["n"], out[i]["cx"], inner(out[i - 1]["w"]))
            for i in range(len(out) - 2, top_i, -1):   # above the widest station (calf -> knee): never narrower going down
                if out[i]["w"] < out[i + 1]["w"]:
                    out[i] = S(out[i]["z"], out[i + 1]["w"], max(out[i]["d"], out[i + 1]["d"]), out[i]["n"], out[i]["cx"], inner(out[i + 1]["w"]))
        return out
    th = cover(k + 6, h + 30, flare_z=h + 3)
    sk = cover(a - 10, k - 6)
    segs += [{"id": "thigh", "role": "shell", "mirror": True, "k": KL, "stations": ends(th, th[0]["z"] - 10, h + 30, 0.86)},
             {"id": "shank", "role": "shell", "mirror": True, "k": KL, "stations": ends(sk, sk[0]["z"] - (16 if REFINE.get("soft_cuffs") else 10), sk[-1]["z"] + 4, 0.70 if REFINE.get("soft_cuffs") else 0.88)}]
    # heel (6-DOF: the ankle-roll servo behind the ankle)
    if lv.legs == "6dof":
        segs.append({"id": "heel", "role": "dark", "mirror": True, "k": 6.0, "stations": [
            S(3.0, 46, 50, 2.8, -44, cy), S(20.3, c.fw("heel_l", 48, 52, 2.8, -44, cy, extra=0.2), 52, 2.8, -44, cy),
            S(76.8, c.fw("heel_l", 48, 52, 2.8, -44, cy, extra=0.2), 52, 2.8, -44, cy), S(86, 28, 34, 2.6, -34, cy)]})
        hw = c.fw("heel_l", 48, 52, 2.8, -44, cy, extra=0.2)
        segs.append({"id": "heel_cover", "role": "shell", "mirror": True, "k": 4.0, "stations": [
            S(16, hw - 2, 58, 3.0, -44, cy), S(22, hw + 3, 62, 3.0, -44, cy), S(72, hw + 3, 62, 3.0, -44, cy), S(80, hw - 4, 56, 3.0, -42, cy)]})
    # foot: toe = the engine's validated reach (0.65 x 0.17 H in front of the ankle); heel = the roll servo (6-DOF) or 0.35 x 0.17 H
    Lf = 0.17 * L["H"]
    toe = 0.65 * Lf
    heel = -68.0 if lv.legs == "6dof" else -0.35 * Lf
    white_from = -40.0 if lv.legs == "6dof" else heel + 4.0
    fw_, fh = 60.0, 22.0
    x0, x1 = white_from, toe
    Lw = x1 - x0
    segs.append({"id": "foot", "role": "shell", "axis": "x", "mirror": True, "k": 3.0, "stations": [
        F(x0, 0.86 * fw_, 0.90 * fh, 3.0, cy, 0.52 * fh), F(x0 + 0.10 * Lw, 0.95 * fw_, fh, 3.0, cy, 0.55 * fh), F(x0 + 0.40 * Lw, fw_, fh, 3.0, cy, 0.55 * fh),
        F(x0 + 0.78 * Lw, 0.92 * fw_, 0.66 * fh, 3.0, cy, 0.40 * fh), F(x1, 0.50 * fw_, 0.30 * fh, 2.6, cy, 0.20 * fh)]})
    segs.append({"id": "sole", "role": "dark", "axis": "x", "mirror": True, "k": 1.0, "stations": [
        F(heel, 0.70 * fw_, 5.0, 3.0, cy, 3.0), F(heel + 8, 0.86 * fw_ + 1.5, 6.0, 3.0, cy, 3.0), F(x0 + 0.78 * Lw, 0.92 * fw_ + 1.5, 6.0, 3.0, cy, 3.0),
        F(x1 - 1.0, 0.52 * fw_ + 1.5, 4.0, 2.6, cy, 2.0)]})
    return segs


def _zones(c: Ctx):
    out = []
    for key in (("gripper", "wrist"), ("elbow",), ("shoulder_roll",)):   # the forearm zone spans the wrist servo too (lever 9b)
        zs = [z for b in c.seg("arm_core_l") if b["id"].startswith(key) for z in b["z"]]
        out.append((min(zs) - 3.1, max(zs) + 3.1))
    return out


def arm_parts(c: Ctx) -> list[dict]:
    L = c.L
    (g0, g1), (e0, e1), (c0, c1) = _zones(c)
    # B4 core depths minus the depth the smaller servo saves (B4: roll/gripper boxes 40.3 deep, elbow 30 deep)
    def xext(prefix):
        bb = [b for b in c.seg("arm_core_l") if b["id"].startswith(prefix)]
        return max(b["x"][1] for b in bb) - min(b["x"][0] for b in bb)
    cap_d, elbow_d, fore_d = 60 - (40.3 - xext("shoulder_roll")), 56 - (30.0 - xext("elbow")), 60 - (40.3 - xext("gripper"))
    sc = min(1.0, (xext("gripper") + 20) / 60.3)          # hand-end sizes follow the gripper servo
    he = L["hand_end"]

    def adepth(z, d):
        """Never thinner than B4's depth offset over every arm box spanning z (a gripper slice next to the elbow keeps its depth)."""
        need = [(b["x"][1] - b["x"][0]) + (26.0 if b["id"].startswith(("elbow", "wrist")) else 19.7)
                for b in c.seg("arm_core_l") if b["z"][0] - 3.1 - ARM_WIN <= z <= b["z"][1] + 3.1 + ARM_WIN]
        return max([d] + need)

    def cw(z, d, extra=0.2):
        return c.fw("arm_core_l", z, d, ARM_N, 0.0, c.ay(z), extra=extra, win=ARM_WIN)
    core = [S(he - 7.3, 20 * sc, 24 * sc, 2.6, 0, c.ay(he - 7.3)), S(he + 2.7, 34 * sc, 36 * sc, 2.8, 0, c.ay(he + 2.7)),
            S(g0 - 12, 42 * sc, 46 * sc, 3.0, 0, c.ay(g0 - 12))]
    for z in dense(g0, e1):
        d = adepth(z, fore_d if z < e0 + 6 else elbow_d)
        core.append(S(z, cw(z, d), d, ARM_N, 0, c.ay(z)))
    zm = (e1 + c0) / 2
    if c0 - e1 > 4:
        core.append(S(zm, 42 * sc, 42 * sc, ARM_N, 0, c.ay(zm)))
    for z in dense(c0, c1):
        core.append(S(z, cw(z, cap_d), cap_d, ARM_N, 0, c.ay(z)))
    core.append(S(c1 + 6, 34 * sc, 36 * sc, 2.6, 0, c.ay(c1 + 6)))
    core.sort(key=lambda q: q["z"])
    # merge stations closer than 1.5 mm (the schema wants increasing z)
    m = [core[0]]
    for q in core[1:]:
        if q["z"] - m[-1]["z"] >= 1.5:
            m.append(q)
    segs = [{"id": "arm_core", "role": "dark", "mirror": True, "k": 3.0, "stations": m}]

    def sh(zs, d, ex):
        return [S(z, cw(z, adepth(z, d) + 6, ex), adepth(z, d) + 6, ARM_N, 0, c.ay(z)) for z in zs]

    def rolled(st, z0, z1, frac):
        out = ends(st, z0, z1, frac)
        for q in out:
            q["cy"] = c.ay(q["z"])
        return out
    cap = sh(dense(c0 + 4, c1 - 3, 12), cap_d, 6.0)
    upper = sh(dense(e0 + 31, e1 - 2, 10), elbow_d, 5.0) if (e1 - 2) - (e0 + 31) > 4 else sh([e1 - 6], elbow_d, 5.0)
    fore = sh(dense(g0 + 4, g1 - 2, 12), fore_d, 5.0)
    joints_only = REFINE.get("arm_bands") == "joints"   # critic r1 (G2/G3): dark bands only at the real joints (shoulder, elbow, wrist)
    gap = 5.0 if joints_only else 12.0
    ua0, fa1 = e0 + 20 + gap / 2, e0 + 20 - gap / 2
    ua1 = (c0 + 3.0) if joints_only else (e1 + 5)       # the upper-arm cover runs up under the shoulder cap (one link: no band)
    if joints_only and c0 - e1 > 12:
        # between the elbow servo and the shoulder cap the arm holds no servo: a SLIM white sleeve 2 mm proud of the dark core there
        def core_at(z, key):
            zs = [q["z"] for q in m]
            i = max(0, min(len(m) - 2, int(np.searchsorted(zs, z)) - 1))
            t = (z - zs[i]) / max(zs[i + 1] - zs[i], 1e-9)
            return m[i][key] + t * (m[i + 1][key] - m[i][key])
        upper = upper + [S(z, core_at(z, "w") + 4.0, core_at(z, "d") + 4.0, ARM_N, 0, c.ay(z)) for z in (e1 + 8.0, (e1 + c0) / 2, c0 - 2.0)]
        upper.sort(key=lambda q: q["z"])
    segs += [{"id": "deltoid", "role": "shell", "mirror": True, "k": KL, "stations": rolled(cap, c0 - 1, c1 + 4, 0.70)},
             {"id": "upper_arm", "role": "shell", "mirror": True, "k": KL, "stations": rolled(upper, min(ua0, upper[0]["z"] - 2), ua1, 0.80 if not joints_only else 1.0)},
             {"id": "forearm", "role": "shell", "mirror": True, "k": KL, "stations": rolled(fore, g0 - 6, max(fa1, fore[-1]["z"] + 2), 0.80)}]
    return segs


SEG_ORDER = ("head", "visor", "neck", "chest", "back", "pelvis", "waist", "glute", "leg_core", "thigh", "shank", "heel", "heel_cover",
             "foot", "sole", "arm_core", "deltoid", "upper_arm", "forearm")
# hard-point segment -> the profile segment that must enclose it
HP_SEG = {"head": "head", "neck": "neck", "chest": "chest", "back": "back", "pelvis": "pelvis", "glute_l": "glute_l",
          "leg_core_l": "leg_core_l", "heel_l": "heel_l", "arm_core_l": "arm_core_l"}


def style_for(lv) -> dict:
    """Head and neck styling: B4 (62 x 68 pill, 36/32 neck) unless the small neck servo frees the head (then a slimmer pill)."""
    if lv.neck != "sts3215-12v":
        return dict(head_w=54.0, head_d=62.0, head_n=2.2, neck_w=(30.0, 26.0), neck_d=42.0)
    return dict(head_w=62.0, head_d=68.0, head_n=2.2, neck_w=(36.0, 32.0))


def build(lv, cant: float, style: dict | None = None, name: str | None = None, refine: dict | None = None) -> dict:
    REFINE.clear()
    REFINE.update(refine or {})
    lay = LY.layout(lv, cant)
    c = Ctx(lay)
    st = style or style_for(lv)
    segs = head_parts(c, st) + torso_parts(c) + leg_parts(c) + arm_parts(c)
    out = []
    for sg in segs:
        o = {"id": sg["id"], "role": sg["role"]}
        if sg.get("axis"):
            o["axis"] = sg["axis"]
        if sg.get("mirror"):
            o["mirror"] = True
        if sg.get("k") is not None:
            o["k_m"] = round(sg["k"] / 1000, 5)
        ax = sg.get("axis", "z")
        sts = sorted(sg["stations"], key=lambda q: q[ax])
        o["stations"] = []
        for q in sts:
            r = {ax: round(q[ax] / 1000, 5), "w": round(q["w"] / 1000, 5), "d": round(q["d"] / 1000, 5), "n": round(q["n"], 3)}
            for kk in ("cx", "cy", "cz"):
                if q.get(kk):
                    r[kk] = round(q[kk] / 1000, 5)
            if o["stations"] and r[ax] - o["stations"][-1][ax] < 0.0008:
                continue
            o["stations"].append(r)
        out.append(o)
    L = lay["L"]
    joints = [{"id": "hip_l", "pos": [0.0, 0.035, round(L["h"] / 1000, 5)]}, {"id": "knee_l", "pos": [0.0, 0.035, round(L["k"] / 1000, 5)]},
              {"id": "ankle_l", "pos": [0.0, 0.035, round(L["a"] / 1000, 5)]}, {"id": "shoulder_l", "pos": [0.0, round(L["ya"] / 1000, 5), round(L["s"] / 1000, 5)]},
              {"id": "elbow_l", "pos": [0.0, round(c.ay(L["e"]) / 1000, 5), round(L["e"] / 1000, 5)]}]
    hps = []
    for hp in lay["hard_points"]:
        q = dict(hp)
        q["segment"] = HP_SEG[hp["segment"]]
        hps.append(q)
    prof = {"schema": "design-profiles/0.1", "name": name or f"adam-pack-{lv.tag()}", "kind": "design", "confidence": "approximate",
            "height_m": L["H"] / 1000, "head_unit_m": 0.084 * L["H"] / 550,
            "sources": ["variants/adam/design/packaging/capsule.py (T-20261019-c1aa): R2a direction B (B4) rules made parametric, "
                        f"around the layout.py hard points for levers [{lv.tag()}]"],
            "blend": {"k_m": K / 1000, "voxel_m": 0.0015},
            "notes": f"PROVISIONAL packaging-for-look variant [{lv.tag()}]; arm display cant {cant:.1f} deg. Role dark = graphite under-structure; shell = matte warm white.",
            "segments": out, "joints": joints, "hard_points": hps}
    errs = validate(prof)
    if errs:
        raise ValueError("; ".join(errs[:5]))
    prof["_L"] = L
    return prof


def hp_fails(prof: dict) -> list:
    p = {k: v for k, v in prof.items() if not k.startswith("_")}
    return [(r["id"], round(r["margin_m"] * 1000, 2)) for r in hard_point_margins(expand(p)) if not r["pass"]]


# ------------------------------------------------------------------------------------------------------------- cant by gap rule
def _edge(seg: dict, z: float, side: str):
    """Front-view half extent of a z-axis segment at height z (linear between stations; None outside it)."""
    sts = seg["stations"]
    zs = [q["z"] for q in sts]
    if z < zs[0] or z > zs[-1]:
        return None
    i = max(0, min(len(zs) - 2, int(np.searchsorted(zs, z) - 1)))
    t = (z - zs[i]) / max(zs[i + 1] - zs[i], 1e-9)
    w = sts[i]["w"] + t * (sts[i + 1]["w"] - sts[i]["w"])
    cy = sts[i].get("cy", 0) + t * (sts[i + 1].get("cy", 0) - sts[i].get("cy", 0))
    return cy - w / 2 if side == "in" else cy + w / 2


def min_gap(prof: dict) -> float:
    """Smallest front-view gap (mm) between the arm (core + shells) inner edge and the body outer edge, from the hand end up to the
    elbow axis + 10 mm (where R2a saw the elbow touch the pelvis; above it the arm meets the torso by design). Linear station interpolation, no blend (the same approximation for every variant)."""
    segs = {s["id"]: s for s in prof["segments"]}
    arm = [segs[i] for i in ("arm_core", "deltoid", "upper_arm", "forearm") if i in segs]
    body = [segs[i] for i in ("pelvis", "waist", "glute", "thigh", "leg_core", "chest", "back") if i in segs]
    L = prof["_L"]
    z0, z1 = L["hand_end"] / 1000 + 0.004, (L["e"] + 10.0) / 1000
    g = 1e9
    for z in np.linspace(z0, z1, 80):
        ins = [v for v in (_edge(s, z, "in") for s in arm) if v is not None]
        outs = [v for v in (_edge(s, z, "out") for s in body) if v is not None]
        if ins and outs:
            g = min(g, (min(ins) - max(outs)) * 1000)
    return g


def gap_rule_cant(lv, target_gap: float, lo: float = 4.0, hi: float = 30.0, step: float = 0.5) -> float:
    def ok(c):
        return min_gap(build(lv, c)) >= target_gap
    c = lo
    while c <= hi and not ok(c):          # coarse 2-degree scan, then the first passing 0.5-degree step below it
        c += 2.0
    if c > hi:
        return hi
    f = max(lo, c - 2.0 + step)
    while f < c and not ok(f):
        f += step
    return min(f, c)
