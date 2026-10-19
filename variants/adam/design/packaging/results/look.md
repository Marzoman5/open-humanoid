<!-- written by variants/adam/design/packaging/study.py (T-20261019-c1aa); re-run, do not edit -->
# Packaging-for-look study: look metrics per lever (PROVISIONAL)

Every variant: same B4 rules (capsule.py), cant by the R2a visible-gap rule, `oh design metrics` code. ✗ = outside the band.

| key | lever | cant ° | HP | P1 | P2a | P2b | P3 | P4 | P5 | P6 | P7 | P8a | P8b | P9a | P9b | P10a | P10b | S3a | S3b | S4a | S4b | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B4 | R2a B4 as signed-provisional (hand-styled) | 21.0 | pass | 0.136 | 0.11 ✗ | 0.561 | 0.397 ✗ | 0.549 | 0.675 | 0.5 | 0.27 | 0.86 ✗ | 0.938 ✗ | 0.024 | 0.153 | 0.238 ✗ | 0.032 | 4 | 3 | 0.129 | 0.514 ✗ | 13/19 |
| V0 | baseline: R1 hardware, B4 rules (B4-generic) | 21.0 | pass | 0.136 | 0.11 ✗ | 0.561 | 0.397 ✗ | 0.549 | 0.627 | 0.5 | 0.27 | 0.956 ✗ | 1.0 ✗ | 0.086 | 0.127 | 0.238 ✗ | 0.032 | 3 | 3 | 0.165 | 0.566 ✗ | 13/19 |
| L1a | shoulder-roll + elbow servos -> STS3045M (6 V rail) | 20.5 | pass | 0.136 | 0.11 ✗ | 0.561 | 0.362 ✗ | 0.602 | 0.691 | 0.5 | 0.27 | 0.956 ✗ | 1.0 ✗ | 0.086 | 0.12 | 0.238 ✗ | 0.032 | 3 | 1 | 0.162 | 0.566 ✗ | 13/19 |
| L1b | shoulder-pitch servos -> STS3045M (narrower chest pair, lower chest top) | 21.0 | pass | 0.136 | 0.162 ✗ | 0.544 | 0.398 ✗ | 0.548 | 0.626 | 0.5 | 0.27 | 0.956 ✗ | 1.0 ✗ | 0.086 | 0.127 | 0.238 ✗ | 0.032 | 3 | 3 | 0.164 | 0.566 ✗ | 13/19 |
| L1c | gripper servo -> SCS0009 | 21.0 | pass | 0.136 | 0.11 ✗ | 0.561 | 0.397 ✗ | 0.549 | 0.627 | 0.5 | 0.27 | 0.956 ✗ | 0.992 ✗ | 0.086 | 0.14 | 0.238 ✗ | 0.032 | 4 | 3 | 0.156 | 0.566 ✗ | 13/19 |
| L1d | whole arm small: roll, elbow, pitch STS3045M; gripper SCS0009 | 20.5 | pass | 0.137 | 0.146 ✗ | 0.535 | 0.358 ✗ | 0.609 | 0.696 | 0.5 | 0.27 | 0.956 ✗ | 0.992 ✗ | 0.086 | 0.14 | 0.238 ✗ | 0.032 | 4 | 5 ✗ | 0.159 | 0.566 ✗ | 12/19 |
| L2 | no waist-yaw servo | 21.0 | pass | 0.136 | 0.11 ✗ | 0.561 | 0.397 ✗ | 0.549 | 0.627 | 0.5 | 0.27 | 0.956 ✗ | 1.0 ✗ | 0.086 | 0.127 | 0.238 ✗ | 0.032 | 3 | 3 | 0.165 | 0.566 ✗ | 13/19 |
| L3a | pack -> Tattu 3S 1300 laid flat across the upper back (22 mm) | 21.0 | pass | 0.136 | 0.11 ✗ | 0.561 | 0.397 ✗ | 0.549 | 0.627 | 0.5 | 0.27 | 0.956 ✗ | 1.0 ✗ | 0.086 | 0.127 | 0.238 ✗ | 0.032 | 3 | 3 | 0.166 | 0.566 ✗ | 13/19 |
| L3b | pack -> GNB 1850 low in the lumbar back (waist yaw removed to free the space) | 21.5 | pass | 0.137 | 0.153 ✗ | 0.544 | 0.398 ✗ | 0.548 | 0.623 | 0.5 | 0.27 | 0.957 ✗ | 1.0 ✗ | 0.082 | 0.12 | 0.238 ✗ | 0.032 | 3 | 3 | 0.161 | 0.564 ✗ | 13/19 |
| L4 | shoulder layout with the chest emptied: small arm + no pack in the upper chest | 24.5 | pass | 0.137 | 0.204 | 0.526 | 0.373 ✗ | 0.585 | 0.668 | 0.5 | 0.27 | 0.956 ✗ | 0.992 ✗ | 0.086 | 0.14 | 0.238 ✗ | 0.032 | 3 | 5 ✗ | 0.154 | 0.566 ✗ | 13/19 |
| L5a | knee servo up into the thigh, 1:1 parallelogram | 21.0 | pass | 0.136 | 0.11 ✗ | 0.561 | 0.397 ✗ | 0.549 | 0.665 | 0.5 | 0.27 | 0.524 | 1.0 ✗ | 0.0 | 0.54 ✗ | 0.238 ✗ | 0.032 | 3 | 4 ✗ | 0.121 | 0.566 ✗ | 12/19 |
| L5b | ankle-pitch servo up into the calf, 1:1 parallelogram | 21.0 | pass | 0.136 | 0.11 ✗ | 0.561 | 0.396 ✗ | 0.55 | 0.626 | 0.5 | 0.27 | 0.988 ✗ | - | 0.082 | 0.62 ✗ | 0.238 ✗ | 0.032 | 6 | 3 | 0.249 | 0.562 ✗ | 12/18 |
| L5c | both: knee servo in the thigh, ankle servo in the calf | 21.0 | pass | 0.136 | 0.11 ✗ | 0.561 | 0.397 ✗ | 0.549 | 0.665 | 0.5 | 0.27 | 0.623 | 0.567 | 0.0 | 0.08 | 0.238 ✗ | 0.032 | 4 | 5 ✗ | 0.112 | 0.566 ✗ | 14/19 |
| L6a | neck pitch + yaw -> SCS0009 (pitch in a slimmer head, yaw in the chest slot) | 21.0 | pass | 0.137 | 0.088 ✗ | 0.52 | 0.397 ✗ | 0.549 | 0.627 | 0.5 | 0.27 | 0.956 ✗ | 1.0 ✗ | 0.086 | 0.127 | 0.238 ✗ | 0.032 | 3 | 3 | 0.167 | 0.566 ✗ | 13/19 |
| L6b | neck pitch + yaw -> SCS0009, yaw servo standing in the neck (chest front slot freed) | 21.0 | 1 | 0.134 | 0.112 ✗ | 0.68 | 0.397 ✗ | 0.549 | 0.627 | 0.5 | 0.27 | 0.956 ✗ | 1.0 ✗ | 0.086 | 0.127 | 0.238 ✗ | 0.032 | 3 | 3 | 0.167 | 0.566 ✗ | 12/19 |
| L7 | 5-DOF legs (no ankle roll; heel and foot at 0.17 H) | 21.0 | pass | 0.136 | 0.11 ✗ | 0.561 | 0.397 ✗ | 0.549 | 0.627 | 0.5 | 0.27 | 0.956 ✗ | 1.0 ✗ | 0.086 | 0.127 | 0.171 ✗ | 0.032 | 3 | 2 | 0.158 | 0.547 ✗ | 13/19 |
| L8 | height 0.60 m, R1 hardware | 19.0 | pass | 0.136 | 0.11 ✗ | 0.528 | 0.356 ✗ | 0.411 ✗ | 0.64 | 0.5 | 0.27 | 0.971 ✗ | 1.0 ✗ | 0.079 | 0.119 | 0.227 ✗ | 0.028 | 3 | 2 | 0.131 | 0.564 ✗ | 12/19 |
