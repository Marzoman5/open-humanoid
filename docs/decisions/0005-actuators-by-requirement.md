# 0005: Actuators are selected from requirements, never hard-coded

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** toolkit

## Decision
`oh size` derives per-joint torque and speed requirements from geometry, mass, and requested gaits (quasi-static single-support worst case × gait dynamic factor × safety factor, plus a speed check on a linear torque-speed curve). It then picks the cheapest catalog actuator that meets them, within the spec's constraints (voltage, feedback, uniform-model preference). A variant may pin parts with `actuation.overrides`. With `body.height_m.mode: maximize`, the tool sweeps height to find the largest feasible robot under budget. Optional joints are added by priority while budget allows.

## Consequences
- (+) A $10k spec automatically lands on BLDC actuators. A $400 spec lands on hobby bus servos.
- (−) The model is first-order. It must be validated against sim torques (P5) and hardware (P8), and its constants live in the spec's `analysis:` block so they can be tuned with evidence.
