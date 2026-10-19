# Third-party reuse ledger

Every piece of reused code, CAD, data, or model gets one row **before** it's copied in. The rules:
1. Re-read the project's actual LICENSE file (not the README) and link it with the commit you read.
2. Check compatibility: MIT software, CERN-OHL-S-2.0 hardware, CC-BY-SA-4.0 docs. Noncommercial (NC), no-license, and GPL code can't come in. CC-BY-SA hardware can't be relicensed under CERN-OHL-S.
3. Keep upstream notices. Apache-2.0 also needs its NOTICE file kept and changes stated.

Candidate list and reasoning: `research/reuse/REUSE.md`.

| Item | Upstream | License (file + commit read) | Used for | Where in repo | Status |
|---|---|---|---|---|---|
| STS3215 actuator models + identification tooling | Rhoban/bam | Apache-2.0. LICENSE re-read 2026-10-19 at commit `e9a619d56da5236206f4de6ceec2c1ee1b497b5c` (main HEAD, 2026-09-13): stock Apache-2.0 text (11357 bytes), source files carry "Copyright 2025 Marc Duclusaud & Gregoire Passault", no NOTICE file at that commit. Python >= 3.12 per its pyproject | P2 actuator model: the six STS3215 7.4 V parameter files `bam/params/feetech_sts3215_7_4V/m1..m6.json` are copied VERBATIM; the control law (`bam/feetech/actuator.py`), DC torque equation (`bam/actuator.py`) and friction models M1-M6 (`bam/model.py`) are RE-IMPLEMENTED (vectorised, plus a stall cap, latency buffer, backlash play, overload protection, thermal state) in `openhumanoid/actuators/servo.py`. Changes stated per Apache-2.0 section 4. Fidelity test against upstream: tests/test_concept.py::test_bam_fidelity (matches to 1e-16 on a pendulum). P7 one-servo ID: planned | `openhumanoid/actuators/data/` (params + `BAM_LICENSE_Apache-2.0.txt`), `openhumanoid/actuators/servo.py` | in use (P2) |
| SO-ARM100/101 parallel gripper | roboninecom | HW CERN-OHL-P-2.0, SW Apache-2.0 (re-read pending; check NOTICE for non-Robonine parts) | R5 table-height pickup | — | planned |
| STS3215 driver + calibration | huggingface/lerobot | Apache-2.0 (re-read pending) | P6 HAL | — | planned |
| Small-biped mechanics/CAD reference | apirrone/Open_Duck_Mini (main repo only) | Apache-2.0 (re-read pending) | reference | — | planned |
| Training envs / assets | MuJoCo Playground, Menagerie | Apache-2.0 / per-model (re-read pending) | P5 | — | planned |
| ZMP preview control (method only) | Kajita et al., ICRA 2003, DOI 10.1109/ROBOT.2003.1241826 | a published method, no code copied | `openhumanoid/concept/motions/lipm.py` is written from the paper's equations. Open Duck's reference-motion generator (no LICENSE) was NOT read or used | `openhumanoid/concept/motions/lipm.py` | in use (P2) |

**Don't copy:** ToddlerBot design files (CC-BY-NC-SA), the Open Duck Playground / reference-motion / Runtime repos (no license), Berkeley Humanoid Lite CAD (CC-BY-SA hardware), and Poppy software (GPL-3).
