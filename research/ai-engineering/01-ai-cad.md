# 01 · AI + CAD: what LLM agents can and can't do in code-CAD

*Research T-0011 · 2026-10-19 · ai-eng-research. Sources were fetched on that date unless marked. Many 2026 items are arXiv preprints. The [CDFAM 2026 benchmark review](https://cdfam.com/ai-to-cad-benchmarks-2026/) warns that most scores are provisional and some are self-reported by vendors. **[UNVERIFIED]** marks claims seen only in a snippet or a secondary source.*

## Bottom line

1. **Frontier models write CAD code that *runs* far more often than it is *right*.** Simple prismatic parts work. Lofts, sweeps and shells fail 70–90% of the time on complex prompts. Mechanical function (mates, threads, gears) is near zero without help.
2. **What works in practice:** declare interfaces first, then deterministic geometry checks, then visual review for *qualitative* issues only. Cap visual refinement at about 2 rounds.
3. **build123d is a sound choice**, but no peer-reviewed benchmark covers it (all of them use CadQuery). Our own examples and cheat-sheet matter more than for CadQuery.
4. **Naming collision:** *Adam* (adam.new) is a funded YC text-to-CAD startup with a 5k-star open-source repo, in exactly our domain. See §4.

## 1. Benchmarks: the numbers that matter for Claude

| Benchmark | What | Key numbers | Source |
|---|---|---|---|
| **BenchCAD** | 17.9k execution-verified CadQuery programs, 106 part families | Image→code executable rate: **Claude Opus 4.7 94.0%**, Gemini 3.1 Pro 79.8%, GPT-5.3 67–70%. But **IoU only ~0.27/0.28/0.20**. Answering numeric questions from **images is 15–20 points worse than from code**. Code-edit accuracy is 0.85–0.87, yet **~64% of "successful" edits also broke unrelated features**. | [arXiv 2605.10865](https://arxiv.org/html/2605.10865v1) (2026-05-11) |
| **Text2CAD-Bench** | 600 curated prompts, 4 difficulty levels, CadQuery | L1 invalid-rate/IoU: GPT-5.2 11%/0.59, Claude 4.5 Sonnet 20%/0.54. **L3 (complex/freeform): invalid 68–92%, IoU 0.17–0.26** for all frontier models. **Sweep, loft and shell cause most failures.** Domain-trained models (Text2CAD, CADFusion) do *worse* than general frontier LLMs. | [arXiv 2605.18430](https://arxiv.org/html/2605.18430v1) (2026-05-18) |
| **CAD-bench** | 17 tasks up to threaded mating pairs and gear trains, checked with rigid-body sim | Best standalone 59.9% overall. **Functional tasks are near zero standalone.** Agent harnesses help but still fail often. | [ICML 2026](https://icml.cc/virtual/2026/67851) |
| **MUSE** | Editable B-rep assemblies with design specs | "Failure cascade from executable code to valid geometry and finally to engineering-ready design" | [arXiv 2605.28579](https://arxiv.org/abs/2605.28579) (2026-05-27) |
| **CADWorld** | Computer-use agents driving the FreeCAD *GUI* | Best agent 17.5% vs 87% for a human expert. GUI driving is far worse than writing code. | [arXiv 2609.16251](https://arxiv.org/pdf/2609.16251) **[UNVERIFIED: fetch failed; numbers via snippet + CDFAM]** |
| Harness effect | Same model, different harness | Changing only the harness moves Parametric CAD Bench by ~10%. Showing the model a render of its output took one CADGenBench score from 0.360 to 0.457. | [CDFAM review](https://cdfam.com/ai-to-cad-benchmarks-2026/) (data through 2026-09-27) **[community claims]** |

Older method papers (for lineage, not for decisions): Text2CAD ([2409.17106](https://arxiv.org/abs/2409.17106), NeurIPS 2024; runs but its IoU is near zero on new benchmarks), Query2CAD ([2406.00144](https://arxiv.org/abs/2406.00144); +23% from refinement, mostly in iteration 1), CAD-Recode ([2412.14042](https://arxiv.org/abs/2412.14042), point cloud→CadQuery), CAD-Coder ([2505.19713](https://arxiv.org/abs/2505.19713), NeurIPS 2025, GRPO with a Chamfer reward), Text-to-CadQuery ([2505.06507](https://arxiv.org/abs/2505.06507)), CAD-Llama ([2505.04481](https://arxiv.org/pdf/2505.04481)), BlenderLLM ([2412.14203](https://arxiv.org/abs/2412.14203)), CAD-Assistant ([ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/html/Mallis_CAD-Assistant_Tool-Augmented_VLLMs_as_Generic_CAD_Task_Solvers_ICCV_2025_paper.html); a VLM planner running Python *inside FreeCAD*, checking each command's effect), and the survey [2505.08137](https://arxiv.org/abs/2505.08137).

### Failure modes (consolidated)
- Invalid or empty geometry, dominated by loft/sweep/shell (Text2CAD-Bench).
- Right shape, wrong parameters (BenchCAD: 94% executable, IoU ~0.27).
- Wrong workplane or orientation, and axes lost after nested rotations (BenchCAD; [HN thread](https://hn.svelte.dev/item/47183039)).
- Hard features silently replaced with simpler ones, e.g. a loft becoming an extrude (BenchCAD).
- Edits that silently break other features (~64%, BenchCAD).
- **Silent boolean failures:** an OCCT union dropped a cylinder at exact tangency with no error, and both agents reported success ([ModelRift CadQuery vs OpenSCAD](https://modelrift.com/blog/cadquery-vs-openscad/), via [summary](https://zeli.app/story/49676577), 2026-09-12).
- **We reproduced a version of this ourselves:** build123d `offset()` reported `is_valid=True` on a lofted shell whose volume was wrong and whose STEP re-import was invalid ([prototypes/README.md](prototypes/README.md)).

## 2. Visual feedback loops: what render→critique actually buys

- **CADCodeVerify** ([arXiv 2410.05340](https://arxiv.org/html/2410.05340v2), ICLR 2025): the VLM asks itself verification questions about renders, answers them, then refines. GPT-4 point-cloud distance improved 0.155→0.127 (**~18%**), with **no gain after round 2**. CodeLlama got *worse* in round 2. The critique's answers were only **64.6% / 68.2% accurate** (rounds 1/2), and 19–27% came back "Unclear". Most fixes were structural errors.
- **Query2CAD** ([2406.00144](https://arxiv.org/abs/2406.00144)): +23.1% success from refinement, mostly in iteration 1. The image critic needed human correction for false negatives.
- **BenchCAD**: models read dimensions from images 15–20 points worse than from code. **Never use a VLM to check sizes; compute them.**
- **CADReview** ([ACL 2025](https://aclanthology.org/2025.acl-long.489/)): MLLMs struggle to recognise multiple geometric components and spatial operations **[numbers not retrieved]**.
- Practitioners ([HN](https://hn.svelte.dev/item/47183039)) say LLMs "can describe flaws in an image but can't fix them", and plain renders of hollow objects hide their problems. On the other side, Claude Code + OpenSCAD with multi-angle PNGs before export is called "pretty impressive".
- For aesthetic critique (the "Roblox" problem), see [06-industrial-design-and-visual-review.md](06-industrial-design-and-visual-review.md). That file covers separate critics, pairwise judging, references and silhouettes.

**Implication:** the visual loop is a *gestalt and missing-feature* detector, not a measuring tool. Put the numbers in deterministic gates.

## 3. Assembly and mechanism design

- **ArtiCAD** ([arXiv 2604.10992](https://arxiv.org/abs/2604.10992), 2026-04-13) is a training-free 4-agent system (design / generation / assembly / review). Its **"Connector" fixes attachment points and joint parameters *before* any geometry is generated**, because LLM spatial reasoning is weak. It has cross-stage rollback and exports URDF. **This is the pattern to copy:** the interface spec comes first and parts are generated to meet it.
- AssemCAD ([2607.05123](https://tldr.takara.ai/p/2607.05123)) and CADMate ([ACL 2026](https://aclanthology.org/2026.acl-long.834/)) were read at abstract level only. "MechAgents" and "CAD-Assembly" could not be verified.
- FreeCAD's Assembly workbench (Ondsel solver) has fixed, revolute and slider joints, but **no documented stable Python joint API** ([wiki](https://wiki.freecad.org/Assembly_Workbench)). For our kinematic chain, the spec plus MJCF is the assembly truth, and the CAD only has to *match* it (checked numerically).

## 4. Commercial landscape and the naming collision

| Product | What it does | Useful to us? |
|---|---|---|
| **Zoo (KittyCAD)**: Design Studio, KCL language, Zookeeper agent, `zoo-mcp` | Cloud B-rep text-to-CAD. Claude Code can write `main.kcl` through MCP ([docs](https://zoo.dev/docs/developer-tools/mcp); [Zookeeper, 2026-02-20](https://www.digitalengineering247.com/article/zoo-introduces-zookeeper-agent-for-cad-design/products)) | No: hosted, billed, proprietary language. Conflicts with "anyone can clone and run". |
| **Onshape AI Advisor** | Documentation and best-practice Q&A. Agents and FeatureScript generation are roadmap only ([Onshape, 2025-12-10](https://www.onshape.com/en/blog/ai-advisor-artificial-intelligence-cad-engineering-software)) | Only for human users of the Onshape backend. |
| **SolidWorks 2026 "Aura"** | Community-knowledge assistant, beta ([Le Monde Informatique](https://www.lemondeinformatique.fr/actualites/lire-des-capacites-genai-viennent-epauler-solidworks-2026-98569.html)) **[secondary]** | No agent API. |
| **Autodesk "Neural CAD"** | Pre-beta foundation-model demos at AU 2025 ([DEVELOP3D](https://develop3d.com/cad/autodesk-shows-its-ai-hand/)) | Not available. |
| **Backflip AI** | Mesh/scan → parametric CAD, $30M raised ([3DPI](https://3dprintingindustry.com/news/markforged-founders-launch-new-ai-3d-model-generator-backflip-with-30m-funding-led-by-nea-and-a16z-235400/)) | Maybe later, for turning sculpted shells into editable CAD. |
| **build123d-mcp** ([PyPI, v0.3.91, 2026-10-15](https://pypi.org/project/build123d-mcp/)), **agentcad** ([2026-06-09](https://hunted.space/product/agentcad)), **text-to-cad skills** ([earthtojake fork](https://github.com/cedrickchee/text-to-cad)) | Persistent build123d sessions, render/measure/validate, STEP/STL/URDF export, stable `@cad[...]` face refs | **Yes, evaluate before building our own.** Three independent tools converging on *build123d + render + validate* is the strongest practitioner signal we have. |
| **Blender MCP** ([ahujasid, 31.6k★](https://github.com/ahujasid/blender-mcp)) | Socket bridge, arbitrary Python | Only if Blender is adopted. **Its socket has no authentication** and safe mode is off by default. |

**⚠ Naming collision: "Adam".** [Adam (adam.new)](https://www.ycombinator.com/companies/adam) is YC W25, "AI Powered CAD" / "end-to-end agents for mechanical design", founded by Zach Dive and Aaron Li. It raised a **$4.1M seed** ([TechCrunch, 2025-10-31](https://techcrunch.com/2025/10/31/yc-alum-adam-raises-4-1m-to-turn-viral-text-to-3d-tool-into-ai-copilot/)) and has "tens of thousands" of users. Its open-source **CADAM** ([GitHub, GPL-3.0, ~5.3k★](https://github.com/Adam-CAD/CADAM)) generates OpenSCAD with **Claude listed as a backend**. A robot called "Adam" from an *AI-designs-hardware* toolkit will collide with them in search, SEO and possibly trademark. This is a product judgement, not legal advice. See the RECOMMENDATIONS item on renaming.

## 5. Which code-CAD for an LLM?

- **Evidence base:** CadQuery dominates the benchmarks, FreeCAD Python appears in some, and no peer-reviewed benchmark targets build123d ([CDFAM](https://cdfam.com/ai-to-cad-benchmarks-2026/)). build123d and CadQuery share the OCCT kernel and most concepts, so CadQuery results transfer roughly.
- **Practitioners:** one HN commenter who spent a month on this recommends build123d because it works on real B-rep. OpenSCAD users report lost axes and ignored `center=true` ([HN](https://hn.svelte.dev/item/47183039)). An April 2024 r/openscad comment said models "haven't learned [build123d] yet", but that predates current models.
- **OpenSCAD** (CADAM's choice) is mesh/CSG with no STEP and weak organic forms. It is fine for brackets and wrong for us.
- **FreeCAD headless:**
  - FEM through `femtools`/CalculiX exists ([wiki](https://wiki.freecad.org/FEM_SolverCalculixCxxtools)), but I found **no complete verified headless script for FreeCAD 1.x**. TechDraw page creation via Python is shown on the [wiki](https://wiki.freecad.org/TechDraw_TemplateGenerator).
  - Budget human debugging time. FreeCAD is **not pip-installable** (conda or the app), which matters for "clone and run".
  - FEA alternatives that stay pip-only: scikit-fem or sfepy on a gmsh/tetgen mesh, or **simple beam/plate hand-calcs in `oh`** for most printed brackets. That is my inference, not tested here.
- **Mesh/SDF → STEP is lossy and pointless**: 100k triangles become 100k planar faces, and FreeCAD "Shape from mesh" does no validation ([CAD Exchanger](https://cadexchanger.com/blog/the-challenge-of-the-polygonal-to-brep-conversion/)). Shells made with SDF or Blender stay STL/3MF. Interfaces and frames stay in B-rep.

## Verdict on the stack

| Layer | Choice | Why |
|---|---|---|
| Frames, mounts, interfaces | **build123d** (keep) | B-rep, STEP, Python, active Claude-oriented tooling. Add a repo cheat-sheet and golden examples, because the training-data gap is real. |
| Sleek shells | **build123d section-lofts + Gordon surfaces** for limbs and torso, and **SDF smooth-unions (manifold3d `level_set`)** for head, chest and feet | Both are pip-only and both were prototyped here. See [06](06-industrial-design-and-visual-review.md). |
| FEA, drawings | **Defer FreeCAD.** Start with analytic checks in `oh`, and try a pip FEM (scikit-fem) for the 3–4 critical printed parts. Add FreeCAD only if a human wants TechDraw drawings. | FreeCAD isn't pip-installable and its headless FEM/assembly scripting is unverified. |
| Renders for review | **pyvista** offscreen (pip) for clay, silhouette and section views. Blender `bpy` (`pip install --dry-run bpy` in our Python 3.11 venv resolves `bpy-5.0.1-cp311-win_amd64`; newer bpy 5.2.x is Python 3.13-only; wheels are 210–400 MB per [PyPI](https://pypi.org/project/bpy/)) only for beauty shots. | Prototyped here. |
| Assembly truth | **spec → MJCF/URDF**, with CAD checked against it | ArtiCAD connector-first pattern. FreeCAD assembly has no stable API. |
