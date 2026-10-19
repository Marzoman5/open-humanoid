# The low-cost actuator class (snapshot 2026-10-19)

Data: `actuators.yaml`, `raw/actuators-raw.yaml`. **Every number is a vendor/retailer claim; no independent bench data or failure reports were found.** Peak torque is transient; RobStride's own guides advise designing to rated torque with heat sinking.

## Price table (cheapest credible listing; single unit)

| Actuator | Peak / rated N.m | Mass g | Volt | Ratio | Encoder | Price USD (cheapest) | US-facing price | Note |
|---|---|---|---|---|---|---|---|---|
| RobStride RS05 | 5.5 / 1.6 | 191 | 48 (15-60) | 7.75 | dual 14-bit | 110 | 155 | arm, neck |
| RobStride RS00 | 14 / 5 | 310 | 48 | 10 | dual | 125 | 185 | shoulder, ankle roll |
| RobStride RS01 | 17 / 6 | 380 | 36 | 7.75 | **single** | 158 | 185 | |
| RobStride RS02 | 17 / 6 | 405 | 48 | 7.75 | dual | 145 | 175 | repo note re-verified |
| **RobStride RS06** | **36 / 11** | 621 | 48 | 9 | dual | **210** | 222 | new; best N.m per dollar and kg in 20-40 class |
| RobStride RS10P | 42 / 14 | 460 | 48 | 25 | dual | null | 234 | 25:1, less backdrivable |
| RobStride RS03 | 60 / 20 | 880 | 48 | 9 | dual | 225 | 250 | repo note re-verified |
| RobStride RS04 | 120 / 40 | 1420 | 48 | 9 | dual | 255 | 295 | |
| Damiao DM-J4310 | 7 or 12.5 (sources conflict) / 3 | 300 | 24 | 10 | dual | 125 | 167 | OpenArm / LeRobot class |
| Damiao DM-J4340 | 27 / 9 (catalog; aifitlab now lists 40 / 14: conflict) | 362 | 24-48 | 40 | dual | 155 | null | slow (52-100 rpm), not backdrivable |
| Damiao DM-J8006 | 20 / 8 | 559 | 24-48 | 6 | dual | 210 | null | dominated by RS06 |
| Damiao DM-J10010L | 120 / 40 | 1375 | 24-48 | 10 | dual | 265 | null | |
| Xiaomi CyberGear | 12 / 4 | 317 | 24 | 7.75 | single | 179 | null | dominated by RS02 |
| Unitree GO-M8010-6 | 23.7 / null | 530 | 12-30 | 6.33 | 15-bit | 280 | 369 | dominated by RS06 |
| CubeMars AK45-36 | 24 / 8 | 340 | 24 | 36 | dual 16-bit | 150 (186 with driver board) | null | 36:1 |
| CubeMars AK70-10 | 24.8 / 8.3 | 521-621 | 48 | 10 | 14-bit | 399 | 564 | |
| MyActuator RMD X6-40 | 40 / 18 | null | 48 | null | null | 545 (paper BOM) | null | no US USD list found |
| Feetech STS3250 (Adam's class) | 4.9 / 1.57 | 75 | 6-12 | 345 | 12-bit | 88-97 (74 at openelab, unverified) | 97 | TTL bus servo |
| Dynamixel XM540 | 10.6 | 165 | 12 | n/a | n/a | 494, sold out | | reference |

Availability: aifitlab is the cheapest but ships from China (SF Express 7-12 business days) and showed "Only Motor" variants backordered on 2026-10-19. openelab.com (US warehouses, duties stated included) and roboticscenter.ai (claims SF stock; RS03 backordered 4-6 weeks plus ~$67 shipping) cost 6-35% more. Expect 3-8 weeks for a first order.

## DIY route
- **Berkeley Humanoid Lite:** printed PLA cycloidal + drone BLDC + B-G431B-ESC1 driver + AS5600 encoder. **$188 (6512, ~20 N.m by a secondary source, our upper bound 27.6) and $136 (5010, ~12 N.m) at US prices;** $157/$94 at China prices. Backlash up to 1.3 deg (authors' measurement), single encoder, 60 h printed-part durability test, thermal effects of printed parts not studied. 22 actuators = 81% of the $4,312 robot BOM.
- **Moteus r4.11** driver $94 (Apache-2.0 firmware), **ODrive S1** $149 (sold out on page), a moteus-class QDD100 module $879 (not stocked).
- **Bottom line:** DIY is **not cheaper** than a bought RS06 ($210, 36 N.m, steel gears, dual encoders) once labour is counted; its advantage is knowing and owning the design. Realistic per-joint DIY cost: $136-188 for 12-20 N.m.

## Tooling and models
- Drivers and protocols: CAN-based. Community libraries exist (damiao-motor, DM_Control_Python, LeRobot Damiao bus, unofficial robstride_ros2); RobStride publishes manuals, STEP files and an OTA tool on GitHub (manuals not read; SDK licence unknown).
- **No MuJoCo/Isaac actuator models exist for RobStride, Damiao or CubeMars.** Adam's repo already requires measured models (BAM, chirp sysid). Noetix's BSD-3 Bumi sim config (delayed implicit PD actuator) is a usable starting template for a robot of this class.
- No brakes on any of these. Holding a pose costs continuous current.

## What this means
The floor for a torque-capable integrated joint is **about $110-145 per joint**, so 21-23 joints cost **$2.4-3.3k** at retail regardless of size. That is the central finding behind `feasibility.md`.
