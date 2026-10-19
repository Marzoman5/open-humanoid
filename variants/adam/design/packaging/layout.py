"""Packaging-for-look study (T-20261019-c1aa): hard-point LAYOUT as a function of the hardware levers.

Every rule is the R1 packaging rule (variants/adam/design/r1_packaging.py, chest-6dof layout) applied to the servo chosen for each joint;
the R2a re-expressions are kept (GNB 3S 1850 pack box; arm servos rotated with the display cant, written as slices). With all levers at
their defaults the boxes equal the R2a hard points (`python layout.py --check`). A lever changes the LAYOUT honestly; no box is shrunk:
a smaller box only ever comes from a different, smaller servo whose dimensions are in parts.yaml.

Levers (keys of `Levers`):
  H            standing height, mm (550 default; 600 = the conditional R1 height)
  arm          servo for shoulder roll + elbow                       (sts3215-12v | sts3045m)
  pitch        servo for the two shoulder-pitch joints (in the chest)  (sts3215-12v | sts3045m)
  grip         gripper servo (forearm)                               (sts3215-12v | sts3045m | scs0009)
  neck         neck pitch (standing in the head) and neck yaw servo  (sts3215-12v | scs0009)
  neck_yaw_at  chest (front chest slot, R1) | neck (standing in the neck; small servo only)
  pack         chest_gnb (R2a: GNB 1850 across the upper back) | chest_flat1300 (Tattu 1300 laid flat, 22 mm deep)
               | lumbar_gnb (GNB 1850 across the lower back above the Pi bay; needs waist=False, the waist ring space is free)
  waist        True: waist-yaw servo between the hip-yaw servos (R1) | False: no waist yaw (R7 by neck yaw + turning in place)
  knee_up      knee servo moved up into the thigh, laid fore-aft, driving the knee through a 1:1 parallelogram (rod + 2 ball links)
  ankle_up     ankle-pitch servo moved up into the calf, laid fore-aft, driving the ankle through a 1:1 parallelogram
  legs         6dof (ankle-roll servo behind the ankle = the heel block) | 5dof (no ankle roll)
Slim joints left behind by knee_up / ankle_up are keep-out boxes (clevis + bearings + crank lever): 32 mm across, 28 mm deep, 32 mm tall.
That is an ESTIMATE (two 3 mm plates, 12 mm tongue, MR105-class bearings, crank plate, wall), to be replaced by CAD.
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field, asdict, replace
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SIL = HERE.parent / "silhouette"
sys.path.insert(0, str(SIL))
import hardpoints as R2A  # noqa: E402  (rotated_slices, R2a hard points for the --check)

PARTS = yaml.safe_load((HERE / "parts.yaml").read_text(encoding="utf-8"))
HOUS = 2.4 + 0.25          # housing wall + sliding fit (dfm.yaml), as R1
SHELL = 1.5 + 1.6          # shell gap + wall
MOVE = 1.0
PLATE = 4.3
BOSS = 2.0
HIP_Y = 35.0
FORK = 52.0                # pitch-joint fork across (CAD foundation section 9): STS3215 at hip, knee, ankle
YAW_Z = (66.0, 101.0)
ROLL_X = (-79.0, -44.0)
PI5 = (17.0, 85.0, 56.0)
CAM = (11.5, 25.0, 24.0)
GNB = (29.0, 75.0, 34.0)   # x depth, y across, z
TATTU = (22.0, 72.0, 36.0)
SLIM = dict(w=32.0, d=28.0, h=32.0)   # slim pin joint keep-out (ESTIMATE, see docstring)
R1_PACK_W = 72.0 + 2 * HOUS           # R1 drew the Tattu 1300; its across-back width sets Tf (R2a kept ya from it)


@dataclass(frozen=True)
class Servo:
    id: str
    L: float
    W: float
    H: float
    AX: float

    @property
    def sv(self) -> float:          # half width (W) incl. housing
        return self.W / 2 + HOUS


def servo(pid: str) -> Servo:
    p = PARTS["servos"][pid]
    return Servo(pid, p["L"], p["W"], p["H"], p["AX"])


@dataclass(frozen=True)
class Levers:
    H: float = 550.0
    arm: str = "sts3215-12v"
    pitch: str = "sts3215-12v"
    grip: str = "sts3215-12v"
    neck: str = "sts3215-12v"
    neck_yaw_at: str = "chest"
    pack: str = "chest_gnb"
    waist: bool = True
    knee_up: bool = False
    ankle_up: bool = False
    legs: str = "6dof"
    upper: float = 0.19        # upper arm, fraction of H (lever 9a)
    fore: float = 0.21         # forearm incl. hand to the hand end, fraction of H (lever 9a)
    wrist: str = ""            # wrist-pitch servo id, "" = no wrist (lever 9b)

    def tag(self) -> str:
        d, b = asdict(self), asdict(Levers())
        return "+".join(f"{k}={v}" for k, v in d.items() if v != b[k]) or "baseline"


def landmarks(lv: Levers) -> dict:
    """R1 vertical landmarks (r1_packaging.layout, chest base). The shoulder axis keeps the R1 rule for the STS3215 pitch servo, so a
    smaller pitch servo lowers the chest top (a longer visible neck) instead of moving the shoulder."""
    H = lv.H
    S0 = servo("sts3215-12v")
    head_need = S0.L + 2 * HOUS + 2 * SHELL
    head_h = max(0.13 * H, head_need)
    chin = H - head_h
    neck_base = chin - 0.30 * head_h
    s = neck_base - (S0.AX + HOUS + SHELL)
    h, k, a = 0.50 * H, 0.27 * H, 66.0
    e = s - lv.upper * H
    hand_end = e - lv.fore * H
    P = servo(lv.pitch)
    chest_top = s + P.AX + HOUS                     # top of the shoulder-pitch housings
    return dict(H=H, head_h=head_h, chin=chin, neck_base_r1=neck_base, s=s, h=h, k=k, a=a, e=e, hand_end=hand_end,
                chest_top=chest_top, hip_y=HIP_Y)


def _box(id_, seg, xr, yr, zr, m=SHELL):
    return {"id": id_, "segment": seg, "center": [round((xr[0] + xr[1]) / 2000, 6), round((yr[0] + yr[1]) / 2000, 6), round((zr[0] + zr[1]) / 2000, 6)],
            "size": [round(abs(xr[1] - xr[0]) / 1000, 6), round(abs(yr[1] - yr[0]) / 1000, 6), round(abs(zr[1] - zr[0]) / 1000, 6)],
            "margin_m": round(m / 1000, 4)}


def layout(lv: Levers, cant: float = 21.0) -> dict:
    """Hard points (R2a format, mm boxes -> m) + landmarks. `cant` = arm display cant (deg); the arm boxes are rotated by it."""
    if lv.pack == "lumbar_gnb" and lv.waist:
        raise ValueError("lumbar_gnb needs waist=False (the pack takes the waist-ring space)")
    if lv.neck_yaw_at == "neck" and lv.neck == "sts3215-12v":
        raise ValueError("neck_yaw_at=neck needs a small neck servo")
    L = landmarks(lv)
    s, h, k, a, e, chin = L["s"], L["h"], L["k"], L["a"], L["e"], L["chin"]
    A, P, G, N = servo(lv.arm), servo(lv.pitch), servo(lv.grip), servo(lv.neck)
    S0 = servo("sts3215-12v")
    hp: list[dict] = []
    notes: list[str] = []
    # ------------------------------------------------------------------ chest: shoulder pitch pair, neck-yaw slot, pack
    top = L["chest_top"]
    pair_w = 2 * (P.H + BOSS) + 2.4
    neck_slot_w = (N.L + 2 * HOUS) if lv.neck_yaw_at == "chest" else 0.0
    pack_w = R1_PACK_W if lv.pack.startswith("chest") else 0.0
    Tf = max(pair_w, neck_slot_w, pack_w)
    ya = Tf / 2 + SHELL + MOVE + SHELL + PLATE + HOUS + A.W / 2
    L.update(Tf=Tf, ya=ya)
    hp.append(_box("shoulder_pitch_servos", "chest", (-P.sv, P.sv), (-Tf / 2, Tf / 2), (s - (P.L - P.AX) - HOUS, top)))
    L["chest_floor"] = s - (P.L - P.AX) - HOUS
    if lv.neck_yaw_at == "chest":
        hp.append(_box("neck_yaw_servo", "chest", (P.sv, P.sv + N.W + 2 * HOUS), (-N.L / 2 - HOUS, N.L / 2 + HOUS), (top - N.H - 2 * HOUS, top)))
    else:   # standing in the neck, output up into the head; body L fore-aft, axis on the neck centre line
        hp.append(_box("neck_yaw_servo", "neck", (-N.AX - HOUS, N.L - N.AX + HOUS), (-N.sv, N.sv), (chin - 1 - (N.H + BOSS) - 2 * HOUS, chin - 1)))
    if lv.pack == "chest_gnb":
        d, w, hh = GNB[0] + 2 * HOUS, GNB[1] + 2 * HOUS, GNB[2] + 2 * HOUS
        hp.append(_box("pack_gnb3s1850", "back", (-P.sv - d, -P.sv), (-w / 2, w / 2), (top - hh, top)))
    elif lv.pack == "chest_flat1300":
        d, w, hh = TATTU[0] + 2 * HOUS, TATTU[1] + 2 * HOUS, TATTU[2] + 2 * HOUS
        hp.append(_box("pack_tattu3s1300", "back", (-P.sv - d, -P.sv), (-w / 2, w / 2), (top - hh, top)))
    # ------------------------------------------------------------------ pelvis: yaw servos, Pi bay (and the lumbar pack)
    for nm, yc in (("hip_yaw_servo_l", HIP_Y), ("hip_yaw_servo_r", -HIP_Y)) + ((("waist_yaw_servo", 0.0),) if lv.waist else ()):
        hp.append(_box(nm, "pelvis", (-S0.AX - HOUS, S0.L - S0.AX + HOUS), (yc - S0.sv, yc + S0.sv), (h + YAW_Z[0] - HOUS, h + YAW_Z[1] + HOUS)))
    pi_z0 = h + (S0.L - S0.AX) + HOUS + 2
    pi_z1 = pi_z0 + PI5[2] + 2 * HOUS
    hp.append(_box("pi5_adapter_buck_imu_bay", "pelvis", (-S0.AX - HOUS - PI5[0] - 2 * HOUS, -S0.AX - HOUS), (-PI5[1] / 2 - HOUS, PI5[1] / 2 + HOUS), (pi_z0, pi_z1)))
    if lv.pack == "lumbar_gnb":
        d, w, hh = GNB[0] + 2 * HOUS, GNB[1] + 2 * HOUS, GNB[2] + 2 * HOUS
        x1 = min(-S0.AX - HOUS, -P.sv) - 0.4
        hp.append(_box("pack_gnb3s1850", "back", (x1 - d, x1), (-w / 2, w / 2), (pi_z1 + 1, pi_z1 + 1 + hh)))
        L["pack_z"] = pi_z1 + 1 + hh / 2
    else:
        L["pack_z"] = top - (GNB[2] + 2 * HOUS) / 2
    # ------------------------------------------------------------------ legs
    hs = S0.sv
    hp.append(_box("hip_pitch_servo_l", "leg_core_l", (-hs, hs), (HIP_Y - FORK / 2, HIP_Y + FORK / 2), (h - S0.AX - HOUS, h + S0.L - S0.AX + HOUS)))
    hip_bot = h - S0.AX - HOUS
    hp.append(_box("hip_roll_servo_l", "glute_l", (ROLL_X[0] - HOUS, ROLL_X[1] + HOUS), (HIP_Y - hs, HIP_Y + hs), (h - S0.AX - HOUS, h + S0.L - S0.AX + HOUS)))
    if lv.knee_up:
        zc = hip_bot - MOVE - hs
        hp.append(_box("knee_servo_l", "leg_core_l", (-S0.AX - HOUS, S0.L - S0.AX + HOUS), (HIP_Y - FORK / 2, HIP_Y + FORK / 2), (zc - hs, zc + hs)))
        hp.append(_box("knee_joint_l", "leg_core_l", (-SLIM["d"] / 2, SLIM["d"] / 2), (HIP_Y - SLIM["w"] / 2, HIP_Y + SLIM["w"] / 2), (k - SLIM["h"] / 2, k + SLIM["h"] / 2)))
        knee_low = k - SLIM["h"] / 2
        L["knee_rod_mm"] = zc - k
    else:
        hp.append(_box("knee_servo_l", "leg_core_l", (-hs, hs), (HIP_Y - FORK / 2, HIP_Y + FORK / 2), (k - S0.AX - HOUS, k + S0.L - S0.AX + HOUS)))
        knee_low = k - S0.AX - HOUS
    if lv.ankle_up:
        t1 = knee_low - MOVE
        t0 = t1 - 2 * hs
        if t0 < a + SLIM["h"] / 2 + MOVE:
            notes.append(f"ankle_up does not fit: calf servo bottom {t0:.1f} mm < ankle joint top {a + SLIM['h'] / 2 + MOVE:.1f} mm")
        hp.append(_box("ankle_pitch_servo_l", "leg_core_l", (-(S0.L - S0.AX) - HOUS, S0.AX + HOUS), (HIP_Y - FORK / 2, HIP_Y + FORK / 2), (t0, t1)))
        hp.append(_box("ankle_joint_l", "leg_core_l", (-SLIM["d"] / 2, SLIM["d"] / 2), (HIP_Y - SLIM["w"] / 2, HIP_Y + SLIM["w"] / 2), (a - SLIM["h"] / 2, a + SLIM["h"] / 2)))
        L["ankle_rod_mm"] = (t0 + t1) / 2 - a
        L["ankle_gap_mm"] = t0 - (a + SLIM["h"] / 2)
    else:
        hp.append(_box("ankle_pitch_servo_l", "leg_core_l", (-hs, hs), (HIP_Y - FORK / 2, HIP_Y + FORK / 2), (a - S0.AX - HOUS, a + S0.L - S0.AX + HOUS)))
    if lv.legs == "6dof":
        hp.append(_box("ankle_roll_servo_l", "heel_l", (-61.5 - HOUS, -26.5 + HOUS), (HIP_Y - hs, HIP_Y + hs), (26.0 - HOUS, 71.0 + HOUS)))
    # ------------------------------------------------------------------ arm (left): R1 placement on the canted line, rotated (R2a)
    tan_t = math.tan(math.radians(cant))

    def ay(z):
        return ya + (s - z) * tan_t
    arm = []
    rz0, rz1 = s - (A.L - A.AX) - HOUS, s + A.AX + HOUS
    arm.append(("shoulder_roll_servo", [0.0, ay((rz0 + rz1) / 2), (rz0 + rz1) / 2], [A.H + 2 * HOUS, A.W + 2 * HOUS, rz1 - rz0]))
    ez0, ez1 = e - A.AX - HOUS, e + A.L - A.AX + HOUS
    arm.append(("elbow_servo", [0.0, ay((ez0 + ez1) / 2), (ez0 + ez1) / 2], [A.W + 2 * HOUS, A.H + BOSS + 2 * HOUS, ez1 - ez0]))
    gz1 = ez0 - 3
    if lv.wrist:     # wrist-pitch servo below the elbow servo, long axis down, axis across y (like the elbow); the gripper hangs below it
        W_ = servo(lv.wrist)
        wz1, wz0 = gz1, gz1 - W_.L - 2 * HOUS
        arm.append(("wrist_servo", [0.0, ay((wz0 + wz1) / 2), (wz0 + wz1) / 2], [W_.W + 2 * HOUS, W_.H + BOSS + 2 * HOUS, wz1 - wz0]))
        gz1 = wz0 - 3
    gz0 = gz1 - G.L - 2 * HOUS
    if gz0 < L["hand_end"] + 8:
        notes.append(f"gripper servo bottom {gz0:.1f} mm is below the hand end + 8 mm ({L['hand_end'] + 8:.1f}): the forearm is too short for this stack")
    arm.append(("gripper_servo", [0.0, ay((gz0 + gz1) / 2), (gz0 + gz1) / 2], [G.H + 2 * HOUS, G.W + 2 * HOUS, gz1 - gz0]))
    for nm, c, sz in arm:
        for i, (cc, ss) in enumerate(R2A.rotated_slices(c, sz, cant, 12)):
            hp.append(_box(f"{nm}_s{i + 1}_l", "arm_core_l", (cc[0] - ss[0] / 2, cc[0] + ss[0] / 2), (cc[1] - ss[1] / 2, cc[1] + ss[1] / 2), (cc[2] - ss[2] / 2, cc[2] + ss[2] / 2)))
    # ------------------------------------------------------------------ head: neck-pitch servo standing, camera in front
    np_ = chin + N.AX + HOUS + SHELL
    hp.append(_box("neck_pitch_servo", "head", (-N.sv, N.sv), (-(N.H + BOSS) / 2 - HOUS, (N.H + BOSS) / 2 + HOUS), (np_ - N.AX - HOUS, np_ + N.L - N.AX + HOUS)))
    hp.append(_box("camera", "head", (N.sv + 1, N.sv + 1 + CAM[0]), (-CAM[1] / 2, CAM[1] / 2), (np_ + 10, np_ + 10 + CAM[2])))
    L.update(cant=cant, tan_t=tan_t, notes=notes, gripper_z=(gz0, gz1), elbow_z=(ez0, ez1), roll_z=(rz0, rz1))
    return {"levers": lv, "L": L, "hard_points": hp}


def check_baseline() -> int:
    """Default levers at 21 deg must reproduce the R2a hard points (same ids, centres and sizes to 0.01 mm)."""
    import directions as D
    ref = {b["id"]: b for b in R2A.hard_points(21.0, D.SEG_MAP)}
    seg_rename = {"leg_core_l": "leg_core_l"}
    out = {b["id"]: b for b in layout(Levers(), 21.0)["hard_points"]}
    bad = []
    for i, b in ref.items():
        o = out.get(i)
        if o is None:
            bad.append(f"missing {i}")
            continue
        for key in ("center", "size"):
            if max(abs(x - y) for x, y in zip(o[key], b[key])) > 1e-5:
                bad.append(f"{i} {key} {o[key]} != {b[key]}")
    extra = set(out) - set(ref)
    print("baseline vs R2a hard points:", "IDENTICAL" if not bad and not extra else f"{len(bad)} differences {bad[:6]} extra {extra}")
    return 0 if not bad and not extra else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    sys.exit(check_baseline() if a.check else 0)
