# 0011: Enforce the rules with hooks and machine-checked gates

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** toolkit · **Deciders:** maintainer, commander
- **Evidence:** research/ai-engineering/03-agentic-workflows.md, RECOMMENDATIONS.md §B1–B2, B7, D3–D4

## Context
AGENTS.md rules are advisory, and agents can and do violate them under pressure, including editing tests to pass them. Gates that agents run and report on themselves aren't evidence.

## Decision
1. `pipeline/gates.yaml` defines every gate: command, thresholds, evidence path, phase. Only `oh gate <id>` writes pass/fail records (`variants/<id>/generated/gates/*.json`, with git SHA). **A phase is done only when a PASS record exists at HEAD.** CI re-runs passed gates.
2. Claude Code hooks (committed, cross-platform Python under `tools/hooks/`) enforce the rules:
   - block writes to `generated/`, gate thresholds, schemas, and contracts, and block writes outside the agent's claimed paths (including Bash redirects)
   - SessionStart (startup/resume/compact) re-injects the coordination status, active task, and last handoff, and runs a smoke gate
   - Stop blocks "done" without a passing gate
   - PreCompact writes a handoff stub
3. **Provenance:** every catalog number and every tuned spec constant cites a source or measurement file, checked by `oh check provenance` in CI.
4. AGENTS.md keeps only the rules that aren't enforced by hooks. Lessons from caught mistakes go into the relevant skill or hook.

## Consequences
- (+) Gates become artifacts a reviewer can trust. Rule drift gets caught mechanically.
- (−) Hooks must stay fast and must not block legitimate work. Escape hatch: a human edits with an ADR.
