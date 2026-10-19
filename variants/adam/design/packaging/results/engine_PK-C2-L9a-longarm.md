<!-- written by variants/adam/design/packaging/engine.py via r1_calibrated.py (T-20261019-c1aa); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: PK-C2-L9a-longarm

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | half-cal worst | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | half PASS | calibrated PASS | bounds passed strict / half / cal | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.55 | 3.716 | 30 deg / 0.25 s | 0.09 (gripper_r) | 0.098 | 0.106 (gripper_r) | ok/ok/ok/FAIL/FAIL | False | False | False | - | - | None |

## 0.55 m

Largest recoverable impulse at nominal (N.s): stand_fwd 0.761, stand_lat 1.097, walk_fwd 0.539, walk_lat_out 0.0, walk_lat_in 0.133

Invalid motions: pickup_0.45m: reference infeasible: pickup at 0.45 m: the arm covers this height but in every whole-body posture t

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 3.716 | 0.09 | 0.098 | 0.106 (gripper_r) | False | False | False | False | knee_l: ['rms', 'envelope']; knee_r: ['rms', 'envelope']; gripper_r: ['envelope'] R10: walk_lat_out,walk_lat_in |
