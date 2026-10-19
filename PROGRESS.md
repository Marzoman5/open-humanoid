# Progress: what exists and where to look

The maintainer-facing index. Everything below is in this folder (`main` branch) and on GitHub (private: `Marzoman5/open-humanoid`). Agents work in temporary branches under `.claude/worktrees/` (hidden); finished work is reviewed and merged here. Live log of decisions: [coordination/commander-log.md](coordination/commander-log.md).

_Last updated: 2026-10-19 (afternoon)._

## Simulation videos (real recordings of the control software)
Recorded with `python -m openhumanoid.runtime.record <scenario> <out.mp4>`. Each comes from the same scenario code as the test suite, with its pass/fail verdict. **Model:** the concept-level primitive model (capsules and boxes with real masses and measured servo models), not the final CAD.

| Video | Scenario verdict |
|---|---|
| [docs/media/adam_dance_sim.mp4](docs/media/adam_dance_sim.mp4) | PASS: 39 s dance, max tilt 1.5°, 0 servo overloads |
| [docs/media/adam_walk_and_turn_sim.mp4](docs/media/adam_walk_and_turn_sim.mp4) | PASS: walked 1.96 m, turned 89°, max tilt 2.1° |
| [docs/media/adam_push_walk_left_sim.mp4](docs/media/adam_push_walk_left_sim.mp4) | PASS: 0.45 N·s sideways push mid-step, recovered, max tilt 1.9° |

Run all 18 scenarios yourself: `.venv/Scripts/oh runtime scenarios`.

## Images worth opening
| What | File |
|---|---|
| CAD: validated left-leg frame (17 printed parts) | [docs/cad-foundation/sheet.png](docs/cad-foundation/sheet.png), [squat pose](docs/cad-foundation/sheet_squat.png), [fit gauge](docs/cad-foundation/fit_gauge.png) |
| Full-body hard-point layout (R1, 0.55–0.60 m) | [docs/design-method/R1/](docs/design-method/R1/) |
| Silhouette directions (R2a) | [docs/design-method/R2a/lineup.png](docs/design-method/R2a/lineup.png) |
| Packaging-for-look study: before/after | [B4](docs/design-method/R2a-packaging/B4_ref/twotone.jpg) → [C3](docs/design-method/R2a-packaging/C3_r3/twotone.jpg) |
| Shell-method bake-off | [docs/design-method/bakeoff/renders/M3/sheet.png](docs/design-method/bakeoff/renders/M3/sheet.png) |

## Where the numbers are
| What | File |
|---|---|
| Requirements (budget locked ≤ $1,600) | [variants/adam/requirements.md](variants/adam/requirements.md) |
| R1 concept (provisional), plus 3 challenger reviews | [variants/adam/reviews/](variants/adam/reviews/) |
| Parts list with verified prices | [variants/adam/sourcing/QUOTES.md](variants/adam/sourcing/QUOTES.md) |
| Engine reports (torque, heat, push, cost per concept) | `variants/adam/generated/concept/*/report.md` |
| Research (evidence, methods, reuse, low-cost humanoids) | [research/](research/) |
| How the toolkit works | [README.md](README.md), [docs/pipeline.md](docs/pipeline.md), [docs/tools.md](docs/tools.md) |

## Status
- **Done:** research + verification; harness (gates, hooks); design tooling + critic + challenger; concept engine calibrated against Open Duck Mini; R1 concept (provisional); CAD foundation (one leg validated); software-in-the-loop (18/18 scenarios); sourcing.
- **Running:** structural strength / FEA; baseline v2 (knee/ankle linkage go/no-go, longer arms).
- **Next:** R2a-v2 review → full-body CAD → CAD-derived simulation and virtual tests → final BOM, wiring, build guide.
- **Waiting on hardware:** bench servos (STS3215 ×2, STS3250), then servo identification, then walking-policy training.
