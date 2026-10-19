# CAD backend adapters

Each adapter turns one tool's output into the [export contract](../EXPORT_CONTRACT.md). Status: notes now, code later.

## build123d (default, AI-native)
- Source lives in `variants/<id>/cad/*.py` and `modules/*/cad/*.py`. Parameters are read from the resolved spec plus `generated/sizing.json`. **No hard-coded dimensions.**
- One script per module. A `build.py` assembles the robot and writes `cad/export/`.
- Mass properties: build123d `Solid.volume` × material density, plus catalog masses for purchased parts.
- Robot description: emit MJCF with mesh geoms, using the same joint names as `openhumanoid.simgen`.

## Onshape
- Keep the document **public** (for open source) and pin a **version** (not a workspace) in `manifest.yaml`.
- Drive key dimensions from Variables/Configurations named like spec fields (`thigh`, `shank`…).
- Run `onshape-to-robot` on the top assembly to get MJCF/URDF. Name mates `dof_<joint_name>` so joint names match.
- The Onshape MCP is fine for reading mass properties and parameters. Don't rely on it for full-robot authoring.

## SolidWorks
- Use the SolidWorks-to-URDF exporter. Set joint names to match the spec. Export STEP and STL per part.
- Commit exports. Native `.SLDPRT`/`.SLDASM` files may be committed via Git LFS or kept external with a revision ID.

## FreeCAD
- Scriptable via its Python API, the same pattern as build123d. GUI users can export with the CROSS or RobotCAD workbenches.
