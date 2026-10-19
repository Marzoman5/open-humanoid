<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-ch23

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | calibrated PASS | robust (cal) across bounds | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.55 | 3.966 | 45 deg / 0.5 s | 0.9 (knee_l) | 1.365 (knee_l) | ok/ok/ok/ok/ok | False | True | False | structure mass x1.4; stall low; walking speed x1.5; benchmark-fit mass (structure x1.39) | 0.367 |
| 0.60 | 4.556 | 45 deg / 0.5 s | 0.717 (knee_l) | 0.87 (knee_l) | ok/ok/ok/ok/ok | False | False | False | structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; walking speed x1.5; benchmark-fit mass (structure x1.47) | 0.376 |
| 0.65 | 5.254 | 45 deg / 0.35 s | 0.572 (knee_l) | 0.69 (knee_l) | ok/ok/ok/ok/ok | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.51) | 0.098 |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.053, stand_lat 1.072, walk_fwd 0.652, walk_lat_out 0.774, walk_lat_in 0.644

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.966 | 0.9 | 1.365 (knee_l) | True | False | True | - |
| structure mass x0.55 | 3.075 | 1.072 | 1.709 (knee_l) | True | True | True | - |
| structure mass x1.4 | 4.758 | 0.76 | 0.943 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| wiring/electronics x0.8 | 3.909 | 0.915 | 1.388 (knee_l) | True | False | True | - |
| wiring/electronics x1.5 | 4.107 | 0.863 | 1.235 (knee_l) | True | False | True | - |
| pessimistic linear torque-speed | 3.966 | 0.9 | 1.122 (knee_r) | True | False | True | - |
| armature low | 3.966 | 0.903 | 1.37 (knee_l) | True | False | True | - |
| armature high | 3.966 | 0.827 | 1.352 (knee_l) | True | False | True | - |
| stall low | 3.966 | 0.675 | 0.787 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| stall high | 3.966 | 0.916 | 1.706 (knee_l) | True | False | True | - |
| walking speed x1.5 | 3.966 | 0.311 | 0.367 (knee_r) | True | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.39) | 4.734 | 0.764 | 0.952 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.301, stand_lat 1.489, walk_fwd 0.85, walk_lat_out 0.958, walk_lat_in 0.939

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 4.556 | 0.717 | 0.87 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| structure mass x0.55 | 3.4 | 0.938 | 1.423 (knee_l) | True | False | True | - |
| structure mass x1.4 | 5.585 | 0.591 | 0.709 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| wiring/electronics x0.8 | 4.5 | 0.728 | 0.893 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| wiring/electronics x1.5 | 4.698 | 0.69 | 0.826 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| pessimistic linear torque-speed | 4.556 | 0.717 | 0.87 (knee_l) | True | False | False | knee_l: ['envelope', 'overload_time']; knee_r: ['envelope', 'overload_time'] |
| armature low | 4.556 | 0.717 | 0.877 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| armature high | 4.556 | 0.71 | 0.885 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| stall low | 4.556 | 0.376 | 0.376 (knee_l) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out |
| stall high | 4.556 | 0.753 | 1.359 (knee_l) | True | False | True | - |
| walking speed x1.5 | 4.556 | 0.717 | 0.87 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| benchmark-fit mass (structure x1.47) | 5.773 | 0.573 | 0.69 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |

## 0.65 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.491, stand_lat 1.583, walk_fwd 1.183, walk_lat_out 1.415, walk_lat_in 0.974

Invalid motions: pickup_0.45m: ideal playback fell over

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 5.254 | 0.572 | 0.69 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| structure mass x0.55 | 3.783 | 0.761 | 0.99 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| structure mass x1.4 | 6.561 | 0.1 | 0.1 (knee_r) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_lat_out |
| wiring/electronics x0.8 | 5.197 | 0.579 | 0.699 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| wiring/electronics x1.5 | 5.396 | 0.385 | 0.385 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| pessimistic linear torque-speed | 5.254 | 0.572 | 0.69 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| armature low | 5.254 | 0.572 | 0.694 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| armature high | 5.254 | 0.559 | 0.699 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| stall low | 5.254 | 0.098 | 0.098 (knee_r) | False | False | False | knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out |
| stall high | 5.254 | 0.619 | 0.893 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| walking speed x1.5 | 5.254 | 0.572 | 0.69 (knee_l) | True | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| benchmark-fit mass (structure x1.51) | 6.928 | 0.099 | 0.099 (knee_r) | False | False | False | knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip']; knee_r: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out |
