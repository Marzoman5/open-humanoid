# Architecture

## Data flow

```
                    schemas/ (contracts)
                          │ validates
 catalog/ ──┐             ▼
            ├──► variants/<id>/spec.yaml ──(extends: parent)──► resolved spec
 modules/ ──┘             │
                          ▼
        ┌──────────── openhumanoid (oh CLI) ─────────────┐
        │ size  → generated/sizing.{json,md}             │
        │ bom   → generated/bom.{csv,md}                 │
        │ sim   → generated/sim/<id>.xml (+ smoke test)  │
        │ coord → coordination/tasks, handoffs           │
        └────────────────────────────────────────────────┘
                          │
   CAD backend (any) ─────┤ export contract (cad/EXPORT_CONTRACT.md)
   variants/<id>/cad/     ▼
                   variants/<id>/cad/export/  (STEP, STL, mass props, robot description)
                          │
                          ▼
              sim (CAD-derived model) → training → policies → software runtime
```

## Layers

| Layer | Folder | Depends on | Must not depend on |
|---|---|---|---|
| Contracts | `schemas/`, `*/INTERFACE.md`, `cad/EXPORT_CONTRACT.md` | nothing | anything |
| Framework | `openhumanoid/` | contracts, catalog format | any specific variant |
| Library | `catalog/`, `modules/` | contracts | variants |
| Variants | `variants/<id>/` | everything above | other variants (except via `extends`) |
| Runtime | `software/core`, `software/plugins` | contracts | CAD tools; plugins never required by core |

## Spec resolution

1. Load `variants/<id>/spec.yaml`.
2. If `extends:` is set, load the parent recursively and deep-merge (child wins; lists are replaced, not merged).
3. Apply schema defaults.
4. Validate against `schemas/spec.schema.json`.
5. Tools may *derive* values (e.g. a maximized height). Derived values are written to `generated/`, never back into the spec.

## Mass model and calibration loop

Before CAD exists, mass is estimated as: actuators (from catalog) + structure (`mass_model.structure_kg_at_1m × h³`) + electronics, compute, and battery (from the BOM). After CAD (P3), the export contract's mass properties replace the estimate. The calibration constant in the variant spec is then updated, which improves the *next* variant's estimate. That's how the toolkit gets smarter over time.

## Software runtime (planned, P6)

```
 plugins (optional):  rl_walking │ llm_mcp │ teleop │ scripted_motion │ mapping …
                      ───────────┴─────────┴────────┴─────────────────┴──────────
 core (always):       robot model ← spec │ joint control │ safety/limits │ state estimation
                      ─────────────────────────────────────────────────────────────
 HAL (one active):    sim (MuJoCo)  │  feetech bus  │  dynamixel bus  │  CAN (BLDC) …
```

The same plugin code runs against the sim or the real robot. You switch with one config value.
