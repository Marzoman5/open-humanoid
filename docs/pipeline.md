# The Open Humanoid pipeline (v0.2)

How a robot goes from "what I want" to "it works the first time it's assembled". Decided in ADRs 0009–0012. Evidence is in `research/` (verified in `research/VERIFICATION.md` and `research/ai-engineering/VERIFICATION.md`).

**"First try" means the physical build works the first time.** It doesn't mean an agent gets everything right in one pass. Getting there takes many gated, checkpointed sessions. That's the product.

## Principles

1. **Tools measure, agents engineer, humans judge.** Code computes every number. Agents propose and iterate against acceptance criteria. The maintainer decides taste, money, and risk at review stops.
2. **Decide expensive things early and cheaply.** Envelopes, packaging, and silhouette come before detailed CAD. Interfaces come before part geometry.
3. **Gates the agent can't edit.** A phase is done only when `oh gate` has written a PASS record at HEAD. Thresholds are hook-protected (ADR 0011).
4. **Separate critics.** No agent grades its own look or its own work at a stop.
5. **Measured beats guessed.** Every tuned constant cites a source or a measurement (provenance check).
6. **Reuse proven, licensed work.** Every reuse is recorded in `THIRD_PARTY.md` after the actual LICENSE file has been re-read.

## Self-correction: challenger and lessons

- **Challenger** (`.claude/agents/challenger.md`, Opus, read-only). It runs at **every wave boundary, before every review stop, and before any decision that's expensive to undo** (purchasing, freezing interfaces, starting detailed CAD). It answers five fixed questions:
  - Is this the right problem?
  - What's assumed and what's known?
  - Is there a better or simpler method?
  - What are the physical failure modes?
  - Was the research applied?

  Its report goes to `variants/<id>/reviews/challenge-<n>-<subject>.md`. The commander **answers every row in writing** (accept + action, or reject + reason) before proceeding. Nobody grades their own plan, including the commander.
- **Advisor and escalation** (research E2, verified: +2.7 points at −11.9% cost). Executors (Sonnet) consult an Opus advisor on hard calls. After **two failed attempts** to pass the same gate or fix the same defect, an executor stops, writes what it tried, and escalates to Opus or the commander instead of trying a third variation.
- **Fresh context per unit of work** (research D7, E3). Intake and planning happen in one session. Execution runs in fresh agents or sessions, each with one task and the repo as its only memory (task file, handoff, gates). Long sessions accumulate wrong assumptions.
- **Lessons ledger** (`coordination/LESSONS.md`). Every caught mistake gets a row and is enforced somewhere real (hook, gate, test, skill, or prompt). The challenger reads it, so mistakes don't repeat.

## Phases

| Phase | What happens | Gate (machine) | Review stop (human) |
|---|---|---|---|
| **P0 Intake** | Interview the maintainer and write `requirements.md` + `spec.yaml`. Execution then starts in a **fresh session**. | G-validate | — |
| **P1 Research & reuse** | Evidence base (actuators, comparable robots, methods), reuse audit, verification pass. Done for Adam. | research verified | — |
| **P2 Concept loop** | Kinematic tree, hard points, measured actuator models (BAM), and the motion library (walk, turn, wave, dance, table pickup). Torque-limited trajectory optimization (casadi). Peak, RMS, and thermal envelopes. Monte Carlo (p95). Power and voltage trade study. Joint layout and actuator choice. First silhouette sheet (D1). Iterate until everything passes. | G-envelopes, G-silhouette | **R1 Concept** (layout, actuators, voltage, height, mass, cost) · **R2a Silhouette** |
| **P3 Detailed design** | `interfaces.yaml` first. Frame inside-out, shells outside-in from `profiles.yaml` (D2–D6). CAD helper library. Geometry gate after each part. Design-critic loop (≤ 3 rounds). Analytic checks plus FEA on the 3–4 highest-stress parts. | G-geometry | **R2 Concept look (3D)** · **R3 Final design** (renders, print layout, mass, cost) |
| **P4 Virtual test suite** | Sim built from the CAD exports. Range of motion, interference, fall impacts, 10-minute thermal walk, pushes, the pickup scenario, the dance routine. | G-cad-sim | — |
| **P5 Behaviours** | RL walking with domain randomization sized to P2 uncertainty (GPU path decided then). Wave, dance, and pickup motions. | policy metrics | **R4 Motion** (sim video and metrics) |
| **P6 Electronics & software** | Generated wiring and power budget. HAL (LeRobot STS3215 driver). `oh doctor` bring-up. On-robot self-identification routine. | bring-up in sim HAL | — |
| **P7 Sourcing & build guide** | Verified regional BOM. Build guide in build order. 20-minute fit gauge. One-servo identification on Adam's own part. | BOM verified ≤ cap | **R5 Buy** |
| **P8 Build & bring-up** | Assembly, calibration, self-ID, policy fine-tune, first walk. | doctor PASS | robot walks |
| **P9 Plugins** | LLM/MCP, mapping, attachments… | per plugin | per plugin |

## Who does what (models)

| Work | Model | Why |
|---|---|---|
| P0 interview, P2 concept decisions, R-stop syntheses, final design critic (R3) | Opus | Errors compound upstream. Judgment-heavy. |
| Tool building, CAD authoring with helpers, sim and gate runs, routine critic rounds, docs | Sonnet | Well-specified, verifiable work |
| Search, lookups, link checks, formatting | Haiku / Sonnet subagents | Cheap fan-out |

Default orchestration is **solo**. Parallel sessions run only on disjoint claimed paths in separate worktrees. Design work on the same segment is never split before `interfaces.yaml` and `profiles.yaml` are frozen.

## Status for Adam (2026-10-19)

- **P0:** done ($550 requirements).
- **P1:** done (research merged).
- **Wave 1 tooling in progress:** T-0015 harness, T-0016 design tooling.
- **P2:** next.
- **P3 CAD (T-0004):** blocked until P2 passes.
