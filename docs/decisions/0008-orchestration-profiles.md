# 0008: Work is checkpointed; parallelism is chosen by orchestration profile

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** toolkit

## Context
Users range from "one Opus session per month" to "1000-agent swarms". Context windows fill. Parallel agents overwrite each other.

## Decision
1. All work is expressed as tasks (`coordination/tasks/`) with declared `paths`. Claims are checked for path overlap.
2. Every phase gate writes a checkpoint (task status + handoff), so any session can die and a fresh one can resume from the repo alone.
3. `coordination/profiles/*.yaml` (solo, pair, team, swarm) set max parallel sessions, model tiers per workstream, and what to do when context fills (prompt the user, start a new session, or hand off to an orchestrator). The user picks a profile. Agents obey it.

## Consequences
- (+) The same one-shot prompt scales from a hobbyist budget to a swarm.
- (−) Agents spend a few tokens on bookkeeping. That's worth it.
