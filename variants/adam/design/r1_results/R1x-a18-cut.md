<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-a18-cut

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | calibrated PASS | robust (cal) across bounds | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.50 | 3.13 | 40 deg / 0.25 s | 1.214 (knee_l) | 1.842 (knee_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.46) | 1.381 |
| 0.55 | 3.622 | 45 deg / 0.25 s | 0.963 (knee_l) | 1.461 (knee_l) | ok/ok/ok/ok/ok | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.56) | 0.855 |
| 0.60 | 4.212 | 45 deg / 0.25 s | 0.761 (knee_l) | 0.943 (knee_l) | ok/ok/ok/ok/ok | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.61) | 0.658 |
| 0.65 | 4.91 | 40 deg / 0.25 s | 0.601 (knee_l) | 0.752 (knee_l) | ok/ok/ok/ok/ok | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.62) | 0.342 |

## 0.50 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.629, stand_lat 0.788, walk_fwd 0.259, walk_lat_out 0.0, walk_lat_in 0.17

Invalid motions: walk_forward: tether supplied 1.3% of body weight on average (limit 1%); walk_backward: tether supplied 1.4% of body weight on average (limit 1%); turn: tether supplied 1.5% of body weight on average (limit 1%); wave: reference infeasible: no abducted-arm pose found: arm joints missing or ranges too small; COM tracki; pickup: reference infeasible: no gripper/arm joints: pickup not possible; COM tracking error 0.00 mm; pickup_0.45m: reference infeasible: no gripper/arm joints: pickup not possible; COM tracking error 0.00 mm

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.13 | 1.214 | 1.842 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 2.46 | 1.489 | 2.258 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 3.725 | 1.043 | 1.582 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 3.079 | 1.236 | 1.875 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 3.256 | 1.162 | 1.763 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 3.13 | 1.214 | 1.663 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 3.13 | 1.227 | 1.861 (knee_l) | True | False | False | - |
| armature high | 3.13 | 1.2 | 1.821 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 3.13 | 0.911 | 1.381 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.13 | 1.221 | 2.302 (knee_l) | False | False | False | - R10: walk_lat_out |
| walking speed x1.5 | 3.13 | 1.214 | 1.842 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.46) | 3.809 | 1.022 | 1.551 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.969, stand_lat 0.975, walk_fwd 0.58, walk_lat_out 0.821, walk_lat_in 0.577

Invalid motions: walk_forward: tether supplied 1.4% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.6% of body weight on average (limit 1%); wave: reference infeasible: no abducted-arm pose found: arm joints missing or ranges too small; COM tracki; pickup: reference infeasible: no gripper/arm joints: pickup not possible; COM tracking error 0.00 mm; pickup_0.45m: reference infeasible: no gripper/arm joints: pickup not possible; COM tracking error 0.00 mm

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.622 | 0.963 | 1.461 (knee_l) | True | False | False | - |
| structure mass x0.55 | 2.731 | 1.21 | 1.868 (knee_l) | False | False | False | - R10: walk_fwd |
| structure mass x1.4 | 4.414 | 0.805 | 1.042 (knee_l) | True | False | False | - |
| wiring/electronics x0.8 | 3.571 | 0.979 | 1.485 (knee_l) | True | False | False | - |
| wiring/electronics x1.5 | 3.748 | 0.926 | 1.405 (knee_l) | True | False | False | - |
| pessimistic linear torque-speed | 3.622 | 0.963 | 1.331 (knee_l) | False | False | False | - R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 3.622 | 0.968 | 1.469 (knee_l) | True | False | False | - |
| armature high | 3.622 | 0.955 | 1.449 (knee_l) | False | False | False | - R10: walk_lat_out,walk_lat_in |
| stall low | 3.622 | 0.722 | 0.855 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.622 | 0.97 | 1.826 (knee_l) | True | False | False | - |
| walking speed x1.5 | 3.622 | 0.963 | 1.461 (knee_l) | True | False | False | - |
| benchmark-fit mass (structure x1.56) | 4.734 | 0.754 | 0.926 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.216, stand_lat 0.858, walk_fwd 0.727, walk_lat_out 0.846, walk_lat_in 0.516

Invalid motions: walk_forward: tether supplied 1.4% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.7% of body weight on average (limit 1%); wave: reference infeasible: no abducted-arm pose found: arm joints missing or ranges too small; COM tracki; pickup: reference infeasible: no gripper/arm joints: pickup not possible; COM tracking error 0.00 mm; pickup_0.45m: reference infeasible: no gripper/arm joints: pickup not possible; COM tracking error 0.00 mm

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 4.212 | 0.761 | 0.943 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| structure mass x0.55 | 3.056 | 1.016 | 1.542 (knee_l) | True | False | False | - |
| structure mass x1.4 | 5.241 | 0.62 | 0.735 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| wiring/electronics x0.8 | 4.162 | 0.772 | 0.971 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| wiring/electronics x1.5 | 4.339 | 0.735 | 0.893 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| pessimistic linear torque-speed | 4.212 | 0.761 | 0.943 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 4.212 | 0.762 | 0.962 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| armature high | 4.212 | 0.753 | 0.952 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_lat_out,walk_lat_in |
| stall low | 4.212 | 0.571 | 0.658 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 4.212 | 0.791 | 1.443 (knee_l) | True | False | False | - |
| walking speed x1.5 | 4.212 | 0.761 | 0.943 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| benchmark-fit mass (structure x1.61) | 5.773 | 0.565 | 0.676 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |

## 0.65 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.997, stand_lat 0.84, walk_fwd 0.658, walk_lat_out 0.829, walk_lat_in 0.641

Invalid motions: walk_forward: tether supplied 1.4% of body weight on average (limit 1%); walk_backward: tether supplied 1.5% of body weight on average (limit 1%); turn: tether supplied 1.8% of body weight on average (limit 1%); wave: reference infeasible: no abducted-arm pose found: arm joints missing or ranges too small; COM tracki; pickup: reference infeasible: no gripper/arm joints: pickup not possible; COM tracking error 0.00 mm; pickup_0.45m: reference infeasible: no gripper/arm joints: pickup not possible; COM tracking error 0.00 mm

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 4.91 | 0.601 | 0.752 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| structure mass x0.55 | 3.439 | 0.837 | 1.163 (knee_l) | True | False | False | - |
| structure mass x1.4 | 6.217 | 0.364 | 0.364 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_lat_in |
| wiring/electronics x0.8 | 4.859 | 0.609 | 0.758 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| wiring/electronics x1.5 | 5.037 | 0.583 | 0.73 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| pessimistic linear torque-speed | 4.91 | 0.601 | 0.752 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_lat_out |
| armature low | 4.91 | 0.601 | 0.752 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| armature high | 4.91 | 0.595 | 0.758 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 4.91 | 0.35 | 0.35 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 4.91 | 0.662 | 0.99 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| walking speed x1.5 | 4.91 | 0.601 | 0.752 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| benchmark-fit mass (structure x1.62) | 6.928 | 0.342 | 0.342 (knee_l) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_in |
