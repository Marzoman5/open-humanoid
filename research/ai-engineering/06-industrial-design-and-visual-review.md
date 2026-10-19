# 06 · From "Roblox" to sleek: silhouette-first design and a real visual review loop

*Research T-0011 · 2026-10-19 · ai-eng-research. This answers the commander's priority question about the first Adam CAD attempt. The evidence is thinner here than in the other files. No humanoid company has published its industrial-design process (I found only job postings). The proportion numbers are anthropometric starting points that must be **calibrated against measured reference images** before they become hard gates. Every pip/tool claim marked "tested" was run locally ([prototypes/](prototypes/README.md)).*

## 1. What went wrong (reading the render)

The first attempt (build123d frame plus filleted-box shells, flat MuJoCo screenshot) shows:
- A torso wider than it is tall, with shoulder boxes and no waist taper.
- A small head on a stick neck.
- An exposed black pelvis plate that reads as a skirt.
- Stubby filleted-cylinder thighs and shanks of almost constant section.
- Brick feet.
- No arms reading as arms.

Every segment's outer shape is the servo package's bounding box plus a fillet. That confirms the commander's diagnosis. Here is how each item maps to a cause:

| Symptom | Root cause | Fix (this file) |
|---|---|---|
| Boxes everywhere | The shell was derived *inside-out* from packaging; build123d's easy path is Box+fillet | Design the **outside-in** (silhouette → sections → loft) and the frame inside-out, and make them meet at a **clearance check** (§3, §4) |
| Wrong proportions | No proportion or silhouette step, no numbers | A **D1 proportion and silhouette sheet** with measured ratios and reference overlays, approved *before* 3D (§5) |
| "Looked fine to the agent" | It graded its own renders; flat lighting hides form | A **separate critic** with references, a rubric and pairwise judging, plus **clay renders** with AO and silhouettes on a fixed rig (§6) |
| Stick neck, tiny head | Nothing tied the head and neck to head-units | Rubric items in head-units (§7) |

## 2. How industrial designers get from silhouette to surface

There's no humanoid-specific primary source; Figure's job ads only confirm that it has an industrial designer and a physical "robot buck" ([Figure job posting](https://jobs.coatue.com/companies/figure-3/jobs/57270167-mechanical-engineer-softgoods-plastics)). The general practice is documented in CAD-vendor material and design texts:

1. **Package and hard points first.** Lay out the things the skin must enclose. For cars these are wheels and occupants; for us they are servo envelopes, joint axes, the battery and the SBC. The designer *wraps* surfaces around the hard points and doesn't let them set the shape.
2. **Orthographic control profiles.** Front, side and top silhouettes as low-control-point curves at scale over the package drawing. Use the fewest control points that hold the shape, because uneven control-point spacing becomes surface noise.
3. **Sections at stations.** Draw cross-sections along each segment's long axis. Shapes are ovals or superellipses whose width, depth and "squareness" vary *smoothly* along the axis. That variation is what makes taper and muscle without bumps.
4. **Feature or character lines.** Two to four dominant lines per volume set the reflections. Panel splits run *along* them.
5. **Theme surface, then refinement.**
   - Continuity ladder: G0 position → G1 tangent → G2 curvature. Higher continuity needs more control points per span (Onshape: G0=1, G1=2, G2=3, G3=4) ([Onshape surfacing help](https://cad.onshape.com/help/Content/surfacing.htm)).
   - Highlights across a G2 joint "appear as one" surface ([GrabCAD Q&A](https://grabcad.com/questions/what-is-definition-of-class-a-surface)).
   - Class-A work checks reflections with zebra stripes and curvature combs, and practitioners want G3 surfaces for G2 zebra stripes ([Onshape forum](https://forum.onshape.com/discussion/19773/g%C2%B3-constraint-for-bezier)).

**What transfers to a 0.5 m FDM robot:** steps 1–4 fully. From step 5, only "G1/G2 by construction plus a reflection check". FDM layer lines make true Class-A pointless.

## 3. Replicating it in code: options ranked by quality per effort for printable shells

| Rank | Technique | Best for | Output | Install | Evidence |
|---|---|---|---|---|---|
| 1 | **build123d section lofts.** Closed periodic `Spline` superellipse sections per station → `Solid.make_loft`. **Hollow as outer loft − inner loft**, never `offset`/`shell`. | Thigh, shank, upper arm, forearm, torso, pelvis band | B-rep → STEP + STL | already in venv | **Tested:** valid, splits into halves, STEP round-trip OK, watertight, <1 s. `offset()` gave a *false-valid* solid ([prototypes](prototypes/README.md)). Text2CAD-Bench says lofts and shells are where LLM CAD fails most ([2605.18430](https://arxiv.org/html/2605.18430v1)), so give the agent a **library function** rather than having it write lofts freehand. |
| 2 | **build123d Gordon surfaces** (`Face.make_gordon_surface(profiles, guides)`) + `thicken` | Panels with two-way curvature: chest plate, shoulder cap, visor | B-rep | already in venv | **Tested:** works when the curves intersect exactly, else `IntersectionError`. Wrap it in a helper that builds guides through profile endpoints. |
| 3 | **SDF smooth unions** (smooth-min of capsules, ellipsoids and round-cones) → `manifold3d.Manifold.level_set` → shell by `abs(d)−t` | Head + neck + collar, feet, hands, shoulder blends, anything blobby | Mesh (STL/3MF) only | `pip install manifold3d` (3.5.4) | **Tested:** watertight, genus-0 shell. **Slow (120 s) with a per-point Python callback**, so vectorise. Mesh→STEP is lossy and pointless ([CAD Exchanger](https://cadexchanger.com/blog/the-challenge-of-the-polygonal-to-brep-conversion/)), so keep mounting interfaces in build123d and boolean them in as meshes (manifold3d gives guaranteed-manifold booleans). |
| 4 | Blender `bpy`: subdivision cage, Skin modifier, Solidify | The most sculptural freedom, plus beauty renders | Mesh | `pip install bpy` resolves **5.0.1 for cp311** in our venv; 5.2.x is Python 3.13-only ([PyPI](https://pypi.org/project/bpy/)); 210–400 MB wheels | Not tested here. LL3M ([2508.08228](https://arxiv.org/abs/2508.08228)) and BlenderAlchemy ([2404.17672](https://arxiv.org/abs/2404.17672)) show LLM-written Blender code works with feedback. Watch for metres vs mm and non-manifold output. **Optional, later.** |
| ✗ | OpenSCAD (hull/minkowski hacks), Plasticity (no API), libfive (no PyPI wheel), raw OCP NURBS (high agent error rate), FreeCAD Surface WB (same OCCT kernel as build123d, not pip) | — | — | — | Skip. |

> **Package trap:** `pip install sdf` installs a *different* package ("Work with Scientific Data Format files"), **not** fogleman's SDF library ([PyPI metadata](https://pypi.org/pypi/sdf/json), checked 2026-10-19). Use manifold3d's `level_set` with our own small numpy SDF helpers (≈50 lines), or install fogleman's from git if really wanted.

**Recommendation:** use a hybrid of ranks 1+2+3, all pip-only, with build123d as the frame and interface authority. Neither Blender nor FreeCAD is needed for the look. Install Blender only if the maintainer wants photoreal marketing renders.

**Structural rule that kills "Roblox":** the profile functions `w(z)`, `d(z)` and `n(z)` (width, depth, squareness per segment), approved at D1, are the **single source of truth for the outer shape**. 3D sections are *derived* from them, so the model can't drift from the approved silhouette. The servo packages only appear as **keep-out volumes**, checked by clearance.

## 4. Hard points vs proportions at Adam's scale (honest constraint)

At H = 0.50 m the thigh is ~112 mm long and must enclose two STS3215 (≈45 × 35 × 25 mm), so the minimum thigh section is ≈39 × 57 mm with walls and gaps ([variants/adam/design-language.md](../../variants/adam/design-language.md)). That makes the thigh width ≈ **0.11 H**, against roughly 0.09–0.10 H for a human-like thigh **[anthropometric estimate, calibrate]**. The pelvis region carries up to 6 hip servos. **Some chunkiness is physics, not taste.** The D1 sheet must overlay the hard points on the silhouette so the conflict is visible early. The resolution is a human choice with three options:
- Accept a slightly "athletic" stylisation, as Atlas has heavy hips.
- Re-orient servos (largest dimension along the limb axis).
- Grow H.

Proportion *ratios* can still hit their targets even when absolute thickness can't: taper ratio, waist/shoulder ratio, head-units and leg/height ratio.

## 5. Proposed design-step order (to put in the P3 prompt or a `design-shell` skill)

| Step | Output (files) | Automated gate | Who reviews |
|---|---|---|---|
| **D0 Brief + references** | `design/brief.md`: 3 adjectives, take/leave per reference (Adam already has this). `design/refs/*.png`: front and side reference images, cropped, background removed, **normalised to the same height**. `design/refs/*.svg`: hand-traced or thresholded reference silhouettes. | Files exist; each reference has a front and a side view | — |
| **D1 Proportion and silhouette sheet** (2D only, cheap) | `design/profiles.yaml` with stations per segment: `z, w, d, n` (superellipse exponent), joint centres from the spec/MJCF, and hard-point boxes from `sizing.json`. Plus `design/D1_sheet.png`: front and side silhouettes with the head-unit grid, the hard points as red boxes, and the reference silhouettes as an outline overlay at equal height. | **Proportion metrics** in range (§7). **Hard points enclosed** with ≥ wall + gap. Silhouette IoU vs the reference outline reported (soft target ≥ 0.8 after normalising). | **Critic subagent** (§6), then **human R2a "silhouette"**. *Stop here until approved.* |
| **D2 Massing in 3D** | Loft and SDF shells derived from `profiles.yaml`, with no details | Geometry gate: valid, STEP round-trip, watertight, min wall ≥ 1.2 mm. **Silhouette IoU vs approved D1 ≥ 0.95** (front and side). | Critic (pairwise vs D1 sheet + refs) |
| **D3 Feature lines, splits, joints** | Panel lines along character lines, dark joint recess bands, joint hubs, visor | ≤ 1 visible seam per segment. Reveal gaps 0.8–2 mm. Every split part fits the printer bed. | Critic |
| **D4 Packaging closure** | Frame (inside-out, build123d) vs shell (outside-in) | **Clearance ≥ 1.5 mm** shell-to-frame/servo. **ROM sweep**: shells don't collide across each joint's full range (sample the MJCF joint limits). Servos, horns and cables are not visible from the 6 rig views (ray test). | — |
| **D5 Surface quality and print prep** | Split into printable parts with magnets/snaps, oriented visible-face-out | Overhang map. Curvature/zebra render. No unintended flat region > ~30% of a segment's visible area (from the Adam design language). | Critic |
| **D6 Final** | Render sheet, print layout, mass/cost recalibration | All the above. Re-run sizing. | Critic, then **human R3** |

D1 is the new, cheap, high-leverage step: a few hundred lines of matplotlib and YAML, minutes of compute, and the place where 80% of the "toy vs product" decision is made.

## 6. The review loop: renders, critic, rubric

**Evidence:**
- **Self-preference is real.** LLM evaluators recognise and favour their own generations, and self-recognition correlates with self-preference ([Panickssery et al. 2404.13076](https://arxiv.org/abs/2404.13076)). Anthropic's harness team found the same in practice: agents "praise their own output", and a QA agent "talked itself into approving" ([2026-03-24](https://anthropic.com/engineering/harness-design-long-running-apps)). **So use a separate critic with fresh context and no authoring history**, and calibrate it by reading its logs.
- **Pairwise beats absolute** for 3D aesthetics: GPTEval3D's pairwise comparison with Elo aligned with human preference ([2401.04092](https://arxiv.org/abs/2401.04092)). **Position bias is systematic** and depends on the quality gap ([Shi et al. 2406.07791](https://arxiv.org/html/2406.07791v7)). Judge twice with the order swapped and only count consistent wins (the MT-Bench practice, [2306.05685](https://arxiv.org/abs/2306.05685)).
- **VLMs are poor at dimensions.** They are ~27 points worse answering numeric questions from images than from code ([BenchCAD](https://arxiv.org/html/2605.10865v1), 0.526 vs 0.801). CADCodeVerify critiques were 65–68% accurate overall, mostly because of "Unclear" answers (yes/no answers were 87–91% right), with gains plateauing after 2 rounds ([2410.05340](https://arxiv.org/html/2410.05340v2)). **Code measures the numbers; the VLM judges gestalt.**
- **Spend compute on the verifier.** BlenderGym found that at higher budgets, more verifier compute beats more generator compute ([2504.01786](https://arxiv.org/abs/2504.01786)). SimWorlds argues that inspecting the scene *state* beats pure visual critique ([2607.01766](https://arxiv.org/pdf/2607.01766)). Both support "metrics first, VLM second".

**Render rig** (pyvista offscreen, pip; tested):
- **Clay:** a single matte material, smooth shading, SSAO, 3-point light. Flat-lit screenshots hide form, which was failure #6.
- **Views:** front, side, back and ¾ front (perspective, ~85 mm-equivalent) plus front and side orthographic **silhouettes** (black on white).
- **Overlays:** reference outline (red) and a head-unit grid. Optional zebra or matcap reflection pass.
- **Consistency:** the same framing for the candidate and the references, and a **fixed camera config committed in the repo** so iterations are comparable.

**Critic protocol** (a subagent defined in `.claude/agents/design-critic.md`):
- **Inputs:** only the render sheet, reference images, the rubric and the metrics JSON. No code and no authoring transcript.
- **Model:** Sonnet is enough for a gestalt judgment. Use Opus only at R3.
- **Output:**
  1. A per-criterion verdict, PASS / FAIL / UNKNOWN, each with visual evidence.
  2. A pairwise preference between candidate and previous best, asked twice with the order swapped.
  3. "Reads as: product / toy / unfinished", with one sentence.
  4. The **top 3 changes**, each mapped to a rubric item and a `profiles.yaml` parameter.
- **Loop:**
  - The author applies only changes tied to failed criteria.
  - Cap at **3 critic rounds per step**; returns diminish after 2 (CADCodeVerify).
  - Keep the best-so-far.
  - Metrics override the VLM on anything numeric.
- **Human gates stay** (R2a silhouette, R2 massing, R3). The critic exists to make the human's time count, not to replace it.

## 7. Draft acceptance rubric

**Calibrate these first:** measure 3–4 reference silhouettes (Optimus, electric Atlas, Figure 03, 1X Neo) with the same metric code, then set the bands. Starting values come from figure-drawing canons and anthropometry (Drillis & Contini, as tabulated in Winter's *Biomechanics and Motor Control of Human Movement*). I did **not** verify the exact table values online.

**Metric (computed by code from mesh or profiles; H = total height; hu = head height):**

| # | Criterion | Start band |
|---|---|---|
| P1 | Head height | 0.13–0.15 H (Adam brief says ~14%) |
| P2 | Visible neck length / width | 0.25–0.5 hu long; neck width ≥ 0.4 × head width (no "stick") |
| P3 | Shoulder width (outer) | 0.22–0.28 H |
| P4 | Waist width / shoulder width | 0.55–0.75 |
| P5 | Pelvis width / shoulder width | 0.70–0.90; pelvis band reads as a recess (dark) |
| P6 | Hip-joint height | 0.46–0.53 H |
| P7 | Knee height | 0.25–0.30 H |
| P8 | Taper: distal / proximal section area | thigh ≤ 0.65; shank (ankle/calf) ≤ 0.6; upper arm→wrist ≤ 0.65 |
| P9 | Widest limb section location | within the proximal 1/3 (thigh), upper 1/3 (calf swell) |
| P10 | Foot length | 0.13–0.17 H; foot height ≤ 0.05 H |
| S1 | Silhouette IoU vs approved D1 | ≥ 0.95 front & side |
| S2 | Silhouette IoU vs normalised references | report; soft target ≥ 0.80 |
| S3 | Section monotonicity | width profile has no unintended local bumps (only designated swells) |
| S4 | Flat-area check | no outward planar region > 30% of a segment's visible area |
| S5 | Hidden hardware | 0 servo, horn or cable pixels from the 6 rig views (ray test) |
| M1 | Printability | watertight, STEP round-trip valid, wall ≥ 1.2 mm, part fits bed, clearance ≥ 1.5 mm, ROM sweep collision-free |

**Gestalt (critic, PASS/FAIL/UNKNOWN with evidence):**
- G1 Reads as an adult product, not a toy or character (no chibi head, no box torso).
- G2 Continuous silhouette: thigh→shank and chest→waist→pelvis read as flowing forms, with joints as deliberate dark recesses.
- G3 Two-tone discipline: white shells, dark recesses, one accent at most.
- G4 Consistent design language: the same radii family and section "squareness" across segments.
- G5 Pairwise vs previous best: preferred in both orders.
- G6 Next to each reference at equal height, it looks like a member of the same family (state which features match).

## 8. What to install

| Need | Package | How | Status |
|---|---|---|---|
| Lofts, Gordon surfaces, STEP | build123d 0.13 | already installed | ✅ |
| SDF→mesh, robust mesh booleans | manifold3d 3.5.4 | `pip install manifold3d` | tested in scratch |
| Mesh checks, slicing, IoU helpers | trimesh 5.1.1 | `pip install trimesh` | **installed into repo .venv during this research** |
| Clay, silhouette and zebra renders | pyvista (VTK) | `pip install pyvista` (~150 MB with VTK) | tested in scratch |
| 2D profile sheets | matplotlib, pillow, scikit-image | pip | pulled in by pyvista |
| Beauty renders (optional) | bpy 5.0.1 (cp311) or the Blender app | `pip install bpy` | not tested |
| FEA, drawings (later) | FreeCAD (conda/app) or scikit-fem (pip) | see [01](01-ai-cad.md) | not needed for the look |

Suggested `pyproject` extra: `design = ["manifold3d", "trimesh", "pyvista", "scikit-image"]`.
