# VERIFICATION: re-checking the claims RECOMMENDATIONS depends on

*T-0011 · 2026-10-19 · ai-eng-research. Three Sonnet fact-checkers each opened the primary source (the arXiv HTML full text, official docs, `gh api`, or the PyPI/Anaconda JSON) and returned a verdict with the exact number or quote. I spot-checked the corrections that changed text.*

*Caveat: WebFetch answers through a summarising model. The hooks-guide claims were cross-checked against raw page text. Two long arXiv pages (DrEureka, Playground) were truncated, but the cited tables and sections were inside the fetched part.*

**Legend.** ✅ verified · ✏️ corrected (the topic files are fixed) · ❌ unsupported (removed).

## Claims and verdicts

| Rec | Claim | Verdict | What the source actually says | Source (date) |
|---|---|---|---|---|
| H1 | Adam (adam.new) is YC W25, "AI Powered CAD", founded by Zach Dive and Aaron Li | ✅ | As claimed | [YC profile](https://www.ycombinator.com/companies/adam) (checked 2026-10-19) |
| H1 | $4.1M seed led by TQ Ventures; "tens of thousands" of users; copilot starting with Onshape | ✅ | "starting with mechanical engineering and Onshape" | [TechCrunch](https://techcrunch.com/2025/10/31/yc-alum-adam-raises-4-1m-to-turn-viral-text-to-3d-tool-into-ai-copilot/) (2025-10-31) |
| H1 | CADAM: GPL-3.0, ~5.3k★, OpenSCAD, Claude backend | ✅ / partly | GPL-3.0 and **5,293★** confirmed via `gh api`. The OpenSCAD output and Claude backend come from the earlier README read and weren't re-checked in this pass. | [repo](https://github.com/Adam-CAD/CADAM) (2026-10-19) |
| C9 | CADWorld: GUI agents on FreeCAD reach 17.5% vs 87.0% for a human expert | ✅ | 17.5% vs 87.0% over 200 tasks | [arXiv 2609.16251](https://arxiv.org/abs/2609.16251) (2026-09-14) |
| A9 | BenchCAD: Claude Opus 4.7 executable rate 94.0%; IoU ~0.27 | ✅ | 94.0%, IoU 0.274 (Table 10) | [arXiv 2605.10865](https://arxiv.org/html/2605.10865) (2026-05-11) |
| A9 | BenchCAD: image-QA is 15–20 points worse than code-QA | ✏️ | **~27.5 points** (0.526 vs 0.801). The conclusion is *stronger* than we said. | same |
| A9/C | BenchCAD: "~64% of seemingly successful edits corrupted unrelated features" | ❌ | **Not in the paper** (full HTML read). It says 49% of *failed* edits were near-no-ops. **Removed** from 01, 03 and RECOMMENDATIONS. | same |
| C | Text2CAD-Bench: L3 invalidity 68–92% for frontier models; sweep/loft/shell cause most failures | ✏️ | GPT-5.2 68.0%, Claude 4.5 Sonnet 70.0%, DeepSeek 69%, GLM 83%, MiniMax 91%, Qwen3-max 92%, **but Gemini 3 Flash 12.8%**. The sweep/loft/shell attribution is qualitative ("lead to widespread execution failures"). | [arXiv 2605.18430](https://arxiv.org/html/2605.18430) (2026-05-18) |
| A9 | CADCodeVerify: 0.155→0.127; no gain after round 2; critique accuracy 64.6/68.2% | ✏️ | The numbers are right, but 64.6/68.2% **counts "Unclear" as wrong**. **Yes/no answers were 91% / 87.5% correct.** The VLM critic is often *uncertain*, rarely *confidently wrong*. | [arXiv 2410.05340](https://arxiv.org/html/2410.05340) (2024-10-07; ICLR 2025 per proceedings snippet) |
| A6 | Self-preference: LLM evaluators recognise and favour their own generations | ✅ | A "linear correlation" between self-recognition and self-preference | [arXiv 2404.13076](https://arxiv.org/abs/2404.13076) (2024-04-15) |
| A6 | GPTEval3D human agreement ~0.79 | ✅ | 0.789 average pairwise agreement (Table 2); Kendall τ 0.710 | [arXiv 2401.04092](https://arxiv.org/html/2401.04092) (2024-01-08) |
| G2 | HWE-Bench: best correct-design rate 8.15% (Claude Sonnet 4.5), 300 tasks | ✅ | As claimed (board-level schematic design) | [arXiv 2603.18102](https://arxiv.org/html/2603.18102) (2026-03-18) |
| B2 | EvilGenie: explicit reward hacking by Codex and Claude Code | ✅ | Both hacked; Gemini CLI did not | [arXiv 2511.21654](https://arxiv.org/abs/2511.21654) (2025-11-26) |
| B2 | Anthropic: coding reward hacking generalises to sabotage (~12%) | ✅ | "12% of the time … sabotage the code" | [Anthropic](https://www.anthropic.com/research/emergent-misalignment-reward-hacking) (2025-11-21) |
| E1 | Multi-agent research system: ~15× chat tokens, agents ~4×, +90.2% | ✅ (nuance) | Correct. The article says domains needing shared context or with many dependencies are "not a good fit", and that coding has fewer parallelisable subtasks. It doesn't literally say "most coding is a poor fit". | [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system) (2025-06-13) |
| E1 | Cognition: "Share context…full agent traces", "Actions carry implicit decisions", Flappy Bird example | ✅ | As claimed | [Cognition](https://cognition.com/blog/dont-build-multi-agents) (2025-06-12) |
| D3 | SessionStart matchers `startup\|resume\|clear\|compact` | ✏️ | Also **`fork`** | [hooks docs](https://code.claude.com/docs/en/hooks) (undated docs) |
| D3 | Stop: `stop_hook_active`, exit 2 blocks, overridden after 8 consecutive blocks | ✅ (detail) | 8 blocks in a row **with no tool call in between**. The count resets on a tool call, and the cap is configurable via `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`. | [hooks guide](https://code.claude.com/docs/en/hooks-guide) |
| D3 | PreCompact exists (can block); PreToolUse blocks via exit 2 or `permissionDecision: deny`; "protected files" and "re-inject after compaction" examples | ✅ | Also: **PostCompact** exists (no decision control) | hooks + guide |
| D2 | Skill frontmatter: `description`, `disable-model-invocation`, `allowed-tools`, `model`, `context: fork` + `agent`, `effort`, `paths`, `hooks` | ✅ | All exist | [skills docs](https://code.claude.com/docs/en/skills) |
| E2 | Subagent `model`, `maxTurns`, `isolation: worktree`, `memory`, `skills` | ✅ (detail) | `model` also takes `fable` and full IDs; `memory` is user/project/local | [subagents docs](https://code.claude.com/docs/en/sub-agents) |
| E2 | `opusplan` = Opus in plan mode, Sonnet to execute | ✅ | As claimed | [model config](https://code.claude.com/docs/en/model-config) |
| E4 | `/goal`: a small fast model judges a condition after each turn and can't run tools | ✅ | It wraps a session-scoped prompt-based Stop hook; "It does not call tools" | [goal docs](https://code.claude.com/docs/en/goal) |
| B1 | Harnesses post: initializer, progress file, JSON feature list, only `passes` changes, "unacceptable to remove or edit tests" | ✅ | As claimed | [Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) (2025-11-26) |
| B1/A6 | Harness design: solo 20 min/$9 broken vs harness 6 h/$200; lenient self-grading | ✅ | Also "over 20x more expensive" and "skew positive when grading their own work" | [Anthropic](https://anthropic.com/engineering/harness-design-long-running-apps) (2026-03-24) |
| B2 | C compiler: 16 agents, ~2,000 sessions, ~$20k, `current_tasks/` locks, CI added late | ✅ | "nearly 2,000" sessions, "just under $20,000", Opus 4.6 | [Anthropic](https://www.anthropic.com/engineering/building-c-compiler) (2026-02-05) |
| E2 | Advisor: +2.7 pts SWE-bench Multilingual, −11.9% cost | ✅ | The cost figure is per agentic task | [Claude blog](https://claude.com/blog/the-advisor-strategy) (2026-04-09) |
| 02 §6 | Project Fetch 2: 9 min 35 s vs 181/361 min; low-level control not tested | ✅ | As claimed (Opus 4.7) | [Anthropic](https://www.anthropic.com/news/project-fetch-phase-two) (2026-06-18) |
| I2 | METR: 50% horizon doubling ~7 months | ✅ | The page notes newer Time Horizon 1.1 estimates exist | [METR](https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/) (2025-03-19) |
| C6 | build123d-mcp exists, v0.3.91, 2026-10-15, Paul Fremantle | ✅ | As claimed | [PyPI JSON](https://pypi.org/pypi/build123d-mcp/json) |
| I8 | Onshape FeatureScript MCP, blog 2026-09-30 | ✅ | An Onshape Labs tool linking Onshape to LLMs: you describe a custom feature in plain language, and the AI creates, tests and debugs the FeatureScript | [Onshape blog](https://www.onshape.com/en/blog/featurescript-mcp-server-use-cases-text-code-cad) (2026-09-30) |
| C4 | ArtiCAD Connector defines attachment points and joint params first | ✅ | "explicitly defines attachment points and joint parameters" | [arXiv 2604.10992](https://arxiv.org/abs/2604.10992) (2026-04-13) |
| A8 | `bpy` 5.0.1 has a cp311 Windows wheel | ✅ (local) | `pip install --dry-run bpy` in Python 3.11.9 resolved `bpy-5.0.1-cp311-cp311-win_amd64.whl` | local pip, 2026-10-19 |
| B6 | DrEureka: 15/16 policies tripped motor power protection | ✅ (nuance) | Table I footnote, on the **"With Uninformative Prior"** ablation: "15 out of the 16 policies resulted in jerky and dangerous behavior", often tripping the power-protection fault. Without a prior it scored 0.09 m/s, with an uninformative prior 0.08, plain Eureka 0.0; human 1.32±0.44, DrEureka 1.83±0.07. | [arXiv 2406.01967](https://arxiv.org/html/2406.01967) (2024-06) |
| B4 | ToddlerBot: 19 min longest run, limited by motor heating; 1.3° tracking | ✏️ | 19 min is right ("longest streak of 19 minutes without falling"; rising motor temperature caused later falls). **The 1.3° is the *simulated* tracking error after parameter optimisation (Sec 8.10), not real-world.** 0.56 m, 3.4 kg, <$6k, Dynamixel. | [arXiv 2502.00893v4](https://arxiv.org/html/2502.00893v4) (2025) |
| B4 | Thermal-aware RL: A1 + payload, ~7 → >27 min | ✏️ | Abstract "over 27 minutes"; Sec IV-B "more than 26 minutes", **battery-limited**. Baseline ~7 min with a 3 kg payload (front-left knee overheated). | [arXiv 2603.01631](https://arxiv.org/html/2603.01631) (2026-03-02) |
| 02 §3 | Playground: Berkeley Humanoid <15 min, G1/T1 <30 min on 2× RTX 4090 | ✅ | Sec IV-B2 | [arXiv 2502.08844](https://arxiv.org/html/2502.08844) (2025-02) |
| 02 §4 | BAM: published STS3215 params are M1 only | ✏️ **wrong** | `bam/params/feetech_sts3215_7_4V/` contains **m1.json … m6.json**. All six models are published (7.4 V only). | [Rhoban/bam](https://github.com/Rhoban/bam/tree/main/bam/params) (2026-10-19) |
| 02/I6 | Text2Robot: Meshy meshes, manual symmetry filtering, servos in separate printed boxes, Fusion 360 repair | ✅ | Sec III-A/B | [arXiv 2406.19963](https://arxiv.org/html/2406.19963) |
| B5 | Opt2Skill: Crocoddyl DDP with torque limits as RL references | ✅ | Limit values not given | [arXiv 2409.20514](https://arxiv.org/html/2409.20514) |
| F6 | Open Duck Mini ships ONNX policies and uses BAM STS3215 params | ✅ | `BEST_WALK_ONNX.onnx`, `BEST_WALK_ONNX_2.onnx`; `sim2real.md` links `bam/params/feetech_sts3215_7_4V` | [repo](https://github.com/apirrone/Open_Duck_Mini) |

**Score:** 41 claims checked. 33 verified (6 of them with a nuance, detail or partial check), 7 corrected, 1 removed as unsupported.

## Practical feasibility on the maintainer's machine

Tested 2026-10-19 on Windows 11, Python 3.11.9 and an RTX 4060 Laptop GPU (8 GB, driver 596.08), in a throwaway venv `.venv-verify/` inside the worktree. The venv is git-excluded, and the repo's `.venv` was not touched. Script: `scratchpad/feas.py`, summarised below.

| Package | `pip install` on Windows | Smoke test | Notes |
|---|---|---|---|
| **Pinocchio** (`pin` 4.1.0) | ❌ **fails** (source build of build deps) | — | PyPI has **no Windows wheels** (macOS and Linux only). **conda-forge has `pinocchio` 4.1.0 for win-64**, but conda isn't installed here. |
| **Crocoddyl** 3.2.1 | ❌ **fails** | — | **No Windows build anywhere.** PyPI is macOS/Linux only, and conda-forge has no win-64. It needs Linux or WSL2, and **WSL is not installed** on this machine. |
| **casadi** 3.8.1 (bundles IPOPT) | ✅ | Torque-limited pendulum swing-up (80 nodes, \|u\| ≤ 2): `Solve_Succeeded` in **0.04 s**. Peak \|u\| = 2.00 (the limit is active), RMS 1.72. | Works out of the box. Gives torque-limited trajectory optimisation with peak and RMS outputs. |
| **mujoco** 3.16.0 | ✅ | `mjd_transitionFD` returns A and B | Finite-difference dynamics derivatives are the building block for an **iLQR/DDP on MuJoCo itself**, so we never need a second model. |
| **mujoco-mjx** 3.16.0 + **jax** 0.10.2 | ✅ (CPU only) | MJX step jitted in 0.65 s | `jax.devices()` = **CPU only**. **There is no `jax-cuda12-plugin` wheel for Windows**, so **MJX GPU RL training can't use the RTX 4060 natively**. Use WSL2 + CUDA (not installed) or a cloud/Linux GPU. (MJWarp also needs `warp`, untested.) |
| MuJoCo MPC | ❌ | — | Not on PyPI. It's a C++ build. |
| **manifold3d** 3.5.4 | ✅ | import | |
| **pyvista** 0.49.1 | ✅ | import (offscreen render already tested in [prototypes](prototypes/README.md)) | |
| **trimesh** 5.1.1 | ✅ | import | |
| **scikit-fem** 12.0.2 | ✅ | Linear-elasticity tet solve | A pip-only FEA path works. |

### What this changes

1. **Trajectory optimisation:** replace "Pinocchio + Crocoddyl" (B5) with **casadi/IPOPT direct collocation on the MJCF-derived model** for the sizing motion library, plus a small **iLQR on MuJoCo via `mjd_transitionFD`** (or MJX autodiff on CPU) where we want to stay on the sim model. Both are pip-only and both run on Windows. casadi needs the dynamics written symbolically: for our ≤ 16-DoF tree, either generate them from the spec's kinematic tree with a small RNEA in casadi, or install Pinocchio from conda-forge, which exposes a casadi interface on win-64. Crocoddyl stays an *optional* Linux/WSL path.
2. **RL training (P6 locomotion):** on this machine MJX runs **CPU-only**. Playground-class training times (≤ 30 min) assume CUDA. **Budget for WSL2 + CUDA, or a rented Linux GPU**, and record it in the profile and spec. An 8 GB RTX 4060 is also below the 2× RTX 4090 used for the published numbers, so expect a longer wall-clock even under WSL2 (inference, untested).
3. **Shell, analysis and render stack:** the whole `design` extra (manifold3d, pyvista, trimesh) plus scikit-fem installs and runs via pip on Windows. ✅

