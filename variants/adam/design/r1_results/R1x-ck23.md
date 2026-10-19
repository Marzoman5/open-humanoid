<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-ck23

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | calibrated PASS | robust (cal) across bounds | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.50 | 3.474 | 40 deg / 0.5 s | 0.96 (hip_roll_l) | 1.456 (hip_roll_l) | ok/ok/ok/ok/ok | False | True | False | structure mass x0.55; pessimistic linear torque-speed; stall low; walking speed x1.5 | 0.106 |
| 0.55 | 3.966 | 30 deg / 0.35 s | 0.811 (knee_r) | 1.123 (knee_l) | ok/ok/ok/ok/ok | False | True | False | structure mass x0.55; pessimistic linear torque-speed; armature high; stall low; walking speed x1.5 | 0.106 |
| 0.60 | 4.556 | 30 deg / 0.35 s | 0.666 (hip_roll_l) | 1.01 (hip_roll_l) | ok/ok/ok/ok/ok | False | True | False | structure mass x1.4; wiring/electronics x1.5; pessimistic linear torque-speed; armature high; stall low; walking speed x1.5; benchmark-fit mass (structure x1.47) | 0.617 |
| 0.65 | 5.254 | 30 deg / 0.25 s | 0.576 (hip_roll_l) | 0.874 (hip_roll_l) | ok/ok/FAIL/ok/FAIL | False | False | False | structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; walking speed x1.5; benchmark-fit mass (structure x1.51) | 0.656 |

## 0.50 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.808, stand_lat 0.879, walk_fwd 0.489, walk_lat_out 0.617, walk_lat_in 0.551

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.474 | 0.96 | 1.456 (hip_roll_l) | True | False | True | - |
| structure mass x0.55 | 2.804 | 1.17 | 1.558 (knee_r) | False | False | False | - R10: walk_fwd,walk_lat_in |
| structure mass x1.4 | 4.069 | 0.827 | 1.255 (hip_roll_l) | True | False | True | - |
| wiring/electronics x0.8 | 3.417 | 0.973 | 1.476 (hip_roll_l) | True | False | True | - |
| wiring/electronics x1.5 | 3.615 | 0.929 | 1.409 (hip_roll_l) | True | False | True | - |
| pessimistic linear torque-speed | 3.474 | 0.841 | 0.992 (hip_pitch_r) | True | False | False | hip_pitch_r: ['envelope'] |
| armature low | 3.474 | 0.985 | 1.494 (hip_roll_l) | True | False | True | - |
| armature high | 3.474 | 0.767 | 1.14 (knee_r) | True | False | True | - |
| stall low | 3.474 | 0.72 | 1.092 (hip_roll_l) | False | False | False | - R10: walk_lat_in |
| stall high | 3.474 | 1.009 | 1.578 (knee_r) | True | True | True | - |
| walking speed x1.5 | 3.474 | 0.09 | 0.106 (hip_pitch_l) | True | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.23) | 3.809 | 0.88 | 1.336 (hip_roll_l) | True | False | True | - |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.816, stand_lat 1.166, walk_fwd 0.564, walk_lat_out 0.86, walk_lat_in 0.589

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.966 | 0.811 | 1.123 (knee_l) | True | False | True | - |
| structure mass x0.55 | 3.075 | 0.822 | 1.123 (knee_l) | False | False | False | - R10: walk_fwd |
| structure mass x1.4 | 4.758 | 0.688 | 1.043 (hip_roll_l) | True | False | True | - |
| wiring/electronics x0.8 | 3.909 | 0.811 | 1.124 (knee_l) | True | False | True | - |
| wiring/electronics x1.5 | 4.107 | 0.791 | 1.122 (knee_l) | True | False | True | - |
| pessimistic linear torque-speed | 3.966 | 0.575 | 0.678 (hip_pitch_r) | True | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| armature low | 3.966 | 0.841 | 1.276 (hip_roll_l) | True | False | True | - |
| armature high | 3.966 | 1.422 | 2.158 (knee_l) | False | False | False | - R10: walk_lat_out |
| stall low | 3.966 | 0.61 | 0.925 (hip_roll_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.966 | 0.811 | 1.123 (knee_l) | True | False | True | - |
| walking speed x1.5 | 3.966 | 0.09 | 0.106 (hip_pitch_l) | True | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.39) | 4.734 | 0.691 | 1.048 (hip_roll_l) | True | False | True | - |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.104, stand_lat 1.065, walk_fwd 0.706, walk_lat_out 0.456, walk_lat_in 0.546

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 4.556 | 0.666 | 1.01 (hip_roll_l) | True | False | True | - |
| structure mass x0.55 | 3.4 | 0.874 | 1.325 (hip_roll_l) | True | False | True | - |
| structure mass x1.4 | 5.585 | 0.556 | 0.844 (hip_roll_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 4.5 | 0.673 | 1.02 (hip_roll_l) | True | False | True | - |
| wiring/electronics x1.5 | 4.698 | 0.65 | 0.986 (hip_roll_l) | True | False | False | hip_roll_l: ['peak', 'envelope'] |
| pessimistic linear torque-speed | 4.556 | 0.649 | 0.766 (hip_pitch_r) | False | False | False | hip_roll_l: ['envelope']; hip_roll_r: ['envelope']; hip_pitch_l: ['envelope'] R10: walk_lat_in |
| armature low | 4.556 | 0.685 | 1.04 (hip_roll_l) | True | False | True | - |
| armature high | 4.556 | 0.866 | 1.314 (shoulder_pitch_r) | True | False | False | - |
| stall low | 4.556 | 0.499 | 0.758 (hip_roll_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; shoulder_pitch_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 4.556 | 0.688 | 1.263 (hip_roll_l) | True | False | True | - |
| walking speed x1.5 | 4.556 | 0.523 | 0.617 (hip_pitch_r) | True | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.47) | 5.773 | 0.539 | 0.818 (hip_roll_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |

## 0.65 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.061, stand_lat 1.078, walk_fwd 0.0, walk_lat_out 0.626, walk_lat_in 0.0

Invalid motions: pickup_0.45m: ideal playback fell over

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 5.254 | 0.576 | 0.874 (hip_roll_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_in |
| structure mass x0.55 | 3.783 | 0.612 | 1.168 (hip_roll_l) | True | False | True | - |
| structure mass x1.4 | 6.561 | 0.475 | 0.721 (hip_roll_l) | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; ankle_pitch_l: ['peak', 'envelope'] R10: walk_fwd,walk_lat_in |
| wiring/electronics x0.8 | 5.197 | 0.581 | 0.882 (hip_roll_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_in |
| wiring/electronics x1.5 | 5.396 | 0.565 | 0.857 (hip_roll_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_in |
| pessimistic linear torque-speed | 5.254 | 0.576 | 0.708 (hip_pitch_r) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; hip_pitch_l: ['envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 5.254 | 0.593 | 0.899 (hip_roll_l) | True | False | False | hip_roll_l: ['peak', 'envelope'] |
| armature high | 5.254 | 0.915 | 1.388 (knee_l) | False | False | False | - R10: walk_lat_out,walk_lat_in |
| stall low | 5.254 | 0.432 | 0.656 (hip_roll_l) | False | False | False | hip_yaw_r: ['peak', 'envelope']; hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 5.254 | 0.581 | 1.093 (hip_roll_l) | True | False | True | - |
| walking speed x1.5 | 5.254 | 0.512 | 0.782 (hip_pitch_r) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; hip_pitch_l: ['envelope'] R10: walk_fwd,walk_lat_in |
| benchmark-fit mass (structure x1.51) | 6.928 | 0.45 | 0.683 (hip_roll_l) | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; ankle_pitch_l: ['peak', 'envelope'] R10: walk_fwd,walk_lat_in |
