# AGENTS.md: rules for every AI agent (and human) working in this repo

This file works with any agent (Claude, Codex, Cursor, local models). `CLAUDE.md` points here.

## What this project is

**Open Humanoid is a humanoid-building toolkit, not a single robot.** Adam (`variants/adam/`) is the first reference variant. Every tool, schema, and module must still work when someone asks for a 2 m, $100k, non-modular, LLM-free gutter-cleaning humanoid designed in SolidWorks. Read `docs/vision.md` once per session if you are doing design work.

## The seven rules

1. **The spec is the source of truth.** A variant's `spec.yaml` drives everything. If a number appears in CAD, sim, BOM, or firmware, it comes from the spec or from a generated file. Don't hard-code it elsewhere.
2. **Framework code is variant-agnostic.** Nothing in `openhumanoid/`, `schemas/`, `catalog/`, `cad/`, `sim/`, `software/core/`, or `prompts/` may assume Adam, a size, a budget, a CAD tool, or a part. Variant specifics go in `variants/<id>/`. If you need a new knob, add it to the schema with a default.
3. **Never hand-edit `generated/` folders.** Change the spec or the generator and re-run the `oh` command. Generated files carry a header saying what made them.
4. **Claim before you write.** Use `oh coord claim <task> --agent <name>` and commit the claim. Only touch paths your task lists. See `coordination/README.md`.
5. **Interfaces are frozen by default.** Changing `schemas/*`, `modules/INTERFACE.md`, `cad/EXPORT_CONTRACT.md`, or `software/core` public APIs needs a decision record in `docs/decisions/` and a schema version bump.
6. **Be honest about numbers.** Every catalog price/spec carries `verified:` and `source:`. Never present an estimate as verified. If sizing says "infeasible", report it. Don't tune assumptions until it passes.
7. **Checkpoint often.** Your context window will run out. After every phase gate, or whenever you'd hate to lose your state, update your task file and write a handoff (`oh coord handoff`). A fresh session must be able to resume from the repo alone.

## Where things go

| You are making… | Put it in |
|---|---|
| A new tool / analysis | `openhumanoid/<tool>.py` + CLI hook in `openhumanoid/cli.py` + test in `tests/` + doc in `docs/tools.md` |
| A part (motor, board, battery…) | `catalog/<category>/<id>.yaml` (schema: `schemas/catalog-part.schema.json`) |
| A reusable joint/limb/hand/attachment | `modules/<kind>/<id>/` with `module.yaml` (see `modules/README.md`) |
| Something only one robot uses | `variants/<id>/…` |
| A prompt others should reuse | `prompts/<area>/<name>.md` with the header block from `prompts/README.md` |
| A design decision | `docs/decisions/NNNN-title.md` (copy `0000-template.md`) |
| A unit of work for an agent | `oh coord new …` → `coordination/tasks/T-NNNN.md` |

## Running things

```bash
.venv/Scripts/python -m openhumanoid --help    # or `oh --help` after `pip install -e .`
.venv/Scripts/python -m pytest -q
```

## Token efficiency

- Read `README.md` / this file / the relevant workstream doc, **not the whole repo**.
- Prefer `oh` commands that print summaries over reading generated files.
- Delegate wide searches to a cheap subagent. Keep expensive models for design decisions.
- Pick an orchestration profile (`coordination/profiles/`) that matches the user's budget. Don't spawn parallel sessions the profile doesn't allow.

## Style

- Python ≥3.10, type hints, small modules, no heavy deps in the core (`pyyaml`, `numpy`, `jsonschema`). Sim/CAD deps are optional extras.
- Units: SI everywhere (m, kg, s, N·m, rad). Prices in USD with a date.
- Docs: write for a smart newcomer. Short sections, tables, and runnable commands.
