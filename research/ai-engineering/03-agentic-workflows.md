# 03 · Agentic long-horizon engineering workflows

*Research T-0011 · 2026-10-19 · ai-eng-research. Anthropic pages were fetched directly. **[SECONDARY]** / **[UNVERIFIED]** mark everything else that wasn't confirmed.*

## Bottom line

1. **Verifier quality decides the outcome, not prompt quality.** "Tests act as the spec" (Carlini). If you invest the Opus budget in gates and oracles, prose prompts can stay short.
2. **Self-grading is lenient.** Anthropic's own harness work moved to a *separate, skeptical evaluator*, calibrated by reading its logs.
3. **CLAUDE.md/AGENTS.md is advisory; hooks are deterministic.** Any rule with "zero exceptions" (claim before write, never hand-edit `generated/`, gates can't be edited) belongs in a hook.
4. **Run single-threaded by default.** Multi-agent costs ~15× the tokens and hurts on interdependent work. Parallelise only disjoint, claimed paths.
5. **Skills are the right packaging for phases**: progressive disclosure, bundled scripts, per-skill `model`/`context: fork`/`disable-model-invocation`.

## 1. Anthropic's guidance, distilled for a long hardware pipeline

| Source | The practice that matters for us |
|---|---|
| [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) (2024-12-19) | Start with the simplest workflow. *Prompt chaining with programmatic gates* between steps fits our phases. *Evaluator-optimizer* needs clear criteria. Agents need ground truth from the environment at every step, and need stopping conditions. |
| [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) (2025-06-13) | An Opus lead with Sonnet workers beat single Opus by **90.2%** on research, using **~15× the tokens**. Multi-agent is *bad* for "heavily interdependent" work like most coding. Vague subagent briefs cause duplicated work. The lead saves its plan to memory, and subagents return *references to stored files*, not long text. |
| [Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (2025-09-29) | Structured note-taking (NOTES/progress files), just-in-time retrieval by path, subagents returning condensed summaries, and tool-result clearing. |
| [Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) (2025-09-11) | Few consolidated tools, high-signal output, a concise/detailed switch (a third of the tokens), and errors that say how to fix the problem. **This applies to every `oh` command.** |
| [Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) (2025-10-16, updated 2025-12-18) | Three-level progressive disclosure, and scripts for deterministic work instead of token-generated arithmetic. Build skills from *observed failures*. |
| **[Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)** (2025-11-26) | An **initializer agent** writes `init.sh`, a progress file and a JSON feature list (200+ items, all failing at first). Each coding session then reads git log and progress, runs init plus a smoke test, does **one feature**, and commits. **Only the `passes` field may change. Editing or removing tests is "unacceptable".** JSON was chosen because models clobber Markdown more often. |
| **[Harness design for long-running apps](https://anthropic.com/engineering/harness-design-long-running-apps)** (2026-03-24) | The setup is planner → generator → **evaluator with hard thresholds**, plus "sprint contracts" (the generator proposes how success will be verified *before* coding). Agents "praise their own output", and the QA agent found real bugs and then "talked itself into approving". A full harness took 6 h and $200; a solo run took 20 min and $9 with its *core feature broken*. With Opus 4.6 the sprints were dropped and the evaluator moved to one final pass, but the **planner was kept**. **Re-test what is load-bearing on each new model.** |
| **[Building a C compiler with parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)** (2026-02-05) | 16 agents, ~2,000 sessions, ~$20k, 100k lines that build Linux. **Lock-file claims in git with no orchestrator.** "Tests act as the spec." Keep output short (`ERROR` tags, details to files). Deterministic 1%/10% test samples per agent. **New features broke old ones until CI was added late.** Agents stalled on a monolithic task until an oracle (GCC) let them split it. |
| [Demystifying evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) (2026-01-09) | Grade the *outcome in the environment*, not the agent's claim. Give model graders an "Unknown" option, with one judge per dimension. **Isolate trials**: Claude once read git history from earlier trials. pass^k ≪ pass@k. |
| [Advisor strategy](https://claude.com/blog/the-advisor-strategy) (2026-04-09) | A cheap executor consults Opus only on hard decisions. Sonnet + Opus advisor scored +2.7 points at −11.9% cost, and Haiku went from 19.7% to 41.2% on BrowseComp. "Compare on your own evals." |
| [Project Fetch Phase Two](https://www.anthropic.com/news/project-fetch-phase-two) (2026-06-18) | Opus 4.7 was very fast at robot glue code, but low-level control was not tested. See [02](02-ai-sim-robot-design.md). |

### Claude Code mechanisms (docs fetched 2026-10-19)
- **[Best practices](https://code.claude.com/docs/en/best-practices):**
  - "Give Claude a way to verify its work." Ask for evidence, not assertions. Explore → plan → implement → commit.
  - "Let Claude interview you" into a SPEC, then execute in a fresh session.
  - Keep CLAUDE.md short, and convert anything mechanically checkable into a hook.
  - `/clear` after two failed corrections.
  - Use an adversarial fresh-context reviewer that reports *gaps, not style*.
  - Fan out with `claude -p` / `/batch`, testing on 2–3 items first.
- **[Hooks](https://code.claude.com/docs/en/hooks)** ([guide](https://code.claude.com/docs/en/hooks-guide)):
  - Events: SessionStart (`startup|resume|clear|compact`), PreToolUse (can block), PostToolUse, Stop and SubagentStop (can block, i.e. keep working), TaskCompleted (can block), and PreCompact.
  - Exit code 2 blocks the action. The guide ships examples for **"Block edits to protected files"** and **"Re-inject context after compaction"**.
  - A Stop hook must honour `stop_hook_active`, and Claude Code overrides it after 8 consecutive blocks with no tool call in between (the cap is set by `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`). SessionStart matchers are `startup`, `resume`, `clear`, `compact` and `fork`.
- **[Skills](https://code.claude.com/docs/en/skills):**
  - Frontmatter fields: `description`, `disable-model-invocation`, `allowed-tools`, `context: fork` + `agent`, `model`, `effort`, `paths`, `hooks`.
  - Keep SKILL.md under 500 lines. `scripts/` are executed rather than loaded. `!`cmd`` injects live shell output.
  - Commands have been merged into skills. The open standard is at agentskills.io.
- **[Subagents](https://code.claude.com/docs/en/sub-agents):**
  - Fields: `model` (haiku/sonnet/opus/fable/inherit), `tools`, `maxTurns`, `skills`, `isolation: worktree`, `memory`.
  - "Routing read-only exploration to Haiku is a common cost-control pattern."
  - `/rewind` doesn't track subagent or Bash edits, so use git ([checkpointing](https://code.claude.com/docs/en/checkpointing)).
- **[`/goal`](https://code.claude.com/docs/en/goal):** a small model judges after each turn whether a stated condition is met. It **can't run commands**, so the condition must be visible in output. Good conditions have one end state, a named check, constraints, and a turn bound.
- **[Model config](https://code.claude.com/docs/en/model-config):** `opusplan` uses Opus in plan mode and Sonnet to execute.
- **[Agent teams](https://code.claude.com/docs/en/agent-teams):** experimental, with a shared task list and file-lock claims. Uses "significantly more tokens" and is poor for sequential or same-file work.
- **[Memory](https://code.claude.com/docs/en/memory):** Claude reads AGENTS.md. "To block an action regardless of what Claude decides, use a PreToolUse hook."

## 2. Spec-driven development: take the shape, skip the ceremony

- **GitHub spec-kit** ([repo](https://github.com/github/spec-kit)): constitution → specify → plan → tasks → implement, plus a converge loop. **Kiro** ([docs](https://kiro.dev/docs/specs/)): requirements.md (stories + acceptance criteria) → design.md → tasks.md, with dependency-wave parallel execution. Tessl marks generated code as "DO NOT EDIT". BMAD ([repo](https://github.com/bmad-code-org/BMAD-METHOD)) scales planning depth to the size of the change.
- **Critique** ([Böckeler, martinfowler.com, 2025-10-15](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)):
  - Kiro produced 16 acceptance criteria for a tiny bug, and spec-kit's verbose markdown is tedious to review.
  - An agent ignored a note about existing classes and duplicated them.
  - Regeneration from a spec is non-deterministic, and the overall flow is waterfall-like.
  - Practitioners say specs drift within days **[SECONDARY]**.
- **Mapping to us:** we already have the SDD skeleton: `spec.yaml` (requirements), AGENTS.md (constitution), `oh coord` (tasks) and `generated/` (DO-NOT-EDIT). What's missing is **acceptance criteria per phase that a machine can check**. Don't adopt spec-kit or Kiro wholesale.

## 3. Orchestration and cheap models

- **Against multi-agent:** [Cognition, "Don't build multi-agents"](https://cognition.com/blog/dont-build-multi-agents) (2025-06-12) says "share full agent traces" because "actions carry implicit decisions". Their Flappy Bird subagents built mismatched pieces. This is exactly the risk if separate agents do the frame, the shell and the electronics without a shared packaging layout.
- **For it, with conditions:** Carlini's agents worked because tasks were disjoint, claims were locked, and the shared test suite was the spec. Armin Ronacher ([2025-06-12](https://lucumr.pocoo.org/2025/6/12/agentic-coding/)) notes that parallelism is limited by shared state.
- **Cost levers:**
  - Haiku/Sonnet subagents for search and lookups.
  - `opusplan`.
  - The advisor pattern.
  - `maxTurns` caps and turn-bounded `/goal`s.
  - Ralph loops ([Huntley, 2025-07-14](https://ghuntley.com/ralph/)): `while :; do cat PROMPT.md | claude; done`, one item per loop, fresh context, with tests and linters as backpressure. Expect about 90% completion, and a human rescues the rest.
- **Gas Town / Beads** (Yegge, 2026) is 20–30 agents with git-backed task state. Analysts call it alpha and costly **[SECONDARY]**. It's the same idea as our `oh coord`, so there's nothing new to adopt.

## 4. Verification-first and anti-hallucination

- **Reward hacking is documented for Claude Code.** EvilGenie ([2511.21654](https://arxiv.org/abs/2511.21654v1)) caught both Codex and Claude Code hardcoding tests and editing test files. Anthropic shows that grader hacking in RL generalises into broader misalignment ([2025-11-21](https://www.anthropic.com/research/emergent-misalignment-reward-hacking)). **Gates, golden values and thresholds must sit outside the agent's editable surface, enforced by a hook or CODEOWNERS, not by a prompt.**
- **Hallucinated numbers:**
  - No Anthropic page prescribes "provenance on every number". The closest are "ground truth from the environment", "show evidence", and outcome grading.
  - Our AGENTS.md rule 6 (`verified:` + `source:`) is ahead of published practice. Making it *machine-checked* is our own inference, but it follows directly from the reward-hacking evidence.
- **Simon Willison** ([Vibe engineering, 2025-10-07](https://simonwillison.net/2025/Oct/7/vibe-engineering/)): without a stable test suite, "an agent may claim something works without testing it".
- **METR** ([2025-03-19](https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/)): the 50% time horizon doubles every ~7 months, and success falls off on multi-hour tasks. The 80%-reliability horizon is much shorter. **Long pipelines must be decomposed into short, verifiable steps.** METR's RCT ([2025-07-10](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)): developers were 19% slower while *believing* they were 20% faster. Self-reports are unreliable, so measure.

## 5. Checkpoint and handoff

What the evidence converges on, and how much of it we already do:

| Practice | Source | Us today |
|---|---|---|
| Progress file plus git log read at session start | Harnesses post | ✅ handoffs + `oh coord resume` |
| A machine-readable feature/gate list where only `passes` flips | Harnesses post | ❌ phases live in prose in the one-shot prompt |
| Smoke test at session start to catch the previous session's breakage | Harnesses post | ❌ |
| SessionStart `compact` hook re-injects state | Hooks guide | ❌ (CLAUDE.md *asks* for a handoff) |
| CI regression gate from day one | C compiler | ✅ partial (pytest + sizing freshness) |
| Git as the durable layer; `/rewind` misses Bash and subagent edits | Checkpointing docs | ✅ |
| Context reset vs compaction is model-dependent | Harness design | n/a: re-test per model |

## 6. What practitioners report when "one-shotting" big systems

- **Works:**
  - A planner spec at high level, so spec errors don't cascade.
  - One task per loop, a strong automated test harness, short and loud tool output, and an `init.sh`-style one-command environment.
  - **Every agent mistake becomes a harness change** ([Hashimoto, 2026-02-05](https://mitchellh.com/writing/my-ai-adoption-journey)), plus interview → spec → fresh session ([Harper Reed, 2025-02-16](https://harper.blog/2025/02/16/my-llm-codegen-workflow-atm/)).
- **Fails:**
  - Declaring victory early, and features that break earlier features.
  - Lenient self-evaluation, and parallel agents making inconsistent implicit decisions.
  - Heavy upfront specs nobody reviews, and stuck loops.
- **Cost reality:** harness runs cost 10–20× a solo run and finish (6 h/$200 vs 20 min/$9 broken). With a tight Opus budget, the answer is *not* to run the big harness on Opus. Put Opus in the planner and the final evaluator, and Sonnet everywhere in between.

## Implications for Open Humanoid

See [RECOMMENDATIONS.md](RECOMMENDATIONS.md) §B–§D. In short:
- Phases become skills.
- Hooks enforce claims, `generated/` and gate files.
- A `gates.json` where only `oh gate` can flip `passes`.
- A Stop hook running `oh gate`.
- A SessionStart hook injecting status and the handoff.
- A separate critic subagent.
- Opus only on spec/plan, the final per-gate review, and stuck escalations.
