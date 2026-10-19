# Research summary for Adam (≤ $400, ~0.5 m, 16× STS3215, walking first)

Evidence accessed 2026-10-19. Details and URLs are in the linked files. ⚠ = contradicts a current assumption.

1. ⚠ **Continuous torque is ~33% of stall, not 40%.** Feetech's own "rated" torque is 6.5 of 19.5 kg·cm (7.4 V) and 10 of 30 kg·cm (12 V); Robotis rates ~20% for Dynamixel. One seller advises ≤50% of max for continuous use. No independent thermal measurement exists (`actuators/feetech-sts3215/`, `methods/e`). Use 20–33% and treat 40% as optimistic.
2. ⚠ **Adam's mass target looks too low.** Real 0.5 m humanoids weigh 3.4–3.5 kg (ToddlerBot, OP3). Fit over 9 robots: mass ≈ 18.2·h^2.26 kg (R² 0.92), about 3.8 kg at 0.5 m. `6.4·h³` is structure only (0.8 kg) and the all-up ~1.7 kg target is not supported by any comparable robot (`robots/benchmarks.md`).
3. **Knee torque is thin.** Comparable robots need ~2.4–4 N·m at the knee (weak fit, N=5). STS3215 stall is 1.9 N·m at 6 V and ~2.9 N·m at 12 V (sources disagree on which voltage gives 19.5 kg·cm). A 3S pack is ~11.1 V nominal (12.6 V full), so which STS3215 voltage variant is bought matters; verify it.
4. **Zero-shot sim-to-real needs an identified actuator model.** ToddlerBot used chirp system ID; Open Duck Mini uses BAM. Only Open Duck Mini is a true STS3215 analogue and its transfer is partial.
5. **A published STS3215 model exists, but only at 7.4 V** (BAM M4: kt 1.27, R 2.47 Ω, armature 0.0234, delay ~5 ms, max speed ~5.07 rad/s). Load-dependent friction is ~4× base friction. There is no 12 V fit, so a 3S-powered Adam needs its own identification (a bench rig is a cheap first task).
6. **Stock simulation gains are wrong.** Open Duck Mini uses kp 17.8, force limit ±3.35 N·m, damping 0.60, frictionloss 0.052; a blog fit of the SO-ARM100 model gave kp ~108 against a stock MJCF kp of 998 that saturates (`methods/a`).
7. **Randomize what the others did.** Open Duck Mini: kp ±10%, action delay 0–3 steps (0–60 ms). ToddlerBot alone randomizes motor strength and backlash. Ranges are tabulated in `methods/domain_randomization_ranges.yaml`; line anchors may drift.
8. **Thermal and protection limits shape the gait.** STS3215 trips at 70 °C and on overcurrent (~2 A for 2 s reported); heat drifts learned policies, so derate to ~50% load. Holding current, thermal time constant and bus capacity are `null`: measure them (`methods/e`, `actuators/*/notes.md`).
9. **Gears and electronics fail before specs say.** Anecdotes: gear stripping on stalls above ~15% of max torque; MOSFETs failing before gears. These are single-source; plan a fall-protection and current-limit strategy and budget spares.
10. **Printed parts: design for Z delamination.** Z strength is 0.60–0.78 of XY (PA12-CF 0.60), with brittle Z failure. No published FEA knockdown or small-humanoid fall-load method exists; the fall estimate in `methods/d` (v=√2gh, a=v²/2d) is derived, not sourced. Verify with drop-test coupons. PLA endurance limit is ~10% of UTS.

**Reference motions (no controller yet):** fastest path is Open Duck Mini's placo gait generator plus MuJoCo Playground/MJX RL, but the generator has no stated license (`methods/c`).

**Open gaps:** STS3215 PID defaults, backlash, 12 V identification, STS3250 and RobStride measured data, Bez/HR-OS and AiNex data, Zeroth mass and servo count (16 vs 18 conflict), and PAHT-CF properties.
