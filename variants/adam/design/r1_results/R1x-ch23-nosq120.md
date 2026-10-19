<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-ch23-nosq120

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | half-cal worst | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | half PASS | calibrated PASS | bounds passed strict / half / cal | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.55 | 3.966 | 40 deg / 0.5 s | 1.0 (knee_r) | 1.376 | 1.657 (knee_l) | ok/ok/ok/ok/ok | True | True | True | 5/11/11 of 13 | pessimistic linear torque-speed; walking speed x1.5 | 0.106 |
| 0.60 | 4.556 | 30 deg / 0.5 s | 0.872 (knee_l) | 1.079 | 1.169 (knee_r) | ok/ok/ok/ok/ok | False | True | True | 1/5/6 of 13 | structure mass x1.4; pessimistic linear torque-speed; armature high; stall low; walking speed x1.5; benchmark-fit mass (structure x1.47); low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 0.415 |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.016, stand_lat 1.067, walk_fwd 0.597, walk_lat_out 0.767, walk_lat_in 0.581

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 3.966 | 1.0 | 1.376 | 1.657 (knee_l) | True | True | True | True | - |
| structure mass x0.55 | 3.075 | 1.11 | 1.624 | 1.955 (knee_r) | True | True | True | True | - |
| structure mass x1.4 | 4.758 | 0.898 | 1.167 | 1.405 (knee_l) | True | False | True | True | - |
| wiring/electronics x0.8 | 3.909 | 1.012 | 1.399 | 1.685 (knee_l) | True | True | True | True | - |
| wiring/electronics x1.5 | 4.107 | 0.975 | 1.321 | 1.59 (knee_l) | True | False | True | True | - |
| pessimistic linear torque-speed | 3.966 | 0.76 | 0.828 | 0.897 (knee_r) | True | False | False | False | knee_l: ['envelope']; knee_r: ['envelope'] |
| armature low | 3.966 | 1.065 | 1.383 | 1.665 (knee_l) | True | True | True | True | - |
| armature high | 3.966 | 0.833 | 1.124 | 1.353 (knee_r) | True | False | True | True | - |
| stall low | 3.966 | 0.819 | 1.032 | 1.136 (knee_l) | True | False | True | True | - |
| stall high | 3.966 | 1.0 | 1.471 | 1.941 (knee_r) | True | True | True | True | - |
| walking speed x1.5 | 3.966 | 0.09 | 0.098 | 0.106 (knee_l) | True | False | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.39) | 4.734 | 0.903 | 1.172 | 1.412 (knee_l) | True | False | True | True | - |
| shelled nominal (structure x1.2) | 4.362 | 0.963 | 1.263 | 1.521 (knee_l) | True | False | True | True | - |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 3.966 | 1.0 | 1.282 | 1.543 (knee_l) | True | True | True | True | - |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.873, stand_lat 1.419, walk_fwd 0.655, walk_lat_out 0.712, walk_lat_in 0.611

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 4.556 | 0.872 | 1.079 | 1.169 (knee_r) | True | False | True | True | - |
| structure mass x0.55 | 3.4 | 1.009 | 1.099 | 1.19 (knee_r) | True | True | True | True | - |
| structure mass x1.4 | 5.585 | 0.723 | 0.911 | 0.971 (knee_l) | True | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| wiring/electronics x0.8 | 4.5 | 0.885 | 1.078 | 1.167 (knee_r) | True | False | True | True | - |
| wiring/electronics x1.5 | 4.698 | 0.841 | 1.06 | 1.173 (knee_r) | True | False | True | True | - |
| pessimistic linear torque-speed | 4.556 | 0.457 | 0.498 | 0.539 (knee_r) | False | False | False | False | knee_l: ['envelope']; knee_r: ['envelope'] R10: walk_lat_out |
| armature low | 4.556 | 0.876 | 1.104 | 1.329 (knee_l) | True | False | True | True | - |
| armature high | 4.556 | 0.708 | 0.772 | 0.836 (knee_r) | True | False | False | False | knee_l: ['envelope']; knee_r: ['envelope'] |
| stall low | 4.556 | 0.415 | 0.415 | 0.415 (knee_l) | True | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| stall high | 4.556 | 0.895 | 1.079 | 1.169 (knee_r) | True | False | True | True | - |
| walking speed x1.5 | 4.556 | 0.872 | 1.099 | 1.324 (knee_l) | True | False | False | False | - |
| benchmark-fit mass (structure x1.47) | 5.773 | 0.701 | 0.884 | 0.926 (knee_l) | True | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| shelled nominal (structure x1.2) | 5.07 | 0.791 | 0.997 | 1.136 (knee_l) | True | False | False | True | - |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 4.556 | 0.661 | 0.72 | 0.78 (knee_r) | False | False | False | False | knee_l: ['envelope']; knee_r: ['envelope'] R10: walk_lat_out |
