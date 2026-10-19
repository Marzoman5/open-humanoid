# Reuse audit for Adam (T-0012), accessed 2026-10-19

Machine-readable detail: [`candidates.yaml`](candidates.yaml) (27 entries, per-artifact licenses with URLs). Requirement context: ≤$550, walk/wave/dance/pick ≤150 g, STS3215, not a toy.

**Trust levels.** Root-license names and SPDX ids marked `root_license_independently_checked` in the YAML were re-checked directly against the GitHub contents/license API (and the raw `LICENSING.md`/README text for roboninecom and ToddlerBot). Other fields came from a summarizing fetcher: **re-read the actual LICENSE text before copying any file.** Per-file headers were not exhaustively scanned. Not legal advice.

## Our licenses and what they allow
| Incoming | Into MIT software | Into CERN-OHL-S hardware | Into CC-BY-SA docs |
|---|---|---|---|
| MIT / BSD / Apache-2.0 (code) | yes, keep notices (Apache: keep NOTICE, state changes) | n/a | n/a |
| Apache-2.0 on CAD (SO-ARM100, Open Duck Mini) | n/a | usable and derivable with attribution, but Apache is not a hardware licence; its patent/scope wording on "source" is unclear for CAD, so credit and ask when in doubt | n/a |
| CERN-OHL-P-2.0 (roboninecom) | n/a | **yes** (permissive into strong-reciprocal) | n/a |
| CC-BY-SA-4.0 hardware (Berkeley Humanoid Lite assets, Poppy, PincOpen, so101-legs) | n/a | **conflict**: not relicensable to CERN-OHL-S; keep separate or avoid | docs only |
| CC-BY-NC-SA (ToddlerBot design files, marc0builds CC-BY-NC, Reachy Mini hardware NC) | **no** | **no** (noncommercial) | no |
| GPL-3 (Poppy software) | **no** (copyleft) | n/a | n/a |
| No LICENSE file (Open Duck Playground / reference-motion generator / Runtime, BHL-Lowlevel, HOPEJr) | **no** (all rights reserved by default) | n/a | n/a |

## Ranked shortlist
| # | Candidate | Verdict | License (root, checked) | Why / effort | STS3215 |
|---|---|---|---|---|---|
| 1 | **Rhoban/bam** | reuse as-is | Apache-2.0 | Identification code plus ready STS3215 7.4 V models (m1/m4/m6); effort S; 552 stars, active | 7.4 V only; no 12 V STS3215 fit |
| 2 | **roboninecom SO-ARM100/101 parallel gripper** | adapt | HW CERN-OHL-P-2.0, SW Apache-2.0, docs CC-BY-4.0 | Gripper for R5, STS3215-driven, permissive hardware licence compatible with our CERN-OHL-S; effort S–M; verify clamp/non-Robonine parts in its NOTICE | yes (servo voltage per kit, check) |
| 3 | **LeRobot** (+ SO-ARM100/101) | adapt | Apache-2.0 (both) | Native STS3215 driver, calibration, teleop, 5–6 DOF arm design to crib for 3-DOF arms; effort M. SO-ARM100 LICENSE names no copyright holder; CAD licence not separately stated | yes, 7.4 V and 12 V variants sold |
| 4 | **Open Duck Mini** (main repo) | adapt | Apache-2.0 (incl. CAD/STL/docs/ONNX per audit) | Proven small biped (4.3k stars, 549 forks), CAD, mechanics, onboard stack ideas; effort M. Servo/voltage not stated in docs fetched | STS3215 (voltage unconfirmed) |
| 5 | **MuJoCo Playground + Menagerie + placo** | adapt / reuse | Apache-2.0 / Apache+BSD per model / MIT | Training envs, humanoid assets, gait/IK library; effort M. placo wheels Linux/macOS only (Windows source build) | n/a (sim) |
Next: XLeRobot arms (Apache-2.0 root, hardware/ CAD licence unstated), zeroth-bot (MIT root, 16-18 STS-class servos unconfirmed), ToddlerBot **code** (MIT, Dynamixel-based, effort L).

## Inspiration-only / avoid (plainly)
- **ToddlerBot design files (Onshape, STL, MJCF): CC-BY-NC-SA-4.0** per README while the root LICENSE is MIT. Noncommercial and share-alike: do not copy into Adam. Code is MIT.
- **Open_Duck_Playground, Open_Duck_reference_motion_generator, Open_Duck_Mini_Runtime: no LICENSE file** (API 404). Even though the main repo is Apache-2.0, these are all rights reserved: read for ideas, reimplement independently, or ask the author for a licence.
- **Berkeley Humanoid Lite:** code MIT, but assets/CAD are CC-BY-SA-4.0 (conflicts with CERN-OHL-S); Lowlevel repo has no licence; actuators are custom BLDC, not STS3215. The repo's licence file is `LICENCE`, not `LICENSE`.
- **Poppy** (GPL-3 software, CC-BY-SA hardware, Dynamixel), **PincOpen** (CC-BY-SA), **so101-legs** (CC-BY-SA, unbuilt), **Reachy Mini** (hardware NC), **marc0builds** (CC-BY-NC), **HOPEJr** (no licence): avoid or inspiration only.
- **Feetech SCServo SDK:** official licence not found; use LeRobot's Apache-2.0 driver instead.

## Top 5 reuse opportunities
1. BAM (Apache-2.0): STS3215 actuator models and identification workflow, directly feeding our sim.
2. Roboninecom parallel gripper (CERN-OHL-P-2.0): ready STS3215 gripper, hardware-licence compatible.
3. LeRobot STS3215 driver and calibration (Apache-2.0): fastest route to a working HAL.
4. Open Duck Mini main repo (Apache-2.0): biped mechanics, CAD and ONNX as a reference build.
5. MuJoCo Playground, Menagerie and placo: training environments and gait generation.

## Open items
- 12 V STS3215 identification does not exist in BAM: we must measure.
- Confirm the CAD licence scope in SO-ARM100, XLeRobot `hardware/`, Open Duck Mini (Apache-2.0 root only), and roboninecom's non-Robonine files (`NOTICE`).
- Ask Open Duck authors to license Playground/reference-motion/Runtime if we want them.
- Onshape, BOM sheets and Google Drive policy checkpoints were not fetched.
