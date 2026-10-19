# 0015: Adam concept frozen at v2 for full-body CAD

- **Status:** accepted by maintainer (2026-10-19). Bench-gated items noted below · **Scope:** variant:adam
- **Evidence:** variants/adam/reviews/R1-concept-2026-10-19.md (+ challenges 1–3), R2a-silhouette (+ packaging study §9), R2a-v2-2026-10-19.md, docs/software.md (18/18 SIL scenarios)

## Decision
Adam's concept for full-body CAD is **v2**, concept file `variants/adam/concepts/V2a-0p55-longarm.yaml`:
- **0.55 m, 23 DOF** (legs 2×6, waist yaw, neck yaw + pitch, arms 2×3, 2 grippers), with longer arms (upper arm 0.20 H, forearm 0.23 H).
- **Actuators:** STS3250 at hip roll and knees, STS3215 12 V elsewhere, on one 3S bus with **two bus adapters** (100 Hz control).
- Pi 5, BNO085, 3S 1850 mAh, star power, fuse/wiring per the R1 post-sign-off power findings. Knee range 0–110°.
- **Cost:** ~$1,545 delivered against the locked ≤ $1,600.
- **Dropped:** the L5c knee/ankle linkage (width moves rather than shrinks, custom metal, fall failure, assembly access).
- **R5:** pickup is accepted for table tops up to ~0.39 m (maintainer).
- **No deep squat is required** (maintainer). If the bench confirms margin, the knees may move to STS3215 (−$126).

## Bench-gated (do not block CAD; CAD keeps both options packaged)
- Knee actuator: STS3250 (default) or STS3215.
- Height 0.60 m: only if the STS3250 bench stall ≥ ~1.3× datasheet. CAD proceeds at 0.55 m.

## Rules for the CAD phase
- **Attainable parts only:** off-the-shelf parts purchasable online; no custom-machined metal unless absolutely needed (requirements, Should).
- **Every printed structural part passes** the geometry gate, ROM sweep, assembly-access check and strength/FEA before it's called done.
- **Vendor CAD models may be downloaded** (maintainer, 2026-10-19), license-checked and recorded in THIRD_PARTY.md; non-redistributable files stay local and gitignored.

## Amendment: upper-body CAD decisions (maintainer, 2026-10-19 evening)
Driven by real vendor servo dimensions:
- **Head:** grows a few mm (deeper / at the chin) so the neck yaw turns about the head centre and the pitch servo fits; visor-pill style kept.
- **Gripper:** sized for soda-can / ball objects (~70 mm opening, ~62 mm palm, so the hand is wider than the forearm).
- **Electronics bay:** in the **pelvis** (Pi 5, 2 bus adapters, BNO085 IMU near the COM, fuse, star distribution). Region B designs it as a tray with a mounting contract for region A.
- **Arms:** keep the ≥ 14° display cant (v2 profiles use 19.5°).
- **Bus adapters split by region** (maintainer, 2026-10-19), refined by the commander after region A found the hip-yaw link sweeps the lower pelvis rear: the **Pi 5 goes in the torso** with the arm/head-bus adapter, star, fuse and battery; the pelvis pocket (~28×114×35 mm) holds only the IMU, the leg-bus adapter and (if it fits) the buck. The pelvis rear stays at R2a depth and the hips keep full ROM.
- **Neck is pitch-first** (region B, accepted): the pitch servo sits in the front chest slot and the yaw servo in the enlarged head, turning about the head centre. The sim template's neck order must be swapped at integration.
- **Battery: Tattu 3S 1300 mAh** (maintainer, 2026-10-19): it fits behind the Pi 5 in the R2a torso; ~28 min runtime (≥ 15 min required); the 1850 would need a back 6 mm deeper. **Both bus adapters sit in the pelvis pocket** (IMU + leg adapter + arm/head adapter; 2 USB through the waist; commander call); the torso holds the Pi 5 + cooler, buck, star, fuse and pack.
