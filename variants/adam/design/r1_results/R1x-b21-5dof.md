<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-b21-5dof

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | calibrated PASS | robust (cal) across bounds | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.50 | 3.312 | 20 deg / 0.25 s | 0.625 (knee_l) | 1.163 (knee_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.33) | 0.935 |
| 0.55 | 3.805 | 20 deg / 0.25 s | 0.516 (knee_l) | 0.862 (knee_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.47) | 0.427 |
| 0.60 | 4.395 | 30 deg / 0.25 s | 0.403 (knee_l) | 0.403 (knee_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.54) | 0.125 |
| 0.65 | 5.093 | 20 deg / 0.25 s | 0.123 (knee_l) | 0.123 (knee_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.56) | 0.1 |

## 0.50 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.484, stand_lat 0.682, walk_fwd 0.0, walk_lat_out 0.0, walk_lat_in 0.0

Invalid motions: walk_forward: ideal playback fell over; walk_backward: tether supplied 2.0% of body weight on average (limit 1%); turn: tether supplied 1.5% of body weight on average (limit 1%); pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.312 | 0.625 | 1.163 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 2.643 | 0.753 | 1.47 (knee_l) | False | False | False | - R10: stand_fwd,walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 3.908 | 0.553 | 0.935 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 3.258 | 0.634 | 1.205 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 3.448 | 0.601 | 1.075 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 3.312 | 0.625 | 1.118 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 3.312 | 0.626 | 1.176 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature high | 3.312 | 0.623 | 1.163 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 3.312 | 0.625 | 0.98 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.312 | 0.625 | 1.339 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| walking speed x1.5 | 3.312 | 0.625 | 1.163 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.33) | 3.809 | 0.564 | 0.971 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.595, stand_lat 0.718, walk_fwd 0.0, walk_lat_out 0.0, walk_lat_in 0.0

Invalid motions: walk_forward: tether supplied 3.0% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.6% of body weight on average (limit 1%); pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.805 | 0.516 | 0.862 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 2.914 | 0.627 | 1.176 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 4.597 | 0.435 | 0.435 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 3.751 | 0.523 | 0.877 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 3.94 | 0.499 | 0.833 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 3.805 | 0.516 | 0.862 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 3.805 | 0.516 | 0.87 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature high | 3.805 | 0.516 | 0.862 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 3.805 | 0.516 | 0.769 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.805 | 0.516 | 0.962 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| walking speed x1.5 | 3.805 | 0.516 | 0.862 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.47) | 4.734 | 0.427 | 0.427 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.817, stand_lat 0.682, walk_fwd 0.0, walk_lat_out 0.0, walk_lat_in 0.0

Invalid motions: walk_forward: tether supplied 1.3% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.7% of body weight on average (limit 1%)

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 4.395 | 0.403 | 0.403 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 3.239 | 0.518 | 0.862 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 5.424 | 0.126 | 0.126 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 4.341 | 0.407 | 0.407 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 4.531 | 0.397 | 0.397 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 4.395 | 0.403 | 0.403 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 4.395 | 0.405 | 0.405 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature high | 4.395 | 0.405 | 0.405 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 4.395 | 0.248 | 0.248 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 4.395 | 0.411 | 0.741 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| walking speed x1.5 | 4.395 | 0.403 | 0.403 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.54) | 5.773 | 0.125 | 0.125 (knee_l) | False | False | False | hip_roll_r: ['overload_time']; knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |

## 0.65 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.823, stand_lat 0.897, walk_fwd 0.0, walk_lat_out 0.0, walk_lat_in 0.0

Invalid motions: walk_forward: tether supplied 1.4% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.8% of body weight on average (limit 1%)

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 5.093 | 0.123 | 0.123 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 3.622 | 0.131 | 0.131 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 6.4 | 0.1 | 0.1 (knee_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 5.039 | 0.123 | 0.123 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 5.229 | 0.122 | 0.122 (knee_l) | False | False | False | hip_roll_r: ['overload_time']; knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 5.093 | 0.123 | 0.123 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 5.093 | 0.123 | 0.123 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature high | 5.093 | 0.123 | 0.123 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 5.093 | 0.12 | 0.12 (knee_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope', 'overload_time']; knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 5.093 | 0.125 | 0.125 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| walking speed x1.5 | 5.093 | 0.123 | 0.123 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.56) | 6.928 | 0.1 | 0.1 (knee_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
