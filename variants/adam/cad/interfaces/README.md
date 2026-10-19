# Adam v2 interfaces: region B (upper body) and the A <-> B contract

| File | What |
|---|---|
| `layout_v2a_upper.yaml` | packaging layout of region B (waist yaw, arms x2, neck), frozen concept V2a + ADR 0015 amendment; comments give every hard point's source |
| `contract_ab.yaml` | **the contract region A builds the pelvis to**: waist turntable split, 6805ZZ outer-race seat, keep-outs, design loads; electronics tray zone, mounting face and inserts; cable pass-throughs; power and bus topology |
| `generate.py` | writes `interfaces_upper.yaml` = CAD-foundation generator output for region B + the contract (`.venv/Scripts/python variants/adam/cad/interfaces/generate.py`) |
| `interfaces_upper.yaml` | generated; region B's parts are built from it and checked against it |

## The A <-> B contract in one table

| Interface | A (pelvis) provides | B provides |
|---|---|---|
| Waist yaw, axis (0, 0, 382) +z, +-60 deg | the **stator**: waist STS3215 in a housing in the pelvis (servo frame origin (0,0,382), body x -10.11..35.11, y +-12.36, z 347..382, horn up), horn relief r 10.6 above z 380.7, plug window in the cover; the **6805ZZ outer-race seat** (bore 37.10, race z 383.75..390.75, shoulder z 382.15..383.75 with inner d 33.8, wall >= 2) | the **rotor**: stock horn, torso hub (spigot d 25 in the inner race, bore 19.8 around the horn), torso floor from z 391.75 |
| Keep-outs | nothing above z 390.75 inside r 44; nothing inside r 13.5 for z 382.75..391.75 | stays above z 391.75 outside r 13.5 |
| Loads | stator + deck sized for 72.8 N*m fall moment, 486 N radial, 2.94 N*m stall torque (SF 3) | its own side (strength toolkit) |
| Electronics pocket | zone x -44..-16, y +-57, z 345..378 kept free; flat rear bulkhead face at x = -16 (normal -x) with 4 x M3 inserts at (y, z) = (+-52, 350), (+-52, 373) | tray with the BNO085 on grommets at (-26, 0, 361.5) and both bus adapters (tilted 25 deg, legs at y < 0, arms/head at y > 0). Pi 5, buck, star, fuse, Tattu 1300 pack are in the torso |
| Waist cables | an opening x -32..-16, y +-20 from z 380 down into the pocket | floor slot behind the axis + ~55 mm flat service loop (r 21..29 over +-60 deg); 4 leg feeds, 2 slim USB (bend r >= 15), arm/head bus data, IMU cable (4 x 28 AWG), waist-servo lead |
| Arms | pelvis/hip shells clear the arm sweep at shoulder roll >= 14 deg | publishes the swept volume with its export |

## Findings that changed the concept's packaging (reported to the maintainer)

1. **Electronics (contract v3, maintainer).** The hip-yaw links sweep the lower pelvis rear, so the pelvis keeps only a pocket
   (x -44..-16, y +-57, z 345..378) for the IMU and both bus adapters (v4). The Pi 5, buck, star, fuse and the Tattu 1300 pack are in the torso.
2. **Neck: pitch first.** For the yaw to turn about the head centre (amendment), the yaw servo sits inverted in the grown head and the pitch
   servo takes R1's front chest slot. The kinematic order becomes pitch -> yaw (the template has yaw -> pitch); the head is the only body
   affected (sim: swap the two neck joints and move the pitch axis to (30.8, 0, 441)).
3. **Fuse 18 A** (R1 post-sign-off: a 20 A fuse equals the WAGO 221-415 rating).
