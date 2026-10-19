# 0012: Engineering before CAD: a concept loop with measured actuators, envelopes, and power architecture

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** toolkit (method) + variant:adam · **Deciders:** maintainer, commander
- **Evidence:** research/SUMMARY.md, research/methods/*, research/ai-engineering/02-ai-sim-robot-design.md, RECOMMENDATIONS.md §B3–B6, F
- **Supersedes:** the quick sizing tool (`oh size`) as the mechanical go/no-go. It stays as a first estimate.

## Context
The quick sizing tool uses guessed constants (continuous torque 40% of stall; research says about 33%). Its mass estimate is below every comparable robot (2.3 kg vs about 3.8 kg benchmark at 0.5 m), and it has no thermal model. Zero-shot sim-to-real walking in comparable projects depended on identified actuator models.

## Decision
1. **Concept loop before detailed CAD.** Kinematics + hard-point packaging + silhouette + envelopes, iterated until all pass:
   - actuator model from measured data
   - reference motions from torque-limited trajectory optimization (walk, turn, squat, get-up, arm motions)
   - per-joint peak, RMS, and thermal envelopes
   - Monte Carlo over mass, friction, backlash, latency, and battery sag (p95 gates)
2. **The power architecture is a trade study, not an assumption.** Compare servo voltage variant vs pack (e.g. STS3215 7.4 V on 2S vs 12 V on 3S, or a stronger servo only at the knees) on torque, speed, heat, runtime, pack mass, peak current, regulator needs, cost, and how good the available actuator model is.
3. **Measurement with Adam's own parts, no prototype robot.** When the servos are bought, identify ONE of Adam's servos (bus adapter from the BOM plus a printed lever arm) at the chosen voltage. Print a 20-minute fit gauge from the same CAD code. Until then, sim uses the published 7.4 V model with widened uncertainty.
4. Any tuned constant must cite a probe or measurement (the DrEureka lesson: guessed randomization ranges cause hardware faults).

## Consequences
- (+) Motors, voltage, battery, and proportions are decided by computation before geometry.
- (−) The trajectory-optimization tooling must work on Windows (feasibility check pending in T-0011 verification).
