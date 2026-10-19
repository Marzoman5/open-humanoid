# The harness: gates, provenance and hooks

Implements [ADR 0011](decisions/0011-enforcement-hooks-gates.md) (and [0013](decisions/0013-provenance.md)). The research behind it (`research/ai-engineering/`) found that prose rules don't constrain agents, and that agents have edited tests to make them pass. Hooks and machine-checked gates do constrain them. So the rules that matter are enforced by code, and AGENTS.md only keeps the ones that aren't.

Design rules for everything below: **fail open** (a broken hook never locks anyone out), **fast** (hooks finish in about 0.15 s; only the session-start smoke run takes longer), **a human is never locked out** (ask, don't deny, plus a kill switch).

## Gates: `oh gate`

`pipeline/gates.yaml` defines every gate: its phase, thresholds, and whether it is implemented. **Only `oh gate` writes `variants/<id>/generated/gates/<gate>.json`**: pass/fail, metrics, the git SHA, a `dirty` flag and a timestamp.

```bash
oh gate                         # list all gates
oh gate G-validate adam         # run one gate and write its record (variant defaults to gates.yaml default_variant)
oh gate --smoke adam            # validate + size + short stand test, about a second, writes NO record
oh gate --status adam           # latest record per gate and whether it is at HEAD
```

| Gate | Status | Checks |
|---|---|---|
| `G-validate` | implemented | spec schema + catalog schema |
| `G-size` | implemented | `oh size` feasible, cost ≤ cap, walk-gait margin |
| `G-sim-stand` | implemented | MuJoCo stand test: no fall, tilt, actuator stall fraction |
| `G-tests` | implemented | the pytest suite |
| `G-provenance` | implemented | `oh check provenance` against its thresholds |
| `G-envelopes`, `G-silhouette-R2a`, `G-geometry`, `G-cad-sim` | **placeholder** | declared (thresholds recorded for G-envelopes: p95 Monte Carlo peak ≤ 70 % of measured stall, RMS ≤ continuous, 10-minute thermal walk). `oh gate` refuses to run them (exit 3) and writes nothing, so they can never show PASS |

**A phase is done only when its gates have a PASS record at HEAD.** A record counts as *current* when its SHA is `HEAD`, or when every file changed since is another gate record or `coordination/` bookkeeping (so committing the record doesn't invalidate it). A record written on a dirty tree (`generated/` and `coordination/` don't count as dirt) is kept but never counts. The `--status` states are `PASS` · `STALE` (code changed since) · `DIRTY` · `FAIL` · `NONE` · `PLACEHOLDER`.

Workflow: commit your work, then `oh gate <id>` on the clean tree, then commit the record. A crashing check is recorded as FAIL, never as a pass. Thresholds live only in `gates.yaml` and are hook-protected; CI should re-run every gate that has a record (a regression gate; the CI itself is T-0010).

Records are evidence, not proof: nothing cryptographically stops someone writing the JSON by hand, but the Bash hook blocks writes into `generated/`, the record carries a SHA a reviewer can re-run, and CI re-runs it.

## Provenance: `oh check provenance`

```bash
oh check provenance adam        # warns; exit 2 only if the G-provenance thresholds are exceeded
```

Every catalog part needs `source` + `verified`; every tuned constant under `analysis:` / `mass_model:` needs an entry in the spec's `provenance:` map (schema v0.2, [ADR 0013](decisions/0013-provenance.md)):

Illustrative shape (these paths and numbers are examples, not Adam's real sources):

```yaml
schema_version: "0.2"
provenance:
  analysis.safety_factor: path/to/a/repo/file.md#anchor
  analysis.dynamic_factor: { source: "https://arxiv.org/abs/2502.00893", note: "ToddlerBot walk torque peaks" }
  mass_model.structure_kg_at_1m: "measurement:variants/adam/cad/export/mass.json"
  mass_model.waste_factor: "estimate: 30 % print waste, unmeasured"
```

## Task ids

`oh coord new` makes ids like `T-20261019-3fa2` (creation day + 4 random hex digits), so branches that create tasks in parallel can never collide and nobody renumbers at merge. They sort by day and read fine. The old `T-0007` ids stay valid. Nothing may assume the digits are a counter.

## Hooks

Committed in `.claude/settings.json`; scripts in `tools/hooks/` (Python, stdlib at import time, re-run under the repo `.venv` if PyYAML is missing); configured by `pipeline/hooks.yaml`. Event, matcher and field names were checked against the Claude Code hooks reference on 2026-10-19; the hook commands use the exec form (`command: python`, `args: [...]`) so they don't depend on Git Bash.

| Event (matcher) | Script | What it does |
|---|---|---|
| `PreToolUse` (`Edit\|Write\|MultiEdit\|NotebookEdit\|Bash\|PowerShell`) | `pretooluse.py` | Protects paths (below). Warns when a worker writes outside its claim. For Bash it parses redirects, `tee`, `sed -i`, `rm`, `mv`, `cp`, `dd`, PowerShell `Set-Content`/`Remove-Item`… (best effort: it can't see inside `python -c`) |
| `SessionStart` (`startup\|resume\|compact\|fork`) | `session_start.py` | Prints the session id, the board, your task, its newest handoff, `git log -5`, then runs the smoke gate. Reports failures, never blocks. Exports `CLAUDE_SESSION_ID` to Bash via `CLAUDE_ENV_FILE` |
| `Stop` | `stop.py` | If your task is `in_progress` and its phase gate(s) have no PASS at HEAD, blocks **once** with the reason (honours `stop_hook_active`). Set the task to `review`/`blocked` if you are legitimately done without the gate |
| `PreCompact` | `precompact.py` | Writes a pre-filled handoff stub for your task (at most one per two minutes). Never blocks compaction |

### Who is a "worker" and who is the "commander"

Hooks only receive a session id. `oh coord claim <task> --agent <name> --session <id>` records the mapping in `coordination/.local/sessions.json` (git-ignored, per checkout; `--session` defaults to `$CLAUDE_SESSION_ID`, and the SessionStart text tells you the id). A session with an active claim is a **worker**. A session with **no registered claim**, or whose task is in a `commander_streams` stream (default `coordination`), is the **commander**: exempt from claimed-path checks and never hard-blocked on contracts.

### Protected paths (`pipeline/hooks.yaml: protected`)

| Rule | Paths | Worker | Commander / unclaimed |
|---|---|---|---|
| `generated` | `**/generated/**` | deny | deny. Re-run the `oh` command that makes it |
| `gate-config` | `pipeline/**`, `tools/hooks/**`, `.claude/settings.json` | deny, unless its task's `paths` list the file | **ask** (a human confirms) |
| `contracts` | `schemas/**`, `cad/EXPORT_CONTRACT.md`, `modules/INTERFACE.md`, `**/INTERFACE.md` | deny, unless its task's `paths` list the file (an ADR task) | **ask** |

A catch-all claim like `./` or `*` never authorises protected files. Outside the protected set, a worker writing outside its claimed `paths` gets a visible warning (`claimed_paths: warn`; set `enforce` to deny). `coordination/` is always allowed. Reverting generated output with `git checkout --` is fine; hooks only look at what a command writes.

### Where Claude Code loads these hooks from (read this before testing)

- **CLI, or a folder you opened directly:** the checkout's own `.claude/settings.json`.
- **Desktop-app worktree sessions** (the Code tab's worktree option): Claude Code reads settings and hooks from the **main checkout's root**, not the worktree, and `${CLAUDE_PROJECT_DIR}` points there ([worktrees docs](https://code.claude.com/docs/en/worktrees#what-worktrees-share-with-the-main-checkout)). So the hooks apply to worktree sessions only after `.claude/settings.json` and `tools/hooks/` are on the main branch. The hook payload's `cwd` is the worktree, and the scripts derive the repo root from it, so claims, `hooks.yaml` and `generated/` are judged against the worktree being edited.
- **Version skew is expected:** the scripts come from main while the worktree may be on an older branch. Hooks therefore keep their protection logic self-contained (`_common.session_task`, built-in default rules) and degrade when `openhumanoid.gate` or the new `coord` functions are missing.
- Verified live on 2026-10-19: a headless CLI session started in the worktree ran the `SessionStart` hook; a desktop-app worktree session on the unmerged branch ran none of them (no context block, no denials), exactly as the docs predict.

### The smoke run uses the toolkit's Python, not the hook's

The hook is started by whatever `python` is first on PATH, which can be a bare system interpreter (PyYAML at most, no jsonschema, numpy or mujoco). So SessionStart runs `oh gate --smoke` as a subprocess under the toolkit interpreter: `$OH_PYTHON`, else `<repo>/.venv`, else the `.venv` of `$CLAUDE_PROJECT_DIR` (a desktop-app worktree usually has none of its own; the main checkout does). If none can import the toolkit it prints `Smoke gate: skipped, toolkit venv not found or incomplete (run python -m venv .venv ...)` instead of a false FAIL. A genuine smoke failure still prints `FAIL`.

### Phases with no gates yet (P2)

The Stop hook only blocks on gates whose `phase` matches the task's phase (or the task's own `gates:` list). Phase **P2** currently has only placeholder gates (G-envelopes, G-silhouette-R2a), which can never PASS, so a P2 task has nothing to block on and **Stop will not stop a P2 session** until those gates are implemented. Until then P2 "done" rests on the review stops (R1, R2a) and on the task's own `gates:` list if it names implemented gates. The same applies to P3 (G-geometry) and P4 (G-cad-sim). Implementing a placeholder gate is an ADR task, because `pipeline/` is protected.

### Failure behaviour and escape hatches

- Any exception, timeout (watchdog 1.8 s; 100 s for the smoke run), unreadable config, or missing Python/PyYAML → the hook does nothing and exits 0. The error goes to `coordination/.local/hooks.log`.
- **Kill switch:** `touch coordination/.local/hooks.off` disables every hook (a human does this; the file is itself protected from agents). Or set `enabled: false` in `pipeline/hooks.yaml`, which also needs a human or an ADR task.
- Deleting `hooks.yaml` doesn't disable protection: the same rules are built in.
- Hooks load at **session start**. After changing `.claude/settings.json`, start a new session.
- Stop blocks are capped by Claude Code itself (8 in a row without a tool call).

### Known limits (be honest)

The Bash parser is a guard rail: it doesn't catch `python -c "open('generated/x','w')"`, writes through an unknown tool, or a new tool name. Task `paths` are a convention enforced as a warning by default. Gate records can be forged by someone determined; the backstop is CI re-running gates plus review. A subagent is expected to carry its parent's `session_id` (hook input also has `agent_id`), so it inherits the parent's claim; that is not tested live.

## Testing

`tests/test_harness.py` covers task ids, gate lifecycle (placeholders, stale/dirty records), provenance, `--session`/`--json`, the shell-write parser, and every hook script as a subprocess fed sample Claude Code JSON on stdin (deny, ask, warn, fail-open, kill switch, `stop_hook_active`, handoff stub, session-start context).
