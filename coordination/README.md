# Coordination protocol

How many agents (and humans) work at once without overwriting each other, and how work survives context limits.

## Objects

| Object | Where | Purpose |
|---|---|---|
| **Task** | `tasks/T-<yyyymmdd>-<4 hex>.md` (legacy `T-NNNN` stays valid) | One unit of work: goal, done-when, `paths` it may write, status, owner |
| **Claim** | `owner` + `status: claimed` in the task file | "I'm working on this". Checked against other claims for path overlap |
| **Handoff** | `handoffs/<date>-<task>-<agent>.md` | State dump so a fresh session can resume: done, next, gotchas |
| **Workstream** | `workstreams.yaml` | Lanes of work (mech, sim, software…), the paths each owns, and a suggested model tier |
| **Profile** | `profiles/*.yaml` | How much parallelism and what to do when context fills (chosen by the user) |
| **Decision** | `docs/decisions/` | Settled questions. Don't relitigate. Supersede with a new ADR |

## Task lifecycle

```
open ──claim──► claimed ──► in_progress ──► review ──► done
  ▲                │              │
  └──release───────┴──blocked─────┘
```

```bash
oh coord status [--json]                         # board: who's on what, overlapping claims (--json for hooks/scripts)
oh coord new "Leg module CAD" --stream mech --paths modules/joints/ variants/adam/cad/leg/
oh coord claim T-0004 --agent mech-1 --session <id>   # refuses if paths overlap an active claim; --session lets hooks find your paths
oh coord set T-0004 in_progress
oh coord handoff T-0004 --agent mech-1           # writes a handoff template to fill in (--auto: pre-filled stub, used by PreCompact)
oh coord done T-0004
```

### Task ids

New tasks are `T-<yyyymmdd>-<4 hex>` (e.g. `T-20261019-3fa2`): the day plus random digits, so two branches creating tasks at once never collide and nobody renumbers at merge. They sort by day. Never assume the number is a counter. Old ids (`T-0007`) remain valid.

### Hooks and gates

Claude Code hooks read `oh coord status --json` and the local session map written by `claim --session` to warn on writes outside your `paths`, remind you of your task and handoff at session start, and block "done" without a PASS gate record. See [docs/harness.md](../docs/harness.md).

## Rules

1. **Claim, then commit the claim, then work.** In a shared checkout the file change is visible at once. Across worktrees/branches, a merge conflict on the task file means someone else got there first. Back off and pick another task.
2. **Stay inside your `paths`.** If you need to touch something outside them, either add it to your task *after* checking `oh coord status` for conflicts, or open a new task for the owner of that path.
3. **Contracts are never in a task's `paths` by default** (`schemas/`, `*/INTERFACE.md`, `cad/EXPORT_CONTRACT.md`). Changing one needs an ADR task.
4. **Small tasks.** If a task won't fit in about half a context window, split it.
5. **Branch per task when parallel.** `task/T-0004-leg-cad`. Merge via PR (or a fast-forward when solo).
6. **Never delete another agent's task, handoff, or branch.**

## Session protocol (context-limit survival)

Agents can't see exactly how full their context is, so the protocol relies on **frequent checkpoints instead of last-second rescues**:

- **Checkpoint triggers:** a phase gate passes · a task changes status · roughly every 30–40 tool calls of heavy work · right after the conversation was compacted/summarized · before any risky or long operation.
- **A checkpoint is:** commit the work, update the task's `## Log`, and write or refresh the handoff.
- **When context is getting long**, the active profile's `on_context_full` decides:
  - `prompt_user`: stop at the next checkpoint and give the user a resume line (`prompts/session/resume.md`) to paste into a fresh session.
  - `new_session`: start a new session (Claude Code desktop/CLI) with the resume prompt and the task ID.
  - `orchestrator`: report to the orchestrator, which reassigns the task.
- **Resuming:** read `AGENTS.md`, run `oh coord status`, then read the newest handoff for your task. Nothing else is required.

## Choosing a profile

| Profile | For | Parallel sessions | Notes |
|---|---|---|---|
| `solo` | Small token budget (≈1–2 heavy sessions/month) | 1 | Sequential phases, subagents only for cheap searches. **Default** |
| `pair` | Moderate | 2 | Design lane + sim/software lane |
| `team` | Comfortable | up to 6 | One session per workstream |
| `swarm` | Large / org scale | many | Orchestrator + per-module agents, strict claims |

The user sets it in the one-shot prompt or in `coordination/active-profile`. Missing means `solo`.
