<!-- written by variants/adam/design/packaging/engine.py via r1_calibrated.py (T-20261019-c1aa); re-run the script, do not edit -->
# R1 feasibility, strict vs ODM-calibrated gates: PK-C1-package

Calibrated = peak x1.52, RMS x1.94 (0.637 N.m label for the 7.4 V part, catalog rated otherwise), envelope x1.18 (ADR 0014); overload, validity and R10 NOT relaxed. The 0.45 m-table pickup is excluded from validity (known planner gap, docs/concept-engine.md). Factors measured at 7.4 V; applied to 12 V / STS3250 by assumption.

| height | mass kg | gait | strict worst (joint) | half-cal worst | calibrated worst (joint) | R10 at 0.45 N.s (stand fwd/lat, walk fwd/lat out/lat in) | strict PASS | half PASS | calibrated PASS | bounds passed strict / half / cal | bounds failing (cal) | min cal margin over bounds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.60 | 4.246 | 45 deg / 0.35 s | 0.905 (shoulder_roll_r) | 1.083 | 1.172 (shoulder_pitch_r) | ok/ok/ok/ok/ok | False | True | True | - | - | None |

## 0.60 m

Largest recoverable impulse at nominal (N.s): stand_fwd 1.226, stand_lat 1.228, walk_fwd 0.856, walk_lat_out 1.082, walk_lat_in 0.842

Invalid motions: pickup_0.45m: reference infeasible: arm too short / table too low: no squat up to 120 deg brings the hand within r

| case | mass kg | strict worst | half worst | cal worst (joint) | R10 all ok | strict pass | half pass | cal pass | cal fails |
|---|---|---|---|---|---|---|---|---|---|
| nominal | 4.246 | 0.905 | 1.083 | 1.172 (shoulder_pitch_r) | True | False | True | True | - |
