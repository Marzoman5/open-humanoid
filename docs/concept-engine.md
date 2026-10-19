# Concept engine (P2 concept-loop instruments)

Tooling for ADR 0012: kinematic templates as data, measured actuator models, a frozen motion library, per-joint envelopes with
bounded uncertainty, and a power/voltage trade study. **It measures; it does not pick Adam's design.** Thresholds live in one file
([`openhumanoid/concept/thresholds.yaml`](../openhumanoid/concept/thresholds.yaml)) for the commander to mirror into `pipeline/gates.yaml`.
Task T-0017. Review of the first plan: `variants/adam/reviews/challenge-1-concept-engine.md` (rows 1-20); how each row was handled is in the
[review table](#challenge-1-how-each-row-was-handled).

## Use

```bash
.venv/Scripts/pip install -e ".[sim,cad,dev,concept]"                      # mujoco + casadi
.venv/Scripts/python -m openhumanoid.concept evaluate variants/adam/concepts/A-3s-12v-sts3215.yaml            # full run, ~4 min
.venv/Scripts/python -m openhumanoid.concept evaluate <concept.yaml> --quick                                   # nominal gates only, ~6 s
.venv/Scripts/python -m openhumanoid.concept evaluate <concept.yaml> --samples 64 --table-height 0.30          # bigger Monte Carlo, other table
.venv/Scripts/python -m openhumanoid.concept sweep <concept.yaml> --heights 0.40 0.45 0.50 0.55 0.60 0.65     # height sweep
.venv/Scripts/python -m openhumanoid.concept compare variants/adam/generated/concept/*/report.json
.venv/Scripts/python -m openhumanoid.concept validate-thermal                                                  # replay the Robonine runs
.venv/Scripts/python -m pytest tests/test_concept.py -m "not slow"                                             # fast tests
```

`evaluate` writes `variants/<base>/generated/concept/<candidate>/report.{json,md}` (tool-written, never hand-edited). `openhumanoid/cli.py` is
untouched; the commander wires `python -m openhumanoid.concept` into `oh`.

A **candidate** is a YAML (see `variants/adam/concepts/`): base variant, height, proportion overrides, template, joints (with optional range /
actuator), default actuator, per-joint actuators, optional `transmissions`, the pack / regulator / compute, and the on-board / off-board
parts. Nothing in `openhumanoid/` assumes Adam: `base:` names any variant, `template:` any kinematic template.

## What runs, in order

1. **Robot.** Candidate -> spec (height, proportions, **packaging floors**) -> component-sum mass -> MJCF built from the template -> servo model per joint.
2. **Frozen motions** (the same for every candidate): stand, walk forward / backward, turn in place, squat 90 and 120, wave, dance, table pickup of 150 g, sit-to-stand at 130 deg knee, get-up (stub). Stress walks: 1.5x speed, -20% step time, +-10 ms landing error, one lateral capture step.
3. **Demand.** Each motion is played in MuJoCo (contacts, free base) with a stiff *ideal* torque-source PD. The joint torque it reports is what the motion needs, including the servo's reflected rotor inertia. BAM friction is added for moving joints. A motion that needed more than 1% of body weight of tether force is **invalid**.
4. **Gates** per joint over all motions (below), at the pack's nominal voltage.
5. **Servo in the loop** (tracking, saturation, overload trips, grasp success; *not* envelopes).
6. **Mixed-activity** thermal / battery simulation, runtime, bus analysis, cost.
7. **Uncertainty:** bounds ("tornado") sweep, mass cases incl. the benchmark-fit mass and "mass to first gate failure", small quasi-static Monte Carlo, stress walks.
8. **Report** with a provenance class on every constant.

## Departures from the brief (and why)

| Brief | What was built | Reason |
|---|---|---|
| 12 V STS3215 by physical scaling of the 7.4 V model ("kt same, stall and speed scale with voltage") | **Datasheet-anchored** 12 V model (stall 2.94 N.m, no-load 4.78 rad/s, stall current 2.7 A) with armature / friction / delay borrowed from the 7.4 V fit. The literal scaling is kept as an *optimistic bound* (`servo_spec("sts3215-12v", "bam_scaled")`: 9.2 rad/s, 3.10 N.m) | The 12 V part is a different winding (vendor kt 11 vs 7.8 kg.cm/A) and Robonine measured 45.6 rpm at 12 V. "kt same" predicts 88 rpm. Torque agrees (3.10 scaled vs 2.94 datasheet); speed does not. Uncertainty is widened to +-25% on stall and speed |
| Torque-limited trajectory optimisation with casadi | **LIPM + ZMP preview control + analytic leg IK + COM compensation** for walking; IK + COM balancing for squat / dance / pickup. casadi is used for a **velocity-limited QP smoother** of the dance keyframes (osqp via `ca.qpsol`) | An IPOPT collocation needs a contact model and a long tuning loop; the preview-control gait is checked against MuJoCo (the free-base replay stays upright, tether < 1%) and is a documented *lower bound* on loads (the stress walks bound the gap). casadi earns its place where a convex QP gives a guaranteed speed-limited, jerk-minimal trajectory. Falls back to a moving average when casadi is missing |
| "Play each motion with the actuator model" for envelopes | Envelopes from the **ideal-torque demand**; the actuator model runs separately for tracking / saturation / trips | A clipped servo torque cannot report a demand above its own cap (challenge-1 row 7) |
| Mass +-15%, ±5% on parts | Structure x0.9-1.8, wiring/electronics x0.8-1.5, servos/battery/boards as listed (challenge-1 row 3, which supersedes the first commander note) | Pre-CAD the printed structure is a guess and biased low (no shells); the benchmark fit is only a sanity bound / stress case |
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
| Walk fwd / back | 0.10 m/s, step time 0.50 s (step 50 mm), 8 steps, foot lift 15 mm, 20% double support |
| Turn in place | 0.50 rad/s (0.25 rad per step) |
| Squat | knee flexion 90 and 120 deg, 2.5 s down, 1 s hold |
| Wave | right arm abducted, elbow +-22 deg at 1.25 Hz, 7 s |
| Dance | 80 BPM, 6 phrases of 8 beats (36 s), one joint-speed limit of 3 rad/s for all joints; the QP smoother may deviate **at most 8 deg** from the choreography or the dance is invalid |
| Pickup | 150 g, 40 mm cylinder, table at **0.25 m** (R5 "table height" is undefined: maintainer question Q1; use `--table-height`), right hand, squat just deep enough |
| Sit-to-stand | quasi-static, 130 deg knee (proxy for get-up) |
| Stress walks | step length x1.5; step time x0.8; landing 10 ms early / late; one 30 mm lateral capture step |

`getup` is a stub (listed as infeasible). A reference that violates a joint range is infeasible (so a squat to 130 deg needs the ankle-pitch range the candidates declare, about -75 deg).

## Gates (starting thresholds; `gates:` in thresholds.yaml)

Per joint, worst case over all valid motions, at the pack nominal voltage (cells x 3.7 V):

| Gate | Value | Note |
|---|---|---|
| peak torque / datasheet stall at bus voltage | <= 0.70 | peak = 100 ms moving average of the demand (a stiff ideal replay shows 20-50 ms touchdown spikes no real servo-foot system transmits) |
| RMS / vendor-rated continuous | <= 1.0 | per motion and over the mixed schedule; **the primary thermal gate** |
| torque-speed envelope utilisation | <= 0.90 | demand point vs `tau_available(w, V)` |
| time above 70% of stall | < 0.5 x Protection_Time; no overload trips | replay of the firmware state machine |
| tether | mean <= 1% of body weight | otherwise the **motion is invalid** (counts as a FAIL) |
| MC p95 peak | <= 0.70 | quasi-static dimensions only |
| tracking error | 2 deg, *noted only* | P-servo with learned feed-forward |
| runtime | >= 15 min | a Should: reported, not gating |

`PASS` = every motion valid, nominal gates met, MC p95 within the gate. The report also states `robust_to_all_bounds` and `passes_at_benchmark_mass` (the challenge-1 decision rule: the winner must stay a winner across the bounds and at the benchmark mass).

## Uncertainty

* **Bounds sweep (headline):** structure mass x0.9 / x1.8; wiring+electronics x0.8 / x1.5; pessimistic linear torque-speed; armature low / high (per-actuator spread); stall low / high; Rth high + 40 C ambient; walking speed x1.5. Each row: worst margin, delta vs nominal, what fails.
* **Mass cases:** structure x1.8, the **benchmark-fit mass** (`18.5 h^2.28`, a sanity bound and a stress case only), and **mass to first gate failure** (structure scaled up to x5). The structure coefficient (6.4 kg/m^3) is not recalibrated until shelled CAD exists.
* **Monte Carlo:** 16 samples by default (`--samples`): structure U(0.9, 1.8), wiring U(0.8, 1.5), torso COM shift +-3% h, floor friction 0.5-1.0, stall / armature / Rth spread. p95 per-joint peak and a pass rate.
* **Needs closed loop (P5):** latency 0-40 ms, backlash 0.2-1.0 deg, kp +-10% are run as servo-in-the-loop *sensitivities* on the walk only.

## Packaging floors (every candidate)

From the T-0004 handoff (STS3215 at h = 0.5 m): ankle height >= 0.06 h, foot >= 92 x 55 mm scaled by h/0.5, hip spacing >= 70 mm (servo-fixed, does not scale), shoulder width >= 0.36 h, links >= 60 mm. The report lists which floors raised a candidate. A candidate with a lower ankle would instead have ankle roll limited to +-18 deg. This is a proportion minimum only: no clearance, self-collision, cable or hard-point check exists yet (challenge-1 row 1 sends that to the decision agent).

## Power and voltage trade study (`tradestudy.py`)

Per candidate, in `report.json`/`.md`: torque and speed margins (gate table), peak bus current and per-branch current (legs, arms, torso/head), pack sag and **minimum voltage at the farthest servo** (assumed 20 mOhm per branch), **fuse sizing** (1.25 x peak, next standard value; the STS3215 connector rating is unknown), runtime (usable 85% of nominal Wh at the mixed-activity average power incl. compute, camera and a 0.03 A/servo standby assumption), pack mass and C-rating check, regulator check for the on-board 5 V rail, BOM cost with **low / typical / high** price bands (the decision needs a pass at the high price), **time over voltage rating with the mitigation and its cost** (e.g. 2S full charge 8.4 V vs the 7.4 V rating: over for 80% of the discharge, mitigation = charge to 3.7 V/cell and lose 80% of the capacity; 3S full 12.6 V vs the STS3250 12 V rating: charge to 4.0 V/cell and lose ~23%), and **actuator-model quality** (7.4 V measured, 12 V extrapolated, STS3250 datasheet-only, with bus voltage vs model voltage). One bus voltage serves all servos: a mix is evaluated with each part's stall and speed scaled to the bus.

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
* **Known-robot check:** `variants/adam/concepts/duck-like-0p42-2s-sts3215.yaml` (0.42 m, 14 STS3215 7.4 V, 2S) through the same frozen motions. It is not Open Duck: the real proportions are not in the research, so spec defaults + packaging floors are used. Its result calibrates how strict the gates are for a robot that does walk (see the results below).

## Known limitations

1. The walking reference is a LIPM/ZMP gait, a lower bound on loads for a real balancing controller; the stress walks narrow but do not close the gap. No trajectory optimisation was built.
2. Reflected rotor inertia (BAM armature 0.0234 kg m^2) dominates the dynamic torque and comes from a 7.4 V identification; applying it to 12 V and STS3250 servos is an extrapolation (+-50% in the sweep).
3. The 12 V mid-speed torque curve is unverified; anchored vs pessimistic linear brackets it. A bench test of one 12 V and one 7.4 V servo is the cheapest way to close this (maintainer question Q2).
4. Printed structure + shell mass is a pre-CAD guess; the model has no shells, brackets or fasteners beyond the catalog kit masses. Nothing is checked for packaging fit.
5. The thermal model fails the Robonine replay (under-predicts the oscillation run by ~19 K); RMS vs rated continuous is the only thermal gate. The vendor "rated torque" is not a measured limit.
6. Overload Protection_Time is unit-unconfirmed; standby current, camera power, wire resistance and the usage mix are assumptions.
7. Table height (R5), get-up (maintainer Q3) and the min walk speed are placeholders / stubs; the quasi-static sit-to-stand at 130 deg only proxies get-up.
8. No-wrist 3-DOF arm: the pickup reports the jaw-axis angle; the gripper holds with a reduced torque limit (15%), a firmware setting the HAL must reproduce.
9. The tether is a very soft pelvis pull (6% cap, mean must be < 1%); a gait that cannot stand without it is invalid, but passing says nothing about push recovery.

## Files

`openhumanoid/templates/` (data) - `openhumanoid/actuators/` (`servo.py`, `data/`) - `openhumanoid/concept/` (`robot.py`, `kin.py`, `motions/`, `playback.py`, `envelopes.py`, `evaluate.py`, `tradestudy.py`, `power.py`, `thermal_validation.py`, `provenance.py`, `thresholds.yaml`, `__main__.py`) - catalog additions in `catalog/power|electronics|compute` - `tests/test_concept.py`.

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
| 11 stress walks, get-up | four stress walks + sit-to-stand 130 (get-up still a stub) |
| 12 known robot | duck-like concept through the gates |
| 13 neck pitch, camera, compute | in every example BOM / mass / power; regulator check |
| 14 height / anchoring | `sweep` command (0.40-0.65 m); per-joint utilisation ranking; candidates share everything but power / actuators |
| 15 rating | time over rating + mitigation |
| 16 BAM fidelity | test vs upstream |
| 18 bus | branch currents, far-servo voltage, fuse |
| 19 cost | low / typical / high bands |
| 20 LIPM vs trajopt | recorded under "Departures" |
| 1, 17 | decision agent / commander |
