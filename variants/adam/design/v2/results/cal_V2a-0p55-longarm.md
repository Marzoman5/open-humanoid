<!-- written by variants/adam/design/v2/engine.py via r1_calibrated.py (T-20261019-4ab5); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: V2a-0p55-longarm

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | half-cal worst | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | half PASS | calibrated PASS | bounds passed strict / half / cal | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.55 | 4.005 | 40 deg / 0.5 s | 1.245 (hip_roll_l) | 1.569 | 1.889 (hip_roll_l) | ok/ok/ok/ok/ok | True | True | True | 10/11/11 of 13 | armature high; walking speed x1.5 | 0.177 |
| 0.60 | 4.595 | 30 deg / 0.5 s | 1.023 (hip_roll_l) | 1.289 | 1.463 (knee_r) | ok/ok/ok/ok/ok | True | True | True | 4/10/11 of 13 | armature high; walking speed x1.5 | 1.1 |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.028, stand_lat 1.234, walk_fwd 0.67, walk_lat_out 0.886, walk_lat_in 0.696

Invalid motions: pickup_0.45m: reference infeasible: pickup at 0.45 m: the arm covers this height but in every whole-body posture t

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 4.005 | 1.245 | 1.569 | 1.889 (hip_roll_l) | True | True | True | True | - |
| structure mass x0.55 | 3.114 | 1.417 | 1.806 | 1.969 (knee_r) | True | True | True | True | - |
| structure mass x1.4 | 4.797 | 1.053 | 1.327 | 1.598 (hip_roll_l) | True | True | True | True | - |
| wiring/electronics x0.8 | 3.948 | 1.259 | 1.587 | 1.911 (hip_roll_l) | True | True | True | True | - |
| wiring/electronics x1.5 | 4.146 | 1.211 | 1.525 | 1.837 (hip_roll_l) | True | True | True | True | - |
| pessimistic linear torque-speed | 4.005 | 1.016 | 1.107 | 1.199 (hip_pitch_r) | True | True | True | True | - |
| armature low | 4.005 | 1.287 | 1.622 | 1.953 (hip_roll_l) | True | True | True | True | - |
| armature high | 4.005 | 0.869 | 1.095 | 1.319 (hip_pitch_r) | True | False | False | False | - |
| stall low | 4.005 | 0.934 | 1.177 | 1.417 (hip_roll_l) | True | False | True | True | - |
| stall high | 4.005 | 1.291 | 1.794 | 1.942 (knee_r) | True | True | True | True | - |
| walking speed x1.5 | 4.005 | 0.15 | 0.163 | 0.177 (hip_pitch_r) | True | False | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.37) | 4.734 | 1.066 | 1.344 | 1.618 (hip_roll_l) | True | True | True | True | - |
| shelled nominal (structure x1.2) | 4.401 | 1.141 | 1.438 | 1.731 (hip_roll_l) | True | True | True | True | - |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 4.005 | 1.16 | 1.462 | 1.746 (knee_r) | True | True | True | True | - |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.116, stand_lat 1.434, walk_fwd 0.664, walk_lat_out 0.955, walk_lat_in 0.798

Invalid motions: pickup_0.45m: reference infeasible: pickup at 0.45 m: the arm covers this height but in every whole-body posture t

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 4.595 | 1.023 | 1.289 | 1.463 (knee_r) | True | True | True | True | - |
| structure mass x0.55 | 3.439 | 1.227 | 1.37 | 1.483 (knee_r) | True | True | True | True | - |
| structure mass x1.4 | 5.624 | 0.846 | 1.066 | 1.283 (hip_roll_l) | True | False | True | True | - |
| wiring/electronics x0.8 | 4.539 | 1.033 | 1.302 | 1.461 (knee_r) | True | True | True | True | - |
| wiring/electronics x1.5 | 4.737 | 0.998 | 1.257 | 1.47 (knee_r) | True | False | True | True | - |
| pessimistic linear torque-speed | 4.595 | 0.932 | 1.016 | 1.1 (hip_pitch_r) | True | False | True | True | - |
| armature low | 4.595 | 1.051 | 1.324 | 1.595 (hip_roll_l) | True | True | True | True | - |
| armature high | 4.595 | 1.167 | 1.47 | 1.77 (knee_l) | True | False | False | False | - |
| stall low | 4.595 | 0.767 | 0.967 | 1.164 (hip_roll_l) | True | False | False | True | - |
| stall high | 4.595 | 1.061 | 1.351 | 1.463 (knee_r) | True | True | True | True | - |
| walking speed x1.5 | 4.595 | 1.033 | 1.302 | 1.568 (hip_roll_l) | True | False | False | False | - |
| benchmark-fit mass (structure x1.46) | 5.773 | 0.825 | 1.039 | 1.252 (hip_roll_l) | True | False | True | True | - |
| shelled nominal (structure x1.2) | 5.109 | 0.926 | 1.166 | 1.404 (hip_roll_l) | True | False | True | True | - |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 4.595 | 0.953 | 1.195 | 1.294 (knee_r) | True | False | True | True | - |
