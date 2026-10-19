# Vision

## One sentence

**Anyone can clone Open Humanoid, describe the humanoid they want, and get a designed, simulated, priced, buildable robot. Their AI agent does the heavy lifting with tools that are already proven.**

## What we are building

1. **A toolkit** (the framework). Sizing, part selection, budgeting, sim generation, training, sourcing, CAD export, testing, and docs generation. It's variant-agnostic and scale-agnostic.
2. **A library.** A parts catalog across every budget tier, plus reusable modules (joints, legs, hands, heads, attachments) that each declare where they're valid.
3. **Reference variants.** Real robots built with the toolkit that prove it works:
   - **Adam**: ≤ $400 all-in (actuators, structure, electronics, compute, battery, charger). As tall as the budget allows (~0.5 m). Walks first, runs if physics allows. Sleek, not toy-like. LLM integration comes later.
   - **Eve** (later): ~$2k, bigger, `extends: adam`.

## Principles

| Principle | What it means in practice |
|---|---|
| **Nothing is locked in** | Height, budget, DOF, CAD tool, compute, brain, manufacturing process, and modularity are all spec fields. The defaults are only defaults. |
| **Requirements in, parts out** | Variants state needs (height, budget, gaits). Tools pick parts from the catalog. Cheap parts are never hard-coded. |
| **Modular, including modularity itself** | `architecture.style: modular` gives swappable joint modules with a standard interface. `integrated` gives a monolithic, optimized design. The toolkit supports both. |
| **CAD-agnostic** | Design in build123d (code, AI-native), Onshape, SolidWorks, or FreeCAD. Every backend meets one **export contract** (STEP, STL, mass properties, robot description). The pipeline consumes exports, never native files. |
| **Sim-first** | Every variant has a MuJoCo model from day one, generated from the spec before CAD exists and replaced by CAD-derived models later. Walking is learned in sim. |
| **Optional brains** | The software core is the hardware abstraction, joint control, safety, and state estimation. RL locomotion, an LLM/MCP agent interface, teleop, and scripted motion are **plugins**. |
| **Honest numbers** | Every price and spec carries `verified` and `source`. Infeasible stays infeasible. |
| **Built for humans and AI** | Small files, schemas, runnable commands, proven prompts, and checkpointed workflows that survive context limits and run solo or as a swarm. |

## The pipeline (what "one-shot a humanoid" means)

```
P0 Intake        spec.yaml complete & valid
P1 Sizing        torques/speeds → actuator choice → max size for budget → feasibility report
P2 Kinematic sim spec → MuJoCo model → physics smoke test
P3 Mechanical    modules/CAD in chosen backend → export contract → mass-model calibration
P4 CAD sim       CAD-derived MJCF/URDF replaces primitive model
P5 Locomotion    train walking (then running) policies in sim, domain-randomized
P6 Electronics   wiring, power budget, bus layout; software core bring-up
P7 Sourcing      BOM with live prices via the sourcing prompt; build guide
P8 Build & test  physical bring-up scripts, calibration, sim-to-real
P9 Plugins       LLM/MCP, manipulation, mapping, attachments…
```

Each phase has a **gate** (a command or check that must pass) and a **checkpoint** (task + handoff update). An agent can run all of it in one long session, or it can be split across many sessions and agents. The orchestration profile decides that.

## Roadmap of toolkit capabilities

| Capability | Status |
|---|---|
| Spec schema + inheritance (`extends`) | ✅ v0.1 |
| Review renders (`oh render`) | ✅ v0.1 |
| Parts catalog (multi-tier actuators, compute, power) | ✅ v0.1, prices unverified |
| Sizing & actuator selection, max-height-for-budget | ✅ v0.1 (quasi-static + dynamic factors) |
| BOM roll-up | ✅ v0.1 |
| Spec → MuJoCo generator + smoke test | ✅ v0.1 |
| Multi-agent coordination CLI | ✅ v0.1 |
| One-shot, sourcing, and handoff prompts | ✅ v0.1 |
| build123d module/CAD pipeline + export contract tooling | planned (P3) |
| Onshape / SolidWorks / FreeCAD export adapters | planned |
| RL walking/running training pipeline (MuJoCo/MJX) | planned (P5) |
| Software core (servo bus HAL, safety, state estimation) | planned (P6) |
| Live price scraping / sourcing automation | planned (P7) |
| Gripper/hand design + grasp physics | planned (P9) |
| LLM/MCP plugin | planned (P9) |
| Mapping / SLAM plugin | planned (P9) |
