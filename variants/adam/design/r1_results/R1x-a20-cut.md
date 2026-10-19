<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-a20-cut

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | calibrated PASS | robust (cal) across bounds | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.50 | 3.252 | 40 deg / 0.25 s | 1.174 (knee_l) | 1.781 (knee_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.37) | 1.336 |
| 0.55 | 3.744 | 45 deg / 0.25 s | 0.936 (knee_l) | 1.42 (knee_l) | ok/ok/ok/ok/ok | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.50) | 0.82 |
| 0.60 | 4.334 | 40 deg / 0.25 s | 0.742 (knee_l) | 0.935 (knee_l) | ok/ok/ok/ok/ok | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.56) | 0.606 |
| 0.65 | 5.032 | 20 deg / 0.25 s | 0.289 (knee_l) | 0.289 (knee_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.58) | 0.124 |

## 0.50 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.624, stand_lat 0.815, walk_fwd 0.278, walk_lat_out 0.0, walk_lat_in 0.18

Invalid motions: walk_forward: tether supplied 1.3% of body weight on average (limit 1%); walk_backward: tether supplied 1.4% of body weight on average (limit 1%); turn: tether supplied 1.5% of body weight on average (limit 1%); pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.252 | 1.174 | 1.781 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 2.582 | 1.425 | 2.162 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 3.847 | 1.015 | 1.539 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 3.198 | 1.196 | 1.814 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 3.384 | 1.123 | 1.704 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 3.252 | 1.174 | 1.52 (gripper_r) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 3.252 | 1.185 | 1.798 (knee_l) | True | False | False | - |
| armature high | 3.252 | 1.161 | 1.761 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 3.252 | 0.88 | 1.336 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.252 | 1.186 | 2.226 (knee_l) | False | False | False | - R10: walk_lat_out |
| walking speed x1.5 | 3.252 | 1.174 | 1.781 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.37) | 3.809 | 1.023 | 1.553 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.994, stand_lat 0.861, walk_fwd 0.597, walk_lat_out 0.846, walk_lat_in 0.511

Invalid motions: walk_forward: tether supplied 1.3% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.6% of body weight on average (limit 1%); pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.744 | 0.936 | 1.42 (knee_l) | True | False | False | - |
| structure mass x0.55 | 2.853 | 1.166 | 1.796 (knee_l) | True | False | False | - |
| structure mass x1.4 | 4.536 | 0.787 | 1.01 (knee_l) | True | False | False | - |
| wiring/electronics x0.8 | 3.691 | 0.951 | 1.443 (knee_l) | True | False | False | - |
| wiring/electronics x1.5 | 3.876 | 0.899 | 1.364 (knee_l) | True | False | False | - |
| pessimistic linear torque-speed | 3.744 | 0.936 | 1.294 (knee_l) | False | False | False | - R10: walk_lat_out,walk_lat_in |
| armature low | 3.744 | 0.94 | 1.426 (knee_l) | True | False | False | - |
| armature high | 3.744 | 0.928 | 1.407 (knee_l) | False | False | False | - R10: walk_lat_out,walk_lat_in |
| stall low | 3.744 | 0.702 | 0.82 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.744 | 0.948 | 1.775 (knee_l) | True | False | False | - |
| walking speed x1.5 | 3.744 | 0.936 | 1.42 (knee_l) | True | False | False | - |
| benchmark-fit mass (structure x1.50) | 4.734 | 0.756 | 0.935 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.102, stand_lat 0.876, walk_fwd 0.73, walk_lat_out 0.864, walk_lat_in 0.528

Invalid motions: walk_forward: tether supplied 1.3% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.7% of body weight on average (limit 1%)

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 4.334 | 0.742 | 0.935 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| structure mass x0.55 | 3.178 | 0.98 | 1.486 (knee_l) | True | False | False | - |
| structure mass x1.4 | 5.363 | 0.608 | 0.763 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| wiring/electronics x0.8 | 4.281 | 0.753 | 0.952 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| wiring/electronics x1.5 | 4.467 | 0.715 | 0.893 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| pessimistic linear torque-speed | 4.334 | 0.742 | 0.935 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 4.334 | 0.743 | 0.952 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| armature high | 4.334 | 0.734 | 0.952 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_lat_out,walk_lat_in |
| stall low | 4.334 | 0.556 | 0.606 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 4.334 | 0.796 | 1.406 (knee_l) | True | False | False | - |
| walking speed x1.5 | 4.334 | 0.742 | 0.935 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| benchmark-fit mass (structure x1.56) | 5.773 | 0.567 | 0.694 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |

## 0.65 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.884, stand_lat 0.887, walk_fwd 0.0, walk_lat_out 0.0, walk_lat_in 0.0

Invalid motions: walk_forward: tether supplied 1.4% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.8% of body weight on average (limit 1%)

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 5.032 | 0.289 | 0.289 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 3.561 | 0.807 | 1.19 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 6.339 | 0.126 | 0.126 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 4.979 | 0.293 | 0.293 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 5.165 | 0.252 | 0.252 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 5.032 | 0.289 | 0.289 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 5.032 | 0.294 | 0.294 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_lat_out |
| armature high | 5.032 | 0.292 | 0.292 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 5.032 | 0.125 | 0.125 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 5.032 | 0.616 | 1.064 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| walking speed x1.5 | 5.032 | 0.289 | 0.289 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.58) | 6.928 | 0.124 | 0.124 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
