# Challenge #3: R1 concept package, 2026-10-19

**Challenger verdict: PROCEED WITH FIXES.** These hold: $550 is infeasible with the MUSTs; 2S is out (R10); all-STS3215 is fragile; the hip roll needs reinforcement above 0.5 m. These are **not supported**: 0.60 m and the knee STS3250s. Both lean on transferring the ODM calibration to the STS3250, whose own motor model gives about 0.57× the STS3215's real-over-datasheet headroom. **No main order before the STS3250 is on the bench.**

| # | Challenge (short) | Sev | Commander response |
|---|---|---|---|
| 1 | ODM factors probably don't transfer to the STS3250, so 0.60 m rests on an assumption; on strict gates 0.55 m beats 0.60 m (8/11 vs 5/11); at half calibration 0.60 m fails and 0.55 m holds | blocker | **Accept.** Hardware choice separated from height. The STS3250 bench unit becomes a **prerequisite** (with the two STS3215s). Height goes to 0.60 m only if the bench STS3250 stall at 11.1 V is ≥ ~1.3× datasheet |
| 2 | Case for 0.60 over 0.55 is thin (speed cliff on one bound; S3a fails at 0.60; p95 from 16 samples) | major | **Accept.** Present it as an explicit look-vs-robustness trade; 64-sample MC; design critic on both studio sheets before look is used as a tie-breaker |
| 3 | Knee STS3250s bought for a 120° squat no MUST needs | major | **Accept.** Rerun hip-roll-only reinforcement without squat_120 (deepest squat = lowest provisional table pickup); maintainer Q3 on squat depth |
| 4 | A 1.6:1 transmission on STS3215 was never compared with buying STS3250 | major | **Accept.** One engine run each at 0.55/0.60 m with a 1.6:1 linkage at hip roll (and knee), R10 included |
| 5 | Engine verdict is FAIL; R5 not established; 0.40 m table spike unexplained | major | **Accept.** State the engine verdict and R5 status by table height in §1; root-cause the spike (contact forces / table contact off) |
| 6 | Margins depend on a slow gait the policy may not use | major | **Accept.** Write "step time ≥ 0.45 s, stance knee 40–45°" as a P5 policy constraint, and report margins at 0.35 s |
| 7 | Mass excludes shells (+0.4–0.6 kg) | major | **Accept.** Add a shelled-nominal row (structure ×1.2, or bake-off M3 wall/mass) |
| 8 | No low-battery case | major | **Accept.** Add a low-SoC bound (SoC 0.15, internal resistance ×1.5) to the bounds; rerun P1/P1r |
| 9 | The 4.0 V/cell charge setting is assumed; pack sizes 1500–1800 not considered | minor | **Accept.** Confirm the B6neo setting (manual); size a 3S 1500–1800 pack; bench STS3250 at 12.6 V |
| 10 | Bus connectors overloaded (5264-style 3 A vs 4.2 A STS3250 stall); fuse 15 vs 20 A mismatch | major | **Accept.** Star power topology per leg (heavier power wire, max servos per segment); bench connector-temperature test; fuse reconciled to 20 A unless the analysis says otherwise |
| 11 | 5-DOF rejection evidence doesn't hold (the 6-DOF walk also exceeds the tether gate under perturbation) | minor | **Accept.** Report the tether gate on ODM case (b); keeping ankle roll stays a conservative choice, reworded honestly |
| 12 | Drop "R10 at 2.1×" as a ranking reason; foot exceeds the look rubric | minor | **Accept.** Drop it; rerun R10 with foot 0.17 H and +20 ms latency |
| 13 | Path 1 lean cost (~$1,390; ~$1,265 with STS3215 knees) | minor | **Accept.** Add a Path 1 lean row and a levers list; fix the sold-out charger and filament price |
| 14 | P3 is infeasible; two narrowing moves untried | minor | **Accept.** Try lateral-face arm servos and a forward arm offset; brief R2a plainly that the numeric P3 band is out of reach with STS-class servos in 0.40–0.65 m, so the critic judges the reading |
| 15 | Sit-to-stand claim overstated | minor | **Accept.** Reword |
| 16 | Flagged issues don't undermine the recommendation | — | Noted |

**Bench protocol** (one STS3250 plus the two STS3215s, at 11.1 and 12.0 V): stall with lever and scale; no-load speed plus torque at ~50% speed (check the suspicious 0.76 drivetrain efficiency implied for the STS3250); BAM pendulum armature/friction; 15-min enclosed thermal hold at hip-roll RMS (~1.46 N·m); overload trip timing and the register map; behaviour at 12.6 V; connector temperature at ~4 A.

## Maintainer questions
1. **Budget:** approve Path 1 (~$1,265–1,505 after the lean and knee fixes) on the condition that nothing beyond the bench servos is ordered until the STS3215 + STS3250 measurements are in?
2. **Look vs robustness:** is ~0.035 H of shoulder ratio worth ~20% less strict margin (0.60 vs 0.55 m)? Or relax the numeric P3 for Adam and let the critic judge?
3. **Squat depth:** does any MUST need a deep squat (≥ 110°), e.g. pickup from 0.30–0.35 m tables or dance moves? If not, the knees stay STS3215.

## Bench protocol addition (2026-10-19 night)
- **Unpowered back-drive torque** of the STS3215 and STS3250 (servo de-energised, measured with a lever and scale), plus behaviour with torque enabled vs disabled. If a fall reflex that de-energises the servos is adopted in the runtime, this may cap fall loads far below the current 2× stall policy, for every arm and neck path (region-B option D). The strength policy changes only after measurement, by the strength owner.
