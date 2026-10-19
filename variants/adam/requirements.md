# Adam requirements (maintainer-set, 2026-10-19)

These are **what Adam must do**. The concept loop (ADR 0012) decides **how**: joint layout, actuators, voltage, height, mass. Changes to this file are the maintainer's call.

## Purpose
A proof of concept that is genuinely impressive and fun to walk around and interact with, **not a toy**, ahead of a multi-thousand-dollar successor (Eve).

## Must
| # | Requirement | Acceptance (verified in sim first, then on the real build) |
|---|---|---|
| R1 | **Budget LOCKED (2026-10-19): ≤ $1,600 delivered** (R1 Path 1 full ≈ $1,540 + catalog additions ≈ $25 + look levers $14, incl. tax, shipping, spares and 10% contingency; lean build ≈ $1,300). It only changes by explicit maintainer decision recorded here. History: $400 → $550 → Path 1, each moved by verified 2026 prices (servos, structure/filament, fasteners, electronics, compute, battery, charger). Excludes printer and tools. | Verified delivered BOM ≤ the confirmed Path 1 total (gate R5) |
| R2 | **Walks around**: forward, backward, turning, on flat indoor floors | Concept-loop envelopes pass; the policy walks ≥ 10 m over 5 seeds under randomization |
| R3 | **Expressive arm motion**: waving and arms raised outward | Arm reach and range cover a wave with the arm abducted outward |
| R4 | **Dances**: scripted full-body routines while staying balanced | A demo routine runs in sim within torque and thermal limits |
| R5 | **Picks up light objects from table height**: about ≤ 150 g (can, ball, small toy) | A grasp-and-lift scenario passes in sim |
| R6 | **Best achievable look at Adam's scale**: clean, sleek small humanoid (design references Tesla Optimus, electric Atlas, Apple). Evidence (packaging study, 2026-10-19) shows an Optimus-like silhouette needs ~0.9–1.2 m and a stronger actuator class, so **that bar moves to Eve** | Maintainer approval at R2a / R2 / R3 (pairwise), critic as an advisor |
| R7 | **Interactive**: head and torso can orient toward a person | Neck/waist (or equivalent) range in the concept |
| R8 | **Works anywhere, standalone**: walking, balance, behaviors, and control run on board. No PC, network, or LLM needed to function | All behaviors run on the onboard computer in the sim-HAL bring-up; a handheld controller works with no network |
| R9 | **Commandable**: handheld gamepad and/or phone, plus a documented command API (velocity, poses, motion clips) that an off-board LLM can drive later | API spec exists; the same commands drive sim and hardware |

| R10 | **Balance recovery / fall prevention**: recovers from moderate pushes and stumbles (ankle and hip strategies, capture steps) instead of falling | Concept push-recovery stress cases pass actuator limits including delay; P5 policy recovers from defined push impulses in sim under randomization |

## Should
- **Attainable parts only** (maintainer, 2026-10-19): no custom-machined or cut metal parts unless absolutely necessary; off-the-shelf parts purchasable online are fine. Adam is the pilot, so guard against scope creep into Eve.
- Self-righting: getting back up after a face-plant is **not required yet** (maintainer, 2026-10-19). Design so a sit-to-stand / kneel-to-stand is feasible; full get-up-from-prone is a later goal.
- Height: as tall as the budget and the physics allow (the previous plan was ~0.5 m).
- Run time ≥ 15 min of mixed activity per charge (to be confirmed by the power trade study).
- Reuse proven, license-compatible open-source designs and code (Open Duck Mini, ToddlerBot, SO-100…) instead of reinventing them. Credit and licenses are tracked.

## Won't (this version)
- Picking objects up off the floor (reported by analysis if it happens to be feasible).
- An onboard LLM. The LLM/MCP plugin comes later and runs off-board.
- Running (stretch only).

## Supersedes
Budget and capability parts of ADR 0006 ($400, walking-first with 2-DOF arms).
