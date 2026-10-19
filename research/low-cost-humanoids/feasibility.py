"""Feasibility sketch: ~0.9 m, 23-DOF Adam built from the cheapest credible actuator class.

Run:  python research/low-cost-humanoids/feasibility.py   (prints the tables used in feasibility.md)

Inputs are the vendor/retailer numbers in actuators.yaml (access date 2026-10-19). Everything
that is our arithmetic or assumption is labelled. No measured data exists for any of it.
"""
from __future__ import annotations

# ---- actuator catalogue: (peak Nm, mass g, price USD aifitlab headline, price USD openelab-DDP or roboticscenter) ----
ACT = {
    "RS05": dict(peak=5.5, rated=1.6, g=191, usd=110, usd_alt=155),
    "RS00": dict(peak=14, rated=5, g=310, usd=125, usd_alt=185),
    "RS02": dict(peak=17, rated=6, g=405, usd=145, usd_alt=175),   # alt = openelab.com DDP 174.99
    "RS06": dict(peak=36, rated=11, g=621, usd=210, usd_alt=222),  # alt = openelab.com sale 221.99
    "RS03": dict(peak=60, rated=20, g=880, usd=225, usd_alt=250),  # alt = openelab.com sale 249.99
    "STS3215": dict(peak=2.9, rated=None, g=55, usd=20.9, usd_alt=20.9),  # repo catalog, 12 V steel gear
    "STS3250": dict(peak=4.9, rated=1.57, g=75, usd=74, usd_alt=97),
}

# ---- required peak torque, scaled from Adam (our arithmetic) ----
# Adam sizing (variants/adam/generated/sizing.md, 0.53 m, 2.52 kg): hip/knee/ankle-pitch peak 1.76-1.85 Nm,
# hip roll 1.66, ankle roll 0.97, hip yaw 0.42, shoulder pitch 0.22. scale.md: joint torque ~ h^3.3.
H_ADAM, H_NEW = 0.53, 0.90
K = (H_NEW / H_ADAM) ** 3.3
REQ_ADAM = {"hip_yaw": 0.42, "hip_roll": 1.66, "hip_pitch": 1.85, "knee": 1.85,
            "ankle_pitch": 1.76, "ankle_roll": 0.97, "shoulder_pitch": 0.22}
# Quasi-static walking requirement only. Push recovery / dance / sim-to-real margin: engineers use 2-3x.
# Bumi's published sim torque limits (hip/knee 60, hip yaw/roll 27, ankle 13, arm 5.5) at 0.98 m are the practitioner reference.

# ---- joint plan. 23 DOF: legs 12, waist 1, arms 8 (shoulder pitch/roll, elbow, wrist pitch), neck 2 ----
PLANS = {
    # lean: cheapest class that clears ~2x the scaled quasi-static requirement
    "lean": {
        "hip_yaw": "RS05", "hip_roll": "RS02", "hip_pitch": "RS06", "knee": "RS06",
        "ankle_pitch": "RS02", "ankle_roll": "RS05",
        "waist_yaw": "RS05", "shoulder_pitch": "RS05", "shoulder_roll": "RS05", "elbow": "STS3250",
        "wrist_pitch": "STS3215", "neck_yaw": "STS3215", "neck_pitch": "STS3215",
    },
    # comfortable: bigger margin, closer to Bumi's torque classes (hips 27 Nm, ankles 13 Nm)
    "comfortable": {
        "hip_yaw": "RS00", "hip_roll": "RS06", "hip_pitch": "RS06", "knee": "RS06",
        "ankle_pitch": "RS02", "ankle_roll": "RS00",
        "waist_yaw": "RS00", "shoulder_pitch": "RS05", "shoulder_roll": "RS05", "elbow": "RS05",
        "wrist_pitch": "STS3215", "neck_yaw": "STS3215", "neck_pitch": "STS3215",
    },
}
COUNT = {  # per-joint multiplicity (mirrored joints x2)
    "hip_yaw": 2, "hip_roll": 2, "hip_pitch": 2, "knee": 2, "ankle_pitch": 2, "ankle_roll": 2,
    "waist_yaw": 1, "shoulder_pitch": 2, "shoulder_roll": 2, "elbow": 2, "wrist_pitch": 2,
    "neck_yaw": 1, "neck_pitch": 1,
}
GRIPPER_STS3215 = 2  # R5 pick-up; not counted in the 23 DOF

# ---- non-actuator parts (our estimates, USD; not researched line by line) ----
OTHER = {
    "battery 12S Li-ion/LiPo ~100-150 Wh (48 V class) + 12S charger": 190,
    "compute: Raspberry Pi 5 + CAN-FD interface x2-3 (USB-CAN/HAT) + IMU": 220,
    "power: fused distribution, 48->12 V and 48->5 V converters, e-stop, contactor": 110,
    "structure: printed shell + machined 6061 hip/thigh/shank brackets (online CNC) + fasteners + bearings": 520,
    "cables, connectors, heat sinks (QDD need them at rated torque)": 90,
}
OTHER_MASS_KG = {"battery": 0.9, "compute+wiring": 0.7, "structure+shell": 3.6}
# structure: Adam 0.95 kg at 0.53 m (sizing.md) -> x (0.9/0.53)^3 = 4.6 kg printed-only; assume hybrid Al/print ~3.6 kg.

DELIVERED_FACTOR_ADAM = 1.40  # Adam R1 accounting: sticker -> delivered incl tax, shipping, spares, 10 % contingency (~$1,100 -> ~$1,540)


def tally(plan: dict[str, str], price_key: str) -> tuple[float, float, int, dict]:
    cost = mass = n = 0
    by_class: dict[str, list] = {}
    for joint, model in plan.items():
        c = COUNT[joint]
        cost += ACT[model][price_key] * c
        mass += ACT[model]["g"] * c
        n += c
        by_class.setdefault(model, [0, 0, 0])
        by_class[model][0] += c
        by_class[model][1] += ACT[model][price_key] * c
        by_class[model][2] += ACT[model]["g"] * c
    cost += GRIPPER_STS3215 * ACT["STS3215"][price_key]
    mass += GRIPPER_STS3215 * ACT["STS3215"]["g"]
    by_class["STS3215"][0] += GRIPPER_STS3215
    by_class["STS3215"][1] += GRIPPER_STS3215 * ACT["STS3215"][price_key]
    by_class["STS3215"][2] += GRIPPER_STS3215 * ACT["STS3215"]["g"]
    return cost, mass / 1000, n, by_class


def main() -> None:
    print(f"scale factor (0.9/0.53)^3.3 = {K:.2f}")
    print("scaled quasi-static peak requirement at 0.9 m (Nm): " + ", ".join(f"{j} {v*K:.1f}" for j, v in REQ_ADAM.items()))
    other_total = sum(OTHER.values())
    for name, plan in PLANS.items():
        print(f"\n=== plan: {name} ===")
        for pk, label in (("usd", "aifitlab headline"), ("usd_alt", "US-facing DDP/stocked")):
            cost, mass, n, by = tally(plan, pk)
            sticker = cost + other_total
            print(f"[{label}] actuators ${cost:,.0f} ({n} joints + {GRIPPER_STS3215} grippers), other ${other_total}, "
                  f"parts sticker ${sticker:,.0f}, delivered x{DELIVERED_FACTOR_ADAM} = ${sticker*DELIVERED_FACTOR_ADAM:,.0f}")
        cost, mass, n, by = tally(plan, "usd")
        for m, (q, c, g) in by.items():
            print(f"   {m:8s} x{q:2d}  ${c:7.0f}  {g/1000:5.2f} kg")
        total_mass = mass + sum(OTHER_MASS_KG.values())
        print(f"   actuator mass {mass:.2f} kg + other {sum(OTHER_MASS_KG.values()):.1f} kg = all-up {total_mass:.1f} kg")
        # margin check against scaled requirement
        for j, req in REQ_ADAM.items():
            key = j if j in plan else None
            if key:
                pk = ACT[plan[key]]["peak"]
                print(f"   {j:15s} {plan[key]:8s} peak {pk:5.1f} Nm vs scaled quasi-static {req*K:4.1f} Nm -> margin {pk/(req*K):4.1f}x")
    print("\nother parts:")
    for k, v in OTHER.items():
        print(f"  ${v:4d}  {k}")
    # mass sanity: mass ~ k h^2.3 fit from Adam 3.7 kg at 0.55 m
    print(f"\nmass-fit check: 3.7 kg x (0.9/0.55)^2.3 = {3.7*(0.9/0.55)**2.3:.1f} kg (Bumi claims 12-17 kg)")
    print("budget lock $1,600 vs delivered:")
    for name, plan in PLANS.items():
        cost, *_ = tally(plan, "usd")
        print(f"  {name}: actuators alone = {cost/1600:.2f}x the whole $1,600 lock (headline prices)")


if __name__ == "__main__":
    main()
