# research/ai-engineering: how to do AI-driven hardware engineering (T-0011)

This question is about methods, not data: how are people actually using AI agents (Claude especially) to design complex hardware end-to-end, and what's the best way for Open Humanoid to do it? Researched 2026-10-19. Five parallel Sonnet search agents plus one industrial-design agent and one generative-3D agent did the searching. The synthesis, local prototypes and recommendations are by `ai-eng-research` (Opus). Actuator and robot benchmark *data* lives in other `research/` folders and isn't duplicated here.

**Start with [RECOMMENDATIONS.md](RECOMMENDATIONS.md).**

| File | Topic |
|---|---|
| [01-ai-cad.md](01-ai-cad.md) | LLM code-CAD benchmarks, failure modes, visual feedback, assemblies, commercial tools, the **"Adam" naming collision**, stack verdict |
| [02-ai-sim-robot-design.md](02-ai-sim-robot-design.md) | Eureka/DrEureka, Text2Robot, simulators, GPU RL timings, sim-to-real for servo robots, trajectory optimisation for sizing, Project Fetch |
| [03-agentic-workflows.md](03-agentic-workflows.md) | Anthropic guidance (harnesses, skills, hooks, subagents, evals), spec-driven development, multi-agent trade-offs, reward hacking, checkpointing |
| [04-hardware-as-code.md](04-hardware-as-code.md) | atopile/KiCad/WireViz, LLM circuit benchmarks, firmware, BOM/sourcing automation, power analysis |
| [05-open-source-robot-practice.md](05-open-source-robot-practice.md) | SO-100/LeRobot, Open Duck Mini, ToddlerBot, BHL, ODRI, InMoov, Prusa, K-Scale: what made them reproducible |
| [06-industrial-design-and-visual-review.md](06-industrial-design-and-visual-review.md) | **The "Roblox" fix:** silhouette-first design, code surfacing options, render rig, separate critic, acceptance rubric, installs |
| [07-challenging-our-assumptions.md](07-challenging-our-assumptions.md) | **Unanchored review:** toolkit vs robot-first, pipeline shape, the one-shot framing, four routes to sleek shells (code / human Onshape / gen-3D / concept images), a blind-critic experiment, what to drop |
| [prototypes/](prototypes/README.md) | Local tests: build123d loft shells (and a false-valid `offset()`), Gordon surfaces, SDF shells via manifold3d, pyvista clay and silhouette renders |

Evidence conventions: every claim carries a URL and date. **[UNVERIFIED]** / **[SECONDARY]** mark claims that rest on snippets or secondary sources. Many 2026 benchmark papers are preprints.
