<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-a21-5dof

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | calibrated PASS | robust (cal) across bounds | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.50 | 3.312 | 40 deg / 0.25 s | 1.15 (knee_l) | 1.745 (knee_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.33) | 1.266 |
| 0.55 | 3.805 | 45 deg / 0.25 s | 0.919 (knee_l) | 1.394 (knee_l) | ok/ok/ok/ok/ok | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.47) | 0.806 |
| 0.60 | 4.395 | 45 deg / 0.25 s | 0.73 (knee_l) | 0.893 (knee_l) | ok/ok/ok/ok/ok | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.54) | 0.38 |
| 0.65 | 5.093 | 20 deg / 0.25 s | 0.26 (knee_l) | 0.26 (knee_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.56) | 0.124 |

## 0.50 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.625, stand_lat 0.829, walk_fwd 0.283, walk_lat_out 0.0, walk_lat_in 0.184

Invalid motions: walk_forward: tether supplied 1.3% of body weight on average (limit 1%); walk_backward: tether supplied 1.4% of body weight on average (limit 1%); turn: tether supplied 1.5% of body weight on average (limit 1%); pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.312 | 1.15 | 1.745 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 2.643 | 1.39 | 2.109 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 3.908 | 0.997 | 1.512 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 3.258 | 1.171 | 1.777 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 3.448 | 1.1 | 1.669 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 3.312 | 1.15 | 1.52 (gripper_r) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 3.312 | 1.161 | 1.761 (knee_l) | True | False | False | - |
| armature high | 3.312 | 1.137 | 1.726 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 3.312 | 0.862 | 1.266 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.312 | 1.164 | 2.181 (knee_l) | False | False | False | - R10: walk_lat_out |
| walking speed x1.5 | 3.312 | 1.15 | 1.745 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.33) | 3.809 | 1.019 | 1.546 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.011, stand_lat 0.875, walk_fwd 0.606, walk_lat_out 0.86, walk_lat_in 0.519

Invalid motions: walk_forward: tether supplied 1.3% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.6% of body weight on average (limit 1%); pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.805 | 0.919 | 1.394 (knee_l) | True | False | False | - |
| structure mass x0.55 | 2.914 | 1.142 | 1.755 (knee_l) | True | False | False | - |
| structure mass x1.4 | 4.597 | 0.774 | 0.98 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| wiring/electronics x0.8 | 3.751 | 0.934 | 1.417 (knee_l) | True | False | False | - |
| wiring/electronics x1.5 | 3.94 | 0.882 | 1.333 (knee_l) | True | False | False | - |
| pessimistic linear torque-speed | 3.805 | 0.919 | 1.271 (knee_l) | False | False | False | - R10: walk_lat_out,walk_lat_in |
| armature low | 3.805 | 0.922 | 1.399 (knee_l) | True | False | False | - |
| armature high | 3.805 | 0.91 | 1.381 (knee_l) | False | False | False | - R10: walk_lat_out,walk_lat_in |
| stall low | 3.805 | 0.689 | 0.806 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.805 | 0.932 | 1.742 (knee_l) | True | False | False | - |
| walking speed x1.5 | 3.805 | 0.919 | 1.394 (knee_l) | True | False | False | - |
| benchmark-fit mass (structure x1.47) | 4.734 | 0.753 | 0.935 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.156, stand_lat 0.892, walk_fwd 0.77, walk_lat_out 0.88, walk_lat_in 0.537

Invalid motions: walk_forward: tether supplied 1.3% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.7% of body weight on average (limit 1%); pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 4.395 | 0.73 | 0.893 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| structure mass x0.55 | 3.239 | 0.961 | 1.457 (knee_l) | True | False | False | - |
| structure mass x1.4 | 5.424 | 0.6 | 0.719 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| wiring/electronics x0.8 | 4.341 | 0.741 | 0.909 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| wiring/electronics x1.5 | 4.531 | 0.704 | 0.847 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| pessimistic linear torque-speed | 4.395 | 0.73 | 0.893 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_lat_out,walk_lat_in |
| armature low | 4.395 | 0.731 | 0.893 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| armature high | 4.395 | 0.723 | 0.893 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 4.395 | 0.38 | 0.38 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 4.395 | 0.766 | 1.385 (knee_l) | True | False | False | - |
| walking speed x1.5 | 4.395 | 0.73 | 0.893 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| benchmark-fit mass (structure x1.54) | 5.773 | 0.566 | 0.68 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |

## 0.65 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.895, stand_lat 0.897, walk_fwd 0.0, walk_lat_out 0.0, walk_lat_in 0.0

Invalid motions: walk_forward: tether supplied 1.4% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.8% of body weight on average (limit 1%)

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 5.093 | 0.26 | 0.26 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 3.622 | 0.791 | 1.136 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 6.4 | 0.126 | 0.126 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 5.039 | 0.289 | 0.289 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 5.229 | 0.132 | 0.132 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 5.093 | 0.26 | 0.26 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_roll_r: ['envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 5.093 | 0.29 | 0.29 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_lat_out |
| armature high | 5.093 | 0.28 | 0.28 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 5.093 | 0.125 | 0.125 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 5.093 | 0.61 | 1.042 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| walking speed x1.5 | 5.093 | 0.26 | 0.26 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.56) | 6.928 | 0.124 | 0.124 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
