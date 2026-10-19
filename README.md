# Open Humanoid

**A toolkit for making the humanoid robot *you* want: any size, any budget, any CAD tool, with or without an AI brain.**

Open Humanoid is not one robot. It is a pipeline plus a library:

```
  your requirements          the toolkit                          your robot
 ┌────────────────┐   ┌──────────────────────────────┐   ┌──────────────────────────┐
 │ spec.yaml      │──►│ size → select parts → budget │──►│ CAD + STL/STEP           │
 │ height, budget │   │ generate sim → train → test  │   │ MuJoCo model + policies  │
 │ priorities     │   │ source → document → build    │   │ BOM with live prices     │
 └────────────────┘   └──────────────────────────────┘   │ build guide + software   │
                                                         └──────────────────────────┘
```

Every robot is a **variant**: one folder under `variants/` with a `spec.yaml`. The tools read that spec and adapt to it. A $400 50 cm walker and a $100k full-size robot go through the same pipeline. The tools pick different parts, processes, and modules.

## Variants

| Variant | Status | Target | Notes |
|---|---|---|---|
| [**Adam**](variants/adam/) | concept | ≤ $400 all-in, max height for budget (~0.5 m), walking first, sleek | Reference variant, 3D printed, hobby serial-bus servos |
| Eve | planned | ~$2k, bigger | Will `extends: adam` and override what changes |

## Quick start

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -e ".[sim,cad,dev]"

oh validate adam                # check the spec against the schema
oh size adam                    # torque/speed sizing + actuator selection (+ max height for budget)
oh bom adam                     # bill of materials with price ranges
oh sim build adam               # generate a MuJoCo model straight from the spec
oh sim test adam                # physics smoke test (stands? falls? explodes?)
oh coord status                 # what are agents working on right now
```

## Make your own humanoid

1. `oh new my-bot` (or copy `variants/_template/`). Use `extends: adam` to start from Adam.
2. Edit `spec.yaml`: height, budget, priorities, which joints, CAD backend, plugins.
3. Give an AI agent [`prompts/oneshot/build-a-humanoid.md`](prompts/oneshot/build-a-humanoid.md). It runs the whole pipeline phase by phase and checkpoints as it goes, so it can stop and resume across sessions.

## Repo map

| Path | What lives there |
|---|---|
| `openhumanoid/` | Python framework + `oh` CLI. **Variant-agnostic.** |
| `schemas/` | JSON Schemas: the contracts (spec, catalog part, module) |
| `catalog/` | Parts database across all budget tiers, one YAML per part |
| `modules/` | Reusable mechanical/electrical/software modules (joints, limbs, hands, attachments) |
| `variants/` | Concrete robots. Each folder has its spec, CAD, generated outputs, and build guide |
| `cad/` | CAD backend adapters & the export contract (build123d, Onshape, SolidWorks, FreeCAD) |
| `sim/` | Simulation: MuJoCo tooling, training, scenarios |
| `software/` | Robot runtime core + optional plugins (RL policy, LLM/MCP, teleop…) |
| `prompts/` | Proven prompts: one-shot pipeline, sourcing, session handoff |
| `coordination/` | Multi-agent protocol: tasks, claims, handoffs, workstreams, token profiles |
| `docs/` | Vision, architecture, design language, decision records (ADRs) |
| `tests/` | Tests for the framework |

## For AI agents

Read [`AGENTS.md`](AGENTS.md) first. It has the rules, the repo map, and how to claim work without overwriting other agents.

## License

Software: MIT · Hardware (CAD, mechanical designs): CERN-OHL-S-2.0 · Docs: CC-BY-SA-4.0. See `LICENSE*`.
