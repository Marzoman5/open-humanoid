---
name: commander
description: How the Open Humanoid commander session plans, delegates, reviews and merges work across agents, including unattended runs. Use when coordinating multiple agents or sessions on this repo.
---

# Commanding Open Humanoid work

Written after the first real commander run (2026-10-19). The mistakes behind each rule are in `coordination/LESSONS.md`.

## Order of operations
research → verification → **challenger** → proposal to the maintainer → maintainer decides → execute → review → merge.
Never write "accepted" decisions, start build work, or install tools on unverified research. Anything built on provisional ground is labelled PROVISIONAL.

## Delegating
- **One task, one fresh agent, one worktree.** Pre-create the task on main before launching **and commit it immediately**, so IDs and paths are settled (an uncommitted task file once blocked a merge). Tell the agent not to run `oh coord new`.
- Brief = goal + the files to read (requirements, ADRs, research sections) + exact deliverables + the task's paths + "stay out of X (owned by Y)" + the definition of done + the final-message format. Don't include your own guesses as facts. Specify the design space and how to sweep it, **never the candidates or a fixed answer**. Challenger #1 caught the commander naming A/B/C and a height.
- Model routing: Sonnet builds and runs checks; Opus for concept decisions, design judgment, and the challenger; Haiku/Sonnet subagents for search.
- **Unattended runs:** the app forbids starting *sessions* on event-triggered turns, so use in-process background agents (Agent tool, worktree isolation). They wake the commander when done. Hold keep-awake.
- Every new tool must be consumed by an Adam deliverable in the same wave (ADR 0009).

## Reviewing (never trust a report alone)
- Re-run the tests yourself **from the branch's own worktree**. cwd selects the checkout, which once produced false failures.
- Look at the evidence: renders, verdict JSONs, gate records. Check that numbers have provenance.
- Run the challenger at wave boundaries and before review stops; answer every row in writing.
- Escalate after two failed attempts on the same problem.

## Merging
- Only with the maintainer's approval (standing approval for an unattended run must be explicit and recorded in memory).
- Merge with `--no-ff`. Resolve task-ID or file collisions by renumbering, never by dropping. Re-run the full suite and `oh gate` on a clean tree, commit the gate records, push.
- Hooks load from main's root for every desktop session, so hook changes go live at merge. Test them in a standalone clone first.

## Logging
- Append to `coordination/commander-log.md` at every milestone. Add a lessons row for every caught mistake, and say where it's enforced.
