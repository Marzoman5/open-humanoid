<!-- prompt: oneshot/build-a-humanoid · version: 0.3 · tested-on: adam (P0–P1) · tier: top -->
# Build a humanoid: pipeline orchestrator

> **How to use:** paste everything below the line into an agent session opened at the repo root, with the blanks filled in. This prompt is deliberately thin. The method lives in `docs/pipeline.md`, the gates in `pipeline/gates.yaml`, and the phase know-how in skills (`.claude/skills/`, added as each phase is first run for real).
>
> v0.3 changes: reframed from "one-shot" to a gated, resumable pipeline (ADR 0009); the concept loop comes before CAD (ADR 0012); silhouette first plus a separate critic (ADR 0010); gates and hooks (ADR 0011). The v0.2 phase table is in git history.

---

You are running the Open Humanoid pipeline for one robot.

- **Variant:** `____` (folder in `variants/`, or a new id)
- **Start at / run until:** `____` / `____` (phases from `docs/pipeline.md`, e.g. `P2` / `P2`)
- **Review stops:** `all` (default) | `looks` | `none`
- **Profile:** `solo` (default) | `pair` | `team` | `swarm`

## How to work
1. Read `AGENTS.md` and `docs/pipeline.md`. Run `oh coord status` and `oh gate --status <variant>`. Read the newest handoff for your task. Don't read the whole repo.
2. If the variant has no `requirements.md`, run **P0**: interview the maintainer, write `requirements.md` + `spec.yaml`, get approval, checkpoint, and **stop**. Execution happens in a fresh session.
3. For each phase in range:
   1. Claim (or create) its task. Use the phase's skill if one exists. Otherwise follow `docs/pipeline.md` and record what you learn so a skill can be written afterwards.
   2. Use the toolkit's instruments for every number (`oh …`). If an instrument you need doesn't exist, build it in `openhumanoid/` with tests, scoped to this robot and parameterized only where a second consumer exists (ADR 0009).
   3. Iterate until the phase's gate passes: `oh gate <gate-id> <variant>` must write PASS at HEAD. Never edit gate thresholds, tests, or `generated/` files to make something pass. If a threshold looks wrong, stop and propose an ADR.
   4. Taste goes to the **design-critic** subagent (never your own judgment). Numbers come from code (never from looking at an image).
   5. At a review stop: write `variants/<id>/reviews/<stop>-<date>.md` (images, key numbers, decisions, ≤ 3 questions), set the task to `review`, checkpoint, and **end your turn**.
   6. Checkpoint (commit, task log, `oh coord handoff`) after every gate and every ~30 heavy tool calls.
4. Reuse before you build: check `research/reuse/REUSE.md`, and record any reuse in `THIRD_PARTY.md` after re-reading the actual LICENSE file.
5. When you stop for any reason, the repo must be resumable: everything committed, task statuses true, and a handoff written. Tell the maintainer in 3–5 lines what passed, what didn't, and the exact resume line (`prompts/session/resume.md`).
