<!-- written by variants/adam/design/packaging/cost.py (T-20261019-c1aa); re-run, do not edit -->
# Packaging-for-look levers: R1-accounting cost (CHEAP scenario)

New prices are vendor listings read 2026-10-19 (parts.yaml, verified: false): STS3045M $40.00 (aifitlab, backordered; Core Electronics A$57.93 in stock), SCS0009/SC09 $8.99 (Waveshare), Pololu D36V50F6 $39.95. Linkage hardware $12 is an ESTIMATE.

| configuration | sticker | R1 total | change vs R1 |
|---|---|---|---|
| R1 recommended (baseline) | $1108 | $1514 | +0 $ |
| L1d small arm (6x STS3045M + 2x SCS0009 + 6 V buck) | $1239 | $1716 | +202 $ |
| L2 no waist yaw | $1087 | $1489 | -25 $ |
| L3a flat Tattu 1300 pack | $1109 | $1515 | +1 $ |
| L3b lumbar pack (needs no waist yaw) | $1087 | $1489 | -25 $ |
| L5 knee + ankle linkages (est. hardware) | $1120 | $1528 | +14 $ |
| L6 small neck (2x SCS0009 + 6 V buck) | $1124 | $1544 | +30 $ |
| L7 5-DOF legs | $1066 | $1464 | -49 $ |
| L8 0.60 m | $1123 | $1531 | +18 $ |
| C1 package (L1d + L6 + L2/L3b + L5, 6-DOF) | $1206 | $1688 | +174 $ |
| C1 with 5-DOF legs | $1164 | $1638 | +124 $ |
| C2 package (L1d + L6b + L5c, flat Tattu 1300, waist kept) | $1228 | $1714 | +200 $ |
| C2 lean (C2 + STS3215 knees, after the bench + Q3) | $1122 | $1588 | +74 $ |
