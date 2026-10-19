<!-- written by variants/adam/cad/linkages/analysis.py (T-20261019-4ab5); re-run, do not edit -->
# L5c linkage: analytic strength and play

Hand checks (research/methods/d); the FEA strength gate (T-20261019-a026) had not merged. SF targets: printed parts 3 on the weakest direction (the crank plates print flat, so the coupler load is in the XY plane), metal parts yield/shear SF >= 1.5, bearings static load <= C0r.

## knee: r 22.0 mm, theta [35.0, 145.0] deg (min sin 0.574), coupler 72.5 mm

| check | stall at the window end | fall F1 (0.10 m drop, n = 20), stance theta |
|---|---|---|
| F_coupler_n | 388.6 | 521.0 |
| coupler_net_tension_mpa | 19.0 | 25.5 |
| coupler_SF_yield_net | 14.49 | 10.81 |
| coupler_bearing_mpa | 43.2 | 57.9 |
| coupler_SF_bearing (1.5 Sy) | 9.59 | 7.15 |
| coupler_euler_n (pinned, out of plane) | 2911.0 | 2911.0 |
| coupler_SF_buckling | 7.49 | 5.59 |
| pin_shear_mpa (single shear, minor d) | 86.8 | 116.4 |
| pin_SF_shear | 8.43 | 6.29 |
| bearing_load_each_n (2 per pin) | 194.3 | 260.5 |
| bearing_load_over_C0r | 0.89 | 1.2 |
| seat_pressure_mpa (F/2 over OD x w) | 4.86 | 6.51 |
| seat_SF_vs_PETG_xy/3 | 2.6 | 1.94 |
| clamp_slip | True | True |
| crank_bending_mpa (tapered arm, plate 4.3) | 14.5 | 32.8 |
| crank_SF_vs_PETG_xy | 2.61 | 1.16 |

| play case | lost motion mm | added backlash deg (mid range) | at the window end |
|---|---|---|---|
| best (clamped, tuned seats) | 0.015 | 0.039 | 0.068 |
| nominal (clamped, bearing play mid, seat compliance at the engine peak) | 0.0802 | 0.209 | 0.364 |
| worst (clamp slips: screw in bore, seat one press step loose) | 0.708 | 1.844 | 3.215 |

## ankle: r 18.0 mm, theta [37.5, 122.5] deg (min sin 0.609), coupler 38.0 mm

| check | stall at the window end | fall F1 (0.10 m drop, n = 20), stance theta |
|---|---|---|
| F_coupler_n | 268.3 | 439.8 |
| coupler_net_tension_mpa | 13.2 | 21.6 |
| coupler_SF_yield_net | 20.99 | 12.8 |
| coupler_bearing_mpa | 29.8 | 48.9 |
| coupler_SF_bearing (1.5 Sy) | 13.89 | 8.47 |
| coupler_euler_n (pinned, out of plane) | 10596.0 | 10596.0 |
| coupler_SF_buckling | 39.49 | 24.09 |
| pin_shear_mpa (single shear, minor d) | 60.0 | 98.3 |
| pin_SF_shear | 12.21 | 7.45 |
| bearing_load_each_n (2 per pin) | 134.2 | 219.9 |
| bearing_load_over_C0r | 0.62 | 1.01 |
| seat_pressure_mpa (F/2 over OD x w) | 3.35 | 5.5 |
| seat_SF_vs_PETG_xy/3 | 3.77 | 2.3 |
| clamp_slip | False | True |
| crank_bending_mpa (tapered arm, plate 4.3) | 7.6 | 20.4 |
| crank_SF_vs_PETG_xy | 4.97 | 1.86 |

| play case | lost motion mm | added backlash deg (mid range) | at the window end |
|---|---|---|---|
| best (clamped, tuned seats) | 0.015 | 0.048 | 0.078 |
| nominal (clamped, bearing play mid, seat compliance at the engine peak) | 0.0623 | 0.198 | 0.326 |
| worst (clamp slips: screw in bore, seat one press step loose) | 0.708 | 2.254 | 3.702 |

