# Challenge #1: P2 concept engine (T-0017), plan and assumptions, 2026-10-19

**Challenger verdict: PROCEED WITH FIXES.** Keep building the engine. The concept decision does not run until rows 1–10 are closed.
Challenger: Opus, read-only, run against the work in progress in worktree `agent-a75199eb87db2b876`. The full report is in the commander session transcript. Its rows are summarized below with the commander's response to each (required by docs/pipeline.md).

| # | Challenge (short) | Sev | Commander response | Owner / when |
|---|---|---|---|---|
| 1 | No packaging or not-a-toy check. P3 shoulder band (≤ 0.29 H) likely infeasible at 0.45 m with chest servos; the pack only fits across the upper back | blocker (decision) | **Accept.** The decision agent must produce a front-view hard-point layout from catalog dims at h = 0.45–0.60 m (chest vs in-arm shoulder servos), run `oh design metrics` P3/P4/HP, and derive a minimum feasible height per layout. That height is a hard lower bound | decision agent, before R1 |
| 2 | Candidate geometry ignores the T-0004 packaging lessons (ankle height, foot size, hip spacing, ankle-roll range) | major | **Accept.** Proportion and range floors derived from the servo envelope + stand-offs, applied to every candidate; re-run walk/turn | concept engine, now |
| 3 | Mass centre biased low (no shells), symmetric band wrong, benchmark check can't fail | major | **Accept.** Uncertainty on non-servo terms only, asymmetric (structure ×U(0.9, 1.8), wiring/electronics ×U(0.8, 1.5)); benchmark-mass stress case; "mass to first gate failure". No recalibration of the structure coefficient until shelled CAD exists. Supersedes my earlier −15%/+40% instruction | concept engine, now |
| 4 | 12 V mid-speed torque unverified; friction counted twice after the datasheet cap | major | **Accept.** Two torque-speed models (anchored+cap, pessimistic linear); friction not counted twice; widen 12 V stall/speed ±25%; document the departure from the brief | concept engine, now |
| 5 | Reflected rotor inertia dominates dynamic loads, not perturbed | major | **Accept.** Armature in `perturbed`: ±20% at 7.4 V, ±50% for 12 V and STS3250 | concept engine, now |
| 6 | Firmware overload trip not modelled (robot collapses mid-pose) | major | **Accept.** Protection state machine plus a time-above-threshold gate; report trips per motion | concept engine, now |
| 7 | Envelopes read from clipped servo torque or tether-assisted runs | major | **Accept.** Envelopes from ideal-mode demand / `mj_inverse`; servo mode reports saturation and tracking; assist-impulse threshold invalidates a motion | concept engine, now |
| 8 | Motions tuned per candidate, so passes are self-fulfilling | major | **Accept.** Frozen motion specs shared by all candidates; smoother deviation over 8° fails | concept engine, now |
| 9 | Monte Carlo over latency/backlash in open-loop replay is false precision | major | **Accept.** Tornado/bounds sweep as the headline; small Monte Carlo over quasi-static dimensions only; latency/backlash labelled "closed loop, P5" | concept engine, now |
| 10 | 10-min thermal verdict decided by assumed constants | major | **Accept.** RMS ≤ vendor-rated continuous is the primary gate; thermal reported as hot-case steady state and minutes to 70 °C over a tau range; the model must reproduce both Robonine runs or its numbers aren't used | concept engine, now |
| 11 | ZMP walk is a load lower bound; get-up is a stub | major | **Accept.** Stress variants (1.5× speed, −20% step time, timing error, capture step). Get-up scope depends on maintainer Q3 | engine now; Q3 maintainer |
| 12 | Never checked against a robot that works | major | **Accept.** Open Duck Mini-like concept through the full gate set; the result calibrates the headroom | decision agent (engine supports it) |
| 13 | R5 "table height" undefined; R7 needs neck pitch + camera; compute check | major | **Accept.** Neck pitch + camera added to every candidate's BOM, mass and power; compute check. R5 needs maintainer Q1 | decision agent; Q1 maintainer |
| 14 | Height fixed at 0.45; candidate set named by the commander (anchoring) | major | **Accept.** I repeated my own lesson. Height sweep 0.40–0.65 m per power architecture between the torque ceiling and the packaging floor; reinforcement chosen from per-joint utilisation, not from my brief | decision agent |
| 15 | 2S full charge exceeds the 7.4 V rating; STS3250 rating vs 3S full | minor | **Accept.** Report time over rating and mitigation cost | concept engine (trade study) |
| 16 | BAM re-implementation not checked against upstream | major (cheap) | **Accept.** Pendulum fidelity test vs the `bam` package | concept engine, now |
| 17 | BAM publishes a 12 V Feetech-class servo (ST3025) that research dropped by mistake | minor | **Accept.** Commander corrects research/VERIFICATION.md; use ST3025 to size the 12 V uncertainty | commander now; engine later |
| 18 | Bus power unchecked (one adapter, unverified rating) | minor | **Accept.** Peak current per branch, minimum voltage at the farthest servo, fuse sizing | concept engine (trade study) |
| 19 | No BOM cost per candidate yet | minor | **Accept.** Cost with low/high bands; the decision requires a pass at the high price | concept engine |
| 20 | Shell method feeds mass and in-shell ambient; LIPM chosen over trajopt without comparison | minor | **Accept.** Bake-off (running) supplies shell mass and wall numbers; record LIPM vs trajopt in docs/concept-engine.md; bake-off must conclude before D2 | bake-off agent; engine docs |

**Decision rule adopted (row "Before/at the decision"):** the winner must be unchanged across the tornado bounds and pass at the benchmark mass. If the ranking flips on torque-speed, armature or Rth, the unknown must be measured with a bench servo before committing.

## Maintainer questions (from the challenger)
1. **R5:** "table height" means a coffee/side table (~0.40–0.50 m) or a dining table (~0.75 m)?
2. **Bench test:** buy one STS3215-12V + one 7.4V (~$30) *before* the concept decision for a short lever test? Inside the $550, or test equipment?
3. **Get-up:** must Adam self-right after a fall?

Answers are recorded below once given.
