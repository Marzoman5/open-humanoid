# Challenge #2: concept-engine results before R1, 2026-10-19

**Challenger verdict: STOP AND RETHINK for the R1 decision.** Keep the engine; it's honest and well instrumented. But the gates are uncalibrated, and the height-driving R10 cases are partly artifacts. Deciding now would likely pick the wrong servos or the wrong height.
**Solid physics finding:** the hip strategy (trunk swing) is unavailable with STS3215s (needs ~11.5 rad/s vs a 4.4 rad/s no-load ceiling). Treat it as unavailable, not as a blocker.

| # | Challenge (short) | Sev | Commander response | Owner |
|---|---|---|---|---|
| 1 | The duck-like check isn't Open Duck Mini (wrong mass 1.70 vs 2.107 kg, 6 vs 5 DOF legs, legs 20% long, gait 0.40 s vs ODM 0.17 s single support), so its FAIL can't attribute the gap | blocker | **Accept.** Calibration run: ODM's own MJCF + its own reference motion through the identical demand/gate code; frozen gait on ODM; frozen gait on ODM-proportioned spec. Read-only, outside the repo (those repos have no LICENSE). Threshold changes only by commander ADR from the measured factor | calibration agent |
| 2 | B and the duck fail on RMS vs a contested retailer "rated" label | major | **Accept.** Show B with RMS denominators 0.49 and 0.64 N·m until bench thermal holds exist | calibration agent; bench |
| 3 | A's pass/fail flips on unmeasured 12 V parameters; the "pessimistic" linear curve may be the physical one | blocker (to committing) | **Accept.** The bench servo test is on the critical path. Recommend the maintainer buy one 12 V (C018/C047) + one 7.4 V (C001) STS3215 now as test equipment (~$40). Bench protocol: BAM identification, mid-speed lift, 15-min thermal holds, overload timing | maintainer (purchase); bring-up task (protocol scripts) |
| 4 | ±50% armature band unfounded; challenge-1 row 17 (ST3025) not applied | major | **Accept.** ST3025 (armature 0.00399) reported as a sensitivity row now; the bench settles it | calibration agent |
| 5 | R10 push scales with each candidate's own foot, and each case is built at the edge of the previous strategy | blocker (for R10 in height) | **Accept.** R10 becomes an absolute impulse, the same for every candidate, recovered by any combination of strategies; one gate: largest recoverable ≥ requirement. Provisional value set below pending the maintainer | calibration agent; maintainer Q1 |
| 6 | Lateral capture forces a step for a push inside double support | major | **Accept.** Lateral double-support case first; step only beyond the support polygon | calibration agent |
| 7 | "Capture step out of reach at 0.45 m" is a 6% margin with a fixed 0.15 s swing and single step | major | **Accept.** Sweep swing time 0.15–0.35 s and allow 2 steps | calibration agent |
| 8 | No push while walking | major | **Accept.** Add a push at mid single support of walk_forward | calibration agent |
| 9 | COP may be referenced to the ankle, not the foot centre | minor/major | **Accept.** Check and fix | calibration agent |
| 10 | Mass sensitivity implausibly low; no `mj_inverse` cross-check | major | **Accept.** Mass-propagation unit test + `mj_inverse` cross-check on stand and walk | calibration agent |
| 11 | Structure mass low vs ODM (non-servo 1.34 vs 0.93 kg) | major | **Accept.** Back out ODM's structure mass as a calibration point; recentre the nominal if the gap > 1.5× | calibration agent |
| 12 | Stance knee flex (40°) not swept | minor | **Accept.** Sweep 20–45°, identical for every candidate | calibration agent |
| 13 | One frozen step time isn't how a policy walks | minor | **Accept.** Frozen *set* {0.25, 0.35, 0.5} s for every candidate; gate on the best feasible | calibration agent |
| 14 | Budget rule can't be met while prices are unverified; missing BOM lines | major | **Accept.** Live quotes at qty 25 (fast US vendors), plus missing lines (charger PSU, spares, shipping, tax/tariff, controller). "High band" replaced by verified quote + 10% contingency | sourcing agent (T-0002) |
| 15 | Fuse conflicts with R10 transients | minor | **Accept.** Size the fuse and adapter from the R10 / all-leg stall transient | calibration agent |
| 16 | Pickup table height 0.25 m vs provisional 0.40–0.50 m | minor | **Accept.** Run both; maintainer confirms | calibration agent; maintainer |
| 17 | A SHOULD (130° sit-to-stand) silently costs a MUST (look: calf pocket) | minor | **Accept.** R1 states knee ROM as an explicit trade (110° vs 130°). Also note the CAD foundation found knee ROM CAD-limited to 115° | decision agent |
| 18 | Stale or overstated text; research says "ODM uses BAM: unsupported" but the ODM README says it did | minor | **Accept.** Fix the text and the research verification row | calibration agent (code text); commander (research) |

**Provisional R10 (pending maintainer Q1):** survive an absolute push of **0.45 N·s** standing **and** mid-walk, by any combination of strategies including steps. This is the top of the ToddlerBot randomization range for a ~2.5 kg robot. The engine also reports the largest recoverable push, so the maintainer can choose with numbers.

**Order before R1:** code fixes and ODM calibration (parallel) → live quotes (parallel) → maintainer answers → re-run all candidates and the height sweep → bench identification when the servos arrive → packaging and minimum height with the knee-ROM-vs-look trade → R1.

## Maintainer questions
1. **R10:** what push must Adam survive? (provisional: 0.45 N·s standing and walking, any strategy)
2. **Bench servos:** approve ~$40 (one 12 V + one 7.4 V STS3215) as test equipment now, knowing R1 waits for the result?
3. **Budget:** if verified prices put 21–23 servos over $550, what gives first: DOF (e.g. one gripper, no waist yaw), the cap, or height?
