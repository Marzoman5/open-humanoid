# Adam v2 interfaces: region B (upper body) and the A <-> B contract

| File | What |
|---|---|
| `layout_v2a_upper.yaml` | packaging layout of region B (torso fixed to the pelvis, arms x2, neck), frozen concept V2a + ADR 0015 amendment; comments give every hard point's source |
| `contract_ab.yaml` | **the contract region A builds the pelvis to**: bolted torso mount (v5: deck, bolts, nut traps, dowels), keep-outs, design loads; electronics tray zone, mounting face and inserts; cable pass-throughs; power and bus topology |
| `generate.py` | writes `interfaces_upper.yaml` = CAD-foundation generator output for region B + the contract (`.venv/Scripts/python variants/adam/cad/interfaces/generate.py`) |
| `interfaces_upper.yaml` | generated; region B's parts are built from it and checked against it |

## The A <-> B contract in one table

| Interface | A (pelvis) provides | B provides |
|---|---|---|
| **Torso mount (v5: fixed, no waist joint)**, plane z 382.15 | flat **deck** top z 382.15 over x -12.7..45, \|y\| <= 19; 4 x M3 ISO 4762 driven **upward** from inside the pelvis (2.5 mm ball-end key, ISO 7089 washers) at (-4, +-13), (26, +-13); 2 x Ø4 x 12 ISO 8734 dowels at (17, +-17), 6 mm in A; key corridors Ø8 x 30 below the heads | solid **pad** under the floor, x -12.7..32.5, \|y\| <= 22, z 382.15..391.75, with 4 side-entry **nut traps** (ISO 7093 washer + ISO 4032 nut, 5.0 mm of pad under the washer) and the dowel holes (6 mm) |
| Keep-outs | nothing of A above z 382.15 inside the waist band | nothing of B below z 382.15; nothing of B beyond the shrunk waist band (x <= 33.5 at \|y\| 13) |
| Loads | deck and bolt heads for the mount wrench (fall policy + stall, no waist cap): B publishes it in `upper/strength/waist_design_load.json`; A's estimate ~850 N per bolt (side tilt, SF 2) | nut traps, pad and floor checked by B at the same wrench |
| Electronics pocket | zone x -44..-16, y +-57, z 343.6..378.6 kept free (v4.2: 35 mm, adapters vertical); flat rear bulkhead face at x = -16 (normal -x) with 4 x M3 inserts at (y, z) = (+-52, 349.6), (+-52, 372.6) | tray with the BNO085 on grommets at (-26, 0, 361.1) and both bus adapters (vertical, legs at y < 0, arms/head at y > 0). Pi 5, buck, star, fuse, Tattu 1300 pack are in the torso |
| Waist cables | the opening x -32..-16, \|y\| <= 20 from z 380 down into the pocket (unchanged) | fixed U-notch in the floor's back edge x -27..-19.2, \|y\| <= 16 (no service loop): 4 leg feeds, 2 slim USB, arm/head bus data, IMU cable |
| Arms | pelvis/hip shells clear the arm sweep at shoulder roll >= 14 deg | publishes the swept volume with its export |

## Findings that changed the concept's packaging (reported to the maintainer)

1. **Electronics (contract v3, maintainer).** The hip-yaw links sweep the lower pelvis rear, so the pelvis keeps only a pocket
   (x -44..-16, y +-57, z 343.6..378.6) for the IMU and both bus adapters (v4.2). The Pi 5, buck, star, fuse and the Tattu 1300 pack are in the torso.
2. **Neck: pitch first.** For the yaw to turn about the head centre (amendment), the yaw servo sits inverted in the grown head and the pitch
   servo takes R1's front chest slot. The kinematic order becomes pitch -> yaw (the template has yaw -> pitch); the head is the only body
   affected (sim: swap the two neck joints and move the pitch axis to (30.8, 0, 441)).
3. **Fuse 18 A** (R1 post-sign-off: a 20 A fuse equals the WAGO 221-415 rating).

## Waist load path: decision history (contract versions)

| Version | Decision | Why it changed |
|---|---|---|
| v1-v3 | 6805ZZ ring bearing (A's outer-race seat, B's inner race on the torso hub) carries the waist; v4.3 added bump stops (A ring r 30-44, six B floor pads, 1 mm gap) for a 72.8 N*m fall tilt (1.65 kg x 30 g x 0.15 m, ad hoc) | region A: the seat ring could not carry 72.8 N*m at SF 2 |
| v4.4 | captured flange: B's floor ring r 30-40 between A's lower stop ring and an A upper retaining ring on posts; design load recomputed from the G-strength fall policy: **22 N*m tilt, 393 N radial** (side fall onto a shoulder bracket) | the stops could only push: tension had no path |
| **v4.5** | **the 6805 seat is the designed load path** (A: 34 MPa vs 57 MPa allowable at 22 N*m x SF 2, Loctite 641); A keeps lower **backstop arcs** at a 1.0 mm gap under B's flat floor disc (r 40) as overload protection only; upper ring and posts dropped | region A: the upper ring could not be fastened (no tool access from above or below) and failed at 3-4 mm; with the policy load the seat passes |
| **v5** | **no waist joint**: the torso is bolted rigidly to the pelvis deck (plane z 382.15): 4 x M3 driven up from the pelvis into captive nuts in B's pad, 2 x Ø4 dowels for torque and shear; fixed cable notch, no loop; DOF 23 -> 22 | region A: the 6805 seat fails at the fall tilt (static SF ~0.5-0.7) and no off-the-shelf bearing fits; walking, turning, push recovery and pickup never use the waist (L2, SIL, pickup planner). B moved A's front bolt pair from x 38 to x 26 (the nut traps would leave the waist band) |
