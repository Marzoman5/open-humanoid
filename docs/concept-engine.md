# Concept engine (P2 concept-loop instruments)

Tooling for ADR 0012: kinematic templates as data, measured actuator models, a frozen motion library, per-joint envelopes with
bounded uncertainty, and a power/voltage trade study. **It measures; it does not pick Adam's design.** Thresholds live in one file
([`openhumanoid/concept/thresholds.yaml`](../openhumanoid/concept/thresholds.yaml)) for the commander to mirror into `pipeline/gates.yaml`.
Task T-0017. Review of the first plan: `variants/adam/reviews/challenge-1-concept-engine.md` (rows 1-20); how each row was handled is in the
[review table](#challenge-1-how-each-row-was-handled). Task T-20261019-e5c9 (calibration + the fixes of `variants/adam/reviews/challenge-2-concept-results.md`):
see [Open Duck Mini calibration](#open-duck-mini-calibration-challenge-2-rows-1-and-11), the redefined [push recovery](#push-recovery-r10-balance-recovery--fall-prevention-is-a-must-redefined-after-challenge-2)
and the [challenge-2 table](#challenge-2-how-each-row-was-handled).

## Use

```bash
.venv/Scripts/pip install -e ".[sim,cad,dev,concept]"                      # mujoco + casadi (scipy comes with the sim extras)
.venv/Scripts/python -m openhumanoid.concept evaluate variants/adam/concepts/A-3s-12v-sts3215.yaml            # full run incl. gait sweep + R10 search, ~10 min
.venv/Scripts/python -m openhumanoid.concept evaluate <concept.yaml> --quick                                   # nominal gates + R10 at the required impulse, ~9 s (no gait sweep)
.venv/Scripts/python -m openhumanoid.concept evaluate <concept.yaml> --samples 64 --table-height 0.30          # bigger Monte Carlo, ONE other table height (replaces 0.25 / 0.45)
.venv/Scripts/python -m openhumanoid.concept sweep <concept.yaml> --heights 0.40 0.45 0.50 0.55 0.60 0.65     # height sweep: gait sweep + R10 + T-0004 AND CAD-foundation floors, ~3 min per height
.venv/Scripts/python -m openhumanoid.concept.motions.pickup <concept.yaml> --scan 0.15 0.52 0.025 --servo   # whole-body pickup: reachable table range + demand per joint (writes pickup_range.{json,md})
.venv/Scripts/python -m openhumanoid.concept calibrate-odm --odm-dir <scratch clone of Open_Duck_Playground>   # Open Duck Mini calibration (read-only, ~3 min)
.venv/Scripts/python -m openhumanoid.concept compare variants/adam/generated/concept/*/report.json
.venv/Scripts/python -m openhumanoid.concept validate-thermal                                                  # replay the Robonine runs
.venv/Scripts/python -m pytest tests/test_concept.py -m "not slow"                                             # fast tests (~30 s); ODM_DIR=<scratch> adds the calibration test
```

`evaluate` writes `variants/<base>/generated/concept/<candidate>/report.{json,md}` (tool-written, never hand-edited). `openhumanoid/cli.py` is
untouched; the commander wires `python -m openhumanoid.concept` into `oh`.

A **candidate** is a YAML (see `variants/adam/concepts/`): base variant, height, proportion overrides, `mass_model` / `body_overrides` (e.g. a pinned total mass), `packaging: [t0004, cad_foundation]`, template, joints (with optional range /
actuator), default actuator, per-joint actuators, optional `transmissions`, the pack / regulator / compute, and the on-board / off-board
parts. Nothing in `openhumanoid/` assumes Adam: `base:` names any variant, `template:` any kinematic template.

## What runs, in order

1. **Robot.** Candidate -> spec (height, proportions, **packaging floors**) -> component-sum mass -> MJCF built from the template -> servo model per joint.
2. **Gait sweep** (rows 12-13): stance knee flexion {20, 30, 40, 45} deg x step time {0.25, 0.35, 0.5} s, the same set for every candidate; the gates below use the best feasible combination (largest worst-joint margin among those whose stand / walks / turn are all valid). Skipped by `--quick` (which uses the concept's own values).
2. **Frozen motions** (the same for every candidate): stand, walk forward / backward, turn in place, squat 90 and 120, wave, dance, table pickup of 150 g at **0.25 m and 0.45 m**, and **five R10 push scenarios (a MUST)**. Sit-to-stand at 130 deg knee is a SHOULD (warning only). A frozen squat deeper than the knee range is run at the range limit and flagged (`rom_clamped_from_deg`). Stress walks: 1.5x speed, -20% step time, +-10 ms landing error, one lateral capture step. Getting up after a face-plant is not required yet (stub).
3. **Demand.** Each motion is played in MuJoCo (contacts, free base) with a stiff *ideal* torque-source PD. The joint torque it reports is what the motion needs, including the servo's reflected rotor inertia. BAM friction is added for moving joints. A motion that needed more than 1% of body weight of tether force is **invalid**.
4. **Gates** per joint over all motions (below), at the pack's nominal voltage.
5. **Servo in the loop** (tracking, saturation, overload trips, grasp success; *not* envelopes).
6. **Mixed-activity** thermal / battery simulation, runtime, bus analysis, cost.
7. **Uncertainty:** bounds ("tornado") sweep (plus a SENSITIVITY row with BAM's ST3025 armature 0.00399, not a bound), mass cases incl. the benchmark-fit mass and "mass to first gate failure", small quasi-static Monte Carlo, stress walks, and the RMS verdict at every circulating "rated continuous" figure.
8. **Report** with a provenance class on every constant.

## Departures from the brief (and why)

| Brief | What was built | Reason |
|---|---|---|
| 12 V STS3215 by physical scaling of the 7.4 V model ("kt same, stall and speed scale with voltage") | **Datasheet-anchored** 12 V model (stall 2.94 N.m, no-load 4.78 rad/s, stall current 2.7 A) with armature / friction / delay borrowed from the 7.4 V fit. The literal scaling is kept as an *optimistic bound* (`servo_spec("sts3215-12v", "bam_scaled")`: 9.2 rad/s, 3.10 N.m) | The 12 V part is a different winding (vendor kt 11 vs 7.8 kg.cm/A) and Robonine measured 45.6 rpm at 12 V. "kt same" predicts 88 rpm. Torque agrees (3.10 scaled vs 2.94 datasheet); speed does not. Uncertainty is widened to +-25% on stall and speed |
| Torque-limited trajectory optimisation with casadi | **LIPM + ZMP preview control + analytic leg IK + COM compensation** for walking; IK + COM balancing for squat / dance / pickup. casadi is used for a **velocity-limited QP smoother** of the dance keyframes (osqp via `ca.qpsol`) | An IPOPT collocation needs a contact model and a long tuning loop; the preview-control gait is checked against MuJoCo (the free-base replay stays upright, tether < 1%) and is a documented *lower bound* on loads (the stress walks bound the gap). casadi earns its place where a convex QP gives a guaranteed speed-limited, jerk-minimal trajectory. Falls back to a moving average when casadi is missing |
| "Play each motion with the actuator model" for envelopes | Envelopes from the **ideal-torque demand**; the actuator model runs separately for tracking / saturation / trips | A clipped servo torque cannot report a demand above its own cap (challenge-1 row 7) |
| Mass +-15%, ±5% on parts | Structure x0.55-1.4 around a nominal of 11.9 kg per m^3 (**recentred on Open Duck Mini's back-out, challenge-2 row 11**; it was 6.4 with x0.9-1.8), wiring/electronics x0.8-1.5, servos/battery/boards as listed (challenge-1 row 3, which supersedes the first commander note) | Pre-CAD the printed structure is a guess and biased low (no shells); the benchmark fit is only a sanity bound / stress case |
| Monte Carlo over latency, backlash, kp, sag | Bounds sweep as the headline; a small MC over **quasi-static** dimensions only. Latency / backlash / kp are applied in the servo-in-the-loop runs as *sensitivity*, labelled "needs closed loop (P5)" | An open-loop replay cannot judge closed-loop robustness (row 9) |
| Pi 5 PSU / buck "if missing" | Added the official 27 W PSU (bench) and the Pololu D36V50F5 5.5 A regulator | Both with dimensions, mass and URLs, `verified: false` |

## Kinematic templates (`openhumanoid/templates/`)

`biped_v1.yaml` (the old model, now data) and `humanoid_v2.yaml`: 6-DOF legs, `waist_yaw`, `neck_yaw` (+ optional `neck_pitch`), shoulder pitch / roll, elbow,
optional `wrist`, and a 1-DOF parallel-jaw `gripper` per hand (fixed finger + one moving jaw on a slide joint driven by a 12 mm/rad pinion).
Link lengths are expressions over the spec proportions (safe AST evaluator, no `eval`). `simgen.build_mjcf` builds the tree from the template and the spec's joints:
a joint the template lacks **raises** (it used to be dropped silently); optional bodies (hand, jaw) fold their mass into the parent when unused. The `biped_v1` output is
semantically identical to the old hand-written builder (same joints, masses, geoms); `oh sim test adam` passes. The spec picks the template with `kinematics.template`.

## Actuator models (`openhumanoid/actuators/`)

* **BAM STS3215 7.4 V** (Rhoban/bam, Apache-2.0, commit `e9a619d`): the six parameter files are copied verbatim (`actuators/data/`, license text alongside). The control law, DC torque equation and the M1-M6 friction budget are re-implemented, vectorised, in `servo.py`. **Fidelity vs upstream:** `tests/test_concept.py::test_bam_fidelity_against_upstream` (set `BAM_SRC` to a checkout; upstream needs Python >= 3.12 and the package is not on PyPI under `bam`) matches friction to 1e-12 and a 3 s pendulum trajectory to 1e-16.
* **Law:** `duty = clip(kp_fw * error_gain * ratio * (q_target_rate_limited - q), +-0.97)`, `tau = kt (V duty - kt w) / R`, clipped to the **datasheet stall** at the bus voltage (the cap is *motor side*: stall + the current friction budget, so the net shaft torque can reach the datasheet figure; friction is not subtracted twice). Armature goes into the MuJoCo joint; BAM friction is written into `dof_frictionloss` / `dof_damping` every step using the BAM MuJoCo-controller convention for the external torque.
* **Pessimistic variant:** `tau = stall (duty/pwm - w / w_noload)` (`spec.with_model("linear")`), because nothing verifies the 12 V mid-speed torque. Both appear in the bounds sweep.
* **Latency** (BAM `command_delay` 4.9 ms + optional extra), **backlash** (a play operator on the measured position, +-0.5 deg; an approximation), **battery sag** (`power.Pack`: open-circuit curve, internal resistance, state of charge).
* **Overload protection** (Overload_Torque 80%, Protection_Time, Protective_Torque 20%): a state machine in the servo bank and a replay of it on the demand; the gate is *time continuously above 70% of stall < half the protection time*, and trips are reported per motion. The unit of Protection_Time is unconfirmed (2 s assumed).
* **Thermal:** one lumped node per servo, `Rth` 3.2 K/W and `tau` 300 s, derived from one Robonine unit with an *assumed* 22 C ambient. **The model reproduces Robonine run 1 (circular: Rth came from it) but not run 2 (71 C after ~110 min): 52 C predicted. So thermal numbers are labelled unusable;** the primary thermal gate is RMS <= vendor-rated continuous. The report still gives a hot case (Rth x1.4, 40 C in-shell) and minutes to 70 C for tau 150-1200 s.
* **STS3250 and unlisted catalog actuators:** datasheet models with +-25-30% stall/speed and +-50% armature; generic catalog parts get an ideal-DC model with wider bands.
* **Perturbation:** `ServoSpec.perturbed(stall, speed, friction, rth, kp, armature)`. Armature is +-20% at 7.4 V and +-50% for 12 V and STS3250, because reflected rotor inertia (BAM 0.0234 kg m^2) dominates the dynamic loads: for a swinging 0.1 m leg it is 40x the link inertia.

## Frozen motion specs (shared by every candidate)

Defined once in `thresholds.yaml` under `motions` (absolute SI units; **not** tuned per candidate, no Froude scaling, no per-candidate speed limits):

| Motion | Spec |
|---|---|
| Walk fwd / back | 0.10 m/s, foot lift 15 mm, 20% double support; step time from the frozen SET {0.25, 0.35, 0.5} s (step length = 0.10 m/s x step time, the walk lasts about 4 s), stance knee flexion from {20, 30, 40, 45} deg (rows 12-13) |
| Turn in place | 0.50 rad/s (0.25 rad per step) |
| Squat | knee flexion 90 and 120 deg, 2.5 s down, 1 s hold |
| Wave | right arm abducted, elbow +-22 deg at 1.25 Hz, 7 s |
| Dance | 80 BPM, 6 phrases of 8 beats (36 s), one joint-speed limit of 3 rad/s for all joints; the QP smoother may deviate **at most 8 deg** from the choreography or the dance is invalid |
| Pickup | 150 g, 40 mm cylinder, table at **0.25 m AND 0.45 m** (row 16; R5 "table height" is undefined: maintainer question Q1; `--table-height` replaces the list; the second is `pickup_0.45m`), right hand, 58 mm jaw opening, **whole-body collision-checked planner** (knee, hip hinge, waist, step-in, then the arm; Cartesian approach over the table edge, straight along the fingers, 30-40 mm lift; see [Whole-body pickup planner](#whole-body-pickup-planner-t-20261019-a536)), 3 s to close the jaw (servo speed), arm joint speed <= 3 rad/s |
| Sit-to-stand | quasi-static, 130 deg knee (proxy for get-up); **a SHOULD** (R10): failures are warnings, not blockers |
| Stress walks | step length x1.5; step time x0.8; landing 10 ms early / late; one 30 mm lateral capture step |

`getup` is a stub (listed as infeasible). A reference that violates a joint range is infeasible (so a squat to 130 deg needs the ankle-pitch range the candidates declare, about -75 deg).

## Whole-body pickup planner (T-20261019-a536)

Why: the R1 package (`variants/adam/reviews/R1-concept-2026-10-19.md` section 1, challenge-3 row 5) found the arm-only planner reporting "arm too short" for every candidate at a 0.45 m table, a 131x-stall
spike at 0.40 m (the planned hand path went through the table top: with the table contact off the same pickup peaked at 0.22 of stall) and nothing reachable above 0.35 m at 0.55 m. The planner
(`openhumanoid/concept/motions/pickup.py`) now does the following; every number it uses is an assumption of the scenario, listed in `PLAN` at the top of the file.

1. **Whole-body posture search.** The grasp posture is knee flexion (5 deg up to the concept's own knee limit: 110 deg for R1, never beyond), hip hinge (pelvis pitch 0-40 deg), waist yaw (0-30 deg, towards the working side,
   only if the template has the joint; `humanoid_v2` has yaw only) and the COM position in the foot polygon, plus the arm. Postures are ordered by a body-effort cost and the first one that passes every check wins, so the
   hinge, waist and a deep knee are used only when the table height needs them (see the table below: 0.15 m uses knee 65 deg + hinge 40 deg; 0.25-0.38 m use the walking stance or less). The standing distance (a
   step-in) is an output: `standing_gap_m` is the gap between the toe line and the table edge, required >= 0.
2. **Arm: closed-form IK, finger tilt as a result.** For a finger tilt tau the planar two-link geometry fixes the reach from the grip height above the shoulder; the 3-D closed-form solve (shoulder pitch, roll, elbow) confirms
   it to < 0.1 mm. With no wrist the finger direction is what the arm gives: tilt limits [-70, +45] deg, jaw axis within 25 deg of horizontal, the arm kept >= 4 mm short of straight (a straight arm is singular and cannot lift).
3. **Collision-aware approach.** The hand goes rest -> an arc about the shoulder (a straight line would cut through the part of the arm's annulus it cannot reach) to a waiting point in front of the table edge (up to 5 cm above the approach line when
   the arm can) -> a pre-grasp point 5 cm back -> a straight approach along the fingers -> a 30-40 mm lift on the circle about the shoulder (a straight arm lifts by swinging up, not by stretching). The path is sampled and solved
   by IK sample by sample, so the planned path is the executed path. The finished reference is then re-measured against the table: **every robot geom** (arm links, hand, fingers, torso, pelvis, thighs, feet), every frame, after the
   velocity smoothing, must stay >= 3 mm from the table top (`meta["table_min_clearance_m"]`), the COM must stay inside the foot polygon with >= 0.2 foot lengths of margin in every frame (`balance_margin_min_m`), and the
   carried object must stay > 15 mm above the table through the stand-up.
4. **What limits it is named** (`meta["limit"]`, and in the invalid-motion reason of a report): `arm reach` (no whole-body posture puts the grip point where the arm can hold it), `table collision` (the arm covers the height but the
   forearm, hand or body meets the table edge in every posture tried), `balance` (the arm could reach with a posture whose COM leaves the foot-polygon margin: balance, not reach, limits it), `leg joint range` (reachable only with knee / hip /
   ankle / waist outside their ranges) and `path/IK`.

**Scenario** (assumptions, not measurements): the table is a slab 0.30 m deep, 0.40 m wide, 20 mm thick, its legs outside the model; the 40 mm x 50 mm, 150 g cylinder stands with its centre **50 mm behind the front edge** (`edge_to_object_m`; the
dominant assumption, see the sensitivity table); the arm links are capsules (re-check in CAD with real servo housings); the gripper opens 58 mm and closes in 3 s. Table height is a parameter everywhere: `pickup(kin, table_height_m=...)`,
`evaluate --table-height`, and the scan below.

```bash
.venv/Scripts/python -m openhumanoid.concept.motions.pickup <concept.yaml> [...] [--tables 0.30 0.35 0.40 0.45] [--scan 0.15 0.52 0.025] [--servo] [--edge-to-object 0.035 --suffix _edge035]
```

writes `variants/<base>/generated/concept/<candidate>/pickup_range{,_suffix}.{json,md}`: the reachable table-height range (a scan, then each boundary bisected to 5 mm; every height is a full collision-checked reference), the
posture, finger tilt, clearance and balance margin at every height, and the grasp-and-lift demand per joint through the engine's own ideal playback and `joint_metrics` (strict = the datasheet gate, peak <= 0.70 of stall;
calibrated = the same peak against 1.52x the stall, the ADR 0014 factor measured on the 7.4 V part and assumed for the 12 V parts); `--servo` adds the servo-in-the-loop grasp test.

**Result for the R1 concepts** (right hand, object 50 mm behind the edge, scan floor 0.15 m; tool outputs: `variants/adam/generated/concept/R1-P1*/pickup_range.md`):

| concept | reachable table tops | not reachable: why |
|---|---|---|
| R1-P1r 0.55 m (default height) | 0.150-0.159 m and **0.206-0.384 m** | 0.163-0.203 m: the table edge meets the thighs/knees or lies behind the toes (the reasons tallied by the planner); **0.388 m up to 0.50 m: table collision** (the arm still has grasp solutions, the forearm meets the edge); 0.525 m and up: arm reach |
| R1-P1 0.60 m | 0.150-0.163 m and **0.191-0.422 m** | 0.166-0.188 m: thighs/knees (same reasons); **0.425 m up to 0.55 m: table collision**; 0.575 m and up: arm reach |

Grasp-and-lift demand, ideal playback, 100 ms peak as a fraction of stall (STS3215 12 V, 2.72 N.m stall on the arm and waist; strict gate 0.70):

| concept, table | shoulder pitch strict / cal | elbow strict / cal | waist yaw strict / cal | gripper strict / cal | tether | servo grasp |
|---|---|---|---|---|---|---|
| P1r, 0.35 m | 0.334 / 0.220 | 0.398 / 0.262 | 0.124 / 0.082 | 0.281 / 0.185 | 0.02 % BW | lifts 29 mm |
| P1r, 0.384 m (its maximum) | 0.344 / 0.227 | 0.396 / 0.261 | 0.137 / 0.090 | 0.281 / 0.185 | 0.02 % BW | lifts 26 mm |
| P1, 0.40 m | 0.399 / 0.263 | 0.388 / 0.255 | 0.151 / 0.099 | 0.281 / 0.185 | 0.02 % BW | lifts 32 mm |
| P1, 0.422 m (its maximum) | 0.401 / 0.264 | 0.386 / 0.254 | 0.150 / 0.099 | 0.281 / 0.185 | 0.02 % BW | lifts 27 mm |

Every arm and waist joint has a strict margin >= 1.7 (0.70 / 0.40) and a calibrated margin >= 2.6 at the heights run; the elbow and shoulder pitch are the worst, the waist yaw the lightest. **The 131x-stall spike is gone**:
the hand path is collision-free by an independent distance check over all frames (a test), and no joint exceeds 0.41 of stall at the heights run (0.30-0.42 m). The 0.45 m result of the old planner at 0.60 m (0.77 of stall) was the same defect: the hand was inside the table.

**Is R5 at a 0.40-0.45 m table established? No.** Reach is limited by the arm geometry, not by balance or the legs (the COM margin is >= 25 mm = a quarter of the foot length at every reachable height and 50 mm above 0.25 m; the knee needs 40 deg or less above 0.25 m, 65-105 deg only at the low tables): a 0.55-0.60 m
robot has its shoulder at 0.42-0.46 m, so a 0.40-0.45 m table top is at shoulder height, where the hand sits at the end of a nearly straight 0.20 m arm with the forearm sloping up into the object, and the forearm meets the table edge. Sensitivity to where the
object stands (reach range, tool outputs `pickup_range_edge*.md`):

| object centre behind the front edge | R1-P1r 0.55 m | R1-P1 0.60 m |
|---|---|---|
| 70 mm | 0.272-0.306 m (scan from 0.25) | 0.25-0.263 and 0.288-0.328 m |
| **50 mm (default)** | **<= 0.384 m** | **<= 0.422 m** |
| 35 mm (rim 15 mm from the edge) | <= 0.431 m | <= 0.469 m |
| 20 mm (rim at the edge) | 0.38-0.47 m (scan 0.38-0.52) | 0.40-0.51 m (scan 0.40-0.54) |

So: at 0.55 m the 0.40 m table needs the object within about 35 mm of the edge and 0.45 m needs it at the very edge; at 0.60 m 0.40-0.42 m works with the default placement and 0.45 m needs the object within about 35 mm of the edge.
Levers the planner did not use or cannot model: a wrist (finger tilt would be free), standing on tiptoe (a few cm of shoulder height, a smaller support polygon), the left hand, sliding the object towards the robot, longer arms
(the untested alternative at 0.55 m: `proportions: {upper_arm, forearm}`), and the step-in itself (only its end point is planned). The waist yaw and the hip hinge are in the search but the cheapest feasible posture never needed them above 0.2 m (the hinge is used at 0.15 m); forcing them still gives collision-free, valid plans (`plan={"waist_deg": (30.0,), "hinge_deg": (0.0,)}` at 0.35 m: waist 30 deg, elbow 0.398 of stall; hinge 20 deg: hip pitch 0.495 of stall), so the waist demand in the table is the holding reaction torque, not a twist. The scan treats heights below 0.15 m as out of scope.

Tests: `tests/test_concept.py` `test_pickup_*` (closed-form IK vs MuJoCo forward kinematics; the finished path re-measured against the table in every frame at 0.15 / 0.30 / 0.35 m; table height as a parameter and the posture changing with it;
knee range honoured; out-of-reach reported with its limit; balance named when it binds; the reach-range output; the left hand; and, marked slow, the ideal-playback demand and servo grasp).

## Push recovery (R10: balance recovery / fall prevention is a MUST), redefined after challenge #2

**The requirement is an absolute impulse, the same for every candidate** (`motions.push.required_impulse_Ns`, **PROVISIONAL 0.45 N.s, pending the maintainer**):
0.45 N.s is the top of the ToddlerBot randomisation range for a ~2.5 kg robot (1-3 N for 0.2 s = 0.06-0.18 m/s on 3.4 kg; 0.18 m/s x 2.5 kg). The push is a velocity
change of the whole body, `dv = J / M`, applied to the free base in MuJoCo. It is recovered by **any combination of strategies**, at two moments:

| Scenario | When | Notes |
|---|---|---|
| `stand_fwd`, `stand_lat` | standing in double support | lateral: ankle / hip-roll load shifting inside the double-support polygon FIRST, a step only for what lies beyond it |
| `walk_fwd`, `walk_lat_out`, `walk_lat_in` | **mid single support of `walk_forward`** (third footfall of the frozen gait) | the swing foot is already in flight and is re-targeted; `lat_out` pushes the body past the stance foot (the swing foot must cross-step, placed a foot length ahead of / behind it), `lat_in` towards the swing foot |

Strategies (`openhumanoid/concept/motions/push.py`): the **ankle strategy** (COP moves inside the support polygon, the hull of the loaded feet, shrunk to 75%); the **hip strategy**
(trunk pitch about the hips, forward pushes only; **treated as unavailable beyond 90% of the hip servos' no-load speed, and never a blocker by itself**: the ankle option is tried separately and
the answer is the maximum over options); **up to two capture steps** with the swing time swept over 0.15 / 0.20 / 0.25 / 0.30 / 0.35 s. The landing point is the capture point at touchdown
(computed from the single-support dynamics for the swing duration) plus 10 mm; the foot lands wider if a lateral drift during the swing needs it, never closer than a foot width to the stance
foot; a second step is taken by the foot the body is NOT over when the capture point is still outside the shrunk double-support polygon. A stepping leg that cannot reach crouches the
stance leg (knee flexion up to 120 deg, capped at the knee range - 5 deg) before the landing is clipped to the reach.

**One gate.** A scenario is *recoverable at J* when some strategy has (1) a LIPM plan that settles, (2) a kinematically feasible Reference (leg IK reach, the candidate's joint ranges, so
the CAD-limited ranges in the height sweep), (3) an actuator demand inside the emergency limits (100 ms-averaged peak <= the whole stall torque, torque-speed utilisation <= 1.0; the
metric window starts at the push), and (4) a servo in the loop with latency that tracks it (<= 8 deg, no fall). The gate: **the largest recoverable impulse >= the requirement in every scenario**.
`pushcheck.largest_recoverable` finds the largest by scanning/bisecting J over every strategy (plan level first, MuJoCo demand only where it can change the answer) and reports it in **N.s and
m/s** with the strategy and what limits it (plan reach / actuator torque or speed), so the maintainer can choose the requirement from numbers.

**Latency.** The controller reacts `d_r` = servo command delay (4.9 ms) + one 10 ms control tick + 10 ms sensing (assumed) = ~25 ms after the push; until then the COM falls freely.
**COP reference (row 9).** The COP limits are referenced to the **foot centre**. The old plan referenced them to the COM's initial position, which sat 5.9-8.0 mm behind the foot centre (above the 3 mm
threshold); the standing COM now starts over the foot centre, exactly as the stand reference does (`tests/...::test_cop_is_referenced_to_the_foot_centre_not_the_initial_com`).
**Controls.** A push-free control (J = 0.02 N.s) must pass every scenario, else the walk's own swing transient would be blamed on the push (that is why the emergency peak uses the same 100 ms
window as the sustained gates and starts at the push).

Plan caveats, all optimistic unless said: LIPM with a perfect state estimate, instant unloading of the stepping foot, no foot rotation, no foot/leg collision, the COM height changes only through
the planned crouch, backward pushes not run (hip extension is CAD-limited to 40 deg: a known gap), the lateral trunk-roll strategy is not modelled, the walking push uses the third footfall only. The
walking cases are the hardest: the nominal swing already uses most of the knee's speed envelope.

## Gates (starting thresholds; `gates:` in thresholds.yaml)

Per joint, worst case over all valid motions, at the pack nominal voltage (cells x 3.7 V):

| Gate | Value | Note |
|---|---|---|
| peak torque / datasheet stall at bus voltage | <= 0.70 | peak = 100 ms moving average of the demand (a stiff ideal replay shows 20-50 ms touchdown spikes no real servo-foot system transmits) |
| RMS / vendor-rated continuous | <= 1.0 | per motion and over the mixed schedule; **the primary thermal gate**. For the 7.4 V STS3215 the rating is contested (0.49 Seeed, 0.637 Evelta): the report shows the verdict at BOTH |
| torque-speed envelope utilisation | <= 0.90 | demand point vs `tau_available(w, V)` |
| time above 70% of stall | < 0.5 x Protection_Time; no overload trips | replay of the firmware state machine |
| tether | mean <= 1% of body weight | otherwise the **motion is invalid** (counts as a FAIL) |
| MC p95 peak | <= 0.70 | quasi-static dimensions only |
| push recovery (R10) | largest recoverable impulse >= the required (provisional 0.45 N.s) in every scenario: demand <= 1.0 of stall and <= 1.0 of the envelope, delivered in time | emergency transient; see Push recovery |
| tracking error | 2 deg, *noted only* | P-servo with learned feed-forward |
| runtime | >= 15 min | a Should: reported, not gating |

`PASS` = every motion valid, nominal gates met, MC p95 within the gate. The report also states `robust_to_all_bounds` and `passes_at_benchmark_mass` (the challenge-1 decision rule: the winner must stay a winner across the bounds and at the benchmark mass).

## Uncertainty

* **Bounds sweep (headline):** structure mass x0.55 / x1.4 (relative to the recentred nominal); wiring+electronics x0.8 / x1.5; pessimistic linear torque-speed; armature low / high (per-actuator spread); stall low / high; Rth high + 40 C ambient; walking speed x1.5. Each row: worst margin, delta vs nominal, what fails. **SENSITIVITY row (not a bound):** every servo with a borrowed armature gets BAM's Waveshare ST3025 value (m4 fit, `bam/params/waveshare_st3025/m4.json`, 0.00399 kg m^2 = 17% of the 7.4 V value; verified in the parameter file) - a different gearbox, so the bench settles it.
* **Mass cases:** structure x1.4, the **benchmark-fit mass** (`18.5 h^2.28`, a sanity bound and a stress case only), and **mass to first gate failure** (structure scaled up to x4.5). The structure coefficient (11.9 kg/m^3, recentred by the ODM back-out) is not recalibrated again until shelled CAD exists.
* **Monte Carlo:** 16 samples by default (`--samples`): structure U(0.55, 1.4), wiring U(0.8, 1.5), torso COM shift +-3% h, floor friction 0.5-1.0, stall / armature / Rth spread. p95 per-joint peak and a pass rate.
* **Needs closed loop (P5):** latency 0-40 ms, backlash 0.2-1.0 deg, kp +-10% are run as servo-in-the-loop *sensitivities* on the walk only.

## Packaging floors (every candidate)

From the T-0004 handoff (STS3215 at h = 0.5 m): ankle height >= 0.06 h, foot >= 92 x 55 mm scaled by h/0.5, hip spacing >= 70 mm (servo-fixed, does not scale), shoulder width >= 0.36 h, links >= 60 mm. The report lists which floors raised a candidate. A candidate with a lower ankle would instead have ankle roll limited to +-18 deg. This is a proportion minimum only: no clearance, self-collision, cable or hard-point check exists yet (challenge-1 row 1 sends that to the decision agent).

**CAD-foundation facts** (`packaging: [t0004, cad_foundation]`, used by the height sweep; `thresholds.yaml` `packaging_cad_foundation`): ankle height >= **66 mm absolute** (35 mm servos on intersecting axes; replaces the 0.06 h floor), CAD-limited ranges knee 0-115, hip pitch -110/+40, ankle pitch -60/+25 deg, and the height these add is taken pro rata from the other vertical proportions so `height_m` stays the standing height (at 0.5 m the legs shrink by ~20%). NOT applied: the 106 mm hip stack above and 84 mm behind the hip axis (it would move the pelvis and trunk COM); a known gap.

## Power and voltage trade study (`tradestudy.py`)

Per candidate, in `report.json`/`.md`: torque and speed margins (gate table), peak bus current and per-branch current (legs, arms, torso/head), pack sag and **minimum voltage at the farthest servo** (assumed 20 mOhm per branch), **fuse sizing** (1.25 x the larger of the frozen motions and the **R10 push transient**, next standard value - a fuse sized from the walk alone would blow on the push it exists to survive - plus the all-leg-stall fault current; the STS3215 connector rating is unknown), runtime (usable 85% of nominal Wh at the mixed-activity average power incl. compute, camera and a 0.03 A/servo standby assumption), pack mass and C-rating check, regulator check for the on-board 5 V rail, BOM cost with **low / typical / high** price bands (the decision needs a pass at the high price), **time over voltage rating with the mitigation and its cost** (e.g. 2S full charge 8.4 V vs the 7.4 V rating: over for 80% of the discharge, mitigation = charge to 3.7 V/cell and lose 80% of the capacity; 3S full 12.6 V vs the STS3250 12 V rating: charge to 4.0 V/cell and lose ~23%), and **actuator-model quality** (7.4 V measured, 12 V extrapolated, STS3250 datasheet-only, with bus voltage vs model voltage). One bus voltage serves all servos: a mix is evaluated with each part's stall and speed scaled to the bus.

## Transmissions

A concept may declare `transmissions: {<joint or base joint>: {ratio, efficiency, host, note}}`: servo angle = joint angle / `ratio`, the joint torque is `eta * tau_servo / ratio` when the motor drives and `tau_servo / (eta * ratio)` when the load back-drives it, reflected inertia is `armature / ratio^2`, and `host` moves the servo's mass to another segment (e.g. `thigh`, `pelvis`). Example (not optimised): `variants/adam/concepts/D-transmission-example.yaml` (ankle-pitch servo moved into the thigh through a rod, knee servo into the pelvis through a 4-bar). The decision agent can compare direct drive with moved-up actuators.

## Constants and provenance

Every constant used in a report is listed in its `provenance` table with a class: **measured** (BAM parameters, Robonine run), **sourced_estimate** (vendor datasheet / retailer figures, other robots' randomisation), **extrapolated** (12 V dynamics, STS3250, derived Rth), **assumption** (documented guess), or **gate** (a threshold). The full list with sources is in `thresholds.yaml`, `actuators/data/servo_models.yaml` and the catalog. Highlights that matter most:

| Constant | Value | Class |
|---|---|---|
| BAM STS3215 7.4 V kt 1.265, R 2.47, armature 0.0234, delay 4.9 ms | m4 | measured (pendulum bench, one servo class) |
| Stall 1.912 N.m (7.4 V) / 2.942 (12 V) / 4.903 (STS3250); no-load 5.67 / 4.78 / 7.85 rad/s; stall current 2.5 / 2.7 / 4.2 A | vendor | sourced_estimate (Robonine: 12 V no-load 45.6 rpm measured; static stall 35 kg.cm on one unit) |
| Rated continuous 0.49 / 0.98 / 1.57 N.m | vendor | sourced_estimate |
| 12 V armature, friction, delay; STS3250 dynamics | borrowed from 7.4 V | extrapolated |
| Rth 3.2 K/W, tau 300 s; ambient 35 C | Robonine + assumed 22 C | extrapolated / assumption |
| Protection_Time 2 s | register 200, unit unconfirmed | assumption |
| Standby 0.03 A per servo, camera 1.2 W, wire 20 mOhm per branch, usage mix | | assumption |
| Mass bands, MC ranges, peak window 0.1 s, envelope utilisation 0.9 | | assumption |

## Checks that back the numbers

* Static stance torque vs a hand calculation (`test_static_stance_torque_against_hand_calculation`, within 45%); knee torque ordering stand < squat 90 < squat 120.
* Leg IK vs MuJoCo FK to 0.1 mm; preview control ZMP tracking error 0.5 mm mean.
* Re-implementation vs upstream BAM (above); Robonine replay (`validate-thermal`).
* **Mass propagation (row 10):** scaling every body mass by 1.5 scales the static knee torque by 1.5 within 5%, and an independent hand calculation from the model's own kinematics agrees within 5% (`test_static_knee_torque_scales_with_the_supported_mass`).
* **`mj_inverse` cross-check (row 10, `invdyn.py`):** replaying the logged PD states through `mj_inverse` reproduces the applied actuator force to < 0.01% on stand/squat and < 6% on the walk (tether and impacts), and shows no closed-chain fighting in double support: the left-right load split is 50/50 on the stand and the squeeze (foot forces that cancel between the feet) is 1% of body weight on average, 8% at the worst instant of the walk. `mintorque.py` (inverse dynamics with a minimum-torque contact distribution, no PD, no tether) agrees with the PD harness within ~4% on the sagittal leg joints.
* **Known-robot check:** the old `duck-like-0p42-2s-sts3215.yaml` (spec-default proportions, 6-DOF legs, two dead arms, legs ~20% longer and a ~0.9 kg lighter structure than the real robot) is kept as column (d) of the calibration table; it is NOT Open Duck Mini. The faithful comparison is `calibrate-odm` (ODM's own MJCF, leg lengths, foot, stance, mass, 5-DOF legs): see the section below.


## Known limitations

1. The walking reference is a LIPM/ZMP gait, a lower bound on loads for a real balancing controller; the stress walks narrow but do not close the gap. No trajectory optimisation was built.
2. Reflected rotor inertia (BAM armature 0.0234 kg m^2) dominates the dynamic torque and comes from a 7.4 V identification; applying it to 12 V and STS3250 servos is an extrapolation (+-50% in the sweep).
3. The 12 V mid-speed torque curve is unverified; anchored vs pessimistic linear brackets it. A bench test of one 12 V and one 7.4 V servo is the cheapest way to close this (maintainer question Q2).
4. Printed structure + shell mass is a pre-CAD guess; the model has no shells, brackets or fasteners beyond the catalog kit masses. Nothing is checked for packaging fit.
5. The thermal model fails the Robonine replay (under-predicts the oscillation run by ~19 K); RMS vs rated continuous is the only thermal gate. The vendor "rated torque" is not a measured limit.
6. Overload Protection_Time is unit-unconfirmed; standby current, camera power, wire resistance and the usage mix are assumptions.
7. Table height (R5, now 0.25 and 0.45 m), get-up (maintainer Q3) and the min walk speed are placeholders / stubs; the quasi-static sit-to-stand at 130 deg only proxies get-up. The 0.45 m pickup is out of reach of the 0.55-0.60 m R1 concepts (planner revised: see the pickup section, which reports the reachable table range).
8. No-wrist 3-DOF arm: the pickup reports the jaw-axis angle; the gripper holds with a reduced torque limit (15%), a firmware setting the HAL must reproduce.
9. The tether is a very soft pelvis pull (6% cap, mean must be < 1%); a gait that cannot stand without it is invalid, but passing says nothing about push recovery.
10. R10 is provisional (0.45 N.s) and modelled with LIPM plans (see Push recovery); the walking pushes use one phase of one gait; the answer moves with the maintainer's number.
11. The ODM calibration rests on a reconstructed base trajectory and a band-limited fit for (a) and on a ZMP shift for (b); the factors are measurements for an ADR, not thresholds. The ideal PD is capped at kd <= 0.6 I/dt (only the ST3025 sensitivity binds).

## Files

`openhumanoid/templates/` (data) - `openhumanoid/actuators/` (`servo.py`, `data/`) - `openhumanoid/concept/` (`robot.py`, `kin.py`, `motions/`, `playback.py`, `envelopes.py`, `evaluate.py`, `tradestudy.py`, `power.py`, `thermal_validation.py`, `provenance.py`, `thresholds.yaml`, `__main__.py`, plus `pushcheck.py`, `sweep.py`, `invdyn.py`, `mintorque.py`, `calibration.py`, `odm_reference.py`, `odm_walk.py`, `odm_experiments.py`) - catalog additions in `catalog/power|electronics|compute` - `tests/test_concept.py`.

## Challenge-1: how each row was handled

| Row | Handled |
|---|---|
| 2 packaging floors | `packaging_floors` applied to every candidate and reported |
| 3 mass | asymmetric non-servo bands, benchmark-mass stress case, mass to first failure, no recalibration |
| 4 12 V / friction twice | anchored + cap vs pessimistic linear; motor-side cap; +-25% stall / speed |
| 5 armature | `perturbed(armature)`; tornado and Monte Carlo |
| 6 overload | protection state machine, time-above-70% gate, trips per motion |
| 7 envelopes from delivery / tether | ideal-mode demand; servo mode only for tracking / saturation / trips; mean tether <= 1% else invalid |
| 8 motions tuned per candidate | frozen motion specs; dance deviation > 8 deg is a FAIL |
| 9 false-precision Monte Carlo | bounds sweep headline; MC quasi-static only; latency/backlash labelled closed loop |
| 10 thermal | RMS <= rated primary; hot case; minutes to 70 C; Robonine replay marks the model unusable |
| 11 stress walks, get-up | four stress walks + push-recovery cases (R10, required: ankle, hip, forward and lateral capture step) + sit-to-stand 130 as a SHOULD (get-up still a stub) |
| 12 known robot | duck-like concept through the gates |
| 13 neck pitch, camera, compute | in every example BOM / mass / power; regulator check |
| 14 height / anchoring | `sweep` command (0.40-0.65 m); per-joint utilisation ranking; candidates share everything but power / actuators |
| 15 rating | time over rating + mitigation |
| 16 BAM fidelity | test vs upstream |
| 18 bus | branch currents, far-servo voltage, fuse |
| 19 cost | low / typical / high bands |
| 20 LIPM vs trajopt | recorded under "Departures" |
| 1, 17 | decision agent / commander |

## Open Duck Mini calibration (challenge-2 rows 1 and 11)

`python -m openhumanoid.concept calibrate-odm --odm-dir <scratch clone of apirrone/Open_Duck_Playground>` (needs only the Playground repo: its MJCF, assets and `polynomial_coefficients.pkl`). **Those repositories have NO LICENSE**:
the tool reads the folder at run time, keeps nothing, and writes only derived numbers (`variants/adam/generated/concept/calibration/odm_calibration.{json,md}`). Nothing from ODM is copied or committed
(`THIRD_PARTY.md` row "read-only"); the pickle is loaded with a numpy-only unpickler. Source commits read: Playground `b9be205`, reference-motion generator `3d7bc6f`, main repo `b23317a`.

Three experiments through the same gate code (walking leg joints, 7.4 V STS3215 model, ODM's own armature 0.027 where its MJCF is used; **no threshold is changed**):

* **(a)** ODM's own MJCF with ODM's own reference (the degree-15 polynomial fit its policy imitates, command snapped to the table like its training code: dy = -0.037, dtheta = -0.074 for "straight"; 0.54 s cycle, 0.27 s steps, ~0.16 m/s).
  The raw fit has end-point oscillation (wrap mismatch up to 0.1 rad, accelerations > 1000 rad/s^2) and is not playable open loop in the PD harness (it falls within a second even with an 8x stronger tether), so it is band-limited to 6 harmonics and its demand is computed by
  `mintorque.py`: inverse dynamics with a minimum-torque contact distribution (no tether, no PD, no stability to lose; agrees with the PD harness within ~4% on the sagittal leg joints of candidate A).
* **(b)** the frozen gait (0.10 m/s, 15 mm clearance, 20% double support; step time {0.25, 0.35, 0.5} s, stance flexion {77, 40} deg, ZMP target {0, 0.03, 0.05} m inboard) on ODM's MJCF with numerical leg IK; the best FEASIBLE combination (no IK failures, no range violation, smallest peak).
  ODM's stance is 163 mm wide with its legs knock-kneed (hip-pitch planes 218 mm apart, 74 mm outboard of the roll axes), so the frozen foot-centre ZMP needs 25+ deg of hip roll (limit 25): without a 0.05 m inboard ZMP shift none of the frozen combinations is realisable on it.
* **(c)** the same gait on `variants/adam/concepts/odm-like-0p42-5dof.yaml`: our generator given ODM's leg lengths (78.65 mm thigh = shank), foot (103 x 41 mm), stance width, 5-DOF legs and total mass (2.107 kg). **(d)** is the old duck-like concept (spec proportions, 6-DOF), now with the recentred structure mass.

**Measured ODM facts** (from its MJCF): thigh = shank = 78.65 mm; ankle axis 38.9 mm above the sole; sole 103 x 41 mm, centre 13 mm ahead of the ankle; stance 163 mm between foot centres; home knee flexion 78 deg (it walks crouched: hip height 0.16 m vs 0.194 m
fully extended; our sweep range 20-45 deg does not reach it); 14 servos, total 2.107 kg; COM 48 mm above the hip-pitch axis; **its training sim lets each servo deliver 3.23 N.m (kp 13.37 N.m/rad) against the 1.912 N.m datasheet stall the gates use (x1.69)**; BAM's own
7.4 V fit gives an electrical stall of 3.7 N.m, so the real stall is the bench's first question.

| gate | threshold | (a) ODM own reference | (b) frozen on ODM MJCF | (c) frozen on ODM-like | (d) old duck-like | a/gate | **b/gate** | c/gate | b/a | c/b |
|---|---|---|---|---|---|---|---|---|---|---|
| peak / stall (100 ms) | 0.70 | 4.32 | 1.06 | 1.44 | 0.97 | 6.17 | **1.52** | 2.06 | 0.25 | 1.36 |
| RMS / rated 0.49 | 1.0 | 12.10 | 2.52 | 2.66 | 1.86 | 12.10 | **2.52** | 2.66 | 0.21 | 1.06 |
| RMS / rated 0.64 | 1.0 | 9.31 | 1.94 | 2.05 | 1.43 | 9.31 | **1.94** | 2.05 | 0.21 | 1.06 |
| torque-speed envelope | 0.90 | >9.99 (speed) | 1.06 | 1.44 | 1.03 | - | **1.18** | 1.61 | - | 1.36 |
| overload run | 1.0 | 0.18 | 0.25 | 0.33 | 0.06 | 0.18 | **0.25** | 0.33 | 1.43 | 1.30 |
| peak speed / no-load (info) | - | 1.98 | 0.73 | 0.77 | 0.69 | | | | | |

Reading it. (1) A robot of ODM's mass and size doing the gentlest consistent frozen gait on ITS OWN mechanism needs **1.5x the peak gate, 1.9-2.5x the RMS gate (0.64 / 0.49 N.m), 1.2x the envelope gate** and passes the overload gate;
so the gates are what a robot that walks fails, not the inputs: the old duck-like input set (d) lands within 0.7-0.9x of (b), our generator's model of the robot (c vs b) adds 1.06x on RMS and 1.36x on peak (mass distribution and inertias). If ODM's
3.23 N.m servo limit were the real stall, (b)'s peak would be 1.06 x 1.912 / 3.23 = 0.63 of stall, inside the 0.70 gate. (2) ODM's OWN reference is NOT a usable load: it asks for 2x the servo's no-load speed (the real robot cannot follow it; its RL policy only imitates it),
so (a) is reported but disqualified as a calibration point, and the 4x gap b/a is the reference, not the gate. (3) The 70%-of-stall and rated-RMS gates are the ones that need the ADR; the commander should weigh them against the bench measurement of the real stall and thermal holds,
because the contested "rated" label (0.49 vs 0.64) moves the RMS factor by 1.3x. **Structure mass (row 11):** 2.107 kg - 14 x 55 g servos - 0.456 kg electronics/wiring estimate (catalog masses of the same parts + 0.12 kg misc; ODM publishes no breakdown) =
**0.88 kg of structure = 11.9 kg per m^3 at 0.42 m, 1.86x the engine's 6.4**: above the 1.5x trigger, so the nominal was recentred to 11.9 (set in each concept's `mass_model`; the band is now x0.55-1.4 around it: 0.55 is the old nominal, 1.4 about the benchmark-fit mass).

## Results of the challenge-2 re-run (2026-10-19, catalog after the T-0002 sourcing merge)

Candidates A-D and the old duck check through the new engine (nominal gates; Monte Carlo 16 samples; recentred structure mass 11.9 kg/m^3; gait sweep per candidate). Reports: `variants/adam/generated/concept/<id>/report.{md,json}`.

| | A 3S + 12 V STS3215 | B 2S + 7.4 V STS3215 | C 3S + STS3250 knees | D A + moved-up servos | old duck-like check |
|---|---|---|---|---|---|
| verdict | FAIL | FAIL | FAIL | FAIL | FAIL |
| mass | 3.04 kg | 2.99 kg | 3.12 kg | 3.04 kg | 2.11 kg (= ODM's 2.107) |
| gait chosen (flex / step time) | 45 deg / 0.5 s | 45 / 0.5 | 45 / 0.5 | 45 / 0.5 | 45 / 0.5 |
| worst nominal joint margin | 1.063 knee_r (pass) | 0.537 knee_r | 1.126 hip_roll_r (pass) | 0.923 knee_r | 0.571 knee_r |
| MC p95 peak | 0.90 knee_r | 1.09 hip_roll_l | 0.88 knee_r | 1.03 knee_r | 1.09 knee_r |
| robust to all bounds / at benchmark mass | no / yes | no / no | no / yes | no / no | no / no |
| RMS verdict at 0.49 / 0.637 (7.4 V parts) | - | FAIL 1.86 / FAIL 1.43 (mixed 1.42 / 1.10, both FAIL) | - | - | FAIL 1.75 / FAIL 1.35 |
| ST3025 armature sensitivity (0.00399) | 1.07 pass | 0.54 fail | 1.18 pass | 1.01 pass | 0.57 fail |
| R10 largest recoverable N.s (m/s): stand fwd / stand lat | 0.72 / 0.81 | 0.62 / 0.85 | 0.71 / 0.83 | 0.63 / 0.85 | 0.34 / 0.61 |
| walk fwd / walk lat out / walk lat in | 0.41 / 0.51 / **0.37** | 0.41 / 0.57 / 0.39 | **0.42** / 0.56 / 0.45 | 0.41 / 0.51 / 0.38 | 0.28 / 0.29 / 0.25 |
| weakest, as m/s (need 0.45 N.s) | 0.123 | 0.131 | 0.134 | 0.124 | 0.118 |
| peak bus current (motions / R10 transient) | 8.2 A (5.9 / 8.2) | 11.3 A (11.1 / 11.3) | 11.0 A (7.8 / 11.0) | 8.8 A | 14.0 A |
| fuse (1.25 x peak) vs sized from motions only | **15 A** vs 7.5 A (would blow) | 15 vs 15 | 15 vs 10 (would blow) | 15 vs 10 | 20 vs 15 |
| all-leg stall (fault) -> fuse to ride through | 30 A -> 40 A | 30 A -> 40 A | 33 A -> 50 A | 30 A -> 40 A | 30 A -> 40 A |
| runtime (mixed) | 64 min | 41 min | 52 min | 61 min | 45 min |
| catalog cost typical / high | $720 / $985 | $709 / $883 | $954 / $1324 | $720 / $985 | $454 / $551 |

Cost: the catalog `typical` above; the sourcing totals (`variants/adam/sourcing/totals.py`, `QUOTES.md`, delivered with tax, shipping, spares and +10% contingency) give A $1064-1300, B $1079-1188, C $1405-1613, D = A, ODM-like reference $752-821 against the $550 cap.
Prices were verified by T-0002; this engine adds no cost logic of its own.

**What changed against the first results.** Every candidate still fails, but for different reasons than before: with the absolute impulse no candidate is blocked by "capture steps unreachable at 0.45 m" (a 0.15-0.25 s single step recovers the standing push, the
largest standing impulse is 0.62-0.72 N.s against 0.45 required); the blockers are the **walking** pushes (0.37-0.45 N.s: the nominal swing already uses most of the knee speed envelope) and, for A/C/D, the p95 Monte Carlo and the unmeasured 12 V curves (pessimistic
linear torque-speed 0.60-0.90, armature high 0.72-0.95, stall low 0.76-0.86). A's nominal worst margin barely moved (1.07 before, 1.06 now) although the mass rose from 2.55 to 3.04 kg: the gait sweep takes 45 deg stance flexion (1.063; 1.054 at the old 40 deg / 0.5 s default) and the two nearly cancel. B fails by a wide margin on RMS at either rated figure.

### Height sweep, 0.40-0.65 m (`sweep`; T-0004 floors + CAD-foundation facts; gait chosen per height; nominal gates + R10)

Nominal gates only, so each answer is a ceiling. **No architecture is feasible at any height tested** (the strict gates); details, with the binding constraint per height (the gate with the largest violation factor):

| arch | closest to feasible | binding there | what binds around it |
|---|---|---|---|
| A 3S / 12 V STS3215 | **0.50-0.55 m** | 0.50: R10 `walk_lat_in` 0.40 vs 0.45 N.s, hip-roll peak x1.03; 0.55: hip-roll peak x1.27, RMS x1.2 (R10 min 0.58 ok) | below 0.50: walking pushes collapse (0.45 m: lat-out 0.07 N.s, crouch cannot buy reach with the 66 mm ankle); above 0.55: hip-roll torque (0.60 x1.5), 0.65: gait and pickup fall over |
| B 2S / 7.4 V STS3215 | **0.45 m** | RMS vs rated x1.9 at knee_r / hip_roll (and peak) | 0.50: R10 lat-out 0.17; >= 0.55: walking pushes 0.0 (7.4 V speed envelope) |
| C 3S / 12 V + STS3250 knees | **0.50-0.55 m** | 0.50: hip-roll peak x1.05, RMS x1.01 (R10 min 0.48 ok); 0.55: hip-roll peak x1.25 (R10 0.60 ok) | the hip roll is still an STS3215: upgrading only the knees does not move the ceiling past ~0.55 m |

Across all three the **hip-roll servo (STS3215)** is the binding joint above 0.5 m, then the walking-push cases below it. The 0.45 m-table pickup (R5 provisional) is invalid at most heights (A: all but 0.60 m; B and C: up to 0.60 m): the planner finds no squat that reaches it (a 0.45 m table is
shoulder height on a 0.5-0.6 m robot; re-checked with the whole-body, collision-checked planner of T-20261019-a536: it is the physics, see the pickup section) and it is reported separately as "binding without the 0.45 m-table pickup"; the 0.25 m pickup falls over at 0.40 m (all three) and at 0.65 m (A, C). `squat_120` and the 130 deg sit-to-stand are run at the CAD knee limit (114.8 deg) and flagged `rom_clamped_from_deg`
(at the unclamped 120 deg they would be infeasible at every height: the 115 deg CAD knee costs a MUST motion, challenge-2 row 17).
INDICATIVE only, never applied: if the joint gates were looser by the factors the frozen gait needs on ODM's own mechanism (peak x1.52, RMS x2.5, envelope x1.18; `sweep.relaxed_feasibility`) the feasible heights would be **A 0.55-0.60 m, C 0.50-0.60 m, B 0.45 m**.

## Challenge-2: how each row was handled

| Row | Handled |
|---|---|
| 1 ODM check not faithful | `calibrate-odm`: (a) ODM's MJCF + own reference, (b) frozen gait on its MJCF with numerical IK, (c) frozen gait on its real proportions / mass / 5-DOF legs by our generator, (d) the old check; per-gate values and factors above; gates untouched |
| 2 RMS vs a contested label | RMS verdicts at 0.49 and 0.637 N.m (per motion and mixed) in every report with 7.4 V parts |
| 3 12 V parameters flip A | not an engine row: the bench servo test is on the critical path (the bounds sweep still shows armature high, stall low, linear curve) |
| 4 ST3025 armature | SENSITIVITY row in the bounds sweep (0.00399, from BAM's file), not a bound |
| 5-8 R10 | absolute impulse, any strategy, standing + mid single support of walk_forward, one gate (largest recoverable >= requirement), swing time 0.15-0.35 s, 2 steps, lateral double support first, hip strategy unavailable when speed-limited (never a blocker) |
| 9 COP reference | fixed: foot centre (was 5.9-8.0 mm behind it) |
| 10 mass propagation / mj_inverse | unit test + `invdyn.py` cross-check; no fighting found in double support (squeeze 1% BW mean) |
| 11 structure mass | ODM back-out 0.88 kg vs 0.47 (1.86x) -> nominal recentred to 11.9 kg/m^3, bands x0.55-1.4 |
| 12-13 stance flexion, step time | gait sweep, same set for every candidate, best feasible per candidate |
| 14 budget | the sourcing task (T-0002); catalog prices now verified, costs reported |
| 15 fuse vs R10 | bus and fuse sized from the R10 transient and the all-leg stall |
| 16 pickup height | both 0.25 m and 0.45 m run; table height is a parameter of the whole-body planner and the reachable range is reported per concept (T-20261019-a536) |
| 17 knee ROM trade | CAD-limited ranges in the sweep; squat 120 / sit-to-stand 130 run at the limit and flagged |
| 18 stale text | docstrings, LIMITATIONS, this document; the research verification row is the commander's |
