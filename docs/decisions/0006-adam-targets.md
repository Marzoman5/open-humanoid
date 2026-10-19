# 0006: Adam targets

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** variant:adam

## Decision
- Budget: **$400 all-in** (actuators, structure/filament, fasteners, electronics, onboard compute, battery, charger). Printer and tools are excluded.
- Height: **maximize within budget**, search range 0.40–0.75 m. Expected about 0.5 m.
- Priorities: walking → motion/expressiveness → aesthetics (sleek) → running (stretch) → LLM (later plugin).
- Architecture: modular joints, frame + shell.
- Manufacturing: FDM, 220×220×250 mm bed minimum.
- CAD backend: build123d (AI-authored). Maintainer may re-surface shells in Onshape/SolidWorks.
- Onboard compute runs the locomotion policy. The LLM, when added, runs off-board.
- Successor: **Eve** (~$2k, larger) will `extends: adam`.

## Note (2026-10-19)
The name "Adam" collides with an AI-for-CAD startup (adam.new / CADAM). The maintainer chose to keep it; revisit before public release.

## Amendment (2026-10-19)
Budget raised to **$550 all-in**. Capabilities expanded to walk, wave, dance, light table-height pickup, and interactive head/torso. Full list in `variants/adam/requirements.md`, which supersedes the budget and capability lines above. The joint layout is decided by the concept loop (ADR 0012), not by the quick sizing tool.
