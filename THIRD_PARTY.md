# Third-party reuse ledger

Every piece of reused code, CAD, data, or model gets one row **before** it's copied in. The rules:
1. Re-read the project's actual LICENSE file (not the README) and link it with the commit you read.
2. Check compatibility: MIT software, CERN-OHL-S-2.0 hardware, CC-BY-SA-4.0 docs. Noncommercial (NC), no-license, and GPL code can't come in. CC-BY-SA hardware can't be relicensed under CERN-OHL-S.
3. Keep upstream notices. Apache-2.0 also needs its NOTICE file kept and changes stated.

Candidate list and reasoning: `research/reuse/REUSE.md`.

| Item | Upstream | License (file + commit read) | Used for | Where in repo | Status |
|---|---|---|---|---|---|
| STS3215 actuator models + identification tooling | Rhoban/bam | Apache-2.0 (re-read pending) | P2 actuator model, P7 one-servo ID | — | planned |
| SO-ARM100/101 parallel gripper | roboninecom | HW CERN-OHL-P-2.0, SW Apache-2.0 (re-read pending; check NOTICE for non-Robonine parts) | R5 table-height pickup | — | planned |
| STS3215 driver + calibration | huggingface/lerobot | Apache-2.0 (re-read pending) | P6 HAL | — | planned |
| Small-biped mechanics/CAD reference | apirrone/Open_Duck_Mini (main repo only) | Apache-2.0 (re-read pending) | reference | — | planned |
| Training envs / assets | MuJoCo Playground, Menagerie | Apache-2.0 / per-model (re-read pending) | P5 | — | planned |

**Don't copy:** ToddlerBot design files (CC-BY-NC-SA), the Open Duck Playground / reference-motion / Runtime repos (no license), Berkeley Humanoid Lite CAD (CC-BY-SA hardware), and Poppy software (GPL-3).
