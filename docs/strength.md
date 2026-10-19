# Structural strength of printed parts (G-strength)

*Task T-20261019-a026 · `openhumanoid/cad/strength/` · research C7 and `research/methods/d-structural-fea-3d-print.md` · maintainer requirement: "this should work first try, so we need tests on strength".*

A CAD part that fits can still snap. The CAD foundation checks fit; this layer checks **strength**: for every printed part, for every load the robot can put on it, it computes a margin, names the failure mode and says PASS or FAIL. It is a screening tool (analytic sections and fastener checks for every part, finite elements for the worst parts) built on stated assumptions. **The physical tests in section 9 replace the assumptions**; until they are done a PASS means "no analytic or FE reason to expect a break", not "proven".

```bash
python -m openhumanoid.cad strength variants/adam/cad/leg_v3.py                      # builds the CAD (about 1 min), prints the margin table, exit 1 on FAIL
python -m openhumanoid.cad strength variants/adam/cad/leg_v3.py --out variants/adam/cad/strength/after
python -m openhumanoid.cad strength variants/adam/cad/leg_v3.py --part foot_l --fea foot_l --fea-case fall_pivot_fwd   # + FEA, two mesh densities
python -m openhumanoid.cad strength variants/adam/cad/leg_v2.py --config variants/adam/cad/strength_leg_v2.yaml        # the "before"
python -m openhumanoid.cad strength <builder.py> --cache model.pkl                    # reuse a pickled strength model (skips the CAD build)
python -m pytest tests/test_strength.py tests/test_strength_fea.py -q                  # 17 tests, about 15 s  (-m slow adds the full-leg run)
```

Outputs (with `--out DIR`): `strength_report.json` (parts, scenarios, context, the rows with margin < 1.5 and the worst row of every part x case x check), `strength_table.md`, `fea_report.json`, `fea_<part>.png`.

## 1. Method in one picture

```
spec / concept report ──► load cases ──► chain solver ──► load path ──► per part:  sections (beam) ─┐
 (robot mass, joint peaks)   (cases a-d)   (joint wrenches)  (who carries what)     fasteners / horn  ├─► margin = allowable / (SF x demand)
 catalog (stall torques)                                                            bearing seats     │   PASS at >= 1
 print_materials.yaml ──► material model (XY / Z, endurance) ──────────────────────► FEA (worst parts)─┘
```

1. **Load cases** (`loadcases.py`): a pose, external forces, an inertial field, each with its provenance (section 3).
2. **Chain solver** (`chain.py`): the static wrench each joint passes between the distal subtree and the servo, in the world frame, plus the joint torque it implies. Sustained cases are **scaled down until no joint exceeds what its servo can hold** (concept peak x 1.25 for walking, stall for stall and push, 2 x stall for falls: a servo back-driven in a fall slips or strips before the structure sees more).
3. **Load path** (`loadpath.py`): which printed part receives the servo case (housing), the horn (root bracket), the idler bearing (idler plate), the pin (cover); a tree of the printed parts of one link from the fastener sites; every part ends up with a list of applied loads in equilibrium with the reaction it hands to its parent. Joints with an idler carry the non-axial moment as a couple between horn and bearing, single-sided joints carry it through the horn.
4. **Analytic checks** (`analytic.py`, `fasteners.py`, `joints.py`): cut the part with planes along x, y, z every 2 mm; the loads on one side of a plane give the internal wrench; the section is the print profile weighted real cross-section (perimeters solid, infill at its volume fraction). Checks: axial + bending + shear + torsion with Kt at internal corners, layer adhesion (the allowable depends on the angle between the plane normal and the build direction), fatigue, Euler buckling of slender members, horn screw bearing / tear-out / pull-through / shear, bolted connections (screw group + compression-only contact patch, preload), insert pull-out, bearing-seat pressure and ligament, assembly clamp.
5. **FEA** (`fea.py`, `fea_run.py`): gmsh tetrahedra from the part's STEP, quadratic tets in scikit-fem, transversely isotropic material along the build direction, loads distributed over bolt-circle / bearing / site patches, failure index = stress / weakest-direction allowable. Two mesh densities per part (section 7).

## 2. Material model

`research/methods/print_materials.yaml` gives XY and Z (across layers) strength, modulus and elongation per material. The check never uses a bulk number: at every plane the allowable is

```
allowable(phi) = process_knockdown / sqrt( sin^2(phi)/sigma_xy^2 + cos^2(phi)/sigma_z^2 ),   phi = angle between the plane normal and the BUILD direction
```

(phi = 0: the plane lies in a layer, the load pulls layers apart: Z value; phi = 90 deg: XY value). Shear = 0.5 x tensile of the same direction, bearing = tensile, compression across layers is not a delamination mode (XY value).

| Material (print_materials.yaml) | XY / Z MPa | Z / XY | endurance fraction of UTS | note |
|---|---|---|---|---|
| PETG (PolyMax) | 37.9 / 29.4 | 0.78 | **0.10 (assumption)**: no PETG value found, the PLA value is borrowed | covers, structure of leg_v2 |
| PLA / PLA+ | 41.3 / 32.4, 49.8 / 36.5 | 0.78, 0.73 | 0.10 (sourced, Ezeh & Susmel 2018) | brittle across layers |
| ASA | 43.8 / 32.0 | 0.73 | 0.25 (sourced, Rodrigues 2026) | needs a ~90 C chamber |
| **PA12-CF10** | 71.6 / 43.3 | 0.60 | 0.17 (assumption: neat Nylon 12 value) | **leg_v3 structure**; hardened nozzle, dry spool, anneal |

Knock-downs (`strength.yaml`): **process 0.8** (datasheet coupons are 100 % infill on a tuned printer, vendors say "not for design"); infill enters through the weighted section, not a blanket factor; design life 5e5 cycles with the S-N slope 5.5 of the PLA reference curve (the endurance limit at 2e6 cycles x 1.29).

## 3. Load cases and where each number comes from

Robot: R1 Path 1 at **0.60 m** (the CAD leg is the 0.60 m stand-in layout), **5.11 kg** shelled nominal (R1 package 2.2), STS3250 at hip roll and knees, STS3215 elsewhere. `S` = sourced, `D` = derived from sourced numbers, `A` = **assumption** (with the test that replaces it).

| Case (class) | What is applied | Numbers | Prov. |
|---|---|---|---|
| `stand`, `walk_toe/heel/lat/med` (walk, SF 3, fatigue) | single support on one foot, stance knee flexion 45 deg, ground reaction 1.5 x weight (75 N) at a centre of pressure offset = concept peak ankle torque / force (x 21 mm, y 11 mm); tangential force fitted so the hip torque equals its concept peak; scaled so no joint exceeds 1.25 x its concept peak | peak torques per joint from `R1-P1-0p60-.../report.json` (hip roll 3.1, knee 2.7, ankle pitch 1.6, hip yaw 1.5, hip pitch 1.3, ankle roll 0.8 N.m: walk, squat, turn, dance) | peaks **S**; 1.5 W **A**; 1.25 headroom **A** (the replay is open-loop: a lower bound) |
| `stall_<joint>_<pt>` (stall, SF 1.5) | each joint pushing its catalog stall torque (STS3215 2.94, STS3250 4.90 N.m) through a blocked toe / heel / foot edge; scaled so no other joint exceeds stall | 24 cases | stall **S** (catalog), lever **D** |
| `push_fwd/back/lat` (push, SF 3, fatigue) | R10 absolute impulse 0.45 N.s over 50 ms = 9 N, ankle at stall | | impulse **S** (provisional R10), 50 ms **A** |
| `fall_pivot_*` (fall, SF 2) | toppling about the toe / heel / side edge: ground reaction 2 x weight, servo-limited (2 x stall) | | 2 x **A** |
| `landing_heel/toe/flat` (fall) | stumble / step-down landing on one foot, 3 x weight, servo-limited | | 3 x **A** |
| `fall_contact_{fwd,back,side}_<link>_{protected,rigid}` | floor contact on the extreme point of each **exposed** link; force = share x fall energy / stopping distance x peak factor | E = m g dh = 13.5 J (CoM 0.55 H, lying 0.06 m); share 0.25; **protected** stop 10 mm -> 507 N, **rigid** 3 mm -> 1691 N; peak/avg 1.5. `protected` is gated (servo-limited to 2 x stall, side force 150 N and side moment 1 x stall at single-sided joints), `rigid` is reported, never gated | E, CoM **S/D**; share, distances, peak factor, servo caps **A** |
| `fall_inertial_<dir>_*` (fall) | the whole leg under n g (27 g protected, 90 g rigid), supported at the hip | n = dh / d | **A** |
| `handling_lift_by_foot` + fastener checks | robot lifted by one foot, +50 % jerk; hand-tightened screw clamp 250 N (M3) against insert pull-out | | **A** |

Fall model, stated plainly. No source gives a stopping distance or peak factor for 0.5 m printed humanoids (`research/methods/d` section 3), so energy method: the leg contact point absorbs `phi E` over `d`, with `d` = 10 mm for a **TPU bumper / compliant shell** (design intent, gated) and 3 mm for bare printed part on a hard floor (informational: **every part fails it by 5 to 100 x, so the leg needs bumpers and the servos as the fuse**). The links the floor can touch directly are set in `variants/adam/cad/strength.yaml` (`fall.exposed_links`: thigh, shank, ankle, foot; the hip yaw and roll links are assumed inside the pelvis shell, re-run when R2a shells exist). **Drop test: section 9.**

## 4. Safety-factor policy

`margin = allowable / (SF x demand)`; PASS at >= 1. The SF multiplies the demand; the allowable is the weakest direction after the knock-downs.

| Class | SF | Gated | Fatigue check | Source |
|---|---|---|---|---|
| walk, push | **3.0** | yes | yes: peak stress x Kt <= endurance at 5e5 cycles (SF 1, the endurance value is already a 95 % survival bound) | brief; research/methods/d 7 |
| stall | **1.5** | yes | no | brief (the servo cannot push more) |
| fall (protected) | **2.0** | yes | no | brief |
| fall_rigid | 1.0 | **no** | no | the unprotected bound |
| handling | 2.0 (clamp 1.0: self-limiting) | yes | no | |

Bolt tension: the safety factor multiplies only the external part, the preload is a known load. Preload credit = 50 % of the hand-tight clamp (assumption; section 9).

## 5. DFM rules added (`openhumanoid/cad/dfm.yaml`)

| Rule | Value | Why |
|---|---|---|
| `fillet.min_internal_mm` | 2.0 (and r >= 0.5 t for thicker plates) | Kt = 1 + 0.35 sqrt(t/r) (fit of the Peterson shoulder-fillet chart): 1.5 at t = 4.3 mm; a sharp printed corner counts as r = 0.3 mm (Kt 2.3) |
| `fillet.default_mm` / `cantilever_root_mm` | 3.0 / 4.0 | what the helpers apply |
| `cantilever_rules` | ribs or gussets, not a thicker plate, when a loaded plate's root modulus is < 4x what the check needs; gusset 3.2 mm at 45 deg; print so the bending stress runs along the filaments | the foot |
| `structural_print` | 4 / **6 perimeters** (structural / load path), infill by part role (bracket 40 %, foot sole 60 %, cover 25 %, bumper TPU 15 %) | stress lives in the skin |

**Helpers apply internal fillets by default**: `Housing.build()` rounds the concave edges its unions create (`fillets.fillet_internal`: guarded, one valid solid that gained volume, radius reduced when a vertex blend fails, nothing skipped silently; `corners.py` reports the corners that remain). `horn_mount(washer_od=)` and `screw_clearance(washer_od=)` widen the counterbore for ISO 7089 washers; horn screw lengths follow the plate thickness; `core.mesh_of` retries finer tessellation until the STL is watertight.

## 6. Print-orientation and the builder contract

Orientation matters twice: the allowable depends on the angle to the build direction (section 2) and heat-set inserts and screws must not pull along the build axis (DFM `insert_boss.axis_rule`). leg_v3 prints the thigh and shank standing on their front face (up = +x), the foot, idler plates and roll plate on their side (+y), the ankle bracket and covers upright (+z). The foot is printed on its side so the plate (z) and the sole and ribs (x) bend in-layer.

Builder contract (a variant's `build(ctx) -> Assembly`): purchased parts named `servo_<joint>`, `horn_<joint>`, `bearing_<joint>` (+ `shaft_`, `shaftb_`) with `Part.mass_kg`; printed parts `process == "fdm"` with `Part.material` and `Part.print_up`; fastener `Site`s with `mates`; a variant `cad/strength.yaml` (robot mass, concept report, design actuators, exposed links, print profile per part). Nothing in `openhumanoid/cad/strength/` names Adam.

## 7. FEA and convergence (PARTIAL: work paused by the maintainer, see the handoff)

Final foot at the fall pivot (`--fea foot_l --fea-case fall_pivot_fwd`): 28 496 -> 85 640 tets (quadratic elements), hot-spot mean failure index changes 1.4 %, peak away from the loads 12.0 %, worst-1 % mean 9.7 %. FE normal stress at the analytic fibre 21 MPa against 2.2 MPa nominal beam stress: the FE peak (index 0.82 away from the loads, margin 0.61 with SF 2) sits on the thin 5.3 mm plate between the two tall ribs next to the horn bolt circle: a local plate-bending effect the analytic section and fastener checks do not see. The leg_v2 foot before the redesign showed a plate-root and sole failure index above 2 over most of the sole (`variants/adam/cad/strength/before/` is to be regenerated). The earlier foot geometry had an 80 MPa compressive hot spot at a sharp re-entrant step; the FE found it, the analytic sections did not, and the step became a 45 degree ramp. `fea_run.py` reports coarse and fine peaks, the change, and FE against analytic stress; the cantilever test (tests/test_strength_fea.py) matches beam theory within 10 % and two densities agree within 10 %. **TODO: regenerate before/after FEA tables for foot, thigh, ankle bracket and roll plate (handoff, next step 2).**

## 8. Validation on the CAD-foundation leg: leg_v2 (before) to leg_v3 (after)

Final leg_v3 analytic result (`python -m openhumanoid.cad strength variants/adam/cad/leg_v3.py`, 75 load cases): **12 of 15 printed parts PASS** (leg_v2: the three covers only). Worst gated margin per class, after (before values are regenerated by the handoff step 2):

| part | walk | push | stall | fall | handling | verdict |
|---|---|---|---|---|---|---|
| foot_l | 2.04 | 1.46 | 11.10 | 1.48 | 3.40 | PASS |
| ankle_bracket_l | 1.05 | 3.35 | 5.94 | 2.03 | 4.06 | PASS |
| ankle_idler_l | 3.19 | 6.50 | 18.93 | 4.03 | 8.13 | PASS |
| shank_l | 1.34 | 1.19 | 8.14 | 4.59 | 9.22 | PASS |
| shank_idler_l | 2.37 | 5.66 | 8.08 | 4.93 | 10.05 | PASS |
| thigh_l | 1.20 | 2.78 | 6.65 | 4.64 | 9.52 | PASS |
| thigh_idler_l | 1.92 | 3.00 | 5.49 | 4.18 | 10.28 | PASS |
| cover_knee_l, cover_ankle_pitch_l, cover_hip_pitch_l, cover_hip_roll_l, cover_ankle_roll_l | >= 1.42 | >= 5.15 | >= 9.27 | >= 1.48 | >= 36 | PASS |
| yaw_bracket_l | 3.18 | 4.21 | 8.49 | **0.80** | 4.96 | **FAIL** |
| roll_plate_l | **0.67** | 1.35 | 1.20 | **0.28** | 1.03 | **FAIL** |
| roll_cradle_l | 5.39 | 18.39 | 9.28 | **0.84** | 1.37 | **FAIL** |

What failed in leg_v2 and what fixed it: the foot was the thin 90 degree cantilever (4.3 x 28 mm plate on a 3.2 mm sole, sharp root, printed standing so the root bend ran across the layers: margin 0.03 walking, 0.06 at the toppling pivot); fix = 8 mm stepped plate with a 45 degree ramp, 6.5 mm sole, two tall and one low rib, 2 to 4 mm fillets, washers under the horn screws, PA12-CF printed on its side. Thigh, shank, ankle bracket: web torsion and plate bending in 3.2 to 6.5 mm sections with sharp corners (0.02 to 0.07): web 10 mm, plates 8 mm, fillets from `Housing.build`, CF-nylon, orientation chosen per part. All covers and brackets: first failure was walking fatigue at 3 to 4 MPa allowable (PETG 10 % of UTS). Open items (the three FAIL parts) need an architecture change at the hip, not more thickness; see the handoff.

CAD checks on leg_v3: geometry gate PASS, ROM sweep PASS within `variants/adam/cad/strength/layout_leg_v3.yaml` (hip pitch [-108, +33] instead of [-110, +40]), assembly access PASS. Clay renders: `docs/strength/foot_before_after.png`, `thigh_before_after.png`, `ankle_bracket_before_after.png`; FE picture of the foot before the final ramp: `variants/adam/cad/strength/after/fea_foot_l_pivot.png`.

## 9. Physical tests that replace the assumptions (do these before the full print)

| # | Test | Replaces | How | Pass |
|---|---|---|---|---|
| 1 | **Coupons**: 5 tension coupons per orientation (XY, Z) printed on the real printer in the real material and profile (PETG and PA12-CF), plus 3 tension-tension fatigue coupons at 10 % and 25 % of UTS (R = 0.1, 5e5 cycles) | process knock-down 0.8, Z / XY ratios, PETG and CF-nylon endurance fraction (0.10 / 0.17), notch sensitivity | print_materials.yaml values are vendor coupons "not for design" | measured allowable >= the model's |
| 2 | **Foot cantilever coupon**: print the ribbed foot from `leg_v3.py`, clamp the horn plate, load the toe with a luggage scale to 3 x the pivot load (~250 N) | foot margins, Kt of the fillets, rib orientation | `foot_l` at the fall pivot load (82 N x 90 mm) | no crack, tip deflection within 30 % of the FEA |
| 3 | **Drop test, 0.30 m, instrumented**: a mass-matched robot (5 kg, servos, no power) dropped forward, sideways and backward onto a hard floor with a 3-axis accelerometer (>= 2 kHz) on the pelvis and one on a shank | fall energy share (0.25), stopping distances (10 mm bumper, 3 mm rigid), peak / average (1.5) | with and without 10 mm TPU bumpers | measured peak force x 1.0 <= the protected case (507 N) |
| 4 | **Servo overload**: clamp one STS3215, hang a weight from a horn lever, find (a) the radial force at which shaft play grows, (b) the side moment, (c) the back-drive torque at which the gears slip | `side_force_n` 150 N, `side_moment_over_stall` 1, `back_drive_over_stall` 2 | the servos are the fuse in every fall case | values >= the assumptions, otherwise the fall cases have to be re-run with them |
| 5 | **Insert pull-out**: 3 heat-set M3 inserts per orientation in PETG and CF-nylon, pulled with a force gauge | M3 pull-out 300 N (25 % of an unverified 1150 N) | | >= 300 N per insert (x the material ratio) |
| 6 | **Preload retention**: tighten 3 M3 screws with a torque screwdriver, re-measure the torque after 24 h at 40 C | preload credit 50 % | | >= 50 % retained |
| 7 | **Walking load**: strain gauge on the shank web or the servo current log while walking | GRF 1.5 x weight, headroom 1.25 | | peaks <= the walk cases |

## 10. Known limits

* Beam theory on sections cut by planes: wrong near load introduction and at sections that graze a face (filtered: section thinner than 1 mm or smaller than 10 mm2). Bolt-circle and bearing load introduction are checked by the fastener checks, not by the sections; the FE peak is reported away from the load patches (8 mm).
* The load path is a tree of rigid bodies: the loads in a bolted joint are shared by the group model, not by a contact solution. Idler joints carry the non-axial moment as a couple with zero moment at the horn.
* Material strength is the weakest direction; FEA uses a transversely isotropic elastic law but a quadratic failure index, not a tested criterion. Infill is represented in the analytic sections only (the FE model is solid).
* Static load cases: no dynamic amplification beyond the stated factors, no creep (PETG under sustained load), no temperature, no moisture (CF-nylon is stiffer and stronger dry).
* The single-sided horn carries the foot's pitch moment as a bolt couple on a 14 mm circle and the servo output carries it too; the check treats the servo as capable of the assumed side load. If test 4 says otherwise, the ankle roll needs a second bearing (see the review below).
* Left leg, one side; the arms and torso are not modelled (handling "lift by an arm" waits for arm CAD).
