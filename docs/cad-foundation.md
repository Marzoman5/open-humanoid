# CAD foundation: parts that fit and work by construction

*Task T-20261019-2426 · `openhumanoid/cad/` · research RECOMMENDATIONS C2-C5, A3, F2 · ADR 0002, 0009-0012.*

Agents write CAD that **runs** far more often than it is **right** (research/ai-engineering/01-ai-cad.md). Lofts, shells and booleans fail
silently, mates and clearances are guessed, and a render can't measure anything. This layer makes the failure modes impossible or loud:

1. every purchased part is a **component** with functional features and a provenance record for every dimension;
2. every joint is fixed in **`interfaces.yaml`** before any part geometry exists, and parts are checked against it numerically;
3. every clearance, wall and hole comes from **`dfm.yaml`** (sourced, with a printer-calibration path), never from a literal;
4. agents compose **helpers** (`servo_pocket`, `horn_mount`, `insert_boss`, ...) that return a checked result instead of raw booleans;
5. a **gate** (solid, STEP round trip, STL, interfaces, walls, bed, interference, clearance), a **range-of-motion sweep** and an
   **assembly-access check** run on the result;
6. a ~25 min **fit gauge**, generated from the same code, is printed before any real part.

This is **tooling plus one validation leg, not Adam's final design.** Design freeze happens after the concept (R1) and silhouette (R2a)
reviews. Everything marked ESTIMATE below is an assumption the fit gauge or a caliper must confirm.

## Method: interface first, frame inside out, shells outside in

| Step | What | Tool |
|---|---|---|
| 1. Interfaces | joint axes, servo placement/orientation, horn and idler interfaces, ROM, keep-outs, mount patterns | `python -m openhumanoid.cad interfaces <variant>` -> `variants/<id>/generated/interfaces.yaml` |
| 2. Frame, inside out | servo housings and brackets around the servos, built only from helpers + interface frames | `servo_housing`, `servo_pocket`, `horn_mount`, `idler_seat`, `insert_boss`, `screw_clearance`, ... |
| 3. Gate every part | solid, STEP round trip, STL, interface expectations, wall, bed | `geometry_gate.check_part` / `... check` |
| 4. Check the assembly | interference, clearance, ROM sweep, assembly order and tool access | `geometry_gate.check_assembly`, `rom`, `access` |
| 5. Fit gauge | print the 25 min gauge, calibrate `dfm.yaml` | `python -m openhumanoid.cad gauge` |
| 6. Shells, outside in | (after R2a) cosmetic shells from `profiles.yaml` that wrap the frame's keep-outs | `loft_shell`, `keepout` |

Rule of thumb: **change the layout, not the part**. If a check fails, ask whether the interface (stand-off, side, ROM) was wrong before
patching geometry; the validation leg below was fixed that way more often than by patching geometry.

## Layout of the package

| Module | Role |
|---|---|
| `components/` + `components/data/*.yaml` | Parametric purchased parts. Servo data lives in `catalog/actuators/*.yaml` (`mechanical:`), everything else in `components/data/`. Every number is `{v, src, conf}` |
| `dfm.yaml`, `dfm.py` | Design-for-manufacture rules and the thin-wall analysis |
| `core.py` | `FeatureResult`, `Site`, `apply`, guarded `safe_cut` / `safe_union`, `overlap_volume`, `min_distance` |
| `features.py`, `housing.py` | The helper primitives and the composite `servo_housing` |
| `interfaces.py` | Generator and consumer API of `interfaces.yaml` |
| `assembly.py`, `geometry_gate.py`, `rom.py`, `access.py` | Assembly container, gate, ROM sweep, assembly access |
| `gauge.py` | Fit gauge generator and result reader |
| `render.py` | Clay views of an assembly (evidence images) |
| `cli.py` / `__main__.py` | `python -m openhumanoid.cad <command>` (the commander wires `oh cad ...` and `pipeline/gates.yaml`) |
| `geom.py`, `biped.py`, `export.py` | The earlier spec-driven biped template (unchanged API; `Part` gained optional fields) |

Units mm. World frame x forward, y left, z up. Installed hardware has its origin on the host surface with +z pointing OUT of the host; a
servo's frame has its origin on the output axis at the horn-face plane, +z out of the horn face, +x toward the long end of the body.

## 1. Component library

`from openhumanoid.cad.components import get` then `get("sts3215")`, `get("sts3250")`, `get("horn-25t")`, `get("bearing:MR105ZZ")`,
`get("screw:M3x8")` (`M3x8L` = low head), `get("insert:M3")`, `get("magnet:6x3")`, `get("rpi-zero-2w")`, `get("rpi-5-4gb")`,
`get("waveshare-bus-servo-adapter")`, `get("buck-5v-5a")`, `get("imu-bno085")`, `get("lipo-3s-2200")`, `get("xt60")`,
`get("power-switch-xt60")`. `python -m openhumanoid.cad components` lists them with their estimate counts.

A `Component` has `.shape`, `.frames` (named `Location`s: `axis`, `horn_seat`, `back_axis`, `cable_exit`), `.holes` (case mounting holes),
`.keepout` (body plus plug room), `.params`, and `.provenance`. `component.estimates()` lists every dimension that is only an engineering
estimate. For the servo, `params["case_shape"]` is the static case and `params["shaft_shapes"]` the spline and back stub that turn with the output.

**Provenance and confidence.** `standard` (ISO/DIN) > `datasheet` > `vendor` > `derived` > `estimate`. What is established and what is not:

| Established (vendor listings, several agree) | ESTIMATE (confirm with the gauge or calipers) |
|---|---|
| STS3215/3250 body 45.2 x 24.7 x 35.0 mm; output spline 25T, OD 5.9 mm; Feetech round horn 20 mm; 3-pin 5264 connector; Raspberry Pi Zero 2 W and Pi 5 outlines and hole patterns (Raspberry Pi mechanical drawings); ISO 4762 / DIN 7984 / ISO 273 / DIN 974-1 screw data; ISO 15 bearing sizes; BNO085 (Adafruit) outline | **axis position along the body (12 mm from the near end); output boss height and diameter; spline protrusion; back-shaft (dual-axis) size and protrusion; case mounting hole positions and thread; connector face and plug length; horn bolt circle, hole size, thickness; horn float; Waveshare adapter and buck module outlines and holes; the power switch** |

The vendor drawings (`ST3215-2D.zip`, `ST3215-3D.zip` on the Waveshare wiki) could not be opened in this environment and **no vendor CAD
file was used or committed**. The gauge tiles G1-G3 exist to replace the estimates by measurements. See `THIRD_PARTY.md` (SO-ARM100 was read
for its licence only; no file was reused).

## 2. `interfaces.yaml` generator

```bash
python -m openhumanoid.cad interfaces adam        # reads variants/adam/spec.yaml + variants/adam/cad/layout_v2.yaml
```

Inputs: the spec (axes, ranges, proportions, bed), optional sizing, and a **layout file** (`variants/<id>/cad/layout*.yaml`) holding the
packaging decisions the concept loop is meant to produce (schema in the module docstring of `interfaces.py`). `layout_v2.yaml` is a
**stand-in** for the 22-DOF humanoid_v2 layout (12 leg + 8 arm + 2 neck DOF, STS3215 throughout, the knee switchable to STS3250 through
`actuators.overrides`). Replace it when the concept loop freezes a layout; the schema does not change.

Output per joint: axis line (origin + direction), ROM (the layout range and the spec range side by side, with a note when CAD limits it),
actuator id and placement (origin, `z_dir` = horn direction, `x_dir` = long end), horn seat and bolt pattern, back (idler) axis and bearing
seat, case-hole positions, servo corner radius, keep-out. The generator runs an analytic pre-check: **servo bodies overlapping at the zero
pose are reported before any part exists** (it caught two of my own arm layouts). The parts consume it through `interfaces.load(spec)`
(`servo_loc(joint)`, `axis_origin(joint)`, `link_origin(link)`), and the gate checks the parts against it (`interface` expectations: the
horn seat a part was built for must equal the file; this caught a stale 0.3 mm horn-float mismatch).

## 3. DFM rules (`dfm.yaml`)

Every rule carries `src` and `conf`; rules marked `tune: true` are printer calibration values the fit gauge measures.

| Rule | Value | Source |
|---|---|---|
| Fit clearance per side: press / slip / sliding / rotating / loose | 0.05 / 0.15 / 0.25 / 0.35 / 0.50 mm | FDM practice (tune with G6) |
| Hole compensation (diameter added) | +0.15 (<= 3.5), +0.20 (<= 10), +0.25 mm | FDM practice |
| Minimum wall: cosmetic / structural / load path | 0.8 / 1.6 / 2.4 mm | 2 / 4 / 6 perimeters at 0.4 nozzle |
| Wall around a heat-set insert | >= 2.0 mm; pocket depth = insert length + 1 mm | research/methods/d section 5 |
| Bearing seat | OD + 0.1 mm, depth = width, shoulder 1.6 mm, wall 2.0 mm | FDM practice (G5) |
| Overhang / bridge | 45 deg; 12 mm (PLA 20) | FDM practice |
| Load paths | along XY; Z strength = 0.78 / 0.73 / 0.78 / 0.73 / 0.60 of XY for PLA / PLA+ / PETG / ASA / CF-nylon; safety factor 3 on Z; cyclic stress < 10 % of UTS | research/methods/d + `print_materials.yaml` (a test asserts the table has not drifted) |
| Snap fit | allowable strain 2.0 % (PLA, PETG), 1.5 % others; L/t >= 6; beam length in the XY plane | derived from vendor elongation x 0.4 |
| Magnet 6x3 | pocket +0.2 mm dia, +0.2 mm deep, 0.6 mm cover (pause the print), wall 1.2 mm | FDM practice (G7) |
| Bed | spec bed minus 5 mm margin per side: 210 x 210 x 245 for the 220 x 220 x 250 bed; dowel split (3 mm, 8 mm deep, 2 per cut) | FDM practice |
| Moving gap between parts that move relative to each other | >= 1.0 mm (rotating clearance 0.7 + 0.3 backlash) | derived |
| Tool corridor | stubby driver: M2 25, M2.5 28, M3 30 mm free along the screw axis; diameter 6/7/8 mm | estimate |

## 4. Helpers

All helpers return a `FeatureResult` (adds, cuts, fastener `Site`s, keep-outs, notes) in their own frame; `at=` places them;
`core.apply(base, *features)` makes all additions first and all cuts second through guarded booleans that raise `CadOpError` instead of
returning a silently wrong part (a feature that floats free, a cut that did nothing, a union that dropped a tangent cylinder).

| Helper | Does | Raises when |
|---|---|---|
| `servo_pocket(actuator, clearance, entry, lip)` | pocket for the servo envelope grown by the fit clearance, entry from any side, far-end retaining lip, cable slot, servo keep-out | - |
| `servo_housing(actuator, ...)` | block + pocket + lip + cover with two insert-held counterbored screws + optional printed idler pin. `Housing.build(loc, adds=[...])` unions bracket bodies **before** the pocket is cut | thin cover for the stub relief |
| `horn_mount(actuator, plate_t, mode)` | centre screw and the horn's bolt-circle holes, counterbored, in the horn-seat frame; `flat` or `recessed` | plate thinner than counterbore + head gap + 1.6 mm floor |
| `idler_seat(bearing, plate_t)` | press-fit bearing seat + race-clearing through hole + chamfer + optional boss | plate thinner than seat + shoulder |
| `insert_boss(thread, boss_h)` | heat-set insert pocket (hole, depth, chamfer) and optional boss with the wall rule | boss leaves < 1.2 mm floor |
| `screw_clearance`, `counterbore` | ISO 273 hole + DFM compensation + DIN 974-1 / DIN 7984 counterbore + a `Site` with its tool corridor | - |
| `cable_channel(path, d)` | polyline of capsules (no sweeps), also a keep-out | fewer than two points |
| `keepout(obj, margin, mode)` | component keep-out or bbox / checked `offset` | - |
| `split_for_bed(shape, bed)` | recursive cut at the smallest section, dowel pockets on both faces | no room for dowels |
| `magnet_boss(spec, access)` | pocket (`pause`: closed void under a cover; `open`) + optional boss | - |
| `loft_shell(sections, wall)` | outer - inner loft, verified valid, one solid, volume < outer | section smaller than 2 x wall |
| `screw_length_for`, `bolt_circle` | stock screw length; module-interface bolt patterns (S class: 4 x PCD 32) | - |

## 5. Geometry gate

`geometry_gate.check_part` runs, per part: (1) valid single solid; (2) **STEP export, re-import, validity, volume and bbox unchanged**;
(3) **watertight STL** with consistent winding and volume within 1 % of the B-rep (trimesh); (4) the part's `meta["expect"]` list against
`interfaces.yaml` (bbox/size, `void_cylinder` hole probes, `contains_bbox`, solid/void points, `interface` values); (5) minimum wall by
voxel opening (resolution 0.25 mm: a nominal wall passes, one 0.3 mm under fails); (6) bed fit in any axis-aligned orientation.
`check_assembly` adds pairwise interference (OCC, mesh fallback) and **minimum clearance**: pairs on different links must stay 1.0 mm
apart, same-link pairs 0.3 mm, designed contacts are declared with `asm.allow(a, b)` and designed gaps with `asm.fit(a, b, gap)`.

## 6. Range-of-motion sweep

`rom.sweep_all(asm, step_deg, gap_check=True)` steps each joint through its range (only part pairs that move relative to each other are
tested), bisects the onset angle to 0.25 deg and reports `limit_pos` / `limit_neg` plus the colliding pair. `rom.check_pose(asm, "squat")`
checks the coupled poses (`squat`, `deep_squat`, `step_forward`, `wave`, `pickup`, `split_stance`, `twist`; fractions of each joint's range,
ankle levelled). The leg has no arms, so `wave` and `pickup` are exercised only by their unit definitions.

## 7. Assembly access

`access.analyse(asm)` derives an assembly **order** from two kinds of constraint: a straight insertion path (translation along a world axis or
a screw axis, 90 mm, manifold3d meshes) against what is already assembled, and a free **tool corridor** along every screw at the moment it is
installed. It builds a precedence graph, topologically sorts it, simulates the order, and reports: the step list with the move direction and the
screws installed at each step, a **subassembly tree** (each link also tested as a bench subassembly), `unreachable_screws` (the owner or its mate
covers the corridor), `stuck_parts` and `cyclic_parts` (no valid order), and `serviceability` (screws that can no longer be reached once the
robot is assembled). Assumptions: pure translations, inserts are prep steps, a screw is installed as soon as both parts exist.

## 8. Fit gauge

```bash
python -m openhumanoid.cad gauge --out variants/adam/cad/fit-gauge     # committed: gauge.stl / .step / gauge_key.md / gauge.json
```

Eight tiles, 24 cm3, about 29 min (estimate) in PETG/PLA+ at 0.2 mm, 15 % infill; see `docs/cad-foundation/fit_gauge.png`:
**G1** the real servo pocket cross-section (L x W, corner radius, cable slot) the servo must drop through; **G2** the 35 mm height and 24.7 mm
width slots; **G3** a horn probe plate with four radial slots (r = 4..9 mm) to find the horn's real bolt circle; **G4** M3 insert holes at
-0.2..+0.2 mm; **G5** bearing seats at -0.1..+0.3 mm; **G6** a clearance ladder (holes for a 5.0 mm peg at 0.05..0.40 mm per side, generated with
the same hole recipe as the real parts) plus the peg bar; **G7** magnet pockets; **G8** wall steps 0.8-2.4 mm and bridges 6/12/18 mm.
`gauge.read_results({...})` turns the readings into PROPOSED `dfm.yaml` / `hardware.yaml` values (it never edits them).

## 9. Validation on a real piece: one Adam leg frame

`variants/adam/cad/leg_v2.py` builds hip-yaw bracket to foot of the representative 22-DOF layout using only the library, the helpers and
`interfaces.yaml` (no raw servo dimension appears in it). Result: **6 STS3215, 6 horns, 3 MR105ZZ bearings, 17 printed parts totalling 469 cm3
(about 0.21 kg at 35 % effective fill, plus 0.33 kg of servos), largest part 164 x 75 x 52 mm (fits the bed whole), 56 screws and 26
heat-set inserts.** The gate, ROM sweep (with the 1 mm moving gap) and access check all pass; evidence in `variants/adam/cad/validation/*.json`
and `docs/cad-foundation/` (clay views, a section through the servo mid-plane, the squat pose).

What each check found, and how it was fixed:

| # | Check | Finding | Fix |
|---|---|---|---|
| 1 | interfaces pre-check | arm servos of the first layout overlapped by 19 000 mm3 | rearranged the shoulder stand-offs in `layout_v2.yaml` |
| 2 | gate: wall | covers 3.2 mm thick leave 0.6 mm under a low-head counterbore; the cover counterbore sat 0.75 mm from the end and side edges | cover 4.4 mm; `servo_housing` now sizes the far wall and the screw position from the counterbore (end wall 9.7 mm) |
| 3 | gate: wall | horn plates 3.2 mm leave a 0.6 mm skin | `horn_mount` rule: plate >= counterbore + head gap + 1.6 mm; plates 4.3 mm |
| 4 | gate: wall | bearing seat shoulder 1.0 mm (the DFM rule contradicted the structural wall) | DFM shoulder 1.6 mm, idler plate 5.6 mm |
| 5 | gate: wall | idler plate counterbores 0.75 mm from the plate edge and corner arc | idler plate 30 mm wide, small tongue corner radius |
| 6 | gate: clearance | the spline and back stub were modelled as static, 0.5 mm from a rotating plate | servo split into case + shafts (shafts turn with the child link); horn float 0.3 mm modelled |
| 7 | gate: interfaces | `interfaces.yaml` horn seat 0.3 mm off the part (stale constant) | generator reads the component frame; a test pins it |
| 8 | ROM | hip extension stopped at 29 deg, knee flexion at 115 deg, ankle pitch at +9/-12 deg, ankle roll at 28.6 deg, squat and step poses clashed | forks' web radius per joint (24 hip, 30 knee), rounded plate corners, thin roll plate + bridge above the fork's swept radius, roll axis moved 28 mm below the pitch axis, S2 stand-off 44 mm, ankle height 45 -> **66 mm** |
| 9 | ROM | what remains is geometry: heel meets glute at 118 deg knee flexion; hip extension limited by the roll plate; ankle dorsiflexion by the roll servo housing | ranges recorded as **CAD-limited** in `interfaces.yaml` (`rom_spec_deg` keeps the spec value): hip pitch [-110, 40], knee [0, 115], ankle pitch [-60, 25]. These go back to the concept loop |
| 10 | access | a one-piece fork with a printed pin on the cover and a closed bearing seat **cannot be assembled** (precedence cycle) | idler plate is a separate part bolted on last (4 x M3 into inserts in the beam); the pin stays on the cover |
| 11 | access | the roll plate's horn screws sat behind its own pitch-servo housing (tool corridor blocked by the owner) | roll bracket split into `roll_plate` (horn screws first) and `roll_cradle` bolted on afterwards through its end wall (M3x35) |
| 12 | access | every shaft piece reported "stuck" | shafts are integral with the servo for planning |

Design facts the leg established for the concept loop (all consequences of 35 mm-wide servos on intersecting axes):

* the hip gimbal needs about **106 mm above** and **84 mm behind** the hip axis (yaw servo above, roll servo behind); the spec's pelvis proportion is 36 mm;
* **ankle height 66 mm** (0.11 h) instead of the spec's 0.045 h, to hold a roll servo behind a pitch fork and clear +-30 deg of roll;
* pitch joints as forks are 52 mm wide across (idler plate to horn plate); legs at hip_width 90 mm keep a ~35 mm gap between the two thighs;
* the ankle-roll axis sits 28 mm below the pitch axis (a small sim deviation); hip and ankle ranges are limited as above.

## Using it

```bash
python -m openhumanoid.cad interfaces adam
python -m openhumanoid.cad check variants/adam/cad/leg_v2.py --out variants/adam/cad/validation    # gate + ROM + access (about 4 min)
python -m openhumanoid.cad render variants/adam/cad/leg_v2.py --out docs/cad-foundation [--pose squat]
python -m openhumanoid.cad gauge --out variants/adam/cad/fit-gauge
```

A builder file defines `build(ctx) -> Assembly` (`ctx.spec`, `ctx.interfaces`); copy `leg_v2.py`. `pip install python-fcl` is **not** needed; the
access check uses manifold3d (already in the `design` extra). Packaging note for the commander: `openhumanoid/cad/dfm.yaml` and
`openhumanoid/cad/components/data/*.yaml` need `[tool.setuptools.package-data]` entries in `pyproject.toml` before a non-editable install.

## Known limits

* Servo mechanical features marked ESTIMATE; the leg is only as right as they are (gauge first).
* Tool access models a stubby driver along the screw axis, not an L-key's swing; insertion paths are pure translations.
* The thin-wall check is voxel based (+-0.25 mm); it ignores features under about 0.5 mm.
* Hardware (screws) is not modelled as solids; cable routing is reserved, not simulated; mass uses volumes, not slicer output.
* `loft_shell`, `keepout(mode="offset")` and `split_for_bed` are tested on simple bodies; the shell bake-off decides the shell method.
* Left leg only; the right leg is a y-mirror (`Part.shape.mirror(bd.Plane.XZ)`) not yet exercised in the gate.
