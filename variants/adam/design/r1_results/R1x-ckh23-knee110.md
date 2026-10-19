<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-ckh23-knee110

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | calibrated PASS | robust (cal) across bounds | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.60 | 4.595 | 45 deg / 0.5 s | 1.019 (hip_roll_l) | 1.546 (hip_roll_l) | ok/ok/ok/ok/ok | True | True | False | armature high | 1.16 |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.316, stand_lat 1.503, walk_fwd 0.925, walk_lat_out 0.968, walk_lat_in 1.099

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 4.595 | 1.019 | 1.546 (hip_roll_l) | True | True | True | - |
| structure mass x0.55 | 3.439 | 1.335 | 2.025 (hip_roll_l) | True | True | True | - |
| structure mass x1.4 | 5.624 | 0.842 | 1.277 (hip_roll_l) | True | False | True | - |
| wiring/electronics x0.8 | 4.539 | 1.03 | 1.562 (hip_roll_l) | True | True | True | - |
| wiring/electronics x1.5 | 4.737 | 0.994 | 1.507 (hip_roll_l) | True | False | True | - |
| pessimistic linear torque-speed | 4.595 | 1.019 | 1.356 (hip_yaw_r) | True | True | True | - |
| armature low | 4.595 | 1.048 | 1.59 (hip_roll_l) | True | True | True | - |
| armature high | 4.595 | 0.95 | 1.459 (ankle_pitch_l) | True | False | False | - |
| stall low | 4.595 | 0.764 | 1.16 (hip_roll_l) | True | False | True | - |
| stall high | 4.595 | 1.071 | 1.775 (hip_roll_l) | True | True | True | - |
| walking speed x1.5 | 4.595 | 0.891 | 1.23 (hip_pitch_r) | True | False | True | - |
| benchmark-fit mass (structure x1.46) | 5.773 | 0.821 | 1.246 (hip_roll_l) | True | False | True | - |
