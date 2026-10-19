# Adam: Open Humanoid reference variant #1

**A sleek, walking humanoid for ≤ $400 all-in, as tall as the budget allows.** Adam is the toolkit's test bench: every tool gets proven here first. Targets: [ADR 0006](../../docs/decisions/0006-adam-targets.md).

| | |
|---|---|
| Spec | [spec.yaml](spec.yaml) |
| Sizing report | [generated/sizing.md](generated/sizing.md) |
| BOM | [generated/bom.md](generated/bom.md) |
| Sim model | [generated/sim/adam.xml](generated/sim/adam.xml) · `oh sim view adam` |
| Design language | [design-language.md](design-language.md) |
| CAD | `cad/` (build123d), planned T-0004 |
| Build guide | `build-guide/`, planned P7 |

## Current status (v0.1.0, concept)

Regenerate with `oh size adam && oh bom adam && oh sim test adam`.

- **Sizing:** feasible at **0.50 m**, about 2.3 kg, 16 × STS3215 (12 V): 6 DOF per leg plus 2 per arm (shoulder pitch, elbow). Height is **budget-limited**: 0.51 m would cost $401.
- **Dropped for budget:** shoulder roll, neck yaw. They come back if the BOM gets cheaper after sourcing (T-0002).
- **Walking:** passes the first-order model. The tightest margin is arm speed (1.04×).
- **Running:** ❌ infeasible on STS3215. Knee speed is about 0.37× what a 3 Hz run needs. This is an honest stretch goal; options are documented in the sizing report.
- **Sim:** primitive model stands (tilt ~3°), with knee holding torque about 19% of stall.
- ⚠️ Every price is an unverified estimate. The structure mass is uncalibrated until CAD exists.
