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
        S(466.0, 0.40 * w, 0.40 * d, 2.2, 3.0), S(471.0, 0.76 * w, 0.70 * d, 2.5, 3.0), S(478.4, 0.92 * w, 0.86 * d, 2.8, 3.5),
        S(492.0, w, d, n, cx), S(530.0, w, d, n, cx), S(542.0, 0.88 * w, 0.88 * d, n, cx), S(549.6, 0.36 * w, 0.40 * d, 2.2, cx)]}
    vz0, vz1 = st["visor_z"]
    vw = st["visor_w"]
    # visor: the head section pushed forward 2 mm, so it wraps the front half of the head (vw < w narrows the wrap)
    sh = st.get("visor_shift", 2.0)
    visor = {"id": "visor", "role": "dark", "k": 1.0, "stations": [
        S(vz0, vw * 0.90, d * 0.96, n, cx + sh), S(vz0 + 5, vw, d, n, cx + sh), S(vz1 - 5, vw, d, n, cx + sh),
        S(vz1, vw * 0.90, d * 0.96, n, cx + sh)]}
    neck = {"id": "neck", "role": "dark", "k": 3.0, "stations": [S(452.0, 36, 36, 2.0, 2.0), S(477.0, 32, 32, 2.0, 3.0)]}
    return [head, visor, neck]


def leg_core():
    """Dark leg structure: encloses the hip-pitch, knee and ankle-pitch servo housings (52 mm forks)."""
    d, n = 54.0, 3.0
    return {"id": "leg_core", "role": "dark", "mirror": True, "cy": CY, "k": 3.0, "stations": [
        S(40.0, 50, 42, n), S(48.2, fit(0.2), d, n), S(104.9, fit(0.2), d, n), S(118, 56, 46, n), S(130.7, fit(0.2), d, n),
        S(187.4, fit(0.2), d, n), S(222, 54, 46, n), S(257.3, fit(0.2), d, n), S(314.0, fit(0.2), d, n), S(322, 48, 40, n)]}


def heel_core():
    return {"id": "heel", "role": "dark", "mirror": True, "cy": CY, "k": 4.0, "stations": [
        S(15.0, 30, 40, 3.0, -42.0), S(20.3, fit(0.2), 50, 3.0, -44.0), S(76.8, fit(0.2), 50, 3.0, -44.0), S(85, 26, 34, 3.0, -36.0)]}


def heel_shell(n=3.0):
    """White heel counter over the ankle-roll servo (it rides on the ankle-pitch output, i.e. with the foot)."""
    return {"id": "heel_cover", "role": "shell", "mirror": True, "cy": CY, "k": 4.0, "stations": [
        S(16.0, fit(-2.0, of="heel"), 58, n, -44.0), S(22.0, fit(3.0, of="heel"), 62, n, -44.0), S(72.0, fit(3.0, of="heel"), 62, n, -44.0),
        S(80.0, fit(-4.0, of="heel"), 56, n, -42.0)]}


def foot(length=(-70.0, 46.0), w=60.0, h=22.0, n=3.0):
    x0, x1 = length
    L = x1 - x0
    shell = {"id": "foot", "role": "shell", "axis": "x", "mirror": True, "cy": CY, "k": 3.0, "stations": [
        F(x0, 0.70 * w, 0.70 * h, n, cz=0.40 * h), F(x0 + 0.08 * L, 0.92 * w, 0.95 * h, n, cz=0.52 * h),
        F(x0 + 0.45 * L, w, h, n, cz=0.52 * h), F(x0 + 0.80 * L, 0.92 * w, 0.72 * h, n, cz=0.40 * h),
        F(x1, 0.48 * w, 0.34 * h, 2.6, cz=0.20 * h)]}
    sole = {"id": "sole", "role": "dark", "axis": "x", "mirror": True, "cy": CY, "k": 1.0, "stations": [
        F(x0 + 1.0, 0.72 * w + 1.5, 6.0, n, cz=3.0), F(x0 + 0.08 * L, 0.92 * w + 1.5, 6.0, n, cz=3.0),
        F(x0 + 0.80 * L, 0.92 * w + 1.5, 6.0, n, cz=3.0), F(x1 - 1.5, 0.52 * w + 1.5, 4.0, 2.6, cz=2.0)]}
    return [shell, sole]


ARM_N = 4.0       # arm sections are a little squarer than the rest: the rotated servos fill their corners
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
    """White arm covers. side_panel: proud front/back but narrower than the core, so a graphite strip runs down each
    side of the arm (narrows the front read); otherwise proud all round."""
    (g0, g1), (e0, e1), (c0, c1) = _zones(st["cant"])
    if st["shoulder"] == "side_panel":
        ex, dd = -6.0, 6.0
    else:
        ex, dd = 4.0, 6.0

    def sh(zs, d):
        return [S(z, fit(ex, of="arm_core", win=ARM_WIN), d + dd, ARM_N) for z in zs]
    cap = sh(_dense(c0 + 4, c1 - 3, 12), 60.0)
    upper = sh(_dense(e0 + 31, e1 - 2, 10), 56.0)          # elbow axis 334.8 mm: the upper-arm cover starts just above it
    fore = sh(_dense(g0 + 4, g1 - 2, 12), 60.0)
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
    "A": dict(key="A", title="Optimus-lean", cant=20.0, n=3.0, k=6.0, head_w=62.0, head_d=68.0, head_n=2.6,
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
             S(461.0, 72, 72, n - 0.2, 6.0), S(464.5, 36, 40, 2.5, 3.0)]
    back = [S(411.6, fit(1.0), 76, n, -24.0), S(457.1, fit(1.0), 76, n, -24.0), S(462.0, 64, 50, n - 0.2, -16.0)]
    pn = n + 1.5     # the pelvis holds three servos side by side: squarer section, else it grows 10 mm wider
    pel = [S(309.8, fit(0.5), 94, pn, -1.0), S(335.3, fit(0.5), 100, pn, 3.0), S(381.7, fit(0.5), 100, pn, 3.0)]
    T = st["torso"]
    if T == "band":       # graphite waist band over a dark pelvis core; white hip shell covers the pelvis below the band
        segs += [{"id": "chest", "role": "shell", "k": k, "stations": [S(388.0, 74, 66, n, 4.0), S(395.0, 86, 84, n, 8.0)] + chest},
                 {"id": "back", "role": "shell", "k": k, "stations": [S(392.0, 80, 50, n, -14.0)] + back},
                 {"id": "pelvis", "role": "dark", "k": k, "stations": [S(294.0, 84, 66, pn, -2.0)] + pel +
                  [S(390.0, 100, 82, n, 2.0), S(402.0, 92, 72, n, 3.0)]},
                 {"id": "hips", "role": "shell", "k": k, "stations": [
                     S(291.0, 88, 72, 3.6, -2.0), S(303.0, fit(3.0, of="pelvis"), 104, 3.6, -1.0), S(318.0, fit(3.5, of="pelvis"), 112, 3.6, 1.0),
                     S(366.0, fit(3.5, of="pelvis"), 114, 3.6, 3.0), S(374.0, fit(-3.0, of="pelvis"), 102, 3.6, 3.0)]}]
    elif T == "capsule":  # white chest capsule and white pelvis capsule; the waist-yaw gap is the only dark torso band
        segs += [{"id": "chest", "role": "shell", "k": k, "stations": [S(393.0, 78, 74, n, 6.0), S(397.0, 88, 88, n, 9.0)] + chest},
                 {"id": "back", "role": "shell", "k": k, "stations": [S(396.0, 82, 56, n, -14.0)] + back},
                 {"id": "pelvis", "role": "shell", "k": k, "stations": [S(290.0, 80, 62, n, -2.0), S(298.0, 100, 80, n, -1.0)] + pel +
                  [S(386.0, 102, 84, n, 3.0), S(390.0, 88, 70, n, 3.0)]},
                 {"id": "waist", "role": "dark", "k": 3.0, "stations": [S(376.0, 92, 70, n, 2.0), S(402.0, 88, 70, n, 3.0)]}]
    else:                 # monolith: one white unibody from shoulder to hip; a thin dark waist reveal
        segs += [{"id": "chest", "role": "shell", "k": k, "stations": [S(384.0, 96, 84, n, 4.0), S(394.0, 98, 92, n, 8.0)] + chest},
                 {"id": "back", "role": "shell", "k": k, "stations": [S(390.0, 88, 64, n, -16.0)] + back},
                 {"id": "pelvis", "role": "shell", "k": k, "stations": [S(288.0, 80, 62, n, -2.0), S(298.0, 104, 84, n, -1.0)] + pel +
                  [S(388.0, 104, 86, n, 3.0)]},
                 {"id": "waist", "role": "dark", "k": 1.5, "stations": [S(384.0, 100, 82, n, 3.0), S(392.0, 98, 82, n, 4.0)]}]
    # glute: the hip-roll servos sit 84 mm behind the hip axis; a white seat shell blended up into the lower back
    segs.append({"id": "glute", "role": "shell", "mirror": True, "cy": CY, "k": 12.0, "stations": [
        S(240.0, 24, 30, 2.6, -50.0), S(250.0, 44, 50, 2.8, -58.0), S(257.3, fit(1.0), 58, 2.8, -61.0), S(314.0, fit(1.0), 58, 2.8, -61.0),
        S(330.0, 44, 52, 2.8, -54.0), S(350.0, 30, 40, 2.6, -44.0)]})
    # ---- legs: dark core + white shells; knee band ~14 mm, ankle band between the shank shell and the foot
    segs += [leg_core(), heel_core(), heel_shell(n), *foot(n=n)]
    L = st["limbs"]
    if L == "tapered":
        thigh = [S(162, 68, 60, n, 0.0, 36.0), S(200, 68, 61, n, 2.0, 36.0), S(240, 70, 63, n, 3.0, 37.0),
                 S(274, 72, 62, n, 1.0, 37.6), S(298, 68, 57, n, -1.0, 37.0)]
        shank = [S(60, 66, 60, n, 0.0, 35.6), S(80, 68, 62, n, -1.0, 35.8), S(104, 69, 66, n, -3.0, 36.0), S(120, 70, 68, n, -4.0, 36.0),
                 S(136, 68, 62, n, -1.0, 36.0)]
        segs += [{"id": "thigh", "role": "shell", "mirror": True, "k": kl, "stations": _ends(thigh, 156.0, 305.0, 0.84)},
                 {"id": "shank", "role": "shell", "mirror": True, "k": kl, "stations": _ends(shank, 52.0, 142.0, 0.86)}]
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
