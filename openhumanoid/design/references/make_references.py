"""Generates the reference / counter-example / sample profiles in this folder from small parameter tables.

Run:  .venv/Scripts/python -m openhumanoid.design.references.make_references

All numbers are fractions of total height H, written down from public dimensions and press images. They are
APPROXIMATE (no pixel measurement of copyrighted images was done; see SOURCES in each file and docs/design-method.md).
Replace a reference with a measured silhouette (`oh design metrics --ref image.png`) as soon as the maintainer supplies one.
"""
from __future__ import annotations

from pathlib import Path

import yaml

HERE = Path(__file__).parent


def _r(x: float) -> float:
    return round(float(x), 5)


def humanoid_profiles(name: str, H: float, p: dict, sources: list[str], kind: str, confidence: str, notes: str = "") -> dict:
    """Build a profiles dict (design-profiles/0.1) from proportion parameters (all fractions of H unless noted)."""
    f = lambda v: _r(v * H)  # noqa: E731
    top = H
    head_h = p["head_h"]
    head_bot = top - head_h * H
    neck_len = p["neck_len"] * H
    neck_bot = head_bot - neck_len
    sh = p["shoulder_w"]          # outer shoulder width incl. deltoid
    arm_w = p["arm_w"]
    crotch = p["crotch_z"]
    hip_w = p["hip_w"]
    waist_w = p["waist_w"]
    waist_z = p["waist_z"]
    ank = p["ankle_z"]
    knee = p["knee_z"]
    foot_h = p["foot_h"]
    foot_l = p["foot_len"]
    foot_w = p["foot_w"]
    leg_gap = p.get("leg_gap", 0.006)
    thigh_top = p["thigh_w"]
    knee_w = p["knee_w"]
    calf_w = p["calf_w"]
    calf_z = knee - p["calf_pos"] * (knee - ank)
    ankle_w = p["ankle_w"]
    chest_z = p.get("chest_z", 0.70)
    shoulder_z = (neck_bot / H) - p.get("shoulder_drop", 0.02)
    tn = p.get("torso_n", 2.6)       # torso section squareness
    ln = p.get("limb_n", 2.2)        # limb section squareness
    hn = p.get("head_n", 2.4)
    chest_d, waist_d, pelvis_d = p["chest_d"], p["waist_d"], p["pelvis_d"]
    trunk_sh_w = sh - 2 * arm_w * p.get("arm_overlap", 0.55)
    leg_cy = thigh_top / 2 + leg_gap / 2

    head_w, head_d = p["head_w"], p["head_d"]
    segs = []
    segs.append({"id": "head", "role": "head", "stations": [
        {"z": _r(head_bot), "w": f(head_w * 0.55), "d": f(head_d * 0.55), "n": 2.2},
        {"z": _r(head_bot + 0.22 * head_h * H), "w": f(head_w * 0.92), "d": f(head_d * 0.92), "n": hn},
        {"z": _r(head_bot + 0.55 * head_h * H), "w": f(head_w), "d": f(head_d), "n": hn},
        {"z": _r(head_bot + 0.85 * head_h * H), "w": f(head_w * 0.85), "d": f(head_d * 0.85), "n": 2.2},
        {"z": _r(top), "w": f(head_w * 0.30), "d": f(head_d * 0.30), "n": 2.0}]})
    segs.append({"id": "neck", "role": "neck", "stations": [
        {"z": _r(neck_bot - 0.012 * H), "w": f(p["neck_w"] * 1.15), "d": f(p["neck_w"] * 1.15), "n": 2.0},
        {"z": _r(neck_bot + neck_len * 0.5), "w": f(p["neck_w"]), "d": f(p["neck_w"]), "n": 2.0},
        {"z": _r(head_bot + 0.02 * H), "w": f(p["neck_w"] * 1.02), "d": f(p["neck_w"] * 1.02), "n": 2.0}]})
    segs.append({"id": "torso", "role": "torso", "stations": [
        {"z": f(crotch + 0.0), "w": f(hip_w * 0.70), "d": f(pelvis_d * 0.80), "n": 2.2},
        {"z": f(crotch + 0.025), "w": f(hip_w * 0.97), "d": f(pelvis_d * 0.97), "n": tn},
        {"z": f(crotch + 0.05), "w": f(hip_w), "d": f(pelvis_d), "n": tn},
        {"z": f(waist_z), "w": f(waist_w), "d": f(waist_d), "n": tn},
        {"z": f(chest_z), "w": f(trunk_sh_w * 0.97), "d": f(chest_d), "n": tn},
        {"z": f(shoulder_z), "w": f(trunk_sh_w * 0.95), "d": f(chest_d * 0.88), "n": 2.4},
        {"z": f(shoulder_z + 0.015), "w": f(trunk_sh_w * 0.62), "d": f(chest_d * 0.70), "n": 2.2},
        {"z": _r(neck_bot + 0.004 * H), "w": f(max(p["neck_w"] * 1.6, trunk_sh_w * 0.30)), "d": f(chest_d * 0.45), "n": 2.2}]})
    arm_len = p["arm_len"]
    splay = p.get("arm_splay", 0.025)
    arm_cy0 = sh / 2 - arm_w / 2
    z_sh = shoulder_z
    z_el = z_sh - arm_len * 0.5
    z_wr = z_sh - arm_len * 0.93
    z_tip = z_sh - arm_len
    hand_w, hand_d = p["hand_w"], p["hand_d"]
    segs.append({"id": "arm", "role": "arm", "mirror": True, "k_m": f(0.004), "stations": [
        {"z": f(z_tip), "w": f(hand_w * 0.45), "d": f(hand_d * 0.6), "n": 2.2, "cy": f(arm_cy0 + splay)},
        {"z": f(z_wr - 0.45 * (z_wr - z_tip)), "w": f(hand_w), "d": f(hand_d), "n": 2.4, "cy": f(arm_cy0 + splay * 0.93)},
        {"z": f(z_wr), "w": f(p["wrist_w"]), "d": f(p["wrist_w"] * 0.95), "n": 2.2, "cy": f(arm_cy0 + splay * 0.9)},
        {"z": f(z_el - 0.35 * (z_el - z_wr)), "w": f(p["forearm_w"]), "d": f(p["forearm_w"] * 1.05), "n": ln, "cy": f(arm_cy0 + splay * 0.6)},
        {"z": f(z_el), "w": f(p["elbow_w"]), "d": f(p["elbow_w"] * 1.0), "n": ln, "cy": f(arm_cy0 + splay * 0.45)},
        {"z": f(z_el + 0.4 * (z_sh - z_el)), "w": f(arm_w), "d": f(arm_w * 1.05), "n": ln, "cy": f(arm_cy0 + splay * 0.2)},
        {"z": f(z_sh), "w": f(arm_w * 1.08), "d": f(arm_w * 1.1), "n": ln, "cy": f(arm_cy0)},
        {"z": f(z_sh + 0.018), "w": f(arm_w * 0.85), "d": f(arm_w * 0.9), "n": 2.1, "cy": f(arm_cy0 - 0.12 * arm_w)},
        {"z": f(z_sh + 0.030), "w": f(arm_w * 0.40), "d": f(arm_w * 0.5), "n": 2.0, "cy": f(arm_cy0 - 0.30 * arm_w)}]})
    segs.append({"id": "leg", "role": "leg", "mirror": True, "k_m": f(0.003), "stations": [
        {"z": f(ank * 0.6), "w": f(ankle_w * 1.1), "d": f(ankle_w * 1.2), "n": ln, "cy": f(leg_cy)},
        {"z": f(ank), "w": f(ankle_w), "d": f(ankle_w * 1.15), "n": ln, "cy": f(leg_cy)},
        {"z": f(calf_z), "w": f(calf_w), "d": f(calf_w * 1.1), "n": ln, "cy": f(leg_cy)},
        {"z": f(knee), "w": f(knee_w), "d": f(knee_w * 1.1), "n": ln, "cy": f(leg_cy)},
        {"z": f(knee + 0.5 * (crotch + 0.02 - knee)), "w": f((knee_w + thigh_top) * 0.5 * 1.04), "d": f((knee_w + thigh_top) * 0.55), "n": ln, "cy": f(leg_cy)},
        {"z": f(crotch + 0.02), "w": f(thigh_top), "d": f(thigh_top * 1.15), "n": ln, "cy": f(leg_cy)},
        {"z": f(crotch + 0.06), "w": f(thigh_top * 0.86), "d": f(thigh_top * 1.0), "n": 2.2, "cy": f(leg_cy - 0.1 * thigh_top)},
        {"z": f(crotch + 0.085), "w": f(thigh_top * 0.45), "d": f(thigh_top * 0.6), "n": 2.0, "cy": f(leg_cy - 0.2 * thigh_top)}]})
    segs.append({"id": "foot", "role": "foot", "axis": "x", "mirror": True, "k_m": f(0.003), "stations": [
        {"x": f(-0.30 * foot_l), "w": f(foot_w * 0.55), "d": f(foot_h * 0.85), "n": 3.0, "cy": f(leg_cy), "cz": f(foot_h / 2)},
        {"x": f(-0.18 * foot_l), "w": f(foot_w * 0.80), "d": f(foot_h), "n": 3.0, "cy": f(leg_cy), "cz": f(foot_h / 2)},
        {"x": f(0.20 * foot_l), "w": f(foot_w), "d": f(foot_h), "n": 3.0, "cy": f(leg_cy), "cz": f(foot_h / 2)},
        {"x": f(0.55 * foot_l), "w": f(foot_w * 0.95), "d": f(foot_h * 0.8), "n": 3.0, "cy": f(leg_cy), "cz": f(foot_h * 0.4)},
        {"x": f(0.70 * foot_l), "w": f(foot_w * 0.55), "d": f(foot_h * 0.45), "n": 2.6, "cy": f(leg_cy), "cz": f(foot_h * 0.23)}]})
    joints = [
        {"id": "hip_l", "pos": [0.0, f(leg_cy), f(p.get("hip_joint_z", crotch + 0.04))]},
        {"id": "knee_l", "pos": [0.0, f(leg_cy), f(knee)]},
        {"id": "ankle_l", "pos": [0.0, f(leg_cy), f(ank)]},
        {"id": "shoulder_l", "pos": [0.0, f(arm_cy0), f(z_sh - 0.01)]},
    ]
    out = {"schema": "design-profiles/0.1", "name": name, "kind": kind, "confidence": confidence,
           "height_m": H, "sources": sources, "segments": segs, "joints": joints}
    if notes:
        out["notes"] = notes
    return out


HEADER = ("# GENERATED by openhumanoid/design/references/make_references.py. Do not edit by hand.\n"
          "# {why}\n")

# ---- parameter tables (fractions of H) ---------------------------------------------------------------------------
HUMAN = dict(head_h=0.130, head_w=0.078, head_d=0.098, neck_len=0.032, neck_w=0.050, shoulder_w=0.270, arm_w=0.050,
             arm_len=0.43, hand_w=0.040, hand_d=0.022, wrist_w=0.028, forearm_w=0.048, elbow_w=0.045, crotch_z=0.470,
             hip_joint_z=0.520, hip_w=0.190, waist_w=0.170, waist_z=0.640, waist_d=0.075, chest_d=0.100, pelvis_d=0.090,
             thigh_w=0.092, knee_w=0.058, knee_z=0.285, calf_w=0.062, calf_pos=0.30, ankle_w=0.040, ankle_z=0.040,
             foot_len=0.152, foot_w=0.055, foot_h=0.039, torso_n=2.4, limb_n=2.1, head_n=2.2)
OPTIMUS = dict(HUMAN, head_h=0.140, head_w=0.082, head_d=0.100, neck_len=0.030, neck_w=0.048, shoulder_w=0.255,
               arm_w=0.047, waist_w=0.145, hip_w=0.172, thigh_w=0.088, knee_w=0.060, calf_w=0.066, ankle_w=0.042,
               crotch_z=0.480, hip_joint_z=0.520, knee_z=0.275, foot_len=0.150, foot_w=0.050, chest_d=0.095,
               pelvis_d=0.085, torso_n=2.6, limb_n=2.3, head_n=2.5)
ATLAS = dict(HUMAN, head_h=0.120, head_w=0.092, head_d=0.092, neck_len=0.030, neck_w=0.055, shoulder_w=0.265,
             arm_w=0.052, waist_w=0.165, hip_w=0.185, thigh_w=0.092, knee_w=0.065, calf_w=0.070, ankle_w=0.045,
             crotch_z=0.480, hip_joint_z=0.520, knee_z=0.275, foot_len=0.140, foot_w=0.058, chest_d=0.105,
             pelvis_d=0.095, torso_n=3.0, limb_n=2.6, head_n=2.0, calf_pos=0.28)
TOY = dict(HUMAN, head_h=0.200, head_w=0.200, head_d=0.170, neck_len=0.012, neck_w=0.090, shoulder_w=0.440,
           arm_w=0.110, arm_len=0.300, hand_w=0.090, hand_d=0.060, wrist_w=0.085, forearm_w=0.105, elbow_w=0.105,
           crotch_z=0.330, hip_joint_z=0.360, hip_w=0.340, waist_w=0.330, waist_z=0.500, waist_d=0.150, chest_d=0.170,
           pelvis_d=0.150, thigh_w=0.160, knee_w=0.150, calf_w=0.150, ankle_w=0.130, ankle_z=0.070, knee_z=0.180,
           foot_len=0.220, foot_w=0.150, foot_h=0.070, torso_n=7.0, limb_n=6.0, head_n=5.0, calf_pos=0.5, arm_splay=0.02)
# Sample for the pipeline demo only: NOT Adam's design. A 0.5 m body with a slightly athletic thigh (hard-point driven).
SLEEK = dict(HUMAN, head_h=0.140, head_w=0.084, head_d=0.100, neck_len=0.030, neck_w=0.046, shoulder_w=0.260,
             arm_w=0.050, waist_w=0.150, hip_w=0.185, thigh_w=0.112, knee_w=0.080, calf_w=0.088, ankle_w=0.060,
             crotch_z=0.470, hip_joint_z=0.505, knee_z=0.275, foot_len=0.160, foot_w=0.074, foot_h=0.045,
             ankle_z=0.050, chest_d=0.115, pelvis_d=0.110, waist_d=0.090, torso_n=2.6, limb_n=2.3, head_n=2.6,
             calf_pos=0.30, wrist_w=0.034, forearm_w=0.056, elbow_w=0.052, hand_w=0.048, hand_d=0.030,
             arm_len=0.40, arm_splay=0.06)

REFS = [
    ("human_canon", 1.75, HUMAN, "reference", "approximate",
     ["Drillis & Contini 1966 segment-length fractions as tabulated in Winter, Biomechanics and Motor Control of Human Movement (4th ed.), Fig. 4.1 (values recalled, not re-verified online)",
      "Silhouette widths (shoulder 0.27H, hip 0.19H, thigh/knee/calf) are textbook anthropometry, ±10%"],
     "Sanity anchor for the rubric bands; not a robot."),
    ("optimus_like", 1.73, OPTIMUS, "reference", "low",
     ["Height 1.73 m, mass ~56 kg: https://humanoid.guide/product/optimus-gen2 (aggregator, unconfirmed by Tesla)",
      "All other proportions: visual estimate from Tesla's public Optimus Gen 2 video stills (Dec 2023); no pixel measurement"],
     "Smooth white shells, small head with black visor, human proportions."),
    ("atlas_like", 1.90, ATLAS, "reference", "low",
     ["Height 1.9 m, mass 90 kg: Boston Dynamics Atlas product spec sheet dated 2025-12-23 (https://bostondynamics.com/wp-content/uploads/2026/01/atlas-spec-sheet.pdf, as reported by search; PDF not opened)",
      "All other proportions: visual estimate from Boston Dynamics' public electric-Atlas stills; no pixel measurement"],
     "Capsule/cylinder primitives blended smoothly, compact head with ring light."),
    ("toy_chibi", 0.50, TOY, "counter_example", "low",
     ["Synthetic counter-example: generic toy-robot proportions (large head, short wide boxy torso, stubby boxy limbs), drawn to resemble the first Adam CAD attempt's Roblox look"],
     "Boxy sections (n=5..7), head 20% of height, shoulder width 44% of height."),
]


def write(name: str, data: dict, why: str, out_dir: Path = HERE) -> Path:
    path = out_dir / f"{name}.yaml"
    path.write_text(HEADER.format(why=why) + yaml.safe_dump(data, sort_keys=False, width=140), encoding="utf-8")
    return path


def main() -> None:
    for name, H, params, kind, conf, sources, notes in REFS:
        write(name, humanoid_profiles(name, H, params, sources, kind, conf, notes), "Reference silhouette profile (approximate).")
    sample = humanoid_profiles(
        "sample_sleek_050", 0.50, SLEEK,
        ["Pipeline demo only. Proportions follow variants/adam/design-language.md (head ~14% H) and docs/design-method.md; NOT Adam's approved design."],
        "design", "approximate", "Demo input for the studio rig, metrics and critic. Hard points are the design-language thigh keep-out.")
    sample["hard_points"] = [
        {"id": "thigh_servos_l", "segment": "leg_l", "center": [0.0, sample["joints"][0]["pos"][1], 0.222], "size": [0.038, 0.028, 0.060], "margin_m": 0.003},
        {"id": "knee_servo_l", "segment": "leg_l", "center": [0.0, sample["joints"][0]["pos"][1], 0.1375], "size": [0.028, 0.022, 0.040], "margin_m": 0.003}]
    out = HERE.parent / "sample"
    out.mkdir(exist_ok=True)
    write("sample_sleek_050", sample, "Sample profiles (pipeline demo, not Adam).", out)
    print("wrote references:", [r[0] for r in REFS], "+ sample")


if __name__ == "__main__":
    main()
