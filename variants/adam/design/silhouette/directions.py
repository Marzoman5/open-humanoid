"""R2a silhouette directions for Adam (task T-20261019-d955): the station tables. Library: build.py (fit + profile writer).

Run:  .venv/Scripts/python variants/adam/design/silhouette/directions.py [--only A B C]
Out:  variants/adam/design/silhouette/dir_<K>/profiles.yaml, and variants/adam/design/profiles.yaml (= the recommended one)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build import REPO, F, S, check, fit, to_profile  # noqa: E402

RECOMMENDED = "A"
CY = 35.0          # hip / leg centre line (R1 hip spacing 70 mm)
SEG_MAP = {"neck_pitch_servo": "head", "camera": "head", "shoulder_pitch_servos": "chest", "neck_yaw_servo": "chest",
           "pack_3s1300": "back", "hip_yaw_servo_l": "pelvis", "hip_yaw_servo_r": "pelvis", "waist_yaw_servo": "pelvis",
           "pi5_adapter_buck_imu_bay": "pelvis", "hip_roll_servo_l": "glute_l", "hip_pitch_servo_l": "leg_core_l",
           "knee_servo_l": "leg_core_l", "ankle_pitch_servo_l": "leg_core_l", "ankle_roll_servo_l": "heel_l",
           "shoulder_roll_servo_l": "arm_core_l", "elbow_servo_l": "arm_core_l", "gripper_servo_l": "arm_core_l"}


def head_parts(st: dict) -> list[dict]:
    """Pill head: slightly tapered to the chin (the standing neck-pitch servo fixes the lower width), full dome on top;
    glossy dark visor proud of the face; dark neck."""
    w, d, cx, n = st["head_w"], st["head_d"], 5.0, st["head_n"]
    head = {"id": "head", "role": "shell", "k": 2.0, "stations": [
        S(472.5, 0.40 * w, 0.40 * d, 2.2, 3.0), S(475.5, 0.76 * w, 0.70 * d, 2.5, 3.0), S(478.4, 0.92 * w, 0.86 * d, 2.8, 3.5),
        S(492.0, w, d, n, cx), S(530.0, w, d, n, cx), S(539.0, 0.93 * w, 0.93 * d, n, cx), S(545.5, 0.74 * w, 0.76 * d, 2.4, cx),
        S(549.6, 0.32 * w, 0.36 * d, 2.2, cx)]}
    vz0, vz1 = st["visor_z"]
    vw = st["visor_w"]
    # visor: the head section pushed forward 2 mm, so it wraps the front half of the head (vw < w narrows the wrap)
    sh = st.get("visor_shift", 2.0)
    if st.get("visor_shape") == "disc":     # Atlas-like round face: the visor width follows a circle in z
        zc, r = (vz0 + vz1) / 2, (vz1 - vz0) / 2
        vst = [S(zc + r * t, vw * max(0.35, (1 - t * t) ** 0.5), d * (0.97 + 0.03 * (1 - t * t) ** 0.5), n, cx + sh)
               for t in (-0.98, -0.8, -0.5, 0.0, 0.5, 0.8, 0.98)]
    else:
        vst = [S(vz0, vw * 0.90, d * 0.96, n, cx + sh), S(vz0 + 5, vw, d, n, cx + sh), S(vz1 - 5, vw, d, n, cx + sh),
               S(vz1, vw * 0.90, d * 0.96, n, cx + sh)]
    visor = {"id": "visor", "role": "dark", "k": 1.0, "stations": vst}
    neck = {"id": "neck", "role": "dark", "k": 3.0, "stations": [S(452.0, 36, 36, 2.0, 2.0), S(478.0, 32, 32, 2.0, 3.0)]}
    return [head, visor, neck]


def leg_core():
    """Dark leg structure: encloses the hip-pitch, knee and ankle-pitch servo housings (52 mm forks)."""
    d, n = 54.0, 3.0
    return {"id": "leg_core", "role": "dark", "mirror": True, "cy": CY, "k": 3.0, "stations": [
        S(40.0, 50, 42, n), S(48.2, fit(0.2), d, n), S(104.9, fit(0.2), d, n), S(118, 56, 46, n), S(130.7, fit(0.2), d, n),
        S(187.4, fit(0.2), d, n), S(222, 54, 46, n), S(257.3, fit(0.2), d, n), S(314.0, fit(0.2), d, n), S(322, 48, 40, n)]}


def heel_core():
    """Dark heel: the ankle-roll servo behind the ankle (CAD foundation), carried down to the sole so it reads as the
    graphite heel of the foot, not as a box hanging behind the ankle."""
    return {"id": "heel", "role": "dark", "mirror": True, "cy": CY, "k": 6.0, "stations": [
        S(3.0, 46, 50, 2.8, -44.0), S(20.3, fit(0.2), 52, 2.8, -44.0), S(76.8, fit(0.2), 52, 2.8, -44.0), S(86, 28, 34, 2.6, -34.0)]}


def heel_shell(n=3.0):
    """White heel counter over the ankle-roll servo (it rides on the ankle-pitch output, i.e. with the foot)."""
    return {"id": "heel_cover", "role": "shell", "mirror": True, "cy": CY, "k": 4.0, "stations": [
        S(16.0, fit(-2.0, of="heel"), 58, n, -44.0), S(22.0, fit(3.0, of="heel"), 62, n, -44.0), S(72.0, fit(3.0, of="heel"), 62, n, -44.0),
        S(80.0, fit(-4.0, of="heel"), 56, n, -42.0)]}


FOOT_TOE = 61.0   # sole reach in front of the ankle the concept engine validated: centre 0.15 L forward, L = 0.17 H (R1 row 12) -> 0.65 L
FOOT_HEEL = -68.0 # behind the ankle: the ankle-roll servo housing + wall (heel hard point) sets it


def foot(w=60.0, h=22.0, n=3.0, white_from=-40.0):
    """White wedge foot shell from `white_from` to the toe over a graphite sole that runs heel to toe; the dark heel core
    sits on the sole behind the white shell, so the white shoe reads ~0.18 H while the footprint keeps the engine's reach."""
    x0, x1 = white_from, FOOT_TOE
    L = x1 - x0
    shell = {"id": "foot", "role": "shell", "axis": "x", "mirror": True, "cy": CY, "k": 3.0, "stations": [
        F(x0, 0.86 * w, 0.90 * h, n, cz=0.52 * h), F(x0 + 0.10 * L, 0.95 * w, h, n, cz=0.55 * h),
        F(x0 + 0.40 * L, w, h, n, cz=0.55 * h), F(x0 + 0.78 * L, 0.92 * w, 0.66 * h, n, cz=0.40 * h),
        F(x1, 0.50 * w, 0.30 * h, 2.6, cz=0.20 * h)]}
    sole = {"id": "sole", "role": "dark", "axis": "x", "mirror": True, "cy": CY, "k": 1.0, "stations": [
        F(FOOT_HEEL, 0.70 * w, 5.0, n, cz=3.0), F(FOOT_HEEL + 8, 0.86 * w + 1.5, 6.0, n, cz=3.0),
        F(x0 + 0.78 * L, 0.92 * w + 1.5, 6.0, n, cz=3.0), F(x1 - 1.0, 0.52 * w + 1.5, 4.0, 2.6, cz=2.0)]}
    return [shell, sole]


ARM_N = 3.4       # arm sections: a touch squarer than n 3 (the rotated servos fill their corners), close to the family
ARM_WIN = 3.2     # arm stations are dense (every ~10 mm), so each fits only the slices within its own wall margin


def _zones(cant):
    """z spans (incl. margin) of the rotated arm servos at this cant: gripper, elbow, shoulder cap."""
    import hardpoints as HPM
    import build as B
    bx = [b for b in HPM.boxes_mm(HPM.hard_points(cant, SEG_MAP)) if b["segment"] == "arm_core_l"]
    out = []
    for key in ("gripper", "elbow", "shoulder_roll"):
        zs = [z for b in bx if b["id"].startswith(key) for z in b["z"]]
        out.append((min(zs) - 3.1, max(zs) + 3.1))
    return out


def _dense(z0, z1, step=10.0):
    k = max(1, round((z1 - z0) / step))
    return [z0 + (z1 - z0) * i / k for i in range(k + 1)]


def arm_core(cant, cap_d=60.0, elbow_d=56.0, fore_d=60.0, n=ARM_N):
    """Dark arm structure on the canted centre line: encloses the rotated shoulder-roll, elbow and gripper servos.
    The hand end (below the forearm shell) is the dark gripper."""
    (g0, g1), (e0, e1), (c0, c1) = _zones(cant)
    sts = [S(212.0, 20, 24, 2.6), S(222.0, 34, 36, 2.8), S(g0 - 12, 42, 46, 3.0)]
    sts += [S(z, fit(0.2, win=ARM_WIN), fore_d if z < e0 + 6 else elbow_d, n) for z in _dense(g0, e1)]
    sts += [S((e1 + c0) / 2, 42, 42, n)]
    sts += [S(z, fit(0.2, win=ARM_WIN), cap_d, n) for z in _dense(c0, c1)]
    sts += [S(c1 + 6, 34, 36, 2.6)]
    return {"id": "arm_core", "role": "dark", "mirror": True, "arm": True, "k": 3.0, "stations": sts}


def arm_shells(st: dict, n: float, k: float) -> list[dict]:
    """White arm covers. side_panel: the shoulder cap is proud front/back but narrower than the core, so its outer face
    reads graphite (narrows the front read of the widest point); the limb covers are then only 1 mm proud at the sides.
    Otherwise every cover is 2 mm proud all round."""
    (g0, g1), (e0, e1), (c0, c1) = _zones(st["cant"])
    panel = st["shoulder"] == "side_panel"
    dd = 6.0

    def sh(zs, d, ex):
        return [S(z, fit(ex, of="arm_core", win=ARM_WIN), d + dd, ARM_N) for z in zs]
    cap = sh(_dense(c0 + 4, c1 - 3, 12), 60.0, -6.0 if panel else 4.0)
    limb_ex = 2.0 if panel else 4.0
    upper = sh(_dense(e0 + 31, e1 - 2, 10), 56.0, limb_ex)  # elbow axis 334.8 mm: the upper-arm cover starts just above it
    fore = sh(_dense(g0 + 4, g1 - 2, 12), 60.0, limb_ex)
    return [{"id": "deltoid", "role": "shell", "mirror": True, "arm": True, "k": k, "stations": _ends(cap, c0 - 1, c1 + 4, 0.70)},
            {"id": "upper_arm", "role": "shell", "mirror": True, "arm": True, "k": k, "stations": _ends(upper, e0 + 26, c0 - 2, 0.80)},
            {"id": "forearm", "role": "shell", "mirror": True, "arm": True, "k": k, "stations": _ends(fore, g0 - 6, e0 + 14, 0.80)}]


def _ends(stations, z0, z1, frac=0.78):
    """Roll a shell's ends in (a shell edge is never a flat cut): add a station beyond each end at `frac` of its size."""
    out = [dict(stations[0]), *stations, dict(stations[-1])]
    for q, z in ((out[0], z0), (out[-1], z1)):
        zc = q["z"]
        q["z"] = z
        for key in ("w", "d"):
            if isinstance(q[key], fit):
                q[key] = fit(q[key].extra, q[key].of, q[key].win)
                q[key].scale, q[key].at_z = frac, zc
            else:
                q[key] = q[key] * frac
    return out


# --------------------------------------------------------------------------------------------------------- directions
STYLES = {
    "A": dict(key="A", title="Optimus-lean", cant=21.0, n=3.0, k=8.0, head_w=62.0, head_d=68.0, head_n=2.4,
              visor_w=62.0, visor_z=(487.0, 531.0), torso="band", shoulder="side_panel", limbs="tapered",
              notes="Optimus-lean: white chest and limb shells, a graphite waist-and-pelvis band, dark recessed joint bands, "
                    "tapered limb capsules with a calf swell, pill head with a full-face visor, dark shoulder side panels."),
    "B": dict(key="B", title="Atlas-capsule", cant=20.0, n=2.5, k=9.0, head_w=62.0, head_d=68.0, head_n=2.3,
              visor_w=50.0, visor_z=(494.0, 526.0), torso="capsule", shoulder="capsule", limbs="capsule",
              notes="Atlas-capsule: near-elliptical sections (n 2.5) blended with large radii, white chest and pelvis capsules, "
                    "dark only at the joints and waist, round shoulder capsules, cylinder limbs, round face disc."),
    "C": dict(key="C", title="Apple-monolith", cant=20.0, n=3.2, k=10.0, head_w=62.0, head_d=68.0, head_n=2.8,
              visor_w=60.0, visor_z=(489.0, 529.0), torso="monolith", shoulder="integrated", limbs="continuous",
              notes="Apple-monolith: one unibody torso shell from shoulder to hip with a single thin dark waist line, shoulder caps "
                    "merged into the chest, thigh and shank as one continuous capsule over the knee, soft squircles (n 3.2)."),
}


def build_direction(st: dict) -> dict:
    n, k = st["n"], st["k"]
    kl = max(3.0, k * 0.5)
    segs = head_parts(st)
    # ---- torso: chest (shoulder-pitch servos + neck-yaw slot) and upper back (3S pack) are white in every direction
    chest = [S(400.4, fit(1.0), 96, n, 10.0), S(430.0, fit(1.5), 98, n, 10.0), S(457.1, fit(1.0), 96, n, 10.0),
             S(459.3, 72, 72, n - 0.2, 6.0), S(461.8, 38, 40, 2.5, 3.0)]      # the chest top rolls over fast: a visible neck
    back = [S(411.6, fit(1.0), 76, n, -24.0), S(457.1, fit(1.0), 76, n, -24.0), S(460.5, 70, 58, n - 0.2, -19.0),
            S(463.0, 40, 36, 2.6, -10.0)]
    tk = k + 4.0     # torso blends: chest, back, waist and hips read as one form
    pn = n + 1.5     # the pelvis holds three servos side by side: squarer section, else it grows 10 mm wider
    pel = [S(309.8, fit(0.5), 94, pn, -1.0), S(335.3, fit(0.5), 100, pn, 3.0), S(381.7, fit(0.5), 100, pn, 3.0)]
    T = st["torso"]
    if T == "band":       # graphite waist band over a dark pelvis core; white hip shell covers the pelvis below the band
        # chest tapers into a narrow graphite waist (P4 is measured lower, on the hip shell, so the band is free to pinch)
        hn = n + 0.4
        segs += [{"id": "chest", "role": "shell", "k": tk, "stations": [S(378.0, 60, 54, n, 4.0), S(388.0, 78, 76, n, 7.0),
                                                                       S(395.0, 90, 88, n, 9.0)] + chest},
                 {"id": "back", "role": "shell", "k": tk, "stations": [S(376.0, 56, 36, n, -8.0), S(390.0, 76, 52, n, -14.0),
                                                                      S(402.0, 88, 66, n, -20.0)] + back},
                 {"id": "pelvis", "role": "dark", "k": k, "stations": [S(294.0, 84, 66, pn, -2.0)] + pel +
                  [S(387.0, 86, 74, n, 3.0), S(397.0, 78, 66, n, 4.0)]},
                 {"id": "hips", "role": "shell", "k": tk, "stations": [
                     S(289.0, 80, 66, hn, -2.0), S(296.0, 98, 92, hn, -2.0), S(303.0, fit(3.0, of="pelvis"), 106, hn, -1.0),
                     S(318.0, fit(4.5, of="pelvis"), 118, hn, 1.0), S(364.0, fit(4.5, of="pelvis"), 120, hn, 3.0),
                     S(371.0, fit(1.0, of="pelvis"), 108, hn, 3.0), S(376.0, fit(-4.0, of="pelvis"), 96, hn, 3.0)]}]
    elif T == "capsule":  # white chest capsule and white pelvis capsule; the waist-yaw gap is the only dark torso band
        segs += [{"id": "chest", "role": "shell", "k": tk, "stations": [S(393.0, 78, 74, n, 6.0), S(397.0, 88, 88, n, 9.0)] + chest},
                 {"id": "back", "role": "shell", "k": tk, "stations": [S(396.0, 82, 56, n, -14.0)] + back},
                 {"id": "pelvis", "role": "shell", "k": tk, "stations": [S(290.0, 80, 62, n, -2.0), S(298.0, 100, 80, n, -1.0)] + pel +
                  [S(386.0, 102, 84, n, 3.0), S(390.0, 88, 70, n, 3.0)]},
                 {"id": "waist", "role": "dark", "k": 3.0, "stations": [S(376.0, 92, 70, n, 2.0), S(402.0, 88, 70, n, 3.0)]}]
    else:                 # monolith: one white unibody from shoulder to hip; a thin dark waist reveal
        segs += [{"id": "chest", "role": "shell", "k": tk, "stations": [S(384.0, 96, 84, n, 4.0), S(394.0, 98, 92, n, 8.0)] + chest},
                 {"id": "back", "role": "shell", "k": tk, "stations": [S(390.0, 88, 64, n, -16.0)] + back},
                 {"id": "pelvis", "role": "shell", "k": tk, "stations": [S(288.0, 80, 62, n, -2.0), S(298.0, 104, 84, n, -1.0)] + pel +
                  [S(388.0, 104, 86, n, 3.0)]},
                 {"id": "waist", "role": "dark", "k": 1.5, "stations": [S(384.0, 100, 82, n, 3.0), S(392.0, 98, 82, n, 4.0)]}]
    # seat: both hip-roll servos sit 84 mm behind the hip axis; one white seat shell across both, blended up into the
    # lower back (two separate pads read as boxes on the back)
    # (a single seat across both servos was tried in iteration A7/A8 and read as a bustle; two rounded glutes read better)
    segs.append({"id": "glute", "role": "shell", "mirror": True, "cy": CY, "k": 10.0, "stations": [
        S(238.0, 26, 26, 2.3, -48.0), S(249.0, 46, 50, 2.4, -58.0), S(257.3, fit(1.5), 62, 2.4, -61.0), S(314.0, fit(1.5), 62, 2.4, -61.0),
        S(332.0, 46, 48, 2.4, -52.0), S(352.0, 30, 30, 2.3, -40.0)]})
    # ---- legs: dark core + white shells; knee band ~14 mm, ankle band between the shank shell and the foot
    segs += [leg_core(), heel_core(), *foot(n=n)]
    L = st["limbs"]

    def inner(w, gap=2.0):    # shell centre so the inner (crotch) edge stays `gap` mm off the mid-plane
        return gap + w / 2
    if L == "tapered":
        # white covers taper below the forks' width (63 mm core): at the knee and ankle the graphite core shows at the sides
        # covers stay proud of the core at the fork servos (clean bands, no blotchy side breakthroughs); the taper lives
        # between the forks (front) and in depth (quad forward, calf behind) because the 52 mm forks fix the front width
        thigh = [S(170, fit(3.0, of="leg_core"), 60, n, 1.0, 35.5), S(184, fit(3.0, of="leg_core"), 60, n, 1.5, 35.5),
                 S(215, 66, 62, n, 3.0, inner(66)), S(250, 70, 64, n, 3.0, inner(70)),
                 S(278, 72, 62, n, 1.0, inner(72)), S(298, 70, 58, n, -1.0, inner(70))]
        shank = [S(66, fit(3.0, of="leg_core"), 60, n, 0.5, 35.0), S(100, fit(3.0, of="leg_core"), 64, n, -2.0, 35.5),
                 S(116, 70, 68, n, -4.0, 36.0), S(126, 70, 68, n, -4.0, 36.0), S(138, fit(3.0, of="leg_core"), 62, n, -1.0, 36.0)]
        segs += [{"id": "thigh", "role": "shell", "mirror": True, "k": kl, "stations": _ends(thigh, 160.0, 305.0, 0.86)},
                 {"id": "shank", "role": "shell", "mirror": True, "k": kl, "stations": _ends(shank, 56.0, 142.0, 0.88)}]
    elif L == "capsule":
        thigh = [S(166, 68, 62, n, 0.0, 36.0), S(230, 69, 63, n, 1.0, 36.5), S(296, 70, 62, n, 0.0, 37.0)]
        shank = [S(62, 66, 60, n, 0.0, 35.8), S(110, 69, 66, n, -3.0, 36.0), S(134, 68, 62, n, -1.0, 36.0)]
        segs += [{"id": "thigh", "role": "shell", "mirror": True, "k": kl, "stations": _ends(thigh, 157.0, 305.0, 0.80)},
                 {"id": "shank", "role": "shell", "mirror": True, "k": kl, "stations": _ends(shank, 53.0, 142.0, 0.80)}]
    else:                 # continuous: one shell from ankle to hip; the knee is a thin dark reveal line only
        leg = [S(60, 66, 60, n, 0.0, 35.6), S(84, 68, 62, n, -1.0, 35.8), S(110, 69, 66, n, -3.0, 36.0), S(128, 70, 66, n, -3.0, 36.0),
               S(144, 70, 62, n, -1.0, 36.0)]
        leg2 = [S(152, 70, 60, n, 0.0, 36.0), S(200, 69, 61, n, 2.0, 36.2), S(250, 71, 63, n, 2.0, 37.0), S(296, 70, 58, n, -1.0, 37.0)]
        segs += [{"id": "shank", "role": "shell", "mirror": True, "k": 1.0, "stations": _ends(leg, 52.0, 147.0, 0.93)},
                 {"id": "thigh", "role": "shell", "mirror": True, "k": 1.0, "stations": _ends(leg2, 149.5, 305.0, 0.84)}]
    # ---- arms
    segs.append(arm_core(st["cant"]))
    segs += arm_shells(st, n, kl)
    return {"key": st["key"], "name": f"adam-r2a-{st['key']}", "title": st["title"], "cant_deg": st["cant"], "head_unit": 84.0,
            "k_default": k, "seg_map": SEG_MAP, "notes": "R2a direction " + st["notes"] +
            " Role dark = graphite under-structure; role shell = matte warm white covers.", "segments": segs}


def write(dirn: dict, path: Path) -> dict:
    prof = to_profile(dirn)
    path.parent.mkdir(parents=True, exist_ok=True)
    head = (f"# R2a silhouette, direction {dirn['key']} '{dirn['title']}' (T-20261019-d955). Written by "
            "variants/adam/design/silhouette/directions.py from its station tables; edit the tables and re-run.\n"
            "# Hard points: variants/adam/design/silhouette/hardpoints.py (R1 0.55 m boxes, GNB 1850 pack, arm servos rotated by the cant).\n")
    path.write_text(head + yaml.safe_dump(prof, sort_keys=False, width=160), encoding="utf-8")
    bad = check(prof)
    print(f"{dirn['key']} {dirn['title']}: {path.relative_to(REPO)}  hard points failing: "
          f"{[(b['id'], round(b['margin_m'] * 1000, 2)) for b in bad] or 'none'}")
    return prof


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args(argv)
    for k, s in STYLES.items():
        if a.only and k not in a.only:
            continue
        d = build_direction(s)
        write(d, HERE / f"dir_{k}" / "profiles.yaml")
        if k == RECOMMENDED:
            write(d, HERE.parent / "profiles.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
