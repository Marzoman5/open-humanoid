# Getting started

This guide takes you from a fresh clone to your own humanoid's first simulation in about 15 minutes. You need Python 3.10+ and git. No GPU is needed until locomotion training.

## 1. Install

```bash
git clone <this repo> open-humanoid && cd open-humanoid
python -m venv .venv
.venv/Scripts/activate            # Windows. Linux/macOS: source .venv/bin/activate
pip install -e ".[sim,cad,dev]"
oh --help
pytest -q                         # should be all green
```

## 2. Look at the reference robot (Adam)

```bash
oh validate adam      # spec + catalog are valid
oh size adam          # how tall can it be for $400? which servos? can it walk/run?
oh bom adam           # parts list with price ranges
oh sim test adam      # does the model stand in physics?
oh render adam        # pictures: variants/adam/generated/renders/sheet.png
oh sim view adam      # interactive 3D viewer (drag to rotate, double-click to select)
```

Read `variants/adam/generated/sizing.md`. It explains every number and what limits the design.

## 3. Make your own

```bash
oh new my-bot --extends adam      # or without --extends to start from toolkit defaults
```

Edit `variants/my-bot/spec.yaml`. Common changes:

| I want… | Change |
|---|---|
| a bigger robot | `body.height_m` (a number, or `{mode: maximize, min, max}`) and `goals.budget_usd` |
| a fixed size, cheapest parts | `height_m: 0.8` and a generous budget. The sizer picks the cheapest parts that work |
| brushless motors / a 48 V system | `actuation.supply_voltage_v: [44, 50]`, `require_feedback: torque` |
| no arms / extra joints | edit `kinematics.joints` (set `priority: optional` to add them only if the budget allows) |
| running | `locomotion.run.required: true`. The sizer will tell you if it's physically possible |
| non-modular, optimized parts | `body.architecture.style: integrated` |
| no shells (lab build) | `body.architecture.shell: false` |
| design in Onshape/SolidWorks | `cad.backend: onshape` and meet `cad/EXPORT_CONTRACT.md` |
| no AI brain | leave `llm_mcp` out of `software.plugins` |

Then re-run `oh validate my-bot && oh size my-bot && oh bom my-bot && oh sim test my-bot && oh render my-bot`.

If sizing says **infeasible**, the report names the joint and the limit (continuous torque, peak torque, or speed). Fixes: a bigger budget, a different voltage, fewer joints, a slower gait, or a stronger part in `catalog/`.

## 4. Let an AI agent do the rest

Open your agent (Claude Code, etc.) at the repo root and paste [`prompts/oneshot/build-a-humanoid.md`](../prompts/oneshot/build-a-humanoid.md) with the blanks filled in. It works phase by phase: sizing, sim, CAD, walking, electronics, sourcing, build guide. It **stops at review gates** so you can see renders and numbers and approve them, and it checkpoints so it can resume in a new session when its context fills.

- Small token budget: profile `solo`, `Run until: P3`, then continue next time with `prompts/session/resume.md`.
- Lots of budget: profile `team` or `swarm`. Workstreams run in parallel, coordinated through `oh coord`.

## 5. Contribute back

- A new part goes in `catalog/<category>/<id>.yaml`. Mark it `verified: true` only with live vendors plus a datasheet.
- A reusable joint/hand/attachment goes in `modules/<kind>/<id>/` with `module.yaml`.
- A new tool goes in `openhumanoid/` + `tests/` + `docs/tools.md`. It must work for every variant, not just yours.
- Read `AGENTS.md` (applies to humans too) and `coordination/README.md` before working alongside agents.
