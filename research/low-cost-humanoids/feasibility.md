# Feasibility sketch: a ~0.9 m, 23-DOF Adam from the cheapest credible actuator class

Reproducible: `python research/low-cost-humanoids/feasibility.py` (output saved in `feasibility-output.txt`). Prices from `actuators.yaml` (vendor/retail, 2026-10-19). Torque requirements are **our scaling**, not measured. Nothing here has been simulated with Adam's engine.

## Method
- **Torque.** Adam sizing (`variants/adam/generated/sizing.md`, 0.53 m, 2.52 kg): hip pitch/knee/ankle pitch 1.76-1.85, hip roll 1.66, ankle roll 0.97, hip yaw 0.42 N.m peak (quasi-static walk). Scale to 0.9 m with `scale.md`'s h^3.3 (x5.7) and, as a pessimistic check, torque ~ mass x height with 11.5 kg (x7.75). Result: hip pitch, knee, ankle pitch **~10-14 N.m**, hip roll 9.5-13, ankle roll 5.6-7.5, hip yaw 2.4-3.3. This covers steady walking only; push recovery (R10), dance and sim-to-real margin typically need 2-3x on top. **Practitioner check:** Noetix Bumi (0.98 m, 17 kg claimed) trains with 60 N.m hip pitch/knee, 27 hip yaw/roll, 13 ankle, 5.5 arm.
- **Mass.** Adam's 3.7 kg at 0.55 m scaled by h^2.3 gives **11.5 kg**; bottom-up below gives 11.7-12.8 kg. Bumi claims 12-17 kg.
- **DOF (23).** legs 12, waist 1, arms 8 (shoulder pitch/roll, elbow, wrist pitch), neck 2; plus 2 gripper servos for R5.

## Actuator count by torque class (peak N.m, USD cheapest listing)

| Joint class | Needs at 0.9 m (scaled) | Lean plan | Comfortable plan |
|---|---|---|---|
| Hip pitch, knee (x4) | 10.6-14.3 | RS06 36 N.m ($210) | RS06 |
| Hip roll (x2) | 9.5-12.9 | RS02 17 ($145) margin 1.3-1.8x | RS06 |
| Ankle pitch (x2) | 10.1-13.6 | RS02 17 margin 1.2-1.7x | RS02 (upgrade to RS06 for +$130) |
| Ankle roll (x2) | 5.6-7.5 | RS00 14 ($125) | RS00 |
| Hip yaw (x2) | 2.4-3.3 | RS05 5.5 ($110) | RS00 14 |
| Waist yaw (x1) | null (small) | RS05 | RS00 |
| Shoulder pitch/roll (x4), elbow (x2) | 1.3-1.7 | RS05 x4; elbow STS3250 | RS05 x6 |
| Wrist pitch (x2), neck (x2), grippers (x2) | <1.5 | STS3215 ($21) | STS3215 |
| **Counts** | | RS06 4, RS02 4, RS00 2, RS05 7, STS3250 2, STS3215 6 | RS06 6, RS02 2, RS00 5, RS05 6, STS3215 6 |

## BOM and cost vs the $1,600 lock

| | Lean | Comfortable |
|---|---|---|
| Actuators (aifitlab headline) | $2,713 | $2,960 |
| Battery (12S ~100-150 Wh + charger), $190 | | |
| Compute (Pi 5, 2-3 CAN-FD interfaces, IMU), $220 | | |
| Power (fusing, 48 to 12/5 V converters, e-stop, contactor), $110 | | |
| Structure (printed shell + CNC 6061 brackets, bearings, fasteners), $520 | | |
| Cables, connectors, heat sinks, $90 | | |
| **Parts sticker** | **$3,843** | **$4,090** |
| With US-facing resellers (DDP/stocked prices) | $4,492 | $4,792 |
| **Delivered**, x1.4 (Adam's own accounting: tax, shipping, spares, 10% contingency) | **$5,380** | **$5,730** |
| Delivered, US-facing prices | $6,290 | $6,710 |
| All-up mass | 11.7 kg | 12.8 kg |

(The "other parts" lines are **our estimates**, not researched line by line. If they are off by 50% the totals move by about $565.)

**It does not fit.** Actuators alone are 1.7-1.85x the entire $1,600 lock. The parts sticker is about 3.5x the $1,100 sticker behind it, and the delivered figure is **3.4-4.2x the lock**. For scale: Adam at 0.55 m is $1,540 delivered with servos at about 65% of the sticker.

**Cross-checks (independent builds at similar size):** Berkeley Humanoid Lite $4,312 BOM at 0.8 m (22 weaker printed actuators, no delivery/spares); AGILOped $6,380 (legs-only, 1.1 m); Roboto Origin about $7,000 (1.25 m, Damiao); Unitree R1 $4,900-5,900 before shipping and customs; Bumi $5,995 from the one US reseller found. Our $5.4-6.7k delivered sits inside that band.

**Even a smaller step does not fit.** Rough, not computed in the script: at 0.7 m the torque class drops to RS00/RS05 and the servo-class (STS3250) for light joints, but 12 leg actuators at about $110-125 plus the rest still total about $1.8-2.1k of actuators.

## Risks (what would hurt a 0.9 m QDD Adam)
1. **Availability and lead time.** Most items backordered; one vendor family (RobStride) covers nearly every class; a stock-out or an end-of-sale on a 23-actuator robot is a schedule risk. No second US source; no real warranty path.
2. **Tariffs.** Landed cost on Chinese motors is not established (sources conflict). A 25% duty on $3k adds $750 inside the sticker.
3. **Drivers and firmware.** CAN-based proprietary protocols (RobStride 29-bit private protocol, Damiao MIT-mode). Community libraries exist; none is certified; mixing 24 V and 48 V parts would need separate supplies.
4. **No measured actuator models.** None exist for RobStride, Damiao or CubeMars. Adam's gates assume measured models (ODM calibration for STS3215). Everything would need bench sysid, and thermal behaviour of 36 N.m peak / 11 N.m rated joints is vendor-claimed only.
5. **Safety at 11-13 kg and 0.9 m.** A falling body of this mass with 36 N.m joints can pinch, crush and injure; Adam at 3.7 kg largely cannot. It needs a gantry/harness for bring-up, a hardware e-stop and contactor, and care with the pack voltage (12S charges to 50.4 V; use 10S or an e-stop-gated bus). These are design obligations, not costed here.
6. **No walking proof for the class at this price.** Of the cheap/open builds, only the legs-only Berkeley Humanoid has strong walking evidence; BHL walked once with no speeds reported; Bumi's walking is unaudited.
7. **Fragility cost.** Adam's printed structure at 12 kg and 36 N.m needs machined parts; ToddlerBot and BHL both report printed-part breakage and wear.

## Verdict
A ~0.9 m QDD Adam is **a $5-7k robot, i.e. Eve's price class, not a variant of Adam's $1,600 lock.** It is buildable; the design data are public (Bumi's SDK, Isaac Lab config and URDF are BSD-3; Roboto Origin's BOM and CAD are CERN-OHL-W). It would be a different project.

## Unknown, only measurable
Real peak and continuous torque, backlash and thermal limits of RS06/RS02/RS00; real delivered price including duties; whether 36 N.m RS06 hips actually hold a 12 kg robot's push recovery; driver latency under 23-node CAN; true 0.9 m mass.
