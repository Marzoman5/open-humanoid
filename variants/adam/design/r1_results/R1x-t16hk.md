<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-t16hk

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | half-cal worst | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | half PASS | calibrated PASS | bounds passed strict / half / cal | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.55 | 3.927 | 45 deg / 0.25 s | 0.526 (knee_l) | 0.625 | 0.625 (knee_l) | ok/ok/FAIL/ok/FAIL | False | False | False | 0/0/0 of 13 | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.41); shelled nominal (structure x1.2); low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 0.29 |
| 0.60 | 4.517 | 20 deg / 0.35 s | 0.385 (knee_l) | 0.385 | 0.385 (knee_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | 0/0/0 of 13 | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.49); shelled nominal (structure x1.2); low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 0.102 |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.719, stand_lat 0.758, walk_fwd 0.0, walk_lat_out 0.447, walk_lat_in 0.0

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 3.927 | 0.526 | 0.625 | 0.625 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_in |
| structure mass x0.55 | 3.036 | 0.614 | 0.844 | 0.847 (knee_l) | True | False | False | False | knee_l: ['overload_time']; knee_r: ['overload_time'] |
| structure mass x1.4 | 4.719 | 0.316 | 0.316 | 0.316 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 3.87 | 0.536 | 0.649 | 0.649 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_in |
| wiring/electronics x1.5 | 4.068 | 0.4 | 0.4 | 0.4 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_in |
| pessimistic linear torque-speed | 3.927 | 0.526 | 0.625 | 0.625 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; hip_pitch_l: ['envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 3.927 | 0.525 | 0.617 | 0.617 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_in |
| armature high | 3.927 | 0.478 | 0.621 | 0.621 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'rms', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 3.927 | 0.29 | 0.29 | 0.29 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.927 | 0.54 | 0.793 | 0.847 (knee_l) | True | False | False | False | knee_l: ['peak', 'envelope', 'overload_time']; knee_r: ['peak', 'envelope', 'overload_time'] |
| walking speed x1.5 | 3.927 | 0.507 | 0.625 | 0.625 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; hip_pitch_l: ['envelope'] R10: walk_fwd,walk_lat_in |
| benchmark-fit mass (structure x1.41) | 4.734 | 0.315 | 0.315 | 0.315 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| shelled nominal (structure x1.2) | 4.323 | 0.368 | 0.368 | 0.368 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_in |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 3.927 | 0.375 | 0.375 | 0.375 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_in |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.748, stand_lat 0.906, walk_fwd 0.0, walk_lat_out 0.227, walk_lat_in 0.0

Invalid motions: pickup_0.45m: ideal playback fell over

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 4.517 | 0.385 | 0.385 | 0.385 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 3.361 | 0.532 | 0.67 | 0.807 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 5.546 | 0.105 | 0.105 | 0.105 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 4.461 | 0.386 | 0.386 | 0.386 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 4.659 | 0.379 | 0.379 | 0.379 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 4.517 | 0.385 | 0.385 | 0.385 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; hip_pitch_l: ['envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 4.517 | 0.383 | 0.383 | 0.383 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature high | 4.517 | 0.383 | 0.383 | 0.383 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 4.517 | 0.102 | 0.102 | 0.102 (knee_r) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 4.517 | 0.444 | 0.645 | 0.777 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| walking speed x1.5 | 4.517 | 0.385 | 0.385 | 0.385 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.49) | 5.773 | 0.103 | 0.103 | 0.103 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'rms', 'envelope', 'overload_time', 'protection_trip'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| shelled nominal (structure x1.2) | 5.031 | 0.309 | 0.309 | 0.309 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; hip_pitch_r: ['envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 4.517 | 0.376 | 0.376 | 0.376 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; hip_pitch_l: ['envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
