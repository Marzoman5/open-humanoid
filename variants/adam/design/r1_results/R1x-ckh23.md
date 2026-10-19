<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-ckh23

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | calibrated PASS | robust (cal) across bounds | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.50 | 3.512 | 45 deg / 0.5 s | 1.319 (knee_r) | 1.864 (knee_r) | ok/ok/ok/ok/ok | True | True | False | structure mass x0.55; walking speed x1.5 | 0.106 |
| 0.55 | 4.005 | 40 deg / 0.5 s | 1.247 (hip_roll_l) | 1.891 (hip_roll_l) | ok/ok/ok/ok/ok | True | True | False | armature high; walking speed x1.5 | 0.157 |
| 0.60 | 4.595 | 45 deg / 0.5 s | 1.019 (hip_roll_l) | 1.546 (hip_roll_l) | ok/ok/ok/ok/ok | True | True | False | armature high | 1.16 |
| 0.65 | 5.293 | 45 deg / 0.35 s | 0.877 (hip_yaw_r) | 1.331 (hip_yaw_r) | ok/ok/ok/ok/ok | False | True | False | structure mass x1.4; armature high; stall low; benchmark-fit mass (structure x1.50) | 0.855 |

## 0.50 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.849, stand_lat 0.893, walk_fwd 0.512, walk_lat_out 0.63, walk_lat_in 0.607

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.512 | 1.319 | 1.864 (knee_r) | True | True | True | - |
| structure mass x0.55 | 2.843 | 1.387 | 1.889 (knee_r) | False | False | False | - R10: walk_fwd |
| structure mass x1.4 | 4.108 | 1.26 | 1.846 (knee_r) | True | True | True | - |
| wiring/electronics x0.8 | 3.456 | 1.328 | 1.862 (knee_r) | True | True | True | - |
| wiring/electronics x1.5 | 3.654 | 1.296 | 1.867 (knee_r) | True | True | True | - |
| pessimistic linear torque-speed | 3.512 | 0.895 | 1.056 (hip_pitch_r) | True | False | True | - |
| armature low | 3.512 | 1.577 | 2.392 (hip_roll_l) | True | True | True | - |
| armature high | 3.512 | 0.909 | 1.341 (knee_r) | True | False | True | - |
| stall low | 3.512 | 1.022 | 1.551 (hip_pitch_l) | True | True | True | - |
| stall high | 3.512 | 1.319 | 1.864 (knee_r) | True | True | True | - |
| walking speed x1.5 | 3.512 | 0.09 | 0.106 (hip_pitch_l) | True | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.20) | 3.809 | 1.29 | 1.855 (knee_r) | True | True | True | - |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.022, stand_lat 1.079, walk_fwd 0.669, walk_lat_out 0.886, walk_lat_in 0.696

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 4.005 | 1.247 | 1.891 (hip_roll_l) | True | True | True | - |
| structure mass x0.55 | 3.114 | 1.413 | 1.961 (knee_r) | True | True | True | - |
| structure mass x1.4 | 4.797 | 1.054 | 1.6 (hip_roll_l) | True | True | True | - |
| wiring/electronics x0.8 | 3.948 | 1.261 | 1.913 (hip_roll_l) | True | True | True | - |
| wiring/electronics x1.5 | 4.146 | 1.212 | 1.838 (hip_roll_l) | True | True | True | - |
| pessimistic linear torque-speed | 4.005 | 1.015 | 1.198 (hip_pitch_r) | True | True | True | - |
| armature low | 4.005 | 1.289 | 1.955 (hip_roll_l) | True | True | True | - |
| armature high | 4.005 | 0.866 | 1.314 (hip_pitch_r) | True | False | False | - |
| stall low | 4.005 | 0.935 | 1.418 (hip_roll_l) | True | False | True | - |
| stall high | 4.005 | 1.293 | 1.935 (knee_r) | True | True | True | - |
| walking speed x1.5 | 4.005 | 0.133 | 0.157 (hip_pitch_r) | True | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.37) | 4.734 | 1.068 | 1.62 (hip_roll_l) | True | True | True | - |

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

## 0.65 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.529, stand_lat 1.595, walk_fwd 1.19, walk_lat_out 1.426, walk_lat_in 1.144

Invalid motions: pickup_0.45m: ideal playback fell over

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 5.293 | 0.877 | 1.331 (hip_yaw_r) | True | False | True | - |
| structure mass x0.55 | 3.822 | 1.031 | 1.733 (hip_yaw_r) | True | True | True | - |
| structure mass x1.4 | 6.6 | 0.726 | 0.99 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| wiring/electronics x0.8 | 5.236 | 0.886 | 1.344 (hip_yaw_r) | True | False | True | - |
| wiring/electronics x1.5 | 5.435 | 0.857 | 1.301 (hip_yaw_r) | True | False | True | - |
| pessimistic linear torque-speed | 5.293 | 0.857 | 1.011 (hip_pitch_l) | True | False | True | - |
| armature low | 5.293 | 0.915 | 1.399 (hip_yaw_r) | True | False | True | - |
| armature high | 5.293 | 0.91 | 1.38 (knee_l) | True | False | False | - |
| stall low | 5.293 | 0.658 | 0.855 (knee_l) | True | False | False | hip_yaw_r: ['envelope']; knee_l: ['overload_time']; knee_r: ['overload_time'] |
| stall high | 5.293 | 0.901 | 1.574 (hip_roll_l) | True | False | True | - |
| walking speed x1.5 | 5.293 | 0.796 | 1.207 (hip_pitch_r) | True | False | True | - |
| benchmark-fit mass (structure x1.50) | 6.928 | 0.691 | 0.935 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
