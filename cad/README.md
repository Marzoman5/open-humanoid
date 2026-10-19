# CAD

Open Humanoid is CAD-agnostic (ADR 0002). Pick a backend per variant with `cad.backend` in its spec. Everything downstream reads only the [export contract](EXPORT_CONTRACT.md).

| Backend | Best for | Agent can author fully? | How exports are produced | Status |
|---|---|---|---|---|
| **build123d** (Python) | AI one-shot design, parametric-from-spec, diffs | ✅ yes | Scripts in `variants/<id>/cad/` write STEP/STL + mass props + MJCF directly | **default**, tooling planned (T-0004) |
| Onshape | Humans, browser, sleek surfacing, sharing | partial (MCP: read, some edits) | [onshape-to-robot](https://github.com/Rhoban/onshape-to-robot) → MJCF/URDF; STEP/STL export | adapter planned |
| SolidWorks | Humans with SW, surfacing, drawings | ❌ | SW→URDF exporter add-in + STEP/STL export | adapter planned |
| FreeCAD | Fully open GUI + Python | ✅ via Python API | FreeCAD Python scripts / CROSS workbench | adapter planned |

See `adapters/` for per-backend notes.

**Hybrid is encouraged.** The agent builds frames in build123d from the spec. A human re-surfaces shells in Onshape or SolidWorks. Both sets of exports land in the same `cad/export/` tree.
