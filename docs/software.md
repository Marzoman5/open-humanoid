# Software-in-the-loop: the Open Humanoid runtime (task T-20261019-2adc)

The robot software runs end to end against MuJoCo plus the **measured servo model**, so the codebase is simulated before hardware exists.
The same loop, safety layer, estimator, behaviours and command API run on the robot; only the HAL changes.

```
 gamepad ─┐                                   ┌──────────── runtime.Runtime.step()  (fixed 100 Hz) ─────────────┐
 phone UI ├─ Command API v1 (JSON) ─ CommandBus ─►  estimator ─► safety.monitor ─► BehaviourManager ─► Safety.filter ─► HAL.write
 TCP/LLM ─┘   (velocity, behaviour, pose,         │  (IMU + kinematics)  (fall, temp,        (Gait planner,     (limits, rate,     │
               look_at, stop, estop, status)      │                       battery, e-stop)    stabiliser,         torque derate,     │
                                                   │                                           wave/dance/pickup)  e-stop, fall pose)│
                                                   └─────────────────────────────── HAL.read ◄────────────────────────────────────┘
 HAL = SimHAL (MuJoCo + ServoBank + battery + IMU)   or   FeetechHAL (STS3215 bus + BNO085; UNTESTED on hardware)
```

Everything is in `openhumanoid/runtime/` (variant-agnostic: pass any concept YAML). Adam's configuration is `software/configs/adam.yaml`
(R1 provisional hardware: 0.55 m, 4.0 kg, 23 DOF, 3S, Pi 5). Tests: `tests/test_runtime.py`. CLI: `python -m openhumanoid.runtime`.

```bash
.venv/Scripts/python -m openhumanoid.runtime scenarios            # all acceptance scenarios, pass/fail table (about 1 minute)
.venv/Scripts/python -m openhumanoid.runtime run --config software/configs/adam.yaml --web 8080 --tcp 8765 --realtime
.venv/Scripts/python -m openhumanoid.runtime bench --seconds 20   # control-loop compute time + Raspberry Pi 5 estimate
.venv/Scripts/python -m openhumanoid.runtime pushscan stand fwd back   # largest recoverable push per direction
.venv/Scripts/python -m pytest tests/test_runtime.py -m "not slow"     # 10 s
.venv/Scripts/python -m pytest tests/test_runtime.py                   # full set, about 1 minute
```

## What is real and what is not

| Part | Status |
|---|---|
| Runtime loop, estimator, safety, gait, behaviours, command API, gamepad/web/TCP front ends | implemented; exercised in sim and in unit tests |
| `SimHAL` (MuJoCo, concept-engine `ServoBank`, battery, IMU) | implemented; the concept engine's actuator model is reused, not re-implemented |
| `FeetechHAL` (+ LeRobot adapter, register map, conversions) | **interface + mapping only, tested against a mock register file, never run on a servo.** Register addresses are from memory of the STS table as mirrored by LeRobot; `check_register_map()` compares them with LeRobot when installed. First power-up is a bench test |
| BNO085 driver | **not written** (`Bno085Imu` raises `NotImplementedError`) |
| Walking controller | interim LIPM/DCM footstep controller (this file). **Not** the P5 RL policy |
| Everything numeric about the servos | the concept engine's extrapolated 12 V model: **provisional until the bench identification** (ADR 0014) |

## Layers (software/README.md plan, as built)

| Layer | Module | Notes |
|---|---|---|
| robot model | `model.py` | `RobotModel.from_concept()`: joints, limits, servo specs, masses, kinematic model, all from `concept.robot.build_robot` |
| HAL interface | `hal/base.py` | `read() -> HalState`, `write(JointCmd)`, `tick()` at a fixed rate; position, velocity, load, current, temperature, voltage + IMU in; goal position, torque limit, enable, P-gain scale out |
| SimHAL | `hal/sim.py` | see below |
| FeetechHAL | `hal/feetech.py` | see below |
| estimator | `estimator.py` | attitude (Mahony), whole-body COM and feet from kinematics, contact weights, COM state relative to the support |
| safety | `safety.py` | the only path to the HAL |
| planner | `locomotion.py` | online DCM footstep gait: hold / weight shift / step |
| behaviours | `control.py`, `clips.py` | stand, walk, wave, dance, pickup (+carry), look-at, pose, crouch, safe-fall; the motion library is compiled to cached clips |
| commands | `commands.py`, `frontends/` | API v1; gamepad mapper, phone web UI, JSON-lines TCP |
| scenarios, bench | `scenarios.py`, `bench.py` | the acceptance tests and the CPU budget |

### SimHAL: what is simulated

* MuJoCo physics of the concept robot (free base, contacts, 2 ms step, control at 100 Hz = 5 substeps).
* Per joint the concept engine's `ServoBank`: BAM-identified firmware law (P gain, 4.9 ms command delay + 3 ms assumed bus latency, rate limit),
  DC torque-speed with the datasheet stall cap, load-dependent friction, backlash, armature, and the firmware overload protection state machine.
  `ThermalBank` gives temperatures; the servo firmware shuts a servo off at its `max_temp_c` (70 C) and latches until it cools 10 C.
* Register semantics: goal position quantised to 4096 counts per servo revolution, torque limit as a fraction of stall, torque enable, P-gain scale; read-back of position, speed (+noise), load, current, temperature (integer C), voltage (0.1 V).
* `concept.power.Pack` battery (open-circuit curve, internal resistance, sag) fed by the summed servo draw plus 5 W of compute.
* IMU on the pelvis: gyro + accelerometer with white noise (0.004 rad/s, 0.06 m/s^2), a drifting gyro bias and 6 ms latency.
* **Not simulated:** dropped bus packets, calibration offsets, cable drag, foot compliance beyond MuJoCo's contact, Pi scheduling jitter, the Feetech D/I registers (see findings).
* Ground truth (`ground_truth()`) exists only to score scenarios; the runtime never reads it.

### FeetechHAL: what exists

`ServoMap` (id, sign, zero offset per joint, ratio), conversions (counts, sign-magnitude speed and load, 0.1 V, 6.5 mA per count, torque limit
0..1000), a `Bus` protocol with `LeRobotBus` (adapter over `lerobot.motors.SerialMotorsBus`, lazy import) and `MockBus`, one `sync_read` of the six status
registers and one `sync_write` each of Goal_Position / Torque_Limit per cycle, `configure()` for P/D/I/torque limit, `tick()` pacing, `close()` torques off. The code
carries `TESTED_ON_HARDWARE = False` and warns at construction. Reuse: LeRobot is imported at run time, no source is copied (license below).

## Safety layer

Nothing reaches the servos except through `Safety.filter` (behaviours do not hold a HAL reference).

| Mechanism | Behaviour |
|---|---|
| joint limits, rate limit | every goal is clamped to the spec limits (margin 0.02 rad) and to 0.85 of the servo's no-load speed per tick; NaN targets hold the last safe command |
| e-stop | a latch (software command, hardware input via `HAL.estop_pressed`, watchdog); every servo torqued off in the same cycle, commands ignored, `reset_estop` refused while the robot is moving or tilted and comes back **limp** (needs `enable`). A hard e-stop on a standing robot makes it fall: that is the defined behaviour |
| temperature | linear torque derate from 55 C to 40 % at 65 C; at 65 C a controlled **crouch** (3 s lowering) then torque off. The servo firmware cuts at 70 C regardless |
| battery | filtered loaded cell voltage < 3.55 V: warning, new walking/dance/pickup refused; < 3.35 V: crouch then torque off |
| overload | firmware overload protection on >= 3 servos at once starts the crouch |
| fall | tilt > 32 deg, or > 18 deg and rising faster than 2 rad/s: **safe-fall pose** (legs tucked, arms folded, torque limited to 45 %), torque off after 1 s at rest |
| command dead-man | velocity commands expire after `ttl` (default 0.5 s); the gamepad needs LB held |

## Estimator

Mahony attitude filter (gyro + gravity from the accelerometer, trust scaled down away from 1 g), gyro bias taken only from a still start-up window;
`mj_kinematics` + `mj_comPos` on the runtime's own model (15 us) give the COM and foot soles in the pelvis frame; contact weights come from the gait schedule;
the COM relative to the support point and its velocity (alpha-beta tracker per foot) feed the DCM. Tested against ground truth: tilt within 1.5 deg, COM-over-support within 6 mm mean.

## Locomotion: how the interim walking controller works

* **Planner** (`locomotion.Gait`): a virtual LIPM (COM position and velocity) is advanced with the planned centre of pressure; the pelvis target is the virtual COM minus the kinematic COM offset (2 FK passes), legs by the concept engine's analytic IK (`kin.lower_body`).
* **Foot placement:** deadbeat on the divergent component of motion. With step time T, double support T_ds, omega = sqrt(g / z_com), kappa = (e^{w T_ds} - 1 - w T_ds) / (w T_ds), the periodic orbit has the DCM offset to the new stance foot `b = (1 + kappa) L / (e^{wT} - 1)` along the motion and `(1 + kappa) s_y w0 / (e^{wT} + 1)` across it (alternating); from the current offset `u`, the landing displacement is `dP = (e^{w (t_rem + T_ds)} u - b_next) / (1 + kappa)`. The landing is recomputed every tick until 45 ms before touchdown, so a disturbance moves the foot. Inside the foot, the COP is modulated (gain 2.5) to hold the DCM on the nominal orbit.
* **Feedback that matters:** (1) the IMU orientation PD + integral on the ankles of the weight-bearing feet; (2) a slow estimate of the COM plan error (servo sag) subtracted from the pelvis command; (3) at each touchdown the virtual state takes 30 % of the measured deviation; (4) joint-level damping injection `q_cmd -= 0.03 * speed` and an upper-body integrator, both stand-ins for the Feetech D and I coefficients.
* Stands, steps forward/back/sideways, turns, stops with a square-up step. Limits: 0.16 m/s, 0.08 m/s, 0.6 rad/s commanded (the longest run is 0.15 m/s).

## Command API v1 (R9)

One versioned JSON interface, three front ends, same messages for sim and hardware. `python -m openhumanoid.runtime describe` prints it.

| cmd | fields | effect |
|---|---|---|
| `velocity` | `vx`, `vy` (m/s), `wz` (rad/s), `ttl` (s) | walk; expires after `ttl` (dead-man) |
| `behaviour` | `name` stand/walk/wave/dance/pickup, `params` | start (wave: `side`; dance: `n_phrases`, `bpm`; pickup: `table_height_m`; stand: `release` drops a carried object pose) |
| `stop` | `name` optional | stop a behaviour (none: everything) |
| `pose` | `joints` {name: rad} | upper-body joint targets, clamped; legs refused |
| `look_at` | `target` [x,y,z] in the body frame, or null | neck + waist toward a point (a person) |
| `estop`, `reset_estop`, `enable` | | safety |
| `status`, `describe` | | battery, safety state, behaviour, tilt, hottest servo, last events; the schema |

Reply: `{"v":1,"id":...,"ok":true,"result":{...}}` or `{"ok":false,"error":{"code":"invalid","message":"..."}}`. Examples:

```json
{"v":1,"id":"7","cmd":"velocity","vx":0.1,"vy":0,"wz":0,"ttl":0.5}
{"v":1,"cmd":"behaviour","name":"wave","params":{"side":"r"}}
{"v":1,"cmd":"look_at","target":[1.0,0.6,0.3]}
```

* **Gamepad** (`frontends/gamepad.py`): stateless mapper (tested with scripted pad states) + a pygame reader. LB is the dead-man, sticks give velocity, A/B/X/Y = stand/wave/dance/pickup, D-pad looks, hold BACK for the e-stop. Works with no network (R8).
* **Phone UI** (`frontends/web.py`): stdlib HTTP server, a single page with two touch sticks and buttons; `--host 0.0.0.0 --token T` to use it from a phone on the robot's hotspot.
* **JSON lines over TCP** (port 8765): one JSON object per line, one reply per line; this is the transport for the later LLM/MCP plugin. The plugin's tools (`walk`, `turn`, `look_at`, `pose`, `status`, `say`, `get_camera_frame`) map onto `velocity`+`ttl`, `look_at`, `pose`, `status`; **gaps for the plugin (not blockers):** `say` and camera frames are not in the runtime yet, and a "walk N metres / turn N degrees" convenience needs odometry in `status` (the scenarios do it client-side from the foot odometry and gyro yaw; adding `odometry` to `status` is a one-line follow-up).

## Results

### Acceptance scenarios (sim, R1-P1r concept, `python -m openhumanoid.runtime scenarios`)

| Scenario | Result | Measured (ground truth) |
|---|---|---|
| stand 60 s | **PASS** | max tilt 1.3 deg, COM within 6 mm of the support centre, no safety reason raised |
| walk 2 m forward, turn 90 deg | **PASS** | 1.96 m (lateral +0.15 m), turn 89.1 deg, max tilt 2.1 deg, commanded through the velocity API from the runtime's own odometry and gyro yaw (0.12 m/s, 0.35 rad/s) |
| push 0.45 N s while standing: fwd / back / left / right | **PASS x4** | max tilt 1.3 / 2.2 / 1.3 / 1.3 deg, no step needed |
| push 0.45 N s while walking (mid single support of footfall 3 and 4): fwd / back / left / right | **PASS x8** | max tilt 1.8 / 2.7 / 1.9 / 2.7 deg (footfall 4), walking continues |
| wave | **PASS** | shoulder roll abducted to 73 deg, elbow swing 66 deg peak to peak, tilt 1.3 deg, clip finishes |
| dance, 36 s clip (6 phrases at 80 BPM) | **PASS** | 39.1 s with lead-in/out, max tilt 1.5 deg, 0 overload trips, hottest servo 25 C |
| pick-up at a 0.30 m table (R1-P1r reachable range 0.206-0.384 m) | **PASS** | object lifted 39 mm, still held 20 mm above its rest height 2 s after the clip, tilt < 1.5 deg |
| look at a person (1 m ahead, 0.6 m left) | **PASS** | head axis 0.9 deg from the target |
| e-stop while walking, client keeps sending commands | **PASS** | all servos torqued off within 1 cycle, stays off; reset refused while moving |
| overheat (knee 66 C) | **PASS** | detected in the same cycle, controlled crouch, torque off, tilt 2.5 deg, no fall |
| low battery (1 % state of charge) | **PASS** | warning at 1.4 s (new walking refused), cutoff crouch, torque off, no fall |
| fall (3 N s push) | **PASS** | detected 0.18 s after the push, safe-fall pose commanded (knee error 0.0 rad), torque limited to 45 %, torque off at rest |

All 18 scenario rows above pass (`41 passed` in `tests/test_runtime.py`, 54 s). Where it does **not** pass yet: **50 Hz control**
(the likely hardware rate, see timing) passes stand and dance but the 2 m walk stops at 1.75 m (-12 %, the criterion is -10 %; turn and
tilt fine); walking has only been run at nominal mass/friction and one sensor-noise seed (no randomisation: that is P5 / R2 acceptance).

### Push recovery (R10), closed-loop controller

Push = a 50 ms force pulse on the torso, impulse in N s (the requirement is the provisional 0.45 N s of the concept engine, `thresholds.yaml`). "Recovers" =
no fall and upright (< 3 deg standing, < 6 deg walking) 3-4 s later. Largest recoverable impulse by scan (0.25 steps) and bisection (0.1 N s):

| Largest recoverable impulse (N s) | fwd | back | left | right | requirement |
|---|---|---|---|---|---|
| standing, passive servo stiffness only (no IMU loop, no capture) | 1.00 | 0.94 | 1.31 | 1.31 | 0.45 |
| **standing, default controller** (IMU ankle loop + COM bias hold; capture off) | **0.88** | **0.81** | **1.31** | **1.31** | 0.45 |
| standing, + opt-in capture step | 0.94 | 0.69 | 1.38 | 1.31 | 0.45 |
| **walking, default controller** (push at mid single support, footfalls 3 and 4 give the same verdict at 0.45) | **0.94** | **0.81** | **0.50** | **0.88** | 0.45 |
| walking with the touchdown re-seed from the estimator off | does not walk (fails at 0.25) | | | | |

Reading it honestly:

* The requirement (0.45 N s) is met in all four directions standing and walking, at both stance parities, with margin: standing 1.8x to 2.0x forward/back and 2.9x sideways, walking 1.1x (left, toward the outside of the stance foot at mid single support: the worst case) to 2.1x.
* **Most of the standing margin is the servo stiffness**: with no stabiliser at all ("passive") the robot absorbs 1.0 N s forward; the IMU ankle loop does not extend that (it is there for the steady state and the walk), and it costs roughly 10 %. Physically, 1.0 N s = 0.25 m/s of COM speed = a DCM offset of 3.8 cm, about the half-length of the 10 cm foot: the limit is the support polygon.
* **The standing capture step does not help**: it is implemented (weight shift, swing, DCM landing, opt-in `capture_enable`) but every measured configuration is at best equal to, and between 0.8 and 1.0 N s worse than, doing nothing, because the lateral weight shift takes ~0.15 s and the DCM has already left the foot by then (the concept engine's capture-step plan assumed instant unloading). Stepping capacity beyond ~1 N s needs either the RL policy (P5) or a hip/trunk strategy (not built).
* The walking controller does depend on the measured feedback: with the touchdown re-seed from the estimator switched off ("open") it does not walk reliably at all.
* Push model caveat: the sim's ankle/knee stiffness (about 30-40 N m/rad per servo, 6.5 Hz, damping ratio 0.4) comes from the extrapolated 12 V model; the bench identification of a real 12 V STS3215 can move every number here.

### Loop timing and the Raspberry Pi 5 (R8)

Measured on the development machine (Intel Core, Raptor Lake mobile, Python 3.11, numpy; **HAL calls excluded**, because on the robot they are bus transfers, not CPU work).
`python -m openhumanoid.runtime bench`:

| Case | mean | p99 | max | share of a 10 ms period (mean / p99) |
|---|---|---|---|---|
| standing | 0.59 ms | 1.06 ms | 9.5 ms (one-off) | 6 % / 11 % |
| walking 0.1 m/s | 0.67 ms | 1.18 ms | 5.0 ms | 7 % / 12 % |
| dance playback | 0.25 ms | 0.51 ms | 2.3 ms | 3 % / 5 % |

**Raspberry Pi 5 (estimate, NOT measured: no board available).** Scaling the host numbers by 3.5x (assumed single-thread ratio, range 3-5x for small numpy/Python loops):
standing 2.1 ms mean (3.2-5.3 ms p99), walking 2.4 ms mean (3.5-5.9 ms p99): **about 24 % of one core at 100 Hz, 12 % at 50 Hz**. The runtime is single-threaded Python;
the planners (casadi dance smoothing ~10 s, pickup planner) are compiled offline to cached clips and are not needed on the robot. Measure on the real board before relying on it.

**The bus, not the CPU, is the 100 Hz risk.** One status read per servo of the contiguous block Present_Position..Present_Current (15 bytes, reply 21 bytes) plus one
goal/torque-limit write (8 bytes) is about 23 x (0.3 + 0.1) ms of 1 Mbit/s TTL traffic = roughly 9-10 ms per cycle for 23 servos on one adapter (estimate from byte counts;
verify on the bench). `FeetechHAL.read()` as written issues six separate sync-reads and must be changed to a block read before bring-up. Plan for **50 Hz on one bus**, or two adapters
(legs / rest) for 100 Hz. At 50 Hz the runtime works in sim (stand, dance pass; walking slightly under-speed as noted above).

## Findings the concept engine and P5 should know

1. **The identified servo (BAM law, P only) is a lightly damped spring.** Armature 0.0234 kg m^2 and about 30-39 N m/rad stiffness give a 6.5 Hz resonance with damping ratio ~0.4; a 2 cm COM step overshoots by 30 %. The runtime adds `q_cmd -= 0.03 * speed` (equivalent to ~1.2 N m s/rad extra damping); on hardware set the Feetech D coefficient and verify, since the real STS3215 firmware has a D term the BAM law does not model.
2. **The engine's tether hid the load-proportional servo sag** (3-6 deg of pelvis pitch standing, ~1 cm of COM). Untethered, the runtime needs an integral term (ankle integrator, COM-plan bias estimate, upper-body integrator). The Feetech I coefficient is the hardware equivalent.
3. **Lateral weight shift is the slow, hard part** of every stepping behaviour on this robot: the real COM follows the commanded one with ~60 ms lag and overshoots; the planner leads the command by 30 ms and uses a DCM tracker for the shift. A measured-state controller that feeds the raw lagged measurement back into the footstep rule is unstable (tested): the measurement enters only through the touchdown re-seed.
4. Dance (36 s) and the 150 g pick-up at a 0.30 m table run untethered in closed loop at tilt < 1.6 deg, no overload trips, hottest servo 25 C (a 36 s clip at 25 C ambient says nothing about the thermal model, which is unvalidated).

## What P5 (RL) and the bench data must still supply

**P5:** a walking policy that replaces `locomotion.Gait` behind the same `Behaviour` interface (velocity command in, joint targets out), robust walking beyond 0.15 m/s and over friction/mass randomisation, push recovery above ~1 N s standing and above 0.5 N s lateral while walking (cross-step / hip strategy), sit-to-stand and get-up (not required yet), and the 10 m x 5 seeds R2 acceptance. The interim controller has not been run under randomisation: only one seed of sensor noise, nominal mass and friction.
**Bench data (ADR 0014):** a real 12 V STS3215 and STS3250 identification (stiffness, damping, delay, torque-speed, overload protection time unit), the D/I register behaviour, the real servo temperature model, and a measurement of the actual register map. Until then every torque, push and thermal number here is as good as the extrapolated model.
**Not in this task:** the BNO085 driver, the FeetechHAL first power-up, the LLM/MCP plugin, camera.

## Reuse and licenses

* `openhumanoid.actuators` (BAM-derived servo model, Apache-2.0), `openhumanoid.concept.*` (kinematics, IK, motion library, power model): used unchanged. **No file under `openhumanoid/concept/` or `openhumanoid/actuators/` was edited.**
* LeRobot (`huggingface/lerobot`): LICENSE read 2026-10-19 at commit `b192c02dda8d7fa8560bfc15f9e8dae0f714e26e`: Apache-2.0 (Copyright 2024 The HuggingFace Inc. team) with MIT notices for third-party code. `FeetechHAL` imports `lerobot.motors.SerialMotorsBus` lazily and copies no source. The driver has moved since the research note: `lerobot.motors.feetech.FeetechMotorsBus` is now a deprecated alias of `SerialMotorsBus`; the adapter uses the new name. Recorded in `THIRD_PARTY.md`.
* The LIPM/DCM equations are written from the published method (Kajita 2003 for preview control in the concept engine; the DCM foot-placement derivation is own work from the LIPM solution). No Open Duck / ToddlerBot code was read or used.
