# Shell-pipeline prototypes (T-0011, 2026-10-19)

Small experiments I ran to check claims about shell surfacing, so the recommendations rest on more than literature. Python 3.11.9, build123d 0.13.0, manifold3d 3.5.4, pyvista (pip, VTK offscreen), trimesh 5.1.1.

| Script | What it tests | Result |
|---|---|---|
| `loft_shell_build123d.py <outdir>` | Tapered thigh from 4 superellipse spline sections (`Solid.make_loft`). Hollowed two ways. | **`offset(..., openings=…)`**: reports `is_valid=True` and volume 26.57 cm³, but the STEP reimport is *invalid* (192 cm³). That is a silent failure. **Outer loft − inner loft** (sections shrunk by 2×wall, inner extended 1 mm past the ends): valid at 22.82 cm³, splits along the sagittal plane into two valid 11.22 cm³ halves, round-trips through STEP, and gives a watertight STL. All of it takes under 1 s. |
| (inline in the same session) | `Face.make_gordon_surface(profiles, guides)` network-of-curves surface | Works once the guides pass exactly through the profile endpoints. `thicken(face, 1.6)` gives a valid solid. It raises `IntersectionError` if the curves don't meet. |
| `sdf_shell_and_clay_render.py <outdir>` | Head + neck + collar as an SDF with smooth-min unions → `manifold3d.Manifold.level_set` → 1.6 mm shell → watertight mesh. Then a pyvista clay render (smooth shading + SSAO) and an orthographic black silhouette. | Shell is watertight, genus 0, 238k tris. **Slow: 120 s**, because the SDF is a per-point Python lambda. Vectorise with numpy grids, or use `level_set` with a coarser edge length plus `refine`/`smooth`, to get this down to seconds. The renders are `proto_clay.png` and `proto_silhouette.png`. |

Lessons that feed [RECOMMENDATIONS.md](../RECOMMENDATIONS.md):
1. **Never trust `is_valid` alone.** The geometry gate must re-import the STEP, re-check validity and volume, and check the mesh is watertight (trimesh).
2. Shell lofted surfaces by **subtracting an inner loft**, never with `offset`/`shell`.
3. Section-based lofts already beat box+fillet visually. Smooth unions handle the double-curved parts (head, chest, feet). Both are pip-only.
4. pyvista gives a usable clay render and silhouette from pip, with no Blender needed for the critique loop.

Note: `trimesh` was pip-installed into the repo `.venv` during this research. `manifold3d` and `pyvista` were installed into a scratch dir, not the venv.
