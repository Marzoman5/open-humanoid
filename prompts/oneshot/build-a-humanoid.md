<!-- prompt: oneshot/build-a-humanoid · version: 0.1 · tested-on: adam@0.1.0 (P0–P2) · tier: top -->
# One-shot: build a humanoid with Open Humanoid

> **How to use:** paste everything below the line into an agent session opened at the repo root. Fill the three blanks first.

---

You are building a humanoid robot with the Open Humanoid toolkit in this repository.

- **Variant:** `____` (an existing folder in `variants/`, or a new id to create)
- **What I want:** ____ (height or "as tall as the budget allows", budget, what it must do, look, CAD tool, brain or no brain)
- **Orchestration profile:** `____` (solo | pair | team | swarm; see `coordination/profiles/`). Default: solo.

## Ground rules
1. Read `AGENTS.md` now. Follow its seven rules for the whole session. Don't read the whole repo. Read only what each phase needs.
2. Run `oh coord status`. If a task for this variant/phase is already claimed by someone else, don't touch its paths. Pick other work or stop and tell me.
3. Before each phase, create or claim a task for it (`oh coord new … --phase Pn` / `oh coord claim`). Commit the claim.
4. Each phase ends with its **gate**. If the gate fails, fix the cause or report honestly. Never fudge spec constants to force a pass without telling me why the new value is justified.
5. After each gate: commit, update the task log, and write a handoff (`oh coord handoff`). That's your checkpoint. If your context is getting long, follow the profile's `on_context_full` rule right after a checkpoint.
6. Ask me only for things that are genuinely mine to decide (taste, money, safety). Otherwise use the spec defaults and record the choice in a decision record.

## Phases

| Phase | Do | Gate (must pass) | Parallel? |
|---|---|---|---|
| **P0 Intake** | Create the variant (`oh new <id> [--extends adam]`) or open it. Translate my wishes into `spec.yaml`: priorities, budget (what it includes), height mode, joints with priorities, gaits, actuation constraints (voltage, feedback), BOM fixed parts, CAD backend, plugins. | `oh validate <id>` | no |
| **P1 Sizing** | `oh size <id>`, then `oh bom <id>`. Read `generated/sizing.md`. If infeasible, explain the cheapest fix (drop a joint, change voltage, raise budget, add a catalog part) and ask me before changing goals. Missing parts mean catalog tasks for the sourcing stream. | feasible, and the walk gait is ok | no |
| **P2 Kinematic sim** | `oh sim build <id>`, then `oh sim test <id>`. Compare holding torques to sizing. | sim test PASS | after P1 |
| **P3 Mechanical** | Design modules/frames in the chosen backend from spec + `generated/sizing.json`. Follow the design language (frame + shell). Respect the printer bed, interface class, and module validity ranges. Export per `cad/EXPORT_CONTRACT.md`. Update `mass_model` from the real masses and re-run P1. | exports complete; re-sized still feasible | per module, yes |
| **P4 CAD sim** | Build the sim from the CAD exports and re-run the smoke test. | sim test PASS with CAD model | after P3 |
| **P5 Locomotion** | Train walking in sim (domain randomization on mass, friction, latency, backlash). Then running if `run` is a goal and sizing says it's feasible. | policy walks ≥ 10 m over 5 seeds | parallel with P6 |
| **P6 Electronics + software** | Wiring/power plan, servo IDs, software core + HAL, sim/real switch. | bring-up scripts run in sim HAL | parallel with P5 |
| **P7 Sourcing + guide** | Run `prompts/sourcing/part-sourcing.md` on the BOM. Write `build-guide/` with print list, assembly steps, calibration. | BOM verified ≤ budget cap | yes |
| **P8 Build & test** | Human builds. Agent supports calibration, sim-to-real tuning, and test logging. | robot stands and walks | — |
| **P9 Plugins** | LLM/MCP, manipulation, mapping, attachments, as listed in `software.plugins`. | per plugin | yes |

Some tools for P3–P9 are still `planned` (see `docs/vision.md` roadmap). When you reach one, **build the tool generically in the framework first** (variant-agnostic, tested, documented in `docs/tools.md`), then use it. That's how the toolkit grows. Don't write one-off scripts inside the variant.

## Parallelism by profile
- **solo:** run phases in order in this session. Use subagents only for cheap read-only searches.
- **pair / team:** after P2, split P3 by module and run P5/P6/P7 in their own sessions, one per workstream (`coordination/workstreams.yaml`). Each session gets a task ID and `prompts/session/resume.md`.
- **swarm:** act as orchestrator. Turn every phase into small tasks with `paths` and `depends_on`. Assign them, review them, and merge them. Don't implement yourself.

## When you stop (finished, blocked, or out of context)
Leave the repo resumable: everything committed, task statuses true, and a handoff written. Then tell me in 3–5 lines what works, what doesn't, and the exact resume command.
