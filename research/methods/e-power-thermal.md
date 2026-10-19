# E. Power and thermal practice for serial-bus-servo robots

Access date for all links: 2026-10-19. "Derived" = arithmetic here from cited inputs; null = not found. Feetech's own datasheet translation is garbled ([PDF](https://core-electronics.com.au/attachments/uploads/sts3215-smart-servo-datasheet-translated.pdf)), so vendor listings are used.

## 1. STS3215 numbers
- 12 V variant: stall torque 30 kg-cm, rated torque 10 kg-cm, stall current 2.7 A, no-load running current 180 mA ([RobotShop](https://robotshop.com/products/feetech-12v-30kgcm-magnetic-encoding-servo-sts3215), [Eckstein](https://eckstein-shop.de/Motors?mf=1602)).
- 6 V variant (19.5 kg-cm): stall 2 A @ 6 V ([AifitLab](https://aifitlab.com/collections/feetech/products/feetech-sts3215-servo-motor)). The 7.4 V (SO-ARM) variant's stall current: null (not found).
- Holding-load current: null in all sources (measure). Stall current is the worst-case bound.
- Protection (vendor listings, unverified, configurable): torque off above 70 C; overcurrent >2 A for 2 s; overload at 80 % of stall for 2 s ([Sigmanortec](https://sigmanortec.ro/en/servo-smart-serial-sts3215-360-degrees-19kg-12-bit-encoder-74v), [datasheet translation](https://core-electronics.com.au/attachments/uploads/sts3215-smart-servo-datasheet-translated.pdf)). Register addresses: null.
- Operating voltage range / max: null (not reliably extracted); verify before using a 3S pack (4.2 V/cell full = 12.6 V is standard Li-ion chemistry, not from a servo source).
- Worst case, 16 servos stalled at 2.7 A = 43 A (derived); realistic walking draw: null, measure.

## 2. Continuous torque fraction (vs the 40 % assumption)
| Source | Continuous / stall | Link |
|---|---|---|
| STS3215 vendor "rated" 10 vs "stall" 30 kg-cm | 33 % (derived) | [RobotShop](https://robotshop.com/products/feetech-12v-30kgcm-magnetic-encoding-servo-sts3215) |
| Robotis (Dynamixel, stall-only models) | 20 % suggested | [Robotis blog (via search; page 404 on re-fetch)](https://www.robotis.us/robotis-blog/torque-ratings/) |
| Hitec service claim (hobby servo) | 80 %; group's own HS-645MG test sustained ~49 % warm, slow | [AIRWiki thread](https://airwiki.deib.polimi.it/index.php/Talk:Servomechanisms_(aka_%22Servos%22)) |
| Forum (DC servo theory) | <=20 % | same thread |
| XL430 e-Manual | real-world performance closer to graph than stall rating | [Robotis](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/) |
Verdict: 40 % exceeds the vendor-rated 33 % and the 20 % Robotis rule; it is defensible only for short duty cycles. Use 20-33 % as sustained holding, 40 % for brief poses.

## 3. Thermal modelling
- Two-parameter lumped model: thermal resistance Rth (C/W) and time constant tau; C = tau/Rth. Four-parameter model adds a winding node; winding tau is ~10x shorter than case tau, and winding vs housing can differ by 30-50 C ([Design News](https://www.designnews.com/motors-actuators-conveyors/try-the-4-parameter-thermal-model-for-servomotors), [Machine Design](https://www.machinedesign.com/motorsdrives/revised-duty-cycle-calculations-using-four-parameter-thermal-model)). Implication: case-temperature sensors lag during overcurrent.
- Published tau / Rth for STS3215 or hobby servos: null. Obtain by step-current test: hold constant torque, log the servo's temperature register, fit exponential.
- Dynamixel thermal shutdown is a configurable limit (user report default 70 C) ([Robotis DX-113](https://emanual.robotis.com/docs/en/dxl/dx/dx-113/), [Synthiam](https://synthiam.com/Community/Questions/Dynamixel-Settings-Question-4152)). Robotis staff: two servos sharing a load run cooler than one ([forum](https://community.robotis.us/t/heat-issues-with-xm430-w350-r/230)).
- Modelling stub: P_loss = I^2 R (I from load torque / Kt); T_winding rises with tau_w; use the 70 C trip as the limit and derate for ambient inside a closed printed shell (null data).

## 4. 3S LiPo, sag, peak current
- Sag = I x R_internal; a 2200 mAh 3S measured ~20 mOhm pack ([Flite Test](https://www.flitetest.com/articles/LiPo_Battery_Internal_Resistance_Testing)); <5 mOhm/cell good for FPV ([Zbotic](https://zbotic.in/?p=595985)).
- Derived: 20 mOhm x 20 A = 0.4 V; x 43 A (all servos stall) = 0.86 V. Choose C-rating so peak servo current < ~50 % of C x capacity (judgement, not sourced). Cutoff 3.0 V/cell = 9.0 V pack (derived).
- Brownouts: simultaneous acceleration or heavy holding loads pull voltage under the servo minimum causing resets and comms dropouts; voltage also sags at the far end of long chains ([Robotis](https://robotis.us/tech-tips-powering-large-dynamixel-daisy-chains-what-you-need-to-know)).

## 5. Bus topology, wiring, fuses
- Robotis recommends ~10 A as ceiling when powering Dynamixel from its boards ([Robotis](https://robotis.us/robotis-blog/powering-dynamixel)); allowable daisy-chain current is per-model connector spec ([U2D2 Power Hub](https://emanual.robotis.com/docs/en/parts/interface/u2d2_power_hub/): 10 A max, 3.5-24 V). STS3215 connector current rating: null.
- Inject power (break out VDD) at several points or use separate feeds for groups, rather than serial power through every servo ([Robotis community](https://community.robotis.us/t/dynamixel-robot-arm-using-u2d2-doubts/251)).
- Servos per bus: null (no published limit found for STS; Robotis says per-model). Wire gauge and fuse sizing: null from primary sources; derive from the connector rating and a fast-blow fuse sized above peak legit draw but below wiring limit.

## 6. Regeneration and fall events
- Regenerative energy raises the bus voltage; industrial drives add shunt resistors or bulk capacitance, C = 2 KE / (Vmax^2 - Vbus^2) ([Celera Motion](https://www.celeramotion.com/ingenia/support/technical-papers/sizing-a-shunt-resistor-for-regenerative-braking/), [formula blog, secondary](https://industrialmonitordirect.com/blogs/knowledgebase/bldc-motor-regenerative-braking-capacitor-sizing-guide)). A low-impedance LiPo absorbs most regen, so a mostly-battery bus rarely overvolts; the risk is when a buck/BMS/switch is in series (it can't accept reverse current). Servo back-EMF behavior of the STS3215: null.

## 7. Raspberry Pi Zero 2 W budget
Idle ~125 mA at 5 V (stock), 75 mA tuned; benchmark 4-core peak ~624 mA; ~1.35 A seen with USB HDD stress ([CNX Software](https://www.cnx-software.com/2021/12/09/raspberry-pi-zero-2-w-power-consumption/)). Foundation PSU recommendation 2.5 A (same article). Camera/Wi-Fi extras: null.

## 8. Buck converter sizing (derived)
Pi + peripherals: 0.15-0.65 A typical, 1.35 A worst seen -> 5 V >=2 A rated buck with low-ESR input cap, fed from a filtered branch, with brownout detect. The servos run from the battery directly (no buck).

## Recommendation for Open Humanoid
Budget peak current from the stall figure (16 x 2.7 A = 43 A theoretical at 12 V; scale for 3S voltage) but design for the realistic gait draw once measured: log current and servo temperature on the first walking rig. Replace the 40 % continuous-torque assumption with 20-33 % sustained and 40 % brief, since the vendor's own rated/stall ratio is 33 % and Robotis uses 20 %. Run the Pi from a separate >=2 A buck, feed servos from the pack through at least two power-injection points (never one long daisy chain), add a fast fuse near the pack, and fit bulk capacitance plus a pack with <=20 mOhm internal resistance; add a brownout/undervoltage cutoff at 9.0 V. Determine thermal tau/Rth by a step-current test on one STS3215, then model with a 4-parameter lumped RC and enforce the 70 C trip with margin. Items still unknown (null): holding current, connector current rating, bus servo count, back-EMF on falls: test on the bench.
