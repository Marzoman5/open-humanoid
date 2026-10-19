<!-- written by variants/adam/design/r1_calibrated.py (T-20261019-36f9); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: R1x-t16h

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | half-cal worst | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | half PASS | calibrated PASS | bounds passed strict / half / cal | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.55 | 3.927 | 45 deg / 0.25 s | 0.532 (hip_roll_l) | 0.67 | 0.807 (hip_roll_l) | ok/ok/FAIL/ok/FAIL | False | False | False | 0/0/2 of 13 | structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; walking speed x1.5; benchmark-fit mass (structure x1.41); shelled nominal (structure x1.2); low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 0.605 |
| 0.60 | 4.517 | 45 deg / 0.25 s | 0.435 (hip_roll_l) | 0.549 | 0.661 (hip_roll_l) | ok/ok/FAIL/FAIL/FAIL | False | False | False | 0/0/0 of 13 | structure mass x0.55; structure mass x1.4; wiring/electronics x0.8; wiring/electronics x1.5; pessimistic linear torque-speed; armature low; armature high; stall low; stall high; walking speed x1.5; benchmark-fit mass (structure x1.49); shelled nominal (structure x1.2); low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 0.379 |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.719, stand_lat 0.758, walk_fwd 0.0, walk_lat_out 0.447, walk_lat_in 0.0

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 3.927 | 0.532 | 0.67 | 0.807 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_in |
| structure mass x0.55 | 3.036 | 0.555 | 0.815 | 1.019 (hip_roll_l) | True | False | False | True | - |
| structure mass x1.4 | 4.719 | 0.445 | 0.561 | 0.675 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_r: ['rms'] R10: walk_fwd,walk_lat_in |
| wiring/electronics x0.8 | 3.87 | 0.538 | 0.678 | 0.817 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 4.068 | 0.517 | 0.652 | 0.785 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_in |
| pessimistic linear torque-speed | 3.927 | 0.532 | 0.67 | 0.741 (knee_r) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; hip_pitch_l: ['envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 3.927 | 0.548 | 0.691 | 0.832 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope'] R10: walk_fwd,walk_lat_in |
| armature high | 3.927 | 0.405 | 0.595 | 0.785 (knee_r) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['peak', 'rms', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 3.927 | 0.399 | 0.503 | 0.605 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 3.927 | 0.534 | 0.785 | 1.008 (hip_roll_l) | True | False | False | True | - |
| walking speed x1.5 | 3.927 | 0.49 | 0.669 | 0.806 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope']; hip_pitch_l: ['envelope'] R10: walk_fwd,walk_lat_in |
| benchmark-fit mass (structure x1.41) | 4.734 | 0.443 | 0.559 | 0.673 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_r: ['rms'] R10: walk_fwd,walk_lat_in |
| shelled nominal (structure x1.2) | 4.323 | 0.485 | 0.611 | 0.736 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_in |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 3.927 | 0.495 | 0.624 | 0.752 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope']; hip_roll_r: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.784, stand_lat 0.923, walk_fwd 0.0, walk_lat_out 0.364, walk_lat_in 0.0

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 4.517 | 0.435 | 0.549 | 0.661 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x0.55 | 3.361 | 0.574 | 0.723 | 0.871 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| structure mass x1.4 | 5.546 | 0.356 | 0.449 | 0.54 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x0.8 | 4.461 | 0.44 | 0.554 | 0.667 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| wiring/electronics x1.5 | 4.659 | 0.425 | 0.535 | 0.644 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| pessimistic linear torque-speed | 4.517 | 0.435 | 0.549 | 0.62 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; hip_pitch_l: ['envelope'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| armature low | 4.517 | 0.446 | 0.562 | 0.677 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['overload_time'] R10: walk_fwd,walk_lat_in |
| armature high | 4.517 | 0.427 | 0.538 | 0.648 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'envelope']; knee_l: ['rms', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall low | 4.517 | 0.327 | 0.379 | 0.379 (knee_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| stall high | 4.517 | 0.448 | 0.659 | 0.826 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['rms'] R10: walk_fwd,walk_lat_in |
| walking speed x1.5 | 4.517 | 0.435 | 0.548 | 0.66 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['rms', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| benchmark-fit mass (structure x1.49) | 5.773 | 0.343 | 0.432 | 0.52 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['peak', 'envelope', 'overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| shelled nominal (structure x1.2) | 5.031 | 0.392 | 0.494 | 0.595 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
| low SoC 0.15 + R x1.5 at 10 A (bus 10.34 V) | 4.517 | 0.406 | 0.511 | 0.615 (hip_roll_l) | False | False | False | False | hip_roll_l: ['peak', 'rms', 'envelope']; hip_roll_r: ['peak', 'rms', 'envelope']; knee_l: ['overload_time'] R10: walk_fwd,walk_lat_out,walk_lat_in |
