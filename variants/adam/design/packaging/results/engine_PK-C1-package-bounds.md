<!-- written by variants/adam/design/packaging/engine.py via r1_calibrated.py (T-20261019-c1aa); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: PK-C1-package

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | half-cal worst | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | half PASS | calibrated PASS | bounds passed strict / half / cal | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.55 | 3.655 | 40 deg / 0.5 s | 1.198 (shoulder_roll_r) | 1.379 | 1.493 (shoulder_pitch_r) | ok/ok/ok/ok/ok | True | True | True | 7/11/11 of 13 | armature high; walking speed x1.5 | 0.106 |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.933, stand_lat 1.137, walk_fwd 0.608, walk_lat_out 0.809, walk_lat_in 0.633

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 3.655 | 1.198 | 1.379 | 1.493 (shoulder_pitch_r) | True | True | True | True | - |
| structure mass x0.55 | 2.765 | 1.375 | 1.701 | 1.842 (knee_r) | True | True | True | True | - |
| structure mass x1.4 | 4.447 | 0.929 | 1.102 | 1.193 (shoulder_pitch_r) | True | False | True | True | - |
| wiring/electronics x0.8 | 3.6 | 1.198 | 1.379 | 1.493 (shoulder_pitch_r) | True | True | True | True | - |
| wiring/electronics x1.5 | 3.794 | 1.198 | 1.38 | 1.494 (shoulder_pitch_r) | True | True | True | True | - |
| pessimistic linear torque-speed | 3.655 | 0.996 | 1.085 | 1.175 (hip_pitch_r) | True | False | True | True | - |
| armature low | 3.655 | 1.198 | 1.398 | 1.513 (shoulder_pitch_r) | True | True | True | True | - |
| armature high | 3.655 | 0.864 | 1.089 | 1.311 (hip_pitch_l) | True | False | False | False | - |
| stall low | 3.655 | 0.881 | 1.11 | 1.336 (shoulder_roll_l) | True | False | True | True | - |
| stall high | 3.655 | 1.198 | 1.379 | 1.493 (shoulder_pitch_r) | True | True | True | True | - |
| walking speed x1.5 | 3.655 | 0.09 | 0.098 | 0.106 (hip_pitch_l) | True | False | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.54) | 4.734 | 0.859 | 1.028 | 1.112 (shoulder_pitch_r) | True | False | True | True | - |
| shelled nominal (structure x1.2) | 4.051 | 1.046 | 1.225 | 1.327 (shoulder_pitch_r) | True | True | True | True | - |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 3.655 | 1.198 | 1.379 | 1.493 (shoulder_pitch_r) | True | True | True | True | - |
