# 0009: Gated, resumable pipeline; "first try" means the physical build; Adam-first tooling

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** toolkit · **Deciders:** maintainer, commander
- **Evidence:** research/ai-engineering/RECOMMENDATIONS.md (I1, I2), 07-challenging-our-assumptions.md
- **Amends:** 0001 (how the toolkit grows, not what it is)

## Context
No credible practitioner one-shots systems of this size in a single agent pass. Long efforts run as many gated sessions. Every reproducible open robot (LeRobot/SO-100, Open Duck Mini, ToddlerBot) started as one well-documented robot and generalized later.

## Decision
1. The product is a **gated, resumable pipeline**: phases with machine-checked gates, human review stops, and checkpoints. **"First try" means the physical build works the first time it's assembled**, not that an agent gets everything right in one pass. The one-shot prompt becomes a thin orchestrator over this pipeline.
2. **Adam-first, generalize on second use.** Keep the cheap, inherently generic layers generic now: spec schema, catalog, gates, coordination, export contract. Write other tools for Adam, parameterize only what has ≥ 2 real consumers, and prove generality with a cheap second consumer (an "Adam-XL" sizing + sim check, then Eve).
3. Default to solo orchestration. Parallelize only disjoint, claimed paths. Team/swarm profiles are for catalog, sourcing, and docs fan-out, not interdependent design.

## Consequences
- (+) Less speculative framework code. Tools are shaped by a real robot.
- (−) Some refactoring when Eve arrives. That's accepted and planned.
