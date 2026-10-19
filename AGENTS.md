# AGENTS.md: rules for every AI agent (and human) working in this repo

This file works with any agent (Claude, Codex, Cursor, local models). `CLAUDE.md` points here.

## What this project is

**Open Humanoid is a humanoid-building toolkit, not a single robot.** Adam (`variants/adam/`) is the first reference variant. Every tool, schema, and module must still work when someone asks for a 2 m, $100k, non-modular, LLM-free gutter-cleaning humanoid designed in SolidWorks. Read `docs/vision.md` once per session if you are doing design work.

## The rules

Two rules need your judgment, because nothing can check them for you:

1. **The spec is the source of truth.** A variant's `spec.yaml` drives everything. If a number appears in CAD, sim, BOM, or firmware, it comes from the spec or from a generated file. Don't hard-code it elsewhere.
2. **Framework code is variant-agnostic.** Nothing in `openhumanoid/`, `schemas/`, `catalog/`, `cad/`, `sim/`, `software/core/`, or `prompts/` may assume Adam, a size, a budget, a CAD tool, or a part. Variant specifics go in `variants/<id>/`. If you need a new knob, add it to the schema with a default.

The rest are enforced by hooks and gates ([docs/harness.md](docs/harness.md)). Read the pointer, and don't try to route around the check; a blocked action says what to do instead.

3. **`generated/` is write-protected** (hook). Change the spec or generator and re-run the `oh` command.
4. **Claim before you write:** `oh coord claim <task> --agent <name> --session <id>` and commit the claim (`coordination/README.md`). The hook warns on writes outside your claimed `paths`.
5. **Interfaces and gate thresholds are frozen** (hook): `schemas/*`, `modules/INTERFACE.md`, `cad/EXPORT_CONTRACT.md`, `pipeline/`. Changing one (or a `software/core` public API, not hook-checked) needs an ADR in `docs/decisions/` and a task whose `paths` list the file.
6. **Numbers carry provenance** (`oh check provenance`): every catalog part has `verified:` and `source:`, every tuned spec constant has a `provenance:` entry. Never present an estimate as verified; if sizing says "infeasible", report it, don't tune assumptions until it passes.
7. **Done means a PASS gate record at HEAD** (`oh gate --status`; the Stop hook blocks "done" without it). Checkpoint at every phase gate with a real handoff (`oh coord handoff`); hooks only re-inject state and write a stub. A fresh session must be able to resume from the repo alone.

**Self-correction:** when a mistake is caught, add a row to [`coordination/LESSONS.md`](coordination/LESSONS.md) and enforce it in a hook, gate, test, skill, or prompt. Plans and results are challenged by the read-only `challenger` agent at wave boundaries and before review stops ([docs/pipeline.md](docs/pipeline.md)). Answer its rows in writing.

## Where things go

| You are making… | Put it in |
|---|---|
| A new tool / analysis | `openhumanoid/<tool>.py` + CLI hook in `openhumanoid/cli.py` + test in `tests/` + doc in `docs/tools.md` |
| A part (motor, board, battery…) | `catalog/<category>/<id>.yaml` (schema: `schemas/catalog-part.schema.json`) |
| A reusable joint/limb/hand/attachment | `modules/<kind>/<id>/` with `module.yaml` (see `modules/README.md`) |
| Something only one robot uses | `variants/<id>/…` |
| A prompt others should reuse | `prompts/<area>/<name>.md` with the header block from `prompts/README.md` |
| A design decision | `docs/decisions/NNNN-title.md` (copy `0000-template.md`) |
| A unit of work for an agent | `oh coord new …` → `coordination/tasks/T-<yyyymmdd>-<hex>.md` |
| A pipeline gate | `pipeline/gates.yaml` + a check in `openhumanoid/gate.py` (ADR task; hook-protected) |

## Running things

```bash
.venv/Scripts/python -m openhumanoid --help    # or `oh --help` after `pip install -e .`
.venv/Scripts/python -m pytest -q
oh gate --smoke adam                           # validate + size + sim stand, about a second
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
