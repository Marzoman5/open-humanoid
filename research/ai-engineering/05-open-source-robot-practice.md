# 05 · What makes open-source robots reproducible by strangers

*Research T-0011 · 2026-10-19 · ai-eng-research. Repo stats come from `gh api` on 2026-10-19. **[SECONDARY]** / **[UNVERIFIED]** are as marked.*

## Premise corrections

- **ToddlerBot does not use the STS3215.** It uses Dynamixel XC330/XM430, costs under $6,000, stands 0.56 m and weighs 3.4 kg ([2502.00893](https://arxiv.org/abs/2502.00893); [tips page](https://github.com/hshi74/toddlerbot/blob/main/docs/sections/05_tips_and_tricks.rst)).
- **Berkeley Humanoid Lite** costs under $5,000 ([2504.17249](https://arxiv.org/abs/2504.17249)).
- Adam's $400 class is **Open Duck Mini** (target under $400, STS3215) and **Zeroth Bot** (BOM from $350, [repo](https://github.com/kscalelabs/zeroth-bot)). Our STS3215 lineage is SO-100/101 plus Open Duck.

## Project by project

| Project | Scale signal | What it does well | What hurts builders |
|---|---|---|---|
| **SO-ARM100/101 + LeRobot** ([repo](https://github.com/TheRobotStudio/SO-ARM100), 7.8k★; [LeRobot](https://github.com/huggingface/lerobot), 28k★) | 9 kit vendors, a worldwide hackathon in 100+ cities (June 2025) **[SECONDARY]** | **BOM tables per region** (US/EU/CN/JP) with unit price, link and total, plus footnotes for gear and voltage variants and an ask for PRs with other countries' links. **Printable fit gauges** against a real STS3215 or a LEGO brick. **One pre-oriented print tray per bed size.** `CHANGELOG.md` per CAD revision. STEP checked in. **`lerobot-setup-motors`** sets ID and baud one motor at a time *before* assembly. **`lerobot-calibrate`**: mid-pose, then a full-range sweep, so a policy transfers between arms ([docs](https://huggingface.co/docs/lerobot/so101)). | Issues (2026): baud/termios errors, kit PSU voltage mismatch, a "list of screws needed" request, dead camera link, calibration failing without a mechanical stop, walls under 0.8 mm, a stray cylinder in one STL, vendor STEP licence unclear. |
| **Open Duck Mini v2** ([repo](https://github.com/apirrone/Open_Duck_Mini), 4.3k★, 549 forks) | No published build count | Four repos split by concern: hardware hub, [Playground RL](https://github.com/apirrone/Open_Duck_Playground), reference motions, [runtime](https://github.com/apirrone/Open_Duck_Mini_Runtime). **BAM-identified STS3215 params** and **pretrained ONNX policies are checked in**, so builders don't train. Masses come from slicer estimates. Wiring diagrams keep the editable `.drawio` source. Fixed servo-ID map. | Assembly guide marked "Not finalized" and prepare_robot "outdated". Screw counts are "TODO". Community moved to [Tnkr](https://tnkr.ai/explore/docs/open-duck-mini/open-duck-mini-v2) and a Feishu wiki. Bus CRC errors and STS3215 variant confusion in the BOM. Asks for a prebuilt SD image. The runtime's TODO checklist wants an automated joint, offset and IMU check. |
| **ToddlerBot** ([repo](https://github.com/hshi74/toddlerbot), 786★, MIT) | The paper claims an independent replication | Sphinx docs, BOM with an **"essentials first" section**, and highlighted rows for v1→v2 migration. **MakerWorld 3MF print profiles** ("Bambu highly recommended… tolerances"). An excellent **tips-and-tricks** page (tape PSU buttons, bus-rate limits, a loose-cable story, a standing backlash test). MJX digital twin plus system-ID params. | The v2 assembly manual lagged the release, so videos and Tnkr filled in. |
| **Berkeley Humanoid Lite** ([repo](https://github.com/HybridRobotics/berkeley-humanoid-lite), 2k★; MIT code, **CC BY-SA 4.0** hardware) | — | A [GitBook](https://berkeley-humanoid-lite.gitbook.io/docs) **ordered as the build order** (tools → print → actuator → flash → robot → software → sim2sim). A **Joint ID Mapping** page. Versioned CAD *Releases*. `uv.lock` plus Docker. Assets live in a separate repo with an Onshape export script. | High-power safety warnings, and actuators that are hard to make. |
| **ODRI Solo** ([actuator hw](https://github.com/open-dynamic-robot-initiative/open_robot_actuator_hardware), 1.5k★, BSD-3) | Commercial kits via PAL | `mechanics/<robot>_v<N>/` per version, with "old versions for reference". **Step-by-step pages with numbered photos.** **Calibration with printed jigs plus steel pins**, re-measured after any repair. A Known Issues page (an empty stub). | Static since 2022. |
| **InMoov** ([inmoov.fr](https://inmoov.fr/head-3/)) | Decade-long community | **Print a calibrator part first**, and tune slicer horizontal expansion. | **STL-only distribution** blocks modification (people rebuild SolidWorks models from STLs). Unfinished subsystems (legs) stay holes for good. |
| **Prusa** ([KB](https://help.prusa3d.com)) | The kit standard | Chapters × steps with a per-step **comment thread**, a per-page tools list, multi-language, and per-model troubleshooting forums. | The 2024 licence shift to the "Open Community License" split the community ([Hackaday, 2024-11-20](https://hackaday.com/2024/11/20/with-core-one-prusas-open-source-hardware-dream-quietly-dies/)). |
| **K-Scale (Zeroth Bot, K-Bot)** | The company closed in Nov 2025 ([36kr](https://eu.36kr.com/en/p/3574072311790723)) **[SECONDARY]** | MIT repos survive. | "Public alpha, breaking changes." Builders stranded when the company stopped. |
| **Reachy Mini** ([repo](https://github.com/pollen-robotics/reachy_mini), 1.6k★) | ~3,000 shipped by Feb 2026 **[SECONDARY]** | Kit plus app store plus Hugging Face distribution. | — |

## Recurring reproducibility failures

1. **Docs lag hardware.** Every active project shows this (Open Duck, ToddlerBot v2, SO-100→101).
2. **Servo bus problems:** IDs, baud, voltage, and a loose cable that shows up as an intermittent bus error.
3. **Calibration ambiguity:** horn alignment "by eye", missing mechanical stops, and offsets not re-measured after repair.
4. **Printer tolerance:** wall thickness, fits, and per-printer variation.
5. **BOM rot:** dead links, variant ambiguity (STS3215 C001/C044/C046 gear ratios; 7.4 V vs 12 V), missing fasteners, PSU mismatches.
6. **Unpinned software:** the counter-examples are BHL's `uv.lock` + Docker and ToddlerBot's pip install.
7. **CAD provenance and licence:** vendor STEP embedded in the repo, and a licence chosen late (Prusa).

## What made the successful ones reproducible

- **A library people already use** (LeRobot CLIs) plus **a cheap BOM** plus **many kit vendors**. SO-101's scale came from distribution, not documentation polish.
- **Guided scripts for the error-prone steps**: per-motor ID/baud setup and calibration sweeps.
- **Physical fit checks before the big print**: gauges and calibrator parts.
- **Shipped sim assets**: identified actuator params plus a pretrained policy, so it "walks without training".
- **Build-order docs**, one page per subassembly, with photos or renders and a troubleshooting page.

## Implications for Open Humanoid

Generated from the spec where possible. Most of this belongs in P7 (sourcing + guide) and P8 (build).

1. **BOM:**
   - Region columns (US/EU/CN/JP) with link, price, `retrieved`, `alternatives`, and **exact variant codes** (e.g. `STS3215-C001 7.4V 1/345`).
   - An "essentials first" ordering, plus fasteners and tools as explicit lines.
   - A weekly link-check in CI.
2. **Print package:**
   - A **fit-gauge STL** (an STS3215 pocket plus an M3 insert boss, generated from the same build123d interface code) in batch 0.
   - Pre-nested trays per bed size, generated from `spec.manufacturing.printer`.
   - 3MF with profiles where possible.
3. **`oh doctor` / bring-up scripts:** per-motor ID and baud setup before assembly, a bus scan, voltage check, joint-range sweep and IMU orientation. This is what Open Duck's TODO asks for.
4. **Calibration jigs** generated in CAD, with offsets stored in versioned `calibration.yaml`.
5. **Ship identified actuator params and a pretrained policy** with every released variant.
6. **CAD:**
   - STEP plus source are always in the repo, and Onshape links are only an addition.
   - A per-variant `CHANGELOG.md` for hardware revisions.
   - **Licence decided before release** (T-0010): e.g. Apache-2.0/MIT for code and CERN-OHL-S or CC BY-SA 4.0 for hardware.
7. **Build guide generated in build order** from spec, BOM and CAD renders, with one page per subassembly, a Known Issues page and a tips page. Issue templates: build problem (printer, filament, BOM version, servo lot), broken link, calibration.
8. **A kit-vendor taxonomy** (printed parts / electronics / full) for later.
