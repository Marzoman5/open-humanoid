# RECOMMENDATIONS: how Open Humanoid should do AI-driven engineering

*T-0011 · 2026-10-19 · ai-eng-research. This is a gap analysis of the repo at `8271887` against the evidence in [01](01-ai-cad.md) · [02](02-ai-sim-robot-design.md) · [03](03-agentic-workflows.md) · [04](04-hardware-as-code.md) · [05](05-open-source-robot-practice.md) · [06](06-industrial-design-and-visual-review.md) · [07 (challenge pass)](07-challenging-our-assumptions.md) · [prototypes](prototypes/README.md).*

> **Revised after the challenge pass.** The commander asked for every named tool and structure to be treated as a hypothesis. [07](07-challenging-our-assumptions.md) tests each one. Outcomes:
> - The **toolkit is sound, but build it Adam-first** and extract generality on second use.
> - **"One-shot" is the wrong framing.** The product is a gated, resumable harness.
> - **Merge virtual prototyping and packaging** into one iterated concept loop.
> - **The shell tool is decided by a one-segment bake-off** (agent code-CAD vs the maintainer in Onshape), not by assumption.
> - **A blind critic was tested** and caught the "Roblox" render.
> - **Demote team/swarm, FreeCAD and Blender.**
>
> The changes are folded into the rows marked ⟳ below and into section I.
>
> **Verified after that.** [VERIFICATION.md](VERIFICATION.md) re-checks 41 claims: 33 verified, 7 corrected, 1 removed. It also tests the installs on the maintainer's Windows machine. Rows that moved are marked ✓:
> - **B5:** trajectory optimisation moves to casadi + a MuJoCo iLQR, because Pinocchio and Crocoddyl don't pip-install on Windows.
> - **B4:** start from the published BAM M1–M6 STS3215 params.
> - **B9 (new):** RL GPU needs WSL2 or Linux.
> - **A9:** the evidence is stronger: a ~27-point image-vs-code gap.
> - **C:** the "64% broken edits" claim is removed.

**Legend.** **NOW** = adopt now (next 1–2 sessions). **LATER** = adopt when the phase is reached or the trigger happens. **REJECT** = don't do this, with the reason. Effort: S < ½ session, M ≈ 1 session, L > 1 session.

## The one-paragraph answer

The evidence says the same thing in every domain:
- **Agents are excellent at proposing and at glue work, and unreliable at judging their own output and at numbers they can't compute.**
- Getting "close to first try" therefore comes from **cheap early decisions made explicit** (silhouette, packaging, envelopes) and from **deterministic gates the agent can't edit**.
- A **separate critic** handles taste, and **humans** sign off at a few high-leverage stops.
- Prose rules in AGENTS.md don't enforce anything. Hooks and gate scripts do.
- Our repo already has the right skeleton: a spec as source of truth, `generated/`, claims, handoffs and review gates. What's missing is the *enforcement* layer and a *design* method between "sizing" and "CAD".

## Top 7 (in priority order)

| # | Recommendation | Status | Effort | Why |
|---|---|---|---|---|
| 1 ⟳ | **Silhouette-first design, with the shell tool settled by evidence.** A D1 proportion and silhouette sheet (`profiles.yaml` + overlay PNG with references and hard points) is approved before any 3D. Then a **time-boxed leg-pair bake-off** compares agent code-CAD (shells derived from profiles by a tested loft/Gordon/SDF library) against the maintainer surfacing in Onshape for ≤ 3 h over agent-made scaffolding. Pick code if it reaches "same family"; otherwise use a hybrid. Servo packages are only keep-out volumes on every route. | NOW | M | D1 fixes "Roblox" root causes 1 and 4 on any route. Code-CAD is the only route that regenerates for other variants. Human surfacing is the only route proven to look good on open robots ([07 §3](07-challenging-our-assumptions.md#3-hypothesis-agent-written-code-cad-is-the-right-way-to-get-sleek-shells), [06](06-industrial-design-and-visual-review.md)). |
| 2 ⟳ | **A separate design-critic subagent** with references, a written rubric, clay and silhouette renders on a fixed rig, and pairwise order-swapped judging. **Calibrate it few-shot with 5–10 maintainer-rated images.** **Metrics decide anything numeric.** | NOW | S | **Tested:** a blind Sonnet critic failed the Roblox render on G1/G2/G4/G6 with correct evidence, but underestimated shoulder width (0.40–0.42 H vs ≈0.45 H measured) ([07 §4](07-challenging-our-assumptions.md#4-experiment-does-a-blind-critic-catch-roblox)). Self-preference is documented ([2404.13076](https://arxiv.org/abs/2404.13076)). |
| 3 | **Machine-readable gates + `oh gate <id>`**. A `pipeline/gates.yaml` lists every gate's command, threshold and evidence file. Only `oh gate` may write a pass record. Thresholds and golden values are hook-protected. | NOW | M | "Tests act as the spec" (Carlini). Claude Code has documented reward hacking that edits tests ([EvilGenie](https://arxiv.org/abs/2511.21654v1)). This mirrors the "only `passes` may change" feature list ([03](03-agentic-workflows.md)). |
| 4 | **Hooks to enforce AGENTS.md.** PreToolUse blocks writes to `generated/`, gate files and unclaimed paths (including Bash redirects). A SessionStart hook (`startup|resume|compact`) injects `oh coord status`, the active task and the last handoff. A Stop hook runs `oh gate --current` before a phase may be declared done. | NOW | M | CLAUDE.md is advisory and hooks are deterministic, per Claude Code's own docs ([memory](https://code.claude.com/docs/en/memory), [hooks guide](https://code.claude.com/docs/en/hooks-guide)). |
| 5 ⟳ | **A concept loop before detailed CAD:** kinematics + hard-point packaging + D1 silhouette + virtual-prototyping envelopes on the concept's masses (measured actuator model → trajectory-optimised motions → peak/RMS/thermal → Monte Carlo p95), iterated until all pass. This replaces quasi-static sizing as the mechanical go/no-go. | NOW (design) / LATER (full) | L | Envelopes and packaging are coupled (concept → embodiment → detail; Fadini's bi-level co-design). Measured bounds beat guessed ones on hardware (DrEureka) ([02](02-ai-sim-robot-design.md), [07 §2](07-challenging-our-assumptions.md#2-h2h3h8-pipeline-shape-and-the-one-shot-framing)). |
| 6 | **Phases become Claude Code skills** (`.claude/skills/<phase>/SKILL.md` plus `scripts/`). Heuristics live in the skill, checks live in scripts, and the one-shot prompt becomes a thin orchestrator that invokes skills. | NOW (P3 design skill first) / LATER (the rest) | M | Progressive disclosure keeps context lean. Skills carry `model`, `context: fork` and `disable-model-invocation` per phase ([03](03-agentic-workflows.md)). |
| 7 | **Interface-first CAD.** Generate an `interfaces.yaml` (joint axes, servo envelopes, horn and mount patterns, clearances) from spec + sizing **before** part geometry. A build123d helper library (`openhumanoid/cad/`) provides loft-shell, Gordon-panel, servo-pocket and keep-out primitives. The geometry gate checks STEP round-trip and watertightness, not `is_valid`. | NOW | M | LLM CAD fails on lofts and shells and on silent booleans ([01](01-ai-cad.md)). ArtiCAD's connector-first pattern. Our own false-valid `offset()` finding. |

Next most important:
- **#8, the rename question** (§H). It's cheap now and expensive later.
- **#9, Adam-first, extract on second use** (§I1). It changes how every framework task is scoped.

---

## A. Design and the visual review loop (the "Roblox" problem)

| ID | Recommendation | Status | Reasoning / evidence |
|---|---|---|---|
| A1 | Insert **D0–D6 design steps** into P3 (brief/refs → **D1 silhouette sheet** → massing → feature lines → packaging closure → surface/print prep → final). Add a new human stop **R2a "silhouette"** at D1. | NOW | The D1 sheet is minutes of compute and is where the toy-vs-product decision is made. It is the cheapest place to iterate ([06 §5](06-industrial-design-and-visual-review.md)). |
| A2 | Make `variants/<id>/design/profiles.yaml` (stations `z, w, d, n` per segment) the **source of truth for outer shape**. A generator derives 3D sections from it, never by hand. | NOW | This removes drift between the approved silhouette and the CAD (06 §3, structural rule). It is the CAD equivalent of AGENTS.md rule 1. |
| A3 | **Outside-in shell, inside-out frame**, meeting at a clearance and ROM-sweep check. | NOW | Servo boxes became the shapes because the shell was grown from the frame. |
| A4 | Upgrade `oh render`: pyvista clay (SSAO, 3-point light), orthographic silhouettes, reference overlay at equal height, head-unit grid, a fixed committed camera rig, and an optional zebra pass. Keep the MuJoCo render for sim. | NOW | Flat renders hide form (failure #6). Prototyped ([prototypes](prototypes/proto_clay.png)). |
| A5 | `oh design metrics <id>` computes the §7 rubric numbers (P1–P10, S1–S5, M1) from mesh or profiles into `generated/design_metrics.json`. **Calibrate the bands** by running it on 3–4 normalised reference silhouettes first. | NOW (tool) / calibrate before gating | VLMs can't measure, so code must. The bands are anthropometric starting points and haven't been verified. |
| A6 | Add a `design-critic` subagent (Sonnet; Opus only at R3). It gets images, references, the rubric and metrics, and **no code or transcript**. It returns per-criterion verdicts, a pairwise preference asked twice with the order swapped, and the top 3 changes mapped to profile parameters. Cap at 3 rounds per step. | NOW | Separate critic (self-preference), pairwise (GPTEval3D), swap order (position bias), round cap (CADCodeVerify plateau) ([06 §6](06-industrial-design-and-visual-review.md)). |
| A7 ⟳ | Code shell toolchain for the R-code arm of the bake-off (and the default if it wins): **build123d section-lofts (outer − inner) + Gordon panels + manifold3d SDF smooth-unions**. Add a `design` pip extra: `manifold3d trimesh pyvista scikit-image`. | NOW | All pip and all tested. No Blender or FreeCAD needed for the look. |
| A8 | Blender `bpy` (5.0.1 cp311 wheel) for beauty renders and sculpted shells. | LATER (only if the maintainer wants photoreal or the hybrid ceiling is hit) | Heavy install and mesh-only output. Its MCP socket has no auth ([01 §4](01-ai-cad.md)). |
| A9 | Use the VLM to check dimensions, or let the authoring agent grade its own look. | **REJECT** | BenchCAD: ~27 points worse from images (0.526 vs 0.801). CADCodeVerify: 65–68% overall (it is often "Unclear"). Self-preference bias. |

**Prompt text to add to P3 (draft, for the commander):**
> Design the outer shape before the frame. (1) Write `design/profiles.yaml` and render the D1 sheet with references and hard points; run `oh design metrics`. Stop for R2a. (2) Derive shells from the profiles with the `openhumanoid.cad` shell helpers; never shape a shell from a servo box. (3) After each step, run the geometry gate, then hand only the render sheet + rubric + metrics to the `design-critic` subagent; change only what it ties to failed criteria; max 3 rounds. Numbers come from `oh design metrics`, never from looking at a picture.

## B. Pipeline phases and gates

Current state: a P0–P9 table in prose inside `prompts/oneshot/build-a-humanoid.md`. The gates are commands the agent runs and reports on itself. Sizing is quasi-static with no thermal term (`docs/tools.md` lists that limitation).

| ID | Recommendation | Status | Reasoning |
|---|---|---|---|
| B1 | **`pipeline/gates.yaml` + `oh gate <gate-id> [--variant]`.** Each gate has a command, metric thresholds, an evidence path and an owner phase. `oh gate` writes `variants/<id>/generated/gates/<gate>.json` (pass/fail, metrics, git SHA, timestamp). The prompt says "phase done ⇔ `oh gate` PASS record at HEAD". | NOW | This is the feature-list + `passes` pattern ([Anthropic harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)). It turns gates from claims into artifacts a reviewer and CI can check. |
| B2 | **Thresholds can't be edited by the phase agent.** Hook-protect `pipeline/gates.yaml`, and changes go through an ADR task. CI re-runs every gate that has a PASS record (a regression gate). | NOW | Reward hacking via test edits is documented. Carlini added CI late and regretted it. |
| B3 | Restructure phases (aligned with the commander's plan): P0 intake → P1 quick sizing → **P2 virtual prototyping** (actuator model, trajectory-optimised reference motions, envelopes, Monte Carlo) → **P3 packaging layout** (interfaces.yaml, hard points, D0–D1 silhouette) → **P4 detailed CAD** (frame + shell D2–D6, FEA on critical parts) → **P5 virtual test suite** (CAD-derived MJCF; ROM, fall, thermal-walk and push tests) → P6 locomotion → electronics / sourcing / build. | NOW (doc) | Decide early whatever is expensive to change later. RL is the final evaluator, not the inner loop ([02 §3](02-ai-sim-robot-design.md)). |
| B4 ✓ | P2 gate (starting thresholds; calibrate with the benchmark stream's measured data): per joint, **p95 Monte Carlo peak ≤ 70% of measured stall at operating voltage**. RMS ≤ continuous rating. Simulated 10-minute walk below thermal shutdown. Held-out actuator-model tracking ≤ ~2°. | LATER (start now from the published BAM params) | **Start from the published BAM STS3215 7.4 V params (models M1–M6 all exist)**. The benchmark stream then only needs to add 12 V, temperature and unit-to-unit spread. ToddlerBot ran 19 minutes before thermal drift. Thermal-aware RL gave ~7 → >26 min (battery-limited). ToddlerBot reached 1.3° tracking *in simulation* after parameter fitting ([02](02-ai-sim-robot-design.md)). |
| B5 ✓ | Trajectory optimisation with **casadi/IPOPT direct collocation** (pip, Windows-tested: torque-limited solve in 0.04 s), with dynamics from a small RNEA generated from the spec's kinematic tree. Add an **iLQR on MuJoCo via `mjd_transitionFD`** where we want to optimise on the sim model itself. Run it over the motion library for reference motions and sizing. Its output also feeds RL imitation rewards (Opt2Skill pattern) and the power budget (E2). Pinocchio (conda-forge only on Windows) and Crocoddyl (no Windows build) are optional Linux/WSL paths. | LATER (P2 build) | There is no published sizing recipe, so this is our contribution. One computation feeds three phases. **Changed after [VERIFICATION](VERIFICATION.md#practical-feasibility-on-the-maintainers-machine):** `pip install pin`/`crocoddyl` fail on Windows. |
| B6 | **LLM proposes, code bounds it** (DrEureka RAPP): any tuned constant (DR range, gain, mass-model constant) must cite a probe or measurement file. Enforce it via the provenance check (D4). | NOW (rule) | Guessed DR ranges caused 15/16 hardware faults in DrEureka. |
| B7 | **Session-start smoke gate**: `oh gate --smoke` (validate + size + sim test, < 1 min) as the first command of every session, injected by the SessionStart hook. | NOW | It catches breakage left by the previous session (Anthropic harnesses pattern). |
| B9 ✓ | **GPU plan for RL (P6):** JAX has **no CUDA wheels for Windows**, so MJX on this machine is CPU-only (tested). Before P6, either install **WSL2 + CUDA** (not currently installed) or budget a rented Linux GPU. Record `compute.training_gpu` in the spec or profile. The published ≤ 30-min training times are on 2× RTX 4090, and an 8 GB laptop 4060 under WSL2 will be slower. | NOW (decision) / LATER (setup) | [VERIFICATION](VERIFICATION.md#practical-feasibility-on-the-maintainers-machine) |
| B8 | Use RL policy training as the per-candidate design evaluator. | **REJECT** (finalists only) | ~15–30 min per run on a 4090-class GPU. Use cheap proxies first ([02 §3](02-ai-sim-robot-design.md)). |

## C. CAD stack

| ID | Recommendation | Status | Reasoning |
|---|---|---|---|
| C1 | **Keep build123d** as the default backend for frames, interfaces and lofted shells. | NOW | B-rep and STEP, and three independent Claude-oriented harnesses converge on it ([01 §4](01-ai-cad.md)). |
| C2 | **`openhumanoid/cad/` helper library** with tested primitives: `loft_shell(profile, wall)` (outer−inner), `gordon_panel`, `servo_pocket(actuator_id)` from the catalog `dimensions_mm`, `keepout()`, `split_for_bed()`, `magnet_boss()`. Agents compose these instead of writing raw lofts. | NOW (part of T-0004) | Lofts and shells cause most LLM CAD failures. A library turns 70–90% failure-prone operations into tested calls. |
| C3 | **Geometry gate**: execute → single valid solid → **STEP export and re-import, then re-check validity and volume** → watertight STL (trimesh) → bbox and key dimensions vs `interfaces.yaml` → pairwise interference and clearance → min wall and bed fit. | NOW | Silent boolean drops ([ModelRift](https://modelrift.com/blog/cadquery-vs-openscad/)) and our false-valid `offset()` ([prototypes](prototypes/README.md)). |
| C4 | `interfaces.yaml` generated from spec + sizing + catalog *before* part geometry (joint axes, servo envelope, horn pattern, ROM). Parts are checked against it numerically. | NOW | ArtiCAD's connector-first pattern. CAD-bench shows mates are near zero standalone. |
| C5 | Commit a `docs/cad-cheatsheet.md` (build123d selectors, BuildPart vs algebra mode, our helpers) plus 3 golden example parts. Load it from the CAD skill. | NOW | No build123d benchmark exists and training data is thinner than for CadQuery. Build skills from observed failures (Anthropic). |
| C6 | **Evaluate build123d-mcp / text-to-cad skills** (render, measure, `@cad` stable face references, URDF export) before writing our own viewer and measure tooling. | LATER (S, one Sonnet session) | Reuse beats rebuild, but check licences and sandboxing first. |
| C7 ✓ | FEA: start with analytic checks in `oh` (beam/plate, bolt bearing, layer-adhesion derating) for printed parts. Use pip FEM (scikit-fem on a gmsh mesh; **pip install and a tet elasticity solve tested on Windows**) for the 3–4 highest-stress parts. **FreeCAD FEM/TechDraw only when a human needs drawings.** | LATER | FreeCAD isn't pip-installable and its headless FEM/assembly scripting is unverified on 1.x ([01 §5](01-ai-cad.md)). |
| C8 | Zoo/KCL text-to-CAD, Onshape AI Advisor, SolidWorks Aura as pipeline components. | **REJECT** | Hosted, billed, proprietary, or docs-Q&A only. That conflicts with "clone and run". Onshape stays a valid *human* backend via the export contract. |
| C9 | Driving a CAD GUI with computer-use agents. | **REJECT** | CADWorld: 17.5% vs 87% for a human. |
| C10 | Converting SDF/mesh shells to STEP. | **REJECT** | Lossy and pointless. Shells ship as STL/3MF, and the export contract should allow `process: fdm` parts as mesh-only (needs an ADR, because `parts/<id>.step` is currently required). |

## D. Prompts, skills and hooks

Current state: AGENTS.md has 7 good rules, all advisory. There is no `.claude/` directory, so no hooks, skills or subagents. The one-shot prompt is ~90 lines and contains the whole phase table.

| ID | Recommendation | Status | Reasoning |
|---|---|---|---|
| D1 | **Skills per phase** under `.claude/skills/`: `intake`, `sizing`, `virtual-proto`, `packaging`, `design-shell` (A1), `cad-part`, `sim-test`, `locomotion`, `electronics`, `sourcing`, `build-guide`. Each SKILL.md (≤ 300 lines) holds *how to decide* (heuristics), the exact `oh` commands, the gate id, and common failures. `scripts/` holds the deterministic parts. | NOW: `design-shell` + `cad-part`. LATER: the rest, as each phase is first run. | Skills are an open standard ([agentskills.io](https://code.claude.com/docs/en/skills)) and AGENTS.md stays tool-agnostic. Build skills from observed failures, so write each skill *after* its phase's first real run. |
| D2 | Frontmatter: `sourcing` → `disable-model-invocation: true` (side effects, live prices) and `model: haiku` with `context: fork`. Research and lookup skills → `context: fork`, `model: sonnet`. `design-critic` → its own subagent with no write tools. | NOW (with D1) | These are the cost and safety levers ([03](03-agentic-workflows.md)). |
| D3 | **Hooks in committed `.claude/settings.json`**, each with a cross-platform Python script under `tools/hooks/`:<br>• `PreToolUse(Edit\|Write\|MultiEdit)` + `PreToolUse(Bash)` → deny writes to `**/generated/**`, `pipeline/gates.yaml`, `schemas/**` and contract files, and deny writes outside the agent's claimed `paths` (reads `oh coord status --json`). Exit 2 with "run `oh …` instead".<br>• `SessionStart(startup\|resume\|compact)` → print `oh coord status`, active task, newest handoff path, `git log -5`, and run `oh gate --smoke`.<br>• `Stop` → if the task is `in_progress` and the phase gate has no PASS record at HEAD, block once with the failing gate. Honour `stop_hook_active`.<br>• `PreCompact` → `oh coord handoff --auto` writes a stub handoff. | NOW | Turns rules 3 and 4 and the checkpoint rule into enforcement. The guide has ready "protected files" and "re-inject after compaction" examples. Bash redirects need their own matcher because the Edit matcher alone is bypassable. |
| D4 | **Provenance check** (`oh check provenance`, run in CI and PostToolUse on catalog/spec writes): every catalog numeric field needs `source` + `verified`. Every tuned constant in a spec needs `# source:` or a `provenance:` map entry pointing to a file, URL or measurement. | NOW (catalog) / LATER (spec constants) | Rule 6 is good but unenforced. No published practice exists, so this is our inference, backed by the reward-hacking evidence. |
| D5 | **Slim the one-shot prompt** into an orchestrator: inputs, ground rules, "for each phase: invoke skill → `oh gate` → review stop → checkpoint". Phase detail moves into skills and gate definitions into `gates.yaml`. Keep it tool-agnostic so non-Claude agents can read the skills as plain markdown. | LATER (after D1–D3) | Less always-on context, and one source per fact. |
| D6 | Add a **LESSONS.md loop**: when an agent mistake is caught, add a line to the relevant skill or a hook, not to AGENTS.md. Prune AGENTS.md lines that are now hooks. | NOW (rule) | Hashimoto's "harness engineering", and Anthropic's "would removing this cause a mistake?" test. |
| D7 | Interview the maintainer at P0, then write the spec, then start a **fresh session** to execute (the Anthropic best-practices pattern). | NOW (prompt line) | This preserves the expensive context for execution. |
| D8 | Adopt spec-kit, Kiro or BMAD wholesale. | **REJECT** | We already have spec + constitution + tasks + DO-NOT-EDIT outputs. Those tools add review burden and waterfall drift (Böckeler 2025-10-15). |

## E. Multi-agent orchestration on a limited Opus budget

| ID | Recommendation | Status | Reasoning |
|---|---|---|---|
| E1 | **Default single-threaded (solo).** Parallelise only disjoint, claimed paths in worktrees. Never split frame, shell and electronics of the *same segment* across agents before `interfaces.yaml` and `profiles.yaml` are frozen. | NOW | Multi-agent costs ~15× the tokens and hurts on interdependent work (Anthropic, Cognition). "Actions carry implicit decisions." |
| E2 | **Model routing table** (put it in `coordination/profiles/*.yaml` per phase):<br>• **Opus:** P0 interview/spec, P3 packaging and D1 decisions, final R3 critic, and stuck escalation after 2 failed corrections.<br>• **Sonnet:** CAD part authoring with helpers, sim and gate runs, design-critic rounds, docs.<br>• **Haiku:** search, catalog lookups, link checks, formatting.<br>• Use `opusplan` for planning-heavy sessions. | NOW | Put Opus where errors compound upstream. Anthropic's harness kept the planner even after dropping everything else. The advisor pattern is +2.7 points at −11.9% cost. |
| E3 | Run unattended stretches as **Ralph-style loops on Sonnet**: `claude -p` with one `oh coord` task per iteration, `oh gate` as backpressure, commit on pass, and a `maxTurns` cap. | LATER (once gates exist) | Fresh context per item. Gates prevent the "declare victory" failure. |
| E4 | Use `/goal "oh gate <id> prints PASS, or stop after 20 turns"` for single-phase sessions. | LATER | It is cheap and built in, but the goal judge can't run commands, so the gate output has to be printed. |
| E5 | Swarm and agent-teams profiles as the default for design work. | **REJECT** (keep them for disjoint catalog, sourcing and docs work) | Coordination cost and inconsistency. Agent teams are experimental. |

## F. Making "close to first try" real

The ranking of levers is my synthesis. The evidence for each is linked above.
1. **Decide expensive things early and cheaply:** P2 envelopes (actuator model + trajectory optimisation + Monte Carlo), P3 packaging and silhouette, and interfaces before geometry.
2. **Measure, don't assume:** measured actuator model, slicer masses (as Open Duck does), and test prints of a **fit gauge** generated from the same `servo_pocket` code (as SO-100 does) *before* the full print. That makes the first physical artifact a 20-minute gauge, not a robot.
3. **Gates the agent can't edit**, plus CI regression of every passed gate.
4. **Separate critics** for taste, and code for numbers.
5. **One-command bring-up**: `oh doctor` per-motor ID and baud setup before assembly, a bus scan, a voltage check, a range sweep and an IMU check (as LeRobot and Open Duck do).
6. **Ship identified params and pretrained policies** so builders don't train first (as Open Duck does).

## G. Electronics, sourcing and build guide

| ID | Recommendation | Status | Reasoning |
|---|---|---|---|
| G1 | P6 = **generated wiring**: `oh wiring <id>` → WireViz YAML + SVG, servo ID map, power budget (stall vs duty from P2 torque time series, AWG drop, BMS and buck rating, runtime). | LATER (P6) | No dedicated tool exists, and the analysis is simple first principles ([04](04-hardware-as-code.md)). |
| G2 | Custom PCB in v1. | **REJECT** (atopile + `kicad-cli` ERC/DRC LATER, if ever) | HWE-Bench: 8% full-design success. SO-100 and Open Duck use stock boards. |
| G3 | **BOM rows must resolve against a source**, each with `{price, currency, region, url, retrieved, variant_code}`. R5 fails if any budget-critical line is unverified. Use region columns (US/EU/CN/JP), essentials-first ordering, fasteners and tools as lines, and a weekly link-check in CI. | LATER (P7; catalog part now via T-0002) | SO-ARM's BOM is the de facto standard. BOM rot is the #1 issue class ([05](05-open-source-robot-practice.md)). |
| G4 | Build guide **generated in build order** (tools → print gauge → print → motor setup → subassemblies → wiring → calibrate → doctor → first walk), with Known Issues and Tips pages, issue templates, a hardware `CHANGELOG.md`, and printed calibration jigs. | LATER (P7–P8) | Docs lag hardware in every project studied. ODRI jigs and BHL's build-order GitBook. |
| G5 | **Decide the hardware licence before the first public release** (e.g. CERN-OHL-S or CC BY-SA 4.0 for hardware, Apache-2.0/MIT for code). Never commit vendor STEP without a licence note. | NOW (feeds T-0010) | Prusa's licence split, SO-ARM's vendor-STEP issue, K-Scale's shutdown. |

## H. Naming

| ID | Recommendation | Status | Reasoning |
|---|---|---|---|
| H1 | **Rename the robot (or brand it so it can't be confused) before going public.** "Adam" is the name of a YC W25 *AI-for-mechanical-design* startup ([adam.new](https://adam.new); $4.1M seed, [TechCrunch 2025-10-31](https://techcrunch.com/2025/10/31/yc-alum-adam-raises-4-1m-to-turn-viral-text-to-3d-tool-into-ai-copilot/)) whose open-source CADAM has ~5.3k★ and uses Claude. "Open Humanoid Adam" in an AI-designs-hardware repo will be confused with them in search, and possibly in trademark. Renaming now costs one `sed` plus an ADR. After release it costs links, forks and SEO. | NOW (maintainer decision; this is a product judgement, not legal advice) | The variant id is in paths, specs and generated files. Eve's `extends: adam` is affected too. |

## I. Challenge-pass changes to the overall approach ([07](07-challenging-our-assumptions.md))

| ID | Recommendation | Status | Reasoning |
|---|---|---|---|
| I1 | **Adam-first, extract on second use.** Replace the one-shot prompt's "build the tool generically in the framework first" with: write tools in `openhumanoid/`, but generalise only parameters with ≥ 2 real consumers. Prove generality with a cheap second consumer (an "Adam-XL" 1.0 m sizing+sim variant, or Eve's sizing). | NOW | Every reproducible open robot started as one robot. LeRobot spread *through* a cheap reference arm. Anthropic: add complexity only when it is shown to help. The toolkit vision stays; its *differentiator* is the harness (gates, measured data, skills, rubric), which generalises naturally. |
| I2 | **Reframe "one-shot"** as a gated, resumable pipeline (rename or reword `prompts/oneshot/`). "First try" means the *physical build* works first time, not that the *agent* gets it right in one pass. | NOW | Nobody credible one-shots systems this size: Carlini ran ~2,000 sessions, Anthropic's solo build broke, and METR horizons show where agents fall off. |
| I3 | Demote the `team`/`swarm` profiles to catalog, sourcing and docs fan-out only. | NOW | ~15× tokens. Interdependent design suffers (Cognition, Anthropic). |
| I4 | Defer the SolidWorks/FreeCAD adapters and the second `architecture.style`. Keep the schema fields and implement only what Adam uses. | NOW | No consumer, and double the work. |
| I5 | ADR: the export contract allows **mesh-only cosmetic `process: fdm` parts** (STEP stays required for structural parts). | LATER (when the first shell lands) | SDF, generative and human-mesh shells can't produce meaningful STEP. |
| I6 | Generative 3D (TRELLIS.2 etc.) as a shipping shell path. | **REJECT** (allowed as an optional form-finding reference only) | No precedent for servo-housing shells. Low floor (~1 in 10 usable). Licence traps: Hunyuan3D excludes the EU/UK/South Korea; SF3D has a revenue cap; TRELLIS.2 needs ≥ 24 GB GPU. |
| I7 | Blender and FreeCAD as required installs. | **REJECT for now** | Not needed for the look (pip route tested) or for v1 analysis. Reconsider only for photoreal renders or human-requested drawings. |
| I8 | Evaluate the Onshape **FeatureScript MCP** as a shared agent+human workspace if the bake-off picks the hybrid route. | LATER | New (2026-09-30), parametric features only, no independent evaluation. |

## Gap analysis summary (current repo vs best practice)

| Area | We have | Best practice | Gap → rec |
|---|---|---|---|
| Source of truth | spec.yaml + generated/ + freshness CI | same | ✅. Extend it to `profiles.yaml` and `interfaces.yaml` (A2, C4) |
| Rule enforcement | AGENTS.md prose | hooks (deterministic) | ❌ → D3 |
| Gates | prose table, self-reported | machine-readable, agent can't edit, CI-regressed | ❌ → B1, B2 |
| Checkpointing | `oh coord` tasks and handoffs | + session-start smoke, compaction re-injection | partial → B7, D3 |
| Design method | text design language, then CAD | silhouette → sections → loft, references, critic | ❌ → A1–A7 |
| Visual review | flat MuJoCo screenshots, self-graded | clay + silhouette rig, separate pairwise critic, metrics | ❌ → A4–A6 |
| Mechanical sizing | quasi-static + dynamic factor, no thermal | trajectory-optimised envelopes + thermal + Monte Carlo on a measured actuator | ❌ → B3–B5 (with the benchmark stream) |
| CAD robustness | none yet (T-0004 in progress) | helper library + round-trip gate + interface-first | ❌ → C2–C5 |
| Context and cost | profiles (solo default), tiers in workstreams | skills with per-skill model, Opus at planner and final review | partial → D1, D2, E2 |
| Numbers provenance | `verified`/`source` on catalog (rule 6) | machine-checked | partial → D4 |
| Reproducibility by strangers | planned P7/P8 | region BOM, gauges, doctor script, jigs, shipped params and policy | planned → G3, G4, F |

## Suggested sequencing (for the commander; respect existing claims)

1. **Next session (Sonnet, framework):** D3 hooks + B1 `oh gate` + B7 smoke. These are small and unblock everything else.
2. **Same or next (Opus, the one heavy session):** A1/A2 D1 silhouette sheet for Adam, A5 metrics, and the A6 critic (few-shot calibrated with maintainer ratings). Then **R2a with the maintainer**. Coordinate with T-0004's owner, because this touches `variants/adam/cad/` and `openhumanoid/cad/`.
3. **Leg-pair bake-off (Sonnet + ≤ 3 maintainer hours):** run the R-code arm (C2 helpers + A7) and the R-human arm in Onshape over exported scaffolding. Judge with the blind pairwise critic and then the maintainer, and log the human hours. Decide code vs hybrid for the full body ([07 §3](07-challenging-our-assumptions.md#3-hypothesis-agent-written-code-cad-is-the-right-way-to-get-sleek-shells)). T-0004 continues with C2–C4 and the geometry gate either way.
4. **The P2 virtual-prototyping build** (B4/B5) once the benchmark stream delivers measured STS3215 data.
5. Decide H1 (rename), G5 (licence), I1 (Adam-first) and I2 (one-shot reframing) with the maintainer at the next review stop.
