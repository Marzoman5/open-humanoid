<!-- written by variants/adam/design/packaging/scale.py (T-20261019-c1aa); re-run, do not edit -->
# Height at which each limb section can be as slim as the references (PROVISIONAL)

Reference width / H from the approximate reference profiles (optimus_like, atlas_like; low confidence). Floor = servo dimension across the limb + housing + shell (11.5 mm). H_min = floor / (reference width / H). The largest H_min sets the scale.

| feature | optimus W/H | atlas W/H | STS3215 direct (R1 layout): floor mm / H_min m (optimus, atlas) | STS3215 legs relocated (slim knee/ankle) + STS3045M arm + SCS0009 neck/gripper: floor mm / H_min m (optimus, atlas) |
|---|---|---|---|---|
| thigh_upper | 0.084 | 0.088 | 58.2 / 0.69, 0.66 | 58.2 / 0.69, 0.66 |
| knee | 0.060 | 0.065 | 58.2 / 0.97, 0.90 | 38.2 / 0.64, 0.59 |
| calf_max | 0.066 | 0.070 | 58.2 / 0.89, 0.83 | 58.2 / 0.89, 0.83 |
| ankle | 0.046 | 0.049 | 58.2 / 1.25, 1.18 | 38.2 / 0.82, 0.77 |
| upper_arm | 0.048 | 0.053 | 36.2 / 0.76, 0.69 | 26.5 / 0.56, 0.50 |
| elbow | 0.045 | 0.046 | 48.5 / 1.07, 1.05 | 42.7 / 0.94, 0.92 |
| forearm | 0.045 | 0.045 | 36.2 / 0.81, 0.81 | 23.6 / 0.53, 0.53 |
| head_w | 0.082 | 0.092 | 48.5 / 0.59, 0.53 | 38.8 / 0.47, 0.42 |

- **STS3215 direct (R1 layout):** binding feature `ankle`, H_min 1.25 m (optimus) / 1.18 m (atlas).
- **STS3215 legs relocated (slim knee/ankle) + STS3045M arm + SCS0009 neck/gripper:** binding feature `elbow`, H_min 0.94 m (optimus) / 0.92 m (atlas).
