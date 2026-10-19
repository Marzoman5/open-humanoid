# Shell-method bake-off: report (T-20261019-9746, 2026-10-19)

Written by the bake-off agent and saved by the commander (the subagent harness doesn't let subagents write report files). Evidence lives next to this file: `results/*.json`, `renders/M1|M2|M3/`, and `critic/` (blind sheets, single verdicts, pairwise in both orders, combined verdicts, plus round 1 of M1 before the loft fix). Meshes and STEP regenerate with `python -m openhumanoid.design.shells.bakeoff` (~12 min).

## Recommendation: hybrid
- **M3, Blender `bpy` subdivision:** the default for **outer cover shells**. Best silhouette fidelity, the only method with uniform 1.6 mm walls, the fastest, deterministic, and the blind critic preferred it over both others in both presentation orders.
- **M1, build123d section-lofts:** for **structural and interface parts** that need STEP. Fewest lines of code. Its inner wall thins on sloped profiles.
- **M2, SDF smooth-union:** dropped for limbs (7 fix iterations, failed fit at +10% length). Possibly still useful for blobby parts (head, neck, collar), but untested there.

**The caveat that matters more than the ranking:** the critic judged **all three "unfinished"** (G1 and G2 FAIL for every method). The limit is the shared target, not the method: servo-driven slab sections, limbs wider than deep, and a planar knee cut. The critic's top three changes were identical for every method (taper, crown the flat faces, design the knee). So this is a cost and robustness decision. The look has to be fixed upstream, in the concept and silhouette.

## Test piece (identical for all methods)
- Thigh + knee + shank of a ~0.5 m humanoid, knee axis on y.
- Keep-outs: 3× STS3215 (45.2 × 35 × 24.7 mm: hip pitch and knee in the thigh, ankle pitch in the shank) plus two 5 mm-radius cable channels.
- 1.5 mm clearance, 1.6 mm wall.
- Knee: 3 mm recess band, 0–130° flexion collision-free.
- 4 panels split on a coronal plane with a 0.8 mm reveal.
- Bed: 220 × 220 × 250 mm.

## Scores (0–5, 5 best)
| Category | M1 build123d | M2 SDF | M3 bpy |
|---|---|---|---|
| Look (blind critic rank; capped at 3 since none reads as a product) | 2 | 1 | **3** |
| Fit (keep-outs, ROM, regeneration) | **5** | 3 | **5** |
| Printability (watertight, wall, overhang, bed, parts) | 2 | 3 | **4** |
| Engineering cost (code, runtime, robustness, determinism, STEP, deps) | **4** | 2 | 3 |
| Agent-friendliness (failures and fixes) | **4** | 2 | **4** |
| **Total / 25** | 17 | 11 | **19** |

## Measurements
| Metric | M1 | M2 | M3 |
|---|---|---|---|
| Silhouette IoU vs target, front / side | 0.987 / 0.986 | 0.936 / 0.943 | 0.989 / 0.986 |
| Keep-outs enclosed, min clearance (needs 1.5 mm) | yes, 1.53 | yes, 1.50 | yes, 1.50 |
| ROM 0–130° collision-free, min gap (mm) | yes, 2.88 | yes, 1.93 | yes, 3.01 |
| Wall, 1st percentile (target 1.6 mm) | 0.78 | 1.32 | 1.57 |
| Area with wall < 1.2 mm, worst panel | 7.0 % | 2.0 % | 1.4 % |
| Best-orientation overhang, 4 panels (mm²) | 5827 | 7843 | 7192 |
| Build time (s) | 18.6 | 9.7 | 3.8 |
| Lines of code in method files (shared spec + meshutil = 335) | 85 | 155 | 236 |
| STEP | yes (47 MB) | no | no |
| Deterministic, watertight, bed fit | yes | yes | yes |

**Regeneration at ±10%** (length and width): all three methods regenerate watertight, bed-fitting, ROM-clear panels with no code edit. Width ×0.9 puts the shell inside the servo, and every method correctly reports that physics failure. M2 also fails its ankle keep-out at length ×1.1, which is a method defect.

## Agent-friendliness log
- **Shared evaluator:** 6 fixes (keep-out check, frames, ray leaks, memory blow-up, self-hits, seam exits).
- **M1:** 0 crashes, 1 quality fix. The critic found a wavy shank, caused by OCC's global B-spline loft through sparse sections. Two extra sections fixed it (IoU 0.972 → 0.987).
- **M2:** 7 fix iterations.
- **M3:** 1 crash (import order), 0 quality fixes. Cage shrink needed 2 calibration passes.

## What surprised the agent (inputs to the concept and silhouette)
1. **130° knee flexion forces a big calf pocket.** Pocket share of the shank envelope: 10.6% at 60°, 12.1% at 90°, 15.5% at 110°, **23.7% at 130°**. Knee range is a concept/R2a decision; 110° roughly halves the penalty.
2. **Servo geometry dictates widths.** 35 mm across the joint axis makes the limbs wider than deep (thigh 52–62 wide × 44–56 deep, calf 64 × 54), nothing like a human limb.
3. `bpy` 5.0.1 works headless on this machine but pins numpy 1.26, so it needs its own venv (`.venv-bpy`).
4. Tessellation noise can fool both zebra and the critic. Use fine tessellation for reviews.
5. The critic's top three changes were identical across methods, which confirms the target is what limits the look.

## Risks and gaps
- A single noisy critic with one run per order, no references (G6), no colour (G3).
- Unequal tuning effort (M2 got structural fixes but no look rounds; M3 got none and still won).
- One test piece only (head, torso and hand untested).
- No physical print (FDM wall behaviour and panel fit untested).
- The target was derived by the agent and approved by nobody.
- **Open contract question:** M3 shells are mesh-only, so shipping them needs the ADR that lets cosmetic `process: fdm` parts be mesh-only (research I5). That touches `cad/EXPORT_CONTRACT.md` (hook-protected, so it's queued for the maintainer).

## Reproduce
```bash
.venv/Scripts/pip install -e ".[design]"          # includes rtree, shapely
python -m venv .venv-bpy && .venv-bpy/Scripts/pip install bpy==5.0.1   # M3 only
.venv/Scripts/python -m openhumanoid.design.shells.bakeoff
.venv/Scripts/python -m pytest tests/test_shells.py -q
```
