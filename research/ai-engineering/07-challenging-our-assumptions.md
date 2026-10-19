# 07 · Challenging our assumptions (unanchored review)

*T-0011 addendum · 2026-10-19 · ai-eng-research. The commander asked for every named tool and structure (build123d, FreeCAD, SDF, Blender, separate critics, the restructured phase order, and the spec-driven toolkit + phase pipeline + one-shot prompt approach itself) to be treated as a **hypothesis**. This file tests each one against the evidence in 01–06, two new experiments, and one more research pass ([§3](#3-hypothesis-agent-written-code-cad-is-the-right-way-to-get-sleek-shells)). Where the evidence points elsewhere I say so.*

## Verdict table

| # | Hypothesis | Verdict | One-line reason |
|---|---|---|---|
| H1 | A spec-driven, variant-agnostic toolkit is the right overall shape | **Sound, with a scope correction** | Precedents for "requirements in, design out" exist (LEAP 71). But every open robot that strangers reproduce began as **one excellent robot**, and toolkits that spread were adopted *through* a cheap reference robot (LeRobot→SO-100). Generality should be *extracted on second use*, not designed up front. |
| H2 | A phase pipeline (P0→P9) | **Sound if it allows loops and its gates are real** | Engineering design methodology and co-design research both iterate concept↔analysis. A linear waterfall with self-reported gates is the failure mode. |
| H3 | "One-shot" prompts | **Wrong framing. Keep the prompt as an entry point; the real product is the harness.** | No credible practitioner one-shots large systems. They run many short sessions against machine gates (Carlini ~2,000 sessions, Anthropic harnesses, Ralph loops, METR horizons). |
| H4 | Agent-written code-CAD for the *look* (build123d/SDF/Blender) | **Open question. Settle it with a one-segment bake-off against human Onshape surfacing.** Gen3D is reference-only. Blender is not needed. | Code-CAD is the only route that regenerates shells for any variant (the toolkit premise), and its validity risk is solved by a library. Its aesthetic ceiling is unproven. Every good-looking open robot was surfaced by a human ([§3](#3-hypothesis-agent-written-code-cad-is-the-right-way-to-get-sleek-shells)). |
| H5 | build123d for frames and interfaces | **Confirmed** | B-rep/STEP, interface precision, and three independent Claude-oriented harnesses converge on it. This is where code-CAD *is* reliable (prismatic parts, L1–L2 benchmarks). |
| H6 | FreeCAD for FEM/assembly/drawings | **Not supported now** | Not pip-installable, and headless FEM and assembly scripting on 1.x is unverified. Analytic checks plus pip FEM cover a 0.5 m printed robot. |
| H7 | A separate critic agent | **Supported, and tested** | A blind Sonnet critic failed the Roblox render on 4/5 gestalt criteria. Its *numbers* were off by about 10% on the key ratio, so metrics must stay in code ([§4](#4-experiment-does-a-blind-critic-catch-roblox)). |
| H8 | Restructured order: research → virtual prototyping → packaging → detailed CAD → virtual tests → locomotion | **Mostly right. Merge virtual prototyping and packaging into one iterated concept loop.** | Envelopes depend on masses and limb lengths, which depend on packaging. This is the classic concept/embodiment loop, and Fadini's bi-level co-design. |
| H9 | Our coordination machinery (claims, handoffs, profiles up to swarm) | **Keep claims and handoffs. Demote team/swarm.** | Claims match Carlini's lock files. Swarm-scale multi-agent hurts interdependent design (Cognition, Anthropic). |

## 1. H1: is a spec-driven toolkit the right shape?

**Evidence for:**
- **LEAP 71 Noyron** is the closest precedent. It is a "computational engineering model" that encodes physics, engineering logic and manufacturing constraints into code that generates a whole *class* of designs from requirements. It has been validated by hot-firing dozens of generated rocket engines on a weeks-long cadence ([metal-am coverage](https://www.metal-am.com/leap-71-scales-computational-rocket-engine-development-to-meganewton-class-thrust/), [Digital Engineering](https://www.digitalengineering247.com/article/partnership-forged-for-ai-designed-aerospace-systems); company claims, with independent validation by TEC still pending). That is our vision with rockets instead of robots. Note what it cost: years of expert-written rules, plus a hardware test loop.
- Our `spec.yaml → generated/` with freshness CI is the same idea as Tessl's "generated from spec, do not edit" ([Böckeler 2025-10-15](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)). Specs drift less when generators *consume* them and CI checks them, which we already do.

**Evidence for a scope correction:**
- **No reproducible open robot started as a toolkit.** Open Duck Mini, SO-100/101, ToddlerBot, Berkeley Humanoid Lite and ODRI Solo are each one robot designed by humans, with tooling extracted around it ([05](05-open-source-robot-practice.md)).
- **LeRobot is the instructive exception.** A *software* toolkit launched May 2024 ([OODA brief, 2024-05-06](https://www.oodaloop.com/briefs/2024/05/06/hugging-face-launches-lerobot-open-source-robotics-code-library/)), and its mass adoption came after Hugging Face and The Robot Studio built one cheap reference arm *for* it, the SO-100 (Oct 2024) ([Gigazine on SO-101](https://gigazine.net/news/20250501-hugging-face-robotic-arm)). **The toolkit spread through an excellent reference robot.**
- Anthropic: "find the simplest solution possible" and add complexity only when it is shown to help ([Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)). Our one-shot prompt currently says "**build the tool generically in the framework first**". For tools with one consumer (Adam), that is premature abstraction. Its cost is real: every P3+ tool must be designed for sizes, budgets and CAD tools nobody has tested.
- K-Scale built a broad open platform stack plus robots and shut down in Nov 2025 ([36kr](https://eu.36kr.com/en/p/3574072311790723), secondary). That is not causal evidence, only a reminder that breadth costs.

**Recommendation (changes AGENTS.md rule 2 *practice*, not the vision):**
- **Adam-first, extract-on-second-use.** Write tools in `openhumanoid/`, but generalise only the parameters Adam actually varies. Prove generality with a **cheap second consumer**: an "Adam-XL" sizing-and-sim-only variant at 1.0 m, or Eve's sizing. Don't build backends no one runs (SolidWorks or FreeCAD adapters).
- **The toolkit's real differentiator isn't variant-agnostic code.** It is the *harness*: gates, measured actuator data, skills, the design rubric and reproducibility tooling. These generalise naturally.
- This respects the maintainer's stated priority (the toolkit over Adam alone) while following the evidence on *how* toolkits succeed.

## 2. H2/H3/H8: pipeline shape and the "one-shot" framing

- **What practitioners actually do:** long work is many short sessions against machine-checked progress.
  - Carlini's compiler took ~2,000 sessions, with "tests act as the spec".
  - Anthropic's harnesses use an initializer plus one-feature-per-session with only the `passes` field flipping.
  - Huntley's Ralph is a loop of fresh contexts with one item each.
  - METR finds agents near-perfect on short tasks and much weaker on multi-hour ones ([03](03-agentic-workflows.md)).
  - **Nobody credible "one-shots" a system of this size.** Anthropic's own one-pass solo build had its core feature broken (20 min/$9 vs 6 h/$200 with the harness).
- **What "close to first try" should mean:** the *physical* build works first time. It should not mean the *agent* gets it right in one pass. The first is achievable with gates; the second is not.
  - **Rename** `prompts/oneshot/build-a-humanoid.md` → `prompts/pipeline/build-a-humanoid.md` (or keep the path and change the wording), and set expectations: "a resumable, gated pipeline you can run unattended between review stops."
- **Phase order.** The commander's restructure is right that analysis must precede detailed CAD, but virtual prototyping and packaging are **coupled**:
  - Trajectory-optimised envelopes need link lengths, masses and inertias.
  - Those come from where servos, battery and SBC sit, which in turn needs envelopes to pick servos.
  - Systematic design methodology handles this with a **concept → embodiment → detail** progression that iterates within each stage (Pahl & Beitz, *Engineering Design: A Systematic Approach*, standard text, not fetched). Co-design research makes the same loop explicit (Fadini bi-level, Dinev; [02 §5](02-ai-sim-robot-design.md)).
  - **Proposed shape:**
    1. **Concept loop** (cheap, iterated): kinematics + 2D/primitive packaging of hard points + silhouette (D1) + virtual-prototyping envelopes on the *concept* masses. Gate: envelopes pass at p95, hard points fit the silhouette, and the maintainer approves the silhouette.
    2. **Embodiment:** frame and shell geometry, then the CAD-derived virtual test suite.
    3. **Detail:** print prep, wiring, BOM, guide.
    4. **Then** locomotion training and the build.

## 3. Hypothesis: agent-written code-CAD is the right way to get sleek shells

There are four realistic routes to the *look*. The frame and interfaces stay in build123d whichever route wins (H5). Evidence was gathered 2026-10-19; **[S]** marks secondary sources.

| Route | Quality ceiling | Evidence it works for robot shells | Agent-drivable? | Scales to other variants (toolkit)? | Reproducible by strangers? | Cost / risk |
|---|---|---|---|---|---|---|
| **R-human: maintainer surfaces shells in Onshape** over agent-built scaffolding (skeleton, servo keep-outs, panel-split planes, magnet bosses as STEP) | **Highest, proven** | Every reproducible small open robot's look was made by a human in Onshape/Fusion: Open Duck Mini (a miniature of Disney's BDX design), ToddlerBot, OpenLCH, pib ([DeepWiki](https://deepwiki.com/apirrone/Open_Duck_Mini), [ToddlerBot](https://arxiv.org/html/2502.00893v4)) **[partly S]** | Partially. Onshape's new **FeatureScript MCP** lets Claude write and run FeatureScript for parametric features, not freeform surfacing ([Onshape blog, 2026-09-30](https://www.onshape.com/en/blog/featurescript-mcp-server-use-cases-text-code-cad); no independent evaluation) | **No.** A hand-surfaced shell is one-off per variant. | Yes (STEP export + public doc) | **Human hours: unquantified.** No build logs found, so "days to two weeks part-time" is a guess. The maintainer's time is the scarcest budget. |
| **R-code: agent edits `profiles.yaml`; a tested library generates lofts, Gordon panels and SDF blends** | **Unproven ceiling.** Probably reaches "clean, Atlas-like blended capsules", but Optimus-style panelling is doubtful | Our prototypes show *validity* (watertight, STEP round-trip, printable halves), not *beauty* ([prototypes](prototypes/README.md)). The electric Atlas form language is itself "capsule and cylinder primitives blended" ([Adam design language](../../variants/adam/design-language.md)), so the vocabulary fits the reference. | **Yes.** It also *changes the agent's task*: from freehand lofts (70–90% invalid at Text2CAD-Bench L3) to choosing ~10 numbers per segment in 2D, which a critic can review. | **Yes, uniquely.** Shells regenerate from profiles at any height. That is the toolkit premise. | Yes (pip only) | Low money and agent time. Risk: it plateaus at "clean but generic". |
| **R-gen3d: image/text-to-3D (TRELLIS.2 etc.)** + mirror, repair, boolean, shell and split | High ceiling, **low floor** | **No precedent for a servo-housing product shell.** Text2Robot used Meshy meshes for crude 8-servo quadrupeds, with servos in separate boxes and hand-filtered symmetry ([2406.19963v3](https://arxiv.org/html/2406.19963v3)). About 1 in 10 commercial generations is usable without rework ([HackerNoon stress test](https://hackernoon.com/how-i-stress-tested-3-ai-3d-generators-on-the-same-inputs-what-the-numbers-actually-show), **[S]**). There is no proportion or dimension control, and generative tools don't enforce fabrication constraints ([2404.10142](https://arxiv.org/abs/2404.10142)). | Yes, but post-processing is heavy | No (regenerate per variant, no parametrics) | **Licence minefield:** Hunyuan3D 2.x excludes the EU, UK and South Korea ([licence](https://huggingface.co/tencent/Hunyuan3D-2/blob/main/LICENSE)). SF3D/SPAR3D have a revenue cap. SAM 3D has trade-restriction wording. TRELLIS.2 is MIT ([HF card](https://huggingface.co/microsoft/TRELLIS.2-4B)) but needs a ≥24 GB NVIDIA GPU. Paid APIs break reproducibility. | High post-processing effort and licence risk |
| **R-concept: AI concept images (front/side sheets) → traced into `profiles.yaml`** | Good *direction-finding* | Reasonable, but **no measurement of orthographic consistency** for image models exists ([N]). Expect proportion drift between views, so lock a landmark grid from the hard points first. | Yes (needs an image-generation API or the maintainer's images) | Yes (the traced profiles are parametric) | The chosen images must be committed as versioned inputs | Cheap. Claude can't generate images itself. |

**Assessment, plainly:**
- **For Adam's look specifically**, the highest-certainty route is **R-human**. The maintainer is a competent Onshape user, and every open robot that looks good got there this way.
- **For the toolkit**, R-human is a dead end: it doesn't regenerate for Eve or a 1 m variant, and it puts the scarcest budget (the maintainer's hours) on the critical path.
- **R-code is the only route that serves the vision**, and its *validity* risk is now low (library plus gates). Its *aesthetic ceiling* is the open question, and nobody has evidence either way.
- **Gen3D is not ready** to be a shipping path for an open toolkit (licences, floor, no precedent). It is at most an optional form-finding reference.
- The earlier diagnosis ("build123d's natural primitives are boxes + fillets") is **half right**. The kernel can make sleek lofts (tested). The problem was that the agent had no method telling it to.

**Recommendation: a time-boxed bake-off on one segment before committing to a full body.**
1. Do the D1 silhouette sheet first (common to all routes, cheap, maintainer-approved).
2. **Leg pair (thigh + shank + knee recess)** made two ways:
   - (a) **R-code:** one Sonnet session using the profile library.
   - (b) **R-human:** the maintainer in Onshape, **time-boxed to ~3 h**, over agent-exported scaffolding STEP (keep-outs, split planes).
   - Optionally (c) R-concept profiles from 2–3 concept images, if an image API is at hand.
3. Judge with the same clay rig. Run the **blind critic pairwise in both orders**, then the maintainer. Log the human hours spent.
4. Decision rule:
   - If R-code is within "same family" of R-human by the maintainer's eye, go **R-code** for the whole body (the toolkit wins).
   - If not, go **hybrid**: R-code generates all shells; the maintainer re-surfaces the 2–3 segments that carry the look (head, chest, thighs) in Onshape; both feed the export contract, which already allows mixed backends ([cad/README.md](../../cad/README.md)).

This costs one Sonnet session and ≤ 3 human hours, and it replaces opinion with evidence on the project's most visible risk.

## 4. Experiment: does a blind critic catch "Roblox"?

**Setup.** A fresh Sonnet subagent got only the failed render and the one-paragraph brief (sleek, adult proportions, head ~14%, Optimus/Atlas/Apple family). It had no code, no history and no rubric beyond G1–G6.

**Result:**
- Verdict: "unfinished prototype leaning toward toy", 70% confidence, 10% adult product.
- G1, G2, G4 and G6 FAIL; G3 partial pass.
- Specific, correct evidence: a box torso with separate box shoulders, no waist taper, a black pelvis "skirt", a neck rod, mixed capsule and box languages.
- It also named the render's limits (flat high-key lighting, perspective, a bent-knee sim pose) and asked for a neutral A-pose, orthographic views and clay lighting. That is exactly A4.

**Numbers vs code.** I measured the front view's silhouette by pixel analysis (perspective camera, so ±10%):

| Quantity | Critic's estimate | Code measurement | Brief/human target |
|---|---|---|---|
| Head height / H | 14–15% | ≈15% | 13–15% |
| Shoulder width / H | 40–42% | **≈45%** | 22–28% |
| Waist / shoulder | 0.8–0.9 | ≈0.83–0.9 (narrowest torso row 0.35–0.38 H vs 0.42 H; arms may overlap the profile) | 0.55–0.75 |
| Thigh taper | ~0.9–1.0 | ≈1.0 (constant 0.24 H pair width) | ≤ 0.65 |

**Conclusions:**
- (a) The original failure was **process** (self-grading, no rubric, no references), not a VLM blind spot. A separate critic would have caught it in one round.
- (b) The critic's numbers point the right way but are imprecise on the most decisive ratio (shoulder width), so **gates use code-measured metrics**.
- (c) The design's largest error is **shoulder width ≈ 1.8× the human band**. The D1 silhouette sheet would have shown that before any 3D work.

Published agreement levels are moderate: GPTEval3D pairwise judging agreed with human annotators ~0.79 of the time ([2401.04092](https://arxiv.org/abs/2401.04092); figure via [summary](https://liner.com/review/gpt4vision-is-humanaligned-evaluator-for-textto3d-generation), **[S]**), and VLM–human correlations on the MUSE CAD benchmark were r = 0.62–0.71 ([2605.28579](https://arxiv.org/pdf/2605.28579), **[S]**). MIT DeCoDE (2026) reports that a few expert ratings given in-context let VLMs rate engineering concepts at statistical equivalence to experts ([Edwards et al.](https://decode.mit.edu/assets/papers/2026_Edwards_judges_jmd.pdf), **[S]**). No study of Claude judging industrial-design aesthetics exists. So put **5–10 maintainer-rated images in the critic's context** (few-shot calibration). One trial is an anecdote, not a calibration. Before trusting the critic as a gate, run it on ~10 labelled images (the reference robots, toy robots, our iterations) and check that it agrees with the maintainer.

## 5. What to drop or demote in the current repo

| Item | Recommendation | Reason |
|---|---|---|
| `team`/`swarm` profiles as advertised options for design work | **Demote**: document them as fine for catalog, sourcing and docs fan-out only | Multi-agent hurts interdependent work (~15× tokens). The maintainer's budget is solo. |
| "Build the tool generically in the framework first" (one-shot prompt) | **Replace** with "Adam-first, extract on second use; generalise only parameters with ≥2 consumers" | §1 |
| Planned SolidWorks/FreeCAD export adapters | **Defer** until a human asks to use that backend | No consumer. The export contract already lets any tool contribute. |
| `architecture.style: modular \| integrated` ("modularity itself is optional") | **Keep the schema field, implement one style** (whichever Adam uses) | Two architectures double CAD and test work with one robot to validate them. |
| The export contract requires STEP for every part | **Amend via ADR** so cosmetic `process: fdm` shells may be mesh-only | Generative and SDF shells can't produce meaningful STEP ([01 §5](01-ai-cad.md)). |
| The "one-shot" name | **Reframe** as a gated pipeline | §2 |

## 6. Net effect on RECOMMENDATIONS.md

- Top-7 items #2–#7 survive the challenge unchanged in substance.
- Item #1 (silhouette-first) survives as the *design step*, but **which tool makes the shells** is reopened in §3. The D1 silhouette sheet and rubric apply to every route.
- New items: H1 scope correction (Adam-first, extract on second use), H3 reframing, the merged concept loop (H8), demotions (§5) and critic calibration (§4).
