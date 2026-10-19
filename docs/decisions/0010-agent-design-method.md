# 0010: Agent-only industrial design: silhouette first, outside-in shells, separate critic

- **Status:** accepted · **Date:** 2026-10-19 · **Scope:** toolkit (method) + variant:adam · **Deciders:** maintainer, commander
- **Evidence:** research/ai-engineering/06-industrial-design-and-visual-review.md, RECOMMENDATIONS.md §A, the blind-critic experiment in 07 §4
- **Trigger:** the first Adam CAD attempt read as "Roblox": a frame of servo boxes with fillets, self-graded on flat renders.

## Decision
1. **Agents design the whole robot, including the look.** The reference flow involves no human CAD. Humans judge at review stops. (Humans may still contribute in any tool via the export contract, ADR 0002.)
2. **Silhouette first.** A proportion and silhouette sheet (`variants/<id>/design/profiles.yaml` + overlay renders with references and hard points) is approved at a new review stop **R2a** before any 3D shell work. `profiles.yaml` is the source of truth for the outer shape.
3. **Outside-in shells, inside-out frame.** Shells are generated from the profiles (section lofts, panels, smooth unions). They are never shaped from servo boxes. Servo packages are keep-out volumes, and the two meet at clearance and range-of-motion checks.
4. **Separate critic, code for numbers.** A design-critic subagent with no write access gets only renders, references, the rubric, and metrics. It judges pairwise with the order swapped, for at most 3 rounds per step. Numeric criteria come from `oh design metrics`, never from a model looking at a picture.
5. **Review renders** use a fixed studio rig (clay, silhouettes, reference overlays). MuJoCo renders are for simulation only.

## Consequences
- (+) Attacks every documented root cause of the toy look.
- (−) New tooling (profiles → shells, metrics, critic, render rig) must exist before the full-body CAD resumes.
