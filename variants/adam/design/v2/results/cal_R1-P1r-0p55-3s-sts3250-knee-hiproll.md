<!-- written by variants/adam/design/v2/engine.py via r1_calibrated.py (T-20261019-4ab5); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1-P1r-0p55-3s-sts3250-knee-hiproll

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | half-cal worst | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | half PASS | calibrated PASS | bounds passed strict / half / cal | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.55 | 4.005 | 40 deg / 0.5 s | 1.247 (hip_roll_l) | 1.571 | 1.891 (hip_roll_l) | ok/ok/ok/ok/ok | True | True | True | 10/11/11 of 13 | armature high; walking speed x1.5 | 0.157 |
| 0.60 | 4.595 | 30 deg / 0.5 s | 1.024 (hip_roll_l) | 1.29 | 1.453 (knee_r) | ok/ok/ok/ok/ok | True | True | True | 4/10/11 of 13 | armature high; walking speed x1.5 | 1.098 |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.022, stand_lat 1.079, walk_fwd 0.669, walk_lat_out 0.886, walk_lat_in 0.696

Invalid motions: pickup_0.45m: reference infeasible: pickup at 0.45 m: the arm covers this height but in every whole-body posture t

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 4.005 | 1.247 | 1.571 | 1.891 (hip_roll_l) | True | True | True | True | - |
| structure mass x0.55 | 3.114 | 1.413 | 1.806 | 1.961 (knee_r) | True | True | True | True | - |
| structure mass x1.4 | 4.797 | 1.054 | 1.329 | 1.6 (hip_roll_l) | True | True | True | True | - |
| wiring/electronics x0.8 | 3.948 | 1.261 | 1.589 | 1.913 (hip_roll_l) | True | True | True | True | - |
| wiring/electronics x1.5 | 4.146 | 1.212 | 1.527 | 1.838 (hip_roll_l) | True | True | True | True | - |
| pessimistic linear torque-speed | 4.005 | 1.015 | 1.107 | 1.198 (hip_pitch_r) | True | True | True | True | - |
| armature low | 4.005 | 1.289 | 1.624 | 1.955 (hip_roll_l) | True | True | True | True | - |
| armature high | 4.005 | 0.866 | 1.091 | 1.314 (hip_pitch_r) | True | False | False | False | - |
| stall low | 4.005 | 0.935 | 1.178 | 1.418 (hip_roll_l) | True | False | True | True | - |
| stall high | 4.005 | 1.293 | 1.787 | 1.935 (knee_r) | True | True | True | True | - |
| walking speed x1.5 | 4.005 | 0.133 | 0.145 | 0.157 (hip_pitch_r) | True | False | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.37) | 4.734 | 1.068 | 1.345 | 1.62 (hip_roll_l) | True | True | True | True | - |
| shelled nominal (structure x1.2) | 4.401 | 1.143 | 1.44 | 1.733 (hip_roll_l) | True | True | True | True | - |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 4.005 | 1.161 | 1.463 | 1.739 (knee_r) | True | True | True | True | - |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.114, stand_lat 1.433, walk_fwd 0.661, walk_lat_out 0.838, walk_lat_in 0.797

Invalid motions: pickup_0.45m: reference infeasible: pickup at 0.45 m: the arm covers this height but in every whole-body posture t

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 4.595 | 1.024 | 1.29 | 1.453 (knee_r) | True | True | True | True | - |
| structure mass x0.55 | 3.439 | 1.222 | 1.361 | 1.474 (knee_r) | True | True | True | True | - |
| structure mass x1.4 | 5.624 | 0.847 | 1.067 | 1.285 (hip_roll_l) | True | False | True | True | - |
| wiring/electronics x0.8 | 4.539 | 1.035 | 1.304 | 1.451 (knee_r) | True | True | True | True | - |
| wiring/electronics x1.5 | 4.737 | 0.999 | 1.259 | 1.46 (knee_r) | True | False | True | True | - |
| pessimistic linear torque-speed | 4.595 | 0.93 | 1.014 | 1.098 (hip_pitch_r) | True | False | True | True | - |
| armature low | 4.595 | 1.053 | 1.326 | 1.597 (hip_roll_l) | True | True | True | True | - |
| armature high | 4.595 | 1.165 | 1.468 | 1.767 (knee_l) | True | False | False | False | - |
| stall low | 4.595 | 0.768 | 0.968 | 1.165 (hip_roll_l) | True | False | False | True | - |
| stall high | 4.595 | 1.063 | 1.342 | 1.453 (knee_r) | True | True | True | True | - |
| walking speed x1.5 | 4.595 | 1.034 | 1.303 | 1.569 (hip_roll_l) | True | False | False | False | - |
| benchmark-fit mass (structure x1.46) | 5.773 | 0.826 | 1.041 | 1.253 (hip_roll_l) | True | False | True | True | - |
| shelled nominal (structure x1.2) | 5.109 | 0.927 | 1.168 | 1.406 (hip_roll_l) | True | False | True | True | - |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 4.595 | 0.954 | 1.187 | 1.285 (knee_r) | True | False | True | True | - |
