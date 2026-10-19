# Roadmap: the reference robots

Each robot proves the toolkit at a larger scale. Each one's lessons (measured data, calibrated models, skills, gates) make the next cheaper to get right. Targets set by the maintainer on 2026-10-19. Capabilities beyond Adam are **aspirations to be checked by research and the concept loop**, not commitments.

| Robot | Budget | Purpose | Status |
|---|---|---|---|
| **Adam** | $550 | **Proof we can make a humanoid** with this toolkit: walks, waves, dances, light table-height pickup, standalone, not a toy | concept (P2 next) |
| **Eve** | ~$3k (to be re-verified at 2026 prices) | **Testbench for real applications.** Target: before Christmas 2026. Mostly well-sourced off-the-shelf parts, little CNC (no 20 custom actuators). A possible basis for funding or crowdfunding. | idea |
| **Cain** | ~$10k | A humanoid the maintainer would actually use in real life (e.g. workshop helper, companion) | idea |

## Working decisions (2026-10-19)
- **Quality over speed.** No rushing gates to hit dates.
- **Sourcing:** prefer fast US vendors, within budget caps.
- **Manufacturing:** a 3D print farm is available, so print time isn't a bottleneck. A Haas 3-axis CNC, mill, and lathe may be available for later robots.
- **Locomotion training:** rented cloud GPU, **only after** a CAD-derived simulation and real one-servo measurement exist. No training on primitive or unrealistic models.
- **Not in scope for any reference robot:** physically supporting or guiding frail people, or "bodyguard" roles. These are safety-critical beyond hobby engineering. Companion roles that walk alongside someone are fine.

## Input from Adam's packaging study (2026-10-19)
An Optimus/Atlas-like silhouette needs roughly **0.9–1.2 m** and **5–13× Adam's leg torque**: a quasi-direct-drive or compact planetary actuator class. Hobby serial-bus servos fail above ~0.65 m. Eve's concept loop should start from this.
