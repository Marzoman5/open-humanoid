# CAD export contract (v0.1)

**Any CAD tool is fine. The pipeline only reads what this contract defines.** Changing this file needs an ADR.

Every variant (and every module) that has CAD must provide, under `<variant or module>/cad/export/`:

| File | Required | Content |
|---|---|---|
| `parts/<part_id>.step` | ✅ | One STEP per unique part, in meters or mm (declare in `manifest.yaml`) |
| `parts/<part_id>.stl` | ✅ for printed parts | Print-ready mesh, oriented for printing, mm |
| `meshes/<link>.stl` | ✅ | Visual/collision mesh per kinematic link, in the link frame |
| `mass_properties.yaml` | ✅ | Per link: mass (kg), COM (m, link frame), inertia tensor (kg·m², about COM) |
| `robot.xml` (MJCF) **or** `robot.urdf` | ✅ | Kinematic tree whose joint names match the spec's expanded joint names (`hip_pitch_l` …) |
| `manifest.yaml` | ✅ | Source tool, source link and **pinned version**, units, export date, part → material/process/qty |
| `drawings/*.pdf` | optional | Assembly drawings for the build guide |

## manifest.yaml

```yaml
contract_version: "0.1"
source:
  backend: build123d | onshape | solidworks | freecad | other
  location: variants/adam/cad/          # or https://cad.onshape.com/documents/<doc>/v/<version-id>
  version: <git sha | onshape version id | file revision>
units: { step: mm, mesh: mm }
exported: 2026-10-19
parts:
  - id: thigh_frame_l
    qty: 1
    process: fdm           # fdm | sla | cnc | sheet | purchased
    material: pla-plus
    print: { orientation: as_exported, supports: false, infill_pct: 30, walls: 4 }
```

## Rules

1. Joint and link names must match the spec (`oh validate` will check this once export validation lands, task T-0008).
2. Masses come from the CAD tool's mass properties with the right material densities, plus purchased parts (servos, boards) at their catalog mass.
3. Exports are committed. Native files may live outside the repo (Onshape) but must be pinned by version in `manifest.yaml`.
4. After the first export, update `mass_model.structure_kg_at_1m` in the variant spec from the real numbers (calibration loop).
