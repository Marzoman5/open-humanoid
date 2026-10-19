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
| `oh cad build <id>` | spec, sizing.json, catalog, `cad/style.yaml` | `cad/export/` (contract) | build123d template (`kinematics.template`), frame + shell, MJCF from the CAD |
| `oh cad check <id> [--min-mm3 20]` | same | `generated/cad_check.json` | part interference at the stand pose + printer-bed fit; exit 2 on problems |
| `oh render <id>` | sim or CAD model | `generated/renders/*.png` | front/side/¾/back + contact sheet for review gates |
| `oh catalog [--category actuator]` | catalog | — | `✓` verified, `~` estimate |
| `oh new <id> [--extends adam]` | `variants/_template` | `variants/<id>/` | |
| `oh coord status\|new\|claim\|set\|done\|release\|handoff\|resume` | `coordination/` | task / handoff files | protocol: `coordination/README.md`. `status --json`, `claim --session <id>`, `handoff --auto` |
| `oh gate [<gate-id> [variant]]` | spec, catalog, `pipeline/gates.yaml` | `variants/<id>/generated/gates/<gate>.json` | the only writer of gate records. `--smoke` (validate + size + stand, nothing recorded), `--status`. Exit 3 for placeholder gates. See `docs/harness.md` |
| `oh check provenance [variant]` | catalog, spec `provenance:` | — | warn-first; exit 2 only past the `G-provenance` thresholds |

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

## CAD pipeline (build123d, v0.1)

`oh cad build <id>` turns the spec into frame + shell CAD and writes everything `cad/EXPORT_CONTRACT.md` asks for. Code: `openhumanoid/cad/`.

| Module | What it does |
|---|---|
| `geom.py` | Generic helpers: servo envelope + horn from catalog `dimensions_mm` (shaft offset defaults to 25 % of the length; override with `actuator.shaft_offset_mm`), rounded plates, lofted **superellipse shells** fitted to real cross-sections of what they wrap, mass properties (OCC, per material density × fill), interference volume, bed fit. |
| `biped.py` | Template `biped_v1` for box servos. Every joint is a servo whose horn drives a U-yoke. Compound joints (hip yaw/roll/pitch, ankle pitch/roll) are gimbals with intersecting axes, so the CAD matches the sim's coincident joints. Intermediate gimbal stages become their own links (`hip_yaw_link_l`, …). Refuses non-box actuators with a clear error. |
| `export.py` | Link tree → `parts/*.step|stl`, `meshes/<link>.stl` (+ `<link>__<colour>.stl` for rendering), `mass_properties.yaml`, `robot.xml` (MJCF with the spec's joint names, CAD inertias, sole contact boxes), `manifest.yaml`. |

**Style.** Look-and-feel lives in `variants/<id>/cad/style.yaml`, merged over `biped.STYLE`: shell wall/gap, section exponent (2 = ellipse, ~3 = squircle), segment profiles (taper and swell along each limb), palette, which links get the dark accent, visor window, payload envelopes (battery, boards) and `arm_cant_deg` (fixed A-pose cant below the shoulder horn). Numbers that change kinematics should graduate to the spec via an ADR.

**How a shell is fitted.** At each station along a segment the template slices the parts the shell wraps, finds the superellipse that clears every cross-section corner, then takes the larger of that and the style profile (median scale). A shrink limit between stations keeps tapers smooth. Shell ends stop at joint **sweep radii** so moving yokes never hit a shell. This leaves the dark joint bands from the design language.

**Not yet:** shell split lines and snap/magnet mounts for printing, horn bolt patterns, joint-range sweep checks (stand pose only), and print-bed layout. Those land with R3 (T-0004) and its follow-ups.

## Design tooling (ADR 0010, v0.1)

Silhouette-first design tools: studio render rig, `profiles.yaml` massing, code-measured rubric, blind critic. Method, rubric bands, calibration caveats and validation evidence: [design-method.md](design-method.md). Code: `openhumanoid/design/`. Extra: `pip install -e ".[design]"`.

| Command (today: `python -m openhumanoid.design …`) | Does |
|---|---|
| `render <variant\|profiles.yaml\|mesh\|dir\|robot.xml> [--ref name=path] [--zebra]` | Clay + SSAO + 3-point light views, orthographic silhouettes with head-unit grid, equal-height reference overlays, review `sheet.png` → `variants/<id>/generated/renders/studio/` |
| `massing <profiles.yaml>` | Smooth massing STL from section stations (SDF smooth union + marching cubes) |
| `metrics <variant\|…> [--approved p.yaml] [--ref …]` | P1–P10, S1–S5, M1, hard-point checks → `generated/design_metrics.json` with PASS/FAIL per rubric band |
| `calibrate` | Runs the metrics over the reference/counter-example set → `docs/design-method/calibration.json` |
| `verdict a.json b.json --metrics m.json` | Combines design-critic reports (both presentation orders) with the fixed rules: UNCERTAIN = no-pass, consistent pairwise only, numeric hard gates override, 3-round cap |

`render.render(spec, studio=True)` is the library entry for `oh render <id> --studio`; wiring `design.cli.register` into `openhumanoid/cli.py` is left to the commander (see the T-0016 handoff). Known limitations: references are approximated (confidence low), no production shell library yet, M1 wall/clearance/ROM belong to the CAD geometry gate.
