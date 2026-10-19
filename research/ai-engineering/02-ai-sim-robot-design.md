# 02 · AI + simulation and robot design

*Research T-0011 · 2026-10-19 · ai-eng-research. This file covers methods only. Actuator and robot benchmark data is a separate research stream under `research/`. **[UNVERIFIED]** means a secondary source or a snippet only.*

## Bottom line

- **LLMs help most where a fast, trusted evaluator already exists.** DrEureka works because the LLM proposes reward and randomization terms *inside bounds measured in simulation*. Without those bounds it fails on hardware.
- **No one has published an LLM-designed hobby-servo humanoid that walks on hardware.** That is a negative result from one session of searching. The novel, publishable part of Open Humanoid is a *measured, gated* pipeline, not "the AI designed it".
- Treat RL as the **expensive final evaluator**, at roughly 15–30 min per run. Cheaper proxies (trajectory optimisation plus torque and thermal envelopes, with Monte Carlo) go first.

## 1. LLM-in-the-loop design: what reached hardware

| Work | LLM's role | Hardware? | Lesson |
|---|---|---|---|
| **Eureka** ([2310.12931](https://arxiv.org/abs/2310.12931), Oct 2023) | Writes reward code, evolutionary search, reflection on training stats | Sim only (beat expert rewards on 83% of 29 tasks) | Reward search works when training is fast. |
| **DrEureka** ([2406.01967](https://arxiv.org/abs/2406.01967), RSS 2024) | Reward plus safety terms, then **RAPP**: sweep each physics parameter in sim and keep the range where the policy still succeeds. The LLM then proposes domain-randomization (DR) configs *within those bounds*. | **Yes**, Go1 and LEAP hand | Go1: **1.83 m/s vs 1.32 human-designed**. **Eureka without safety/DR: 0 m/s.** Uninformed DR ranges: **15/16 policies tripped motor-power protection**. About 3 h wall-clock vs 10–20 h for CEM/BayRn. ([table](https://arxiv.org/html/2406.01967v1)) |
| **Text2Robot** ([2406.19963](https://arxiv.org/abs/2406.19963), ICRA 2025) | Text-to-3D body proposal, then evolutionary body/control co-optimisation including electronics and manufacturability | **Yes**, printed quadrupeds | The LLM handles the *creative* proposal. Physics is done by optimisation. |
| Language to Rewards ([2306.08647](https://arxiv.org/abs/2306.08647)) | Fills a reward-term library; MuJoCo MPC solves | Arm **[secondary]** | A constrained vocabulary beats free-form generation. |
| RoboMorph ([2407.08626](https://arxiv.org/abs/2407.08626)), LASeR ([ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/934eb45b99eff8f16b5cb8e4d3cb5641-Abstract-Conference.html)), RoboGen ([2311.01455](https://arxiv.org/abs/2311.01455)), RoboMoRe ([2506.00276](https://arxiv.org/pdf/2506.00276)) | LLM as mutation operator or task proposer, scored by RL | Sim only | Morphology claims are sim-only. |
| **AlphaEvolve** ([launch 2025-05-14](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/); [impact 2026-05-07](https://deepmind.google/blog/alphaevolve-impact/)) | LLM edits code, an automated evaluator scores it, the best is kept | TPU circuits, power flow, scheduling | No mechanical-design application found. **The pattern transfers directly:** an agent edits parametric build123d/spec values against a fast scalar evaluator. |

**Generalisable rule:** let the LLM *propose* (rewards, DR configs, parameter changes, morphologies), and have code *measure* the bounds and *score* the result. An LLM-chosen number is never accepted unless a probe or measurement backs it.

## 2. Agents driving simulators

- **MuJoCo Playground** ([2502.08844](https://arxiv.org/abs/2502.08844), Feb 2025; [site](https://playground.mujoco.org/)) is MJX-based and ships envs for Berkeley Humanoid, G1, H1, Booster T1, OP3, Go1, Spot and more. It demonstrates zero-shot sim-to-real. **Open Duck Mini's training stack is built on it.**
- **MuJoCo Warp** ([repo](https://github.com/google-deepmind/mujoco_warp)) is NVIDIA-only and is missing some integrators and solvers. **mjlab** ([2601.22074](https://arxiv.org/abs/2601.22074), Jan 2026) puts an Isaac-Lab-style manager API on MJWarp. Neither published wall-clock humanoid numbers. Watch them; don't depend on them yet.
- **Isaac Lab** ([2511.04831](https://arxiv.org/abs/2511.04831)) needs the Omniverse runtime, which conflicts with "clone and run".
- **Genesis:** an independent benchmark found its headline FPS came from a stripped scene, it was 3–10× slower than ManiSkill on manipulation, and had accuracy problems ([blog](https://stoneztao.substack.com/p/the-new-hyped-genesis-simulator-is)) **[secondary]**. Skip it for contact-rich legged work.
- **MCP servers:** isaac-sim-mcp exists ([repo](https://github.com/omni-mcp/isaac-sim-mcp)). The MuJoCo ones are toys, and I found none for Genesis. **A Claude Code agent doesn't need MCP for MuJoCo.** It runs Python and reads JSON, logs and renders, which is what our `oh sim` already does. Simon Willison also recommends shell commands over MCP ([2025-09-30](https://simonwillison.net/2025/Sep/30/designing-agentic-loops/)).
- **LLM-written sim environments** (GenSim [2310.01361](https://arxiv.org/abs/2310.01361), GenSim2 [2410.03645](https://arxiv.org/abs/2410.03645)) suffer syntax errors, hallucination and weak physical grounding. **Generated MJCF needs automatic validators**: it steps, masses and inertias are sane (positive-definite, triangle inequality), no initial penetration, and joint names match the spec.

## 3. Fast GPU RL as an inner loop

- Playground numbers ([paper HTML](https://arxiv.org/html/2502.08844v1)): **Berkeley Humanoid flat in under 15 min, G1 and T1 in under 30 min, on 2× RTX 4090.** MJX JIT compile takes 1–3 min. Brax PPO on an A100 runs 106k–290k steps/s for humanoids. Training is staged: flat ground then rough, and narrow commands then wide.
- **ToddlerBot** ([2502.00893](https://arxiv.org/abs/2502.00893)) uses MJX/Brax PPO with 3×10⁸ steps and 1,024 envs. Its longest streak was **19 min before motor heating pushed it out of distribution**.
- **Thermal-aware RL** ([2603.01631](https://arxiv.org/abs/2603.01631), 2026-03-02) adds motor temperature to the observation plus thermal rewards. An A1 carrying a 3 kg payload went from a knee-motor overheat at **~7 min** to **>26–27 min** (the abstract says 27, Sec IV-B says 26; the run ended when the battery ran out). Directly relevant to STS3215 thermal shutdown.
- **Implication (inference):** a 16-DoF Adam-class model should train in tens of minutes on one 4090-class GPU **under Linux/WSL2**. JAX has no CUDA wheels for Windows, and MJX was CPU-only on the maintainer's machine (tested). That supports "train a policy per *finalist* design" (a handful per day), not per candidate. The maintainer's GPU availability is a planning constraint to record in the spec or profile.

## 4. Sim-to-real for cheap servo robots

- **BAM (Better Actuator Models)** ([docs](https://bam.readthedocs.io/en/latest/theory/models.html); ICRA 2025, Rhoban) has six friction models (M1 Coulomb–viscous → M2 Stribeck → M3 load-dependent → M4 → M5 directional → M6 quadratic directional). It fits them, picks by validation error, and exports to MuJoCo (`damping`, `kp`, `frictionloss`, `armature`, `forcerange`). **Published STS3215 (7.4 V) params exist for all six models, M1 through M6** ([`bam/params/feetech_sts3215_7_4V`](https://github.com/Rhoban/bam/tree/main/bam/params), checked 2026-10-19). An earlier draft said "M1 only"; that was wrong. What remains *unpublished* is a 12 V STS3215, temperature dependence, and unit-to-unit spread. *(The actuator-benchmark stream owns the data; this file only notes the method.)*
- **ToddlerBot system-ID recipe** ([2502.00893v4](https://arxiv.org/html/2502.00893v4)): chirp tracking on the robot, plus a motor test bed (back-drive with a torque sensor, spin-down for armature). It jointly fits 9 actuation params with constrained ranges, adds low- and high-speed torque limits, and uses zero-point calibration. Result: **1.3° mean tracking error in simulation after parameter optimisation** (Sec 8.10). This is not a real-world accuracy figure. Known gaps: no temperature model, and poor accuracy near limits.
- **Open Duck Mini** ([sim2real.md](https://raw.githubusercontent.com/apirrone/Open_Duck_Mini/refs/heads/v2/docs/sim2real.md)): BAM-identified STS3215, slicer-estimated masses (infill-aware), and a Disney-BDX-style imitation reward ([Disney 2501.05204](https://arxiv.org/abs/2501.05204)) on placo-generated parametric-walk reference motions ([generator repo](https://github.com/apirrone/Open_Duck_reference_motion_generator)). Ships **pretrained ONNX** policies.
- **Domain randomization (Playground):** sensor noise, COM, reflected inertia, joint calibration offsets, friction and payload. Add latency and the half-duplex bus rate. The bus rate for 16 servos is a real control-rate limit, so compute it before choosing the policy rate.
- **Minitaur lesson** ([1804.10332](https://arxiv.org/pdf/1804.10332)): high PD gains were stable in sim but oscillated on real motors. Hobby servos have *internal* PID, so model the servo's position loop and don't treat it as a torque source.

## 5. Trajectory optimisation for sizing and co-design

- **Fadini et al.** ([LAAS](https://gepettoweb.laas.fr/articles/fadini2022.html), ICRA 2021 / 2022) use a bi-level method: a genetic-algorithm outer loop over size, actuators and timing, with trajectory optimisation inside. The actuator model includes friction and Joule losses. They report up to 60% energy savings.
- **Dinev et al.** ([2103.04660](https://arxiv.org/abs/2103.04660)) differentiate through DDP (differential dynamic programming) to co-design morphology and actuators, applied to the Solo robot.
- **Opt2Skill** ([2409.20514](https://arxiv.org/abs/2409.20514)) uses Crocoddyl DDP trajectories with torque limits as **RL reference motions**. Dynamically feasible references beat kinematic-only ones.
- **Tooling (revised after [VERIFICATION](VERIFICATION.md#practical-feasibility-on-the-maintainers-machine)):** Pinocchio + Crocoddyl is the research standard, but **neither pip-installs on Windows**. Pinocchio is conda-forge only on win-64, and Crocoddyl has no Windows build at all. On the maintainer's Windows machine, use **casadi/IPOPT** (pip; a torque-limited collocation solve was tested) with dynamics from a small RNEA, plus **iLQR on MuJoCo via `mjd_transitionFD`** (tested). Keep Crocoddyl as an optional Linux/WSL path. MJWarp is not differentiable, so gradients come from casadi or MJX-on-CPU.
- **No published "actuator sizing recipe" exists.** Proposed workflow (to be gated):
  1. Run trajectory optimisation over a motion library: walk at 3 speeds, turn, squat, sit-to-stand, get-up front and back, push-recovery step.
  2. Record per-joint peak torque and speed, RMS torque, and the torque–speed cloud.
  3. Check them against the *measured* servo envelope plus a lumped thermal model.
  4. Wrap this in Monte Carlo over mass, COM, friction, voltage sag and servo unit-to-unit spread, and gate on the 95th percentile.
- **This replaces `oh size`'s quasi-static model** in the virtual-prototyping phase. `oh size` stays as the fast first pass.

## 6. End-to-end autonomous agent robotics: the honest state

- **Project Fetch Phase Two** ([Anthropic, 2026-06-18](https://www.anthropic.com/news/project-fetch-phase-two)): Claude Opus 4.7 in Claude Code completed the four shared quadruped tasks in **9 min 35 s, against 181 min (human team with Claude) and 361 min (human team without Claude)**.
  - Its failures: it defaulted to an outdated object-detection algorithm, and its closed-loop ball nudging was imprecise.
  - **Anthropic explicitly says low-level control was not tested.** Phase 1 ([2025-11-12](https://www.anthropic.com/research/project-fetch-robot-dog)) only had humans with and without Claude.
- **Takeaway:** Claude is very strong at the glue (SDKs, tooling, perception code, pipelines) and unproven at closed-loop physical control. That supports our split: agents build and run the pipeline, while **measurement and gates** decide what is true.

## Implications for Open Humanoid

1. **Simulator:** MuJoCo (CPU) for every check, and MJX via Playground-style envs for RL. Track MJWarp and mjlab, and skip Genesis and Isaac. Don't add an MCP server for sim.
2. **Virtual-prototyping phase** (new, between P1 and P3): measured actuator model → trajectory-optimised reference motions → torque, speed and thermal envelopes → Monte Carlo → **gate**. This should be the main "first try" lever for mechanics.
3. **The LLM proposes and code bounds it**, DrEureka-style, for DR ranges, gains and any tuned constant. Each proposal must cite a probe or measurement file.
4. **Gates (thresholds are starting points; calibrate them):** peak ≤ 70% of measured stall at operating voltage (p95 Monte Carlo); RMS ≤ continuous rating; actuator-model held-out tracking ≤ ~2°; simulated 10-minute walk stays below thermal shutdown; the policy survives push, latency and temperature extremes; and a no-DR ablation shows DR isn't masking problems.
5. **Ship identified params and pretrained policies**, as Open Duck does, so strangers can reproduce the robot without a GPU.
