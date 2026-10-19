# Tools reference

All tools are subcommands of `oh` (or `python -m openhumanoid`). Each prints a short summary and writes full results to `variants/<id>/generated/`.

| Command | Reads | Writes | Notes |
|---|---|---|---|
| `oh validate <id>` | spec (+ parents), catalog | — | JSON Schema + semantic checks |
| `oh size <id>` | spec, catalog | `generated/sizing.{json,md}` | see the sizing model below |
| `oh bom <id>` | spec, sizing.json, catalog | `generated/bom.{csv,md}` | typical/low/high totals, unverified count |
| `oh sim build <id>` | spec, sizing.json | `generated/sim/<id>.xml` | primitive MJCF, joint names follow the spec |
| `oh sim test <id> [--json]` | sim model | — | stand-hold smoke test, torque usage per actuator |
| `oh sim view <id>` | sim model | — | interactive MuJoCo viewer |
| `oh render <id>` | sim or CAD model | `generated/renders/*.png` | front/side/¾/back + contact sheet for review gates |
| `oh catalog [--category actuator]` | catalog | — | `✓` verified, `~` estimate |
| `oh new <id> [--extends adam]` | `variants/_template` | `variants/<id>/` | |
| `oh coord status\|new\|claim\|set\|done\|release\|handoff\|resume` | `coordination/` | task / handoff files | protocol: `coordination/README.md` |

## Sizing model (v0.1)

1. **Geometry** = `body.proportions × height`.
2. **Mass** = actuators (catalog) + structure (`structure_kg_at_1m × h³`, split across segments by `body.STRUCT_SHARE`) + fixed BOM parts + electronics. This feeds back into actuator choice (fixed-point iteration).
3. **Per-joint static torque** for single support in the gait's crouch (`stance_knee_flex_deg`):
   - knee / hip pitch: supported mass × g × thigh × sin(flex/2)
   - ankle pitch: (M − foot) × g × 0.4 × foot length
   - hip roll: (M − leg) × g × hip_width/2 · ankle roll: (M − foot) × g × foot_width/2 · hip yaw: 0.25 × hip roll
   - arms: arm mass × g × half arm length (arm horizontal) · elbow: forearm only
4. **Checks** against each actuator: continuous (static × SF) · peak (static × dynamic factor × SF ≤ peak_fraction × stall) · speed (π·f·A × margin ≤ no-load speed × (1 − swing load/stall)).
5. **Selection:** cheapest catalog actuator passing all required gaits, filtered by feedback, voltage, and family. Uniform mode uses one model for all joints.
6. **Height search** (`mode: maximize`): sweep min→max with required joints, keep the tallest that fits the cap, report what blocks the next step up, then add optional joints by order while they still fit.

Known limitations: there's no thermal model, no inertial/acceleration terms beyond the dynamic factor, no linkage/transmission ratios, and the arm speed requirement is a constant. Improve these with evidence (`prompts/analysis/validate-sizing.md`).
