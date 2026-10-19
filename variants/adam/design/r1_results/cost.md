| Configuration | Servos | Sticker parts | Spares | Tax | Ship (est) | Delivered | **R1 total (+10%)** | Fits $550? | Fast-US R1 total | Worst tariff case | Estimate lines |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 RECOMMENDED hardware at the DEFAULT height 0.55 m: 19 STS3215-12V + 4 STS3250 (knees, hip roll), Pi 5 1 GB + D36V50F5, GNB 3S 1850, BNO085, B6neo, gamepad | 23 | $1108 | $116 | $92 | $60 | $1376 | **$1514** | NO | $1690 | $1697 | $189 |
| P1 same hardware at the CONDITIONAL height 0.60 m (only if the bench STS3250 stall at 11.1 V >= ~1.3x datasheet) | 23 | $1123 | $116 | $93 | $60 | $1392 | **$1531** | NO | $1708 | $1715 | $204 |
| P1 LEAN, 0.55 m: STS3250 at hip roll ONLY (knees STS3215, if Q3 says no deep squat and the bench 12 V curve is not the linear one), phone, ICM-42688, DFR0831 | 23 | $907 | $116 | $77 | $60 | $1160 | **$1276** | NO | $1470 | $1476 | $158 |
| P1 LEAN, 0.55 m, knees kept STS3250 (phone, ICM-42688, DFR0831) | 23 | $1013 | $116 | $85 | $60 | $1274 | **$1401** | NO | $1579 | $1584 | $158 |
| P1 if the bench is favourable: 23 STS3215-12V, 0.55 m, Pi 5 1 GB | 23 | $896 | $63 | $72 | $60 | $1091 | **$1200** | NO | $1418 | $1426 | $189 |
| P2 RECOMMENDED (cheapest that keeps every engine-checked MUST): 21 servos, 6-DOF legs, no waist, neck 2, 3-DOF arms, 1 gripper, 0.55 m, lean + B3 charger | 21 | $689 | $63 | $57 | $60 | $868 | **$955** | NO | $1158 | $1164 | $138 |
| P2 rec. with no spares | 21 | $689 | $0 | $52 | $60 | $801 | **$881** | NO | $1059 | $1064 | $138 |
| P2 cap held on the sticker: 14 servos (5-DOF legs, neck yaw, ONE arm: shoulder pitch + roll + gripper), 0.55 m, lean + B3 charger, no spares | 14 | $543 | $0 | $41 | $60 | $643 | **$708** | NO | $827 | $831 | $138 |
| ref: 23 x STS3215-12V, 0.758 kg filament (QUOTES.md basis), Pi Zero 2 W board price (out of stock) | 23 | $795 | $63 | $65 | $60 | $982 | **$1081** | NO | $1302 | $1307 | $156 |

One more 12 V STS3215 at the R1 accounting: $27.93 (CHEAP) / $37.41 (FAST)
Non-servo floor at the R1 accounting (lean: phone, B3, ICM-42688, camera, 3S 1300): Pi 5 $460, Pi Zero 2 W $308
Pi 5 1 GB + DFR0831 lean floor $347; most servos under $550: 8
Most 12 V servos that fit $550 at the R1 accounting on that floor: Pi 5 3, Pi Zero 2 W 9

| Lever on the recommended Path 1 build (alone) | R1 total change |
|---|---|
| phone instead of the gamepad (R9 allows it) | -46 $ |
| ICM-42688 instead of BNO085 (unverified, own sensor fusion) | -25 $ |
| DFR0831 4 A buck instead of the D36V50F5 (Pi 5 at reduced USB current; confirm at bring-up) | -41 $ |
| STS3215 knees instead of STS3250 (needs Q3 = no deep squat AND a non-linear 12 V curve on the bench) | -126 $ |
| B3 charger instead of B6neo (unverified, ~0.8 A, no 4.0 V/cell setting) | -84 $ |
| no spares (risk: 10-20 day re-order) | -137 $ |
| 0.60 m instead of 0.55 m (filament) | +18 $ |

Bench order (test equipment, outside the BOM): STS3215 12 V (Seeed C047) $22.00, STS3215 7.4 V (Seeed C001) $21.99, STS3250 12 V (OpenELAB C002, DDP) $73.99 = $117.98 + shipping
