"""R2a hard points for Adam at the provisional R1 baseline (0.55 m, chest-6dof layout, 23 DOF). Task T-20261019-d955.

Source of every box: variants/adam/design/r1_packaging/chest-6dof-550/profiles.yaml (written by r1_packaging.py, T-20261019-36f9).
Boxes are servo/pack/compute bodies INCLUDING their printed housing; margin_m = 3.1 mm (1.5 mm shell gap + 1.6 mm shell wall).
They are inviolable: this module never resizes a box. It changes only two things, both stated in the R2a review:

1. Battery: the R1 sign-off replaced the Tattu 3S 1300 with the **GNB 3S 1850** (75 x 29 x 34 mm, R1 section 7.1). The keep-out is
   re-derived with r1_packaging.py's own rule (pack + 2 x housing, top flush with the shoulder-servo housings, behind them).
   It is 7 mm deeper and 3 mm wider than the R1 box, i.e. LARGER.
2. Arm servos: r1_packaging.py places the arm boxes on the canted arm centre line but keeps them axis-aligned (a shear, not a
   rotation; its docstring says so). A sheared box needs a ~6 mm wider arm section per side than the servo it stands for.
   Here each arm servo box is ROTATED by the arm cant about its own centre (same centre as R1) and re-expressed, because
   the profiles schema only has axis-aligned boxes, as a stack of horizontal slices whose union CONTAINS the rotated box
   (conservative). Box sizes are unchanged. The cant is a display-pose choice (>= the R1 minimum 13.83 deg that clears the
   hip forks); the boxes follow the same R1 placement rule at whatever cant is chosen.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
R1_PROFILE = HERE.parent / "r1_packaging" / "chest-6dof-550" / "profiles.yaml"

# constants copied from r1_packaging.py (same sources) so the re-derivations below use the R1 rule exactly
HOUS = 2.4 + 0.25
S_W = 24.7
GNB_1850 = (29.0, 75.0, 34.0)     # x depth, y across, z: GNB 3S 1850 mAh 100C, 75 x 29 x 34 mm (R1 review section 7.1; catalog task T-20261019-c669)
R1_CANT_DEG = 13.83               # r1_packaging chest-6dof-550: smallest A-pose cant that clears the hip forks
SHOULDER_Y, SHOULDER_Z = 65.15, 439.3   # shoulder roll axis (R1 joints: shoulder_l)
ARM_SERVOS = ("shoulder_roll_servo_l", "elbow_servo_l", "gripper_servo_l")

# landmarks (mm) of the R1 0.55 m layout
LM = dict(H=550.0, ankle=66.0, knee=148.5, hip=275.0, hip_y=35.0, shoulder_y=SHOULDER_Y, shoulder_z=SHOULDER_Z,
          elbow=334.8, hand_end=219.3, neck_base_r1=457.3, chin_r1=478.5, head_h_r1=71.5)


def r1_hard_points() -> list[dict]:
    return copy.deepcopy(yaml.safe_load(R1_PROFILE.read_text(encoding="utf-8"))["hard_points"])


def _mm(hp):
    c = [v * 1000 for v in hp["center"]]
    s = [v * 1000 for v in hp["size"]]
    return c, s


def _box(id_, seg, c, s, m=3.1):
    return {"id": id_, "segment": seg, "center": [round(v / 1000, 6) for v in c], "size": [round(v / 1000, 6) for v in s],
            "margin_m": round(m / 1000, 4)}


def rotated_slices(c: list, s: list, cant_deg: float, n: int = 6) -> list[tuple[list, list]]:
    """Axis-aligned slices (centre, size) whose union contains box (c, s) rotated by cant_deg in the y-z (frontal) plane about
    its centre. Rotation sense: the box's lower end moves outward (+y), like the arm."""
    t = math.radians(cant_deg)
    hy, hz = s[1] / 2, s[2] / 2
    # rotated corners in (y, z) relative to the centre; arm hangs down and out: a point at z below centre moves to +y
    corners = []
    for sy in (-1, 1):
        for sz in (-1, 1):
            y, z = sy * hy, sz * hz
            corners.append((y * math.cos(t) - z * math.sin(t), y * math.sin(t) + z * math.cos(t)))
    zmin, zmax = min(p[1] for p in corners), max(p[1] for p in corners)
    out = []
    edges = [(corners[0], corners[1]), (corners[1], corners[3]), (corners[3], corners[2]), (corners[2], corners[0])]
    for i in range(n):
        za, zb = zmin + (zmax - zmin) * i / n, zmin + (zmax - zmin) * (i + 1) / n
        ys = []
        for (y0, z0), (y1, z1) in edges:              # clip each edge to the slab [za, zb], collect y extents
            for zz in (za, zb):
                if min(z0, z1) <= zz <= max(z0, z1) and z1 != z0:
                    ys.append(y0 + (y1 - y0) * (zz - z0) / (z1 - z0))
            for (yy, zz) in ((y0, z0), (y1, z1)):
                if za <= zz <= zb:
                    ys.append(yy)
        y_lo, y_hi = min(ys), max(ys)
        out.append(([c[0], c[1] + (y_lo + y_hi) / 2, c[2] + (za + zb) / 2], [s[0], y_hi - y_lo, zb - za]))
    return out


def arm_centre_y(z: float, cant_deg: float) -> float:
    return SHOULDER_Y + (SHOULDER_Z - z) * math.tan(math.radians(cant_deg))


def hard_points(cant_deg: float = R1_CANT_DEG, seg_map: dict | None = None, slices: int = 12) -> list[dict]:
    """The R2a hard-point set (mm-exact copies of R1 boxes, pack updated, arm boxes rotated + sliced at `cant_deg`).
    seg_map: {r1 hard-point id: segment id that must enclose it} (the profiles segment names of the direction)."""
    seg_map = seg_map or {}
    out = []
    for hp in r1_hard_points():
        c, s = _mm(hp)
        hid = hp["id"]
        if hid == "pack_3s1300":
            x1 = c[0] + s[0] / 2                       # front face stays against the shoulder-servo housings (x = -15)
            z1 = c[2] + s[2] / 2                       # top flush with the shoulder-servo housing top
            d, w, h = GNB_1850[0] + 2 * HOUS, GNB_1850[1] + 2 * HOUS, GNB_1850[2] + 2 * HOUS
            out.append(_box("pack_gnb3s1850", seg_map.get("pack_3s1300", "torso"), [x1 - d / 2, 0.0, z1 - h / 2], [d, w, h]))
            continue
        if hid in ARM_SERVOS:
            # R1 rule: centre on the canted centre line at the box's mid height
            c = [c[0], arm_centre_y(c[2], cant_deg), c[2]]
            for i, (cc, ss) in enumerate(rotated_slices(c, s, cant_deg, slices)):
                out.append(_box(f"{hid[:-2]}_s{i + 1}_l", seg_map.get(hid, hp["segment"]), cc, ss, hp["margin_m"] * 1000))
            continue
        out.append(_box(hid, seg_map.get(hid, hp["segment"]), c, s, hp["margin_m"] * 1000))
    return out


def boxes_mm(hps: list[dict]) -> list[dict]:
    """Hard points (both sides) in mm with explicit bounds, for fitting sections."""
    res = []
    for hp in hps:
        c, s = _mm(hp)
        for side in ((1, -1) if hp["id"].endswith("_l") else (1,)):
            seg = hp["segment"]
            if side == -1 and seg.endswith("_l"):
                seg = seg[:-2] + "_r"
            cy = c[1] * side
            res.append({"id": hp["id"] if side == 1 else hp["id"][:-2] + "_r", "segment": seg, "m": hp["margin_m"] * 1000,
                        "x": (c[0] - s[0] / 2, c[0] + s[0] / 2), "y": (cy - s[1] / 2, cy + s[1] / 2), "z": (c[2] - s[2] / 2, c[2] + s[2] / 2)})
    return res
