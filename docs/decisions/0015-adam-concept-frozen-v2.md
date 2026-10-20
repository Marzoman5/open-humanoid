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
- **Gripper: rotary claw (SO-ARM style)** (commander, following the maintainer's can/ball choice): one jaw on the gripper-servo horn plus a fixed finger on a 62 mm palm; 0–80° gives ~70 mm at the tips. A parallel gripper would need a ~106 mm hand. **Integration must update the sim template:** the gripper joint becomes revolute, and the neck order becomes pitch-first.
- **Neck pitch** pivots at the neck base (3, 0, 462) on a torso-frame tongue, driven from the front-slot servo through a short printed 4-bar (~1.8:1); direct drive would hit the shoulder-servo retainers at ±30°. **Integration:** sim neck-pitch axis at (3, 0, 462), with the ratio and speed applied.
- **Waist bump stops** (commander, 2026-10-19): the 6805ZZ seat ring can't carry the 72.8 N·m fall moment at SF 2 within the cable-loop envelope, and a single-row bearing shouldn't take that tilt. Region A has a stop ring at r 30–44 (top ≤ z 390.75) and region B has torso-floor stop pads with a 1.0 mm gap, carrying fall tilt; the bearing takes only service loads (contract v4.3).
- **Waist captured flange** (commander, 2026-10-19): stops only push, and a single-row 6805 holds only ~1 kN axially, so the torso floor flange is captured between A's lower stop ring and an A-side upper retaining ring (1.0 mm gaps both sides). Tilt reacts in compression on two stops; nothing goes in tension through the bearing or horn (contract v4.4). The **waist fall load uses the strength toolkit's standard fall policy** (the same model as the legs), not an ad-hoc 30 g figure, so every part is judged consistently.
- **Inter-leg clearance** (commander, 2026-10-19, conditional): the real forks are ~60 mm wide (vs 52 mm assumed), so at 70 mm hip spacing the legs are 4.5 mm apart. Hip yaw toe-in is limited to ~−15° and adduction to ~−1°, and one dance pose collides; walk, turn, push, pickup, squat and lunge poses pass. Accepted with CAD-limited and coordinated limits recorded for the engine and runtime. **Condition:** at integration, R10 (especially lateral-in) and the dance are re-run under these limits; if R10 fails, widening to 80 mm hip spacing goes to the maintainer (look impact).
- **Waist load path, final** (commander, 2026-10-19, superseding the captured flange): with the standard-fall-policy load (22 N·m tilt, 393 N radial), the 6805 seat ring passes on its own (OD 42, root fillet, Loctite 641 retention). The A-side upper ring was dropped (no tool access, fails at 3–4 mm). A lower stop ring stays as an overload backstop only, as partial arcs inside the waist silhouette. Conditional on the bearing's own moment/static check at 44 N·m; if it fails, an off-the-shelf thin-section, four-point or paired bearing (contract v4.5).
- **Waist yaw REMOVED** (maintainer-approved 2026-10-19, "if you deem it won't be noticeable, remove it"): the 6805 waist bearing fails the fall tilt (static SF ~0.5–0.7), and no off-the-shelf bearing fits the envelope (the THK RB2508 also fails). Evidence it won't noticeably affect walking or mobility: the packaging study (no-waist margins 1.264 vs 1.247), the SIL (walk, turn and push recovery never use the waist), and the pickup planner (the waist never twists). The loss is torso twist in dances; R7 is met by neck yaw ±90° plus stepping turns. **DOF 23 → 22**, ~−$25 servo/bearing. The torso–pelvis joint is a rigid bolted flange (contract v5). **Integration:** remove the waist joint from the sim template and the runtime config; re-run the concept engine and the 18 SIL scenarios.
