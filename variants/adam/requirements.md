# Adam requirements (maintainer-set, 2026-10-19)

These are **what Adam must do**. The concept loop (ADR 0012) decides **how**: joint layout, actuators, voltage, height, mass. Changes to this file are the maintainer's call.

## Purpose
A proof of concept that is genuinely impressive and fun to walk around and interact with, **not a toy**, ahead of a multi-thousand-dollar successor (Eve).

## Must
| # | Requirement | Acceptance (verified in sim first, then on the real build) |
|---|---|---|
| R1 | **Budget ≤ $550 all-in** (servos, structure/filament, fasteners, electronics, compute, battery, charger). Excludes printer and tools. | Verified BOM ≤ $550 (gate R5) |
| R2 | **Walks around**: forward, backward, turning, on flat indoor floors | Concept-loop envelopes pass; the policy walks ≥ 10 m over 5 seeds under randomization |
| R3 | **Expressive arm motion**: waving and arms raised outward | Arm reach and range cover a wave with the arm abducted outward |
| R4 | **Dances**: scripted full-body routines while staying balanced | A demo routine runs in sim within torque and thermal limits |
| R5 | **Picks up light objects from table height**: about ≤ 150 g (can, ball, small toy) | A grasp-and-lift scenario passes in sim |
| R6 | **Does not read as a toy**, in stills and in motion. Design references: Tesla Optimus, electric Atlas, Apple | Maintainer approval at R2a / R2 / R3, plus the design-critic rubric |
| R7 | **Interactive**: head and torso can orient toward a person | Neck/waist (or equivalent) range in the concept |

| R8 | **Works anywhere, standalone**: walking, balance, behaviors, and control run on board. No PC, network, or LLM needed to function | All behaviors run on the onboard computer in the sim-HAL bring-up; a handheld controller works with no network |
| R9 | **Commandable**: handheld gamepad and/or phone, plus a documented command API (velocity, poses, motion clips) that an off-board LLM can drive later | API spec exists; the same commands drive sim and hardware |

## Should
- Height: as tall as the budget and the physics allow (the previous plan was ~0.5 m).
- Run time ≥ 15 min of mixed activity per charge (to be confirmed by the power trade study).
- Reuse proven, license-compatible open-source designs and code (Open Duck Mini, ToddlerBot, SO-100…) instead of reinventing them. Credit and licenses are tracked.

## Won't (this version)
- Picking objects up off the floor (reported by analysis if it happens to be feasible).
- An onboard LLM. The LLM/MCP plugin comes later and runs off-board.
- Running (stretch only).

## Supersedes
Budget and capability parts of ADR 0006 ($400, walking-first with 2-DOF arms).
