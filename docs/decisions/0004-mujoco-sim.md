# 0004: MuJoCo is the default simulator; sim exists from P2

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** toolkit

## Context
Walking is learned in sim. We need a free, fast, cross-platform simulator that works with or without an NVIDIA GPU, with a path to massively parallel RL.

## Decision
MuJoCo (with MJX/MuJoCo-Warp for GPU-parallel training later). `oh sim build` generates an MJCF from the spec using primitives, so locomotion work can start before CAD. CAD-derived models replace it in P4 through the export contract. `sim.engine` stays a spec field, so Isaac or Genesis adapters can be added later.

## Consequences
- (+) Runs on the maintainer's Windows laptop (RTX 4060) and on Linux clusters.
- (−) Primitive models are approximate. Mass/inertia must be recalibrated after CAD.
