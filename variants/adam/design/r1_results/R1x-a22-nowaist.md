<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-a22-nowaist

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | calibrated PASS | robust (cal) across bounds | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.55 | 3.866 | 40 deg / 0.5 s | 0.801 (hip_roll_l) | 1.215 (hip_roll_l) | ok/ok/ok/ok/ok | False | True | False | structure mass x0.55; structure mass x1.4; pessimistic linear torque-speed; stall low; walking speed x1.5; benchmark-fit mass (structure x1.44) | 0.106 |
| 0.60 | 4.456 | 30 deg / 0.35 s | 0.678 (hip_roll_l) | 0.836 (knee_r) | ok/ok/ok/ok/ok | False | False | False | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.51) | 0.106 |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.989, stand_lat 1.04, walk_fwd 0.598, walk_lat_out 0.748, walk_lat_in 0.566

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 3.866 | 0.801 | 1.215 (hip_roll_l) | True | False | True | - |
| structure mass x0.55 | 2.975 | 1.027 | 1.558 (hip_roll_l) | False | False | False | - R10: walk_lat_in |
| structure mass x1.4 | 4.658 | 0.67 | 1.017 (hip_roll_l) | False | False | False | - R10: walk_lat_out |
| wiring/electronics x0.8 | 3.81 | 0.811 | 1.23 (hip_roll_l) | True | False | True | - |
| wiring/electronics x1.5 | 4.004 | 0.777 | 1.18 (hip_roll_l) | True | False | True | - |
| pessimistic linear torque-speed | 3.866 | 0.761 | 0.897 (knee_r) | False | False | False | knee_l: ['envelope']; knee_r: ['envelope'] R10: walk_lat_in |
| armature low | 3.866 | 0.816 | 1.239 (hip_roll_l) | True | False | True | - |
| armature high | 3.866 | 0.782 | 1.187 (hip_roll_l) | True | False | True | - |
| stall low | 3.866 | 0.601 | 0.84 (knee_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.866 | 0.843 | 1.519 (hip_roll_l) | True | False | True | - |
| walking speed x1.5 | 3.866 | 0.09 | 0.106 (knee_l) | True | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope'] |
| benchmark-fit mass (structure x1.44) | 4.734 | 0.66 | 0.99 (knee_l) | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] R10: walk_lat_out |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.855, stand_lat 1.214, walk_fwd 0.689, walk_lat_out 0.594, walk_lat_in 0.622

| case | mass kg | strict worst | cal worst (joint) | R10 all ok | strict pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|
| nominal | 4.456 | 0.678 | 0.836 (knee_r) | True | False | False | knee_l: ['envelope', 'overload_time']; knee_r: ['envelope', 'overload_time'] |
| structure mass x0.55 | 3.3 | 0.705 | 0.832 (knee_r) | True | False | False | knee_l: ['envelope']; knee_r: ['envelope'] |
| structure mass x1.4 | 5.485 | 0.559 | 0.813 (knee_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 4.401 | 0.685 | 0.837 (knee_r) | True | False | False | knee_l: ['envelope', 'overload_time']; knee_r: ['envelope', 'overload_time'] |
| wiring/electronics x1.5 | 4.595 | 0.662 | 0.832 (knee_r) | True | False | False | knee_l: ['envelope', 'overload_time']; knee_r: ['envelope', 'overload_time'] |
| pessimistic linear torque-speed | 4.456 | 0.327 | 0.385 (knee_r) | False | False | False | hip_roll_l: ['envelope']; hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope'] R10: walk_lat_out,walk_lat_in |
| armature low | 4.456 | 0.699 | 1.0 (knee_l) | True | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| armature high | 4.456 | 0.519 | 0.612 (knee_r) | False | False | False | knee_l: ['envelope', 'overload_time']; knee_r: ['envelope', 'overload_time'] R10: walk_lat_out |
| stall low | 4.456 | 0.42 | 0.42 (knee_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 4.456 | 0.699 | 0.836 (knee_r) | True | False | False | knee_l: ['envelope']; knee_r: ['envelope'] |
| walking speed x1.5 | 4.456 | 0.09 | 0.106 (knee_l) | True | False | False | hip_pitch_l: ['envelope']; hip_pitch_r: ['envelope']; knee_l: ['envelope', 'overload_time'] |
| benchmark-fit mass (structure x1.51) | 5.773 | 0.537 | 0.781 (knee_l) | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
