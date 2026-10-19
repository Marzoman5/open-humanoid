# 04 · Hardware-as-code beyond CAD (electronics, firmware, BOM, docs)

*Research T-0011 · 2026-10-19 · ai-eng-research. Sources were fetched on that date unless noted. **[UNVERIFIED]** marks claims that rest only on a search summary or a secondary source.*

## Bottom line

For Adam's class of robot (16 bus servos on one TTL bus, an SBC, a battery and an IMU), the electronics are an **integration** problem, not a board-design problem. Agents are weak at from-scratch circuit design, but good at analysis and consistency checks. So we should generate wiring, power and BOM artifacts from `spec.yaml` with deterministic tools, and keep PCB design out of v1.

## 1. Electronics as code: what exists

| Tool | What it is | Agent fit | Source |
|---|---|---|---|
| **atopile** | MIT-licensed declarative `.ato` language → `.kicad_pcb`, with a package registry | Good: typed, diffable, modular. The repo itself ships `CLAUDE.md`/`AGENTS.md` and is developed with agents. | [github.com/atopile/atopile](https://github.com/atopile/atopile) (fetched 2026-10-19) |
| **tscircuit** | MIT, React/TypeScript circuits, exports Gerber/BOM/PnP | Good for code. Auto-placement isn't finished, so positions are set by hand. | [github.com/tscircuit/tscircuit](https://github.com/tscircuit/tscircuit) (fetched 2026-10-19) |
| **SKiDL** | Python → netlist | Any Python-capable LLM can use it. Status not re-checked. **[UNVERIFIED]** | — |
| **KiCad IPC API** | protobuf/NNG control of a *running GUI*, stabilised in KiCad 9. Community reports say the schematic API isn't available until KiCad 11. | Poor for headless agents. Edit the S-expression files instead and use `kicad-cli` for ERC/DRC/export. | [KiCad IPC docs](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/index.html); [forum](https://forum.kicad.info/t/kicad-ipc-api-attached-to-kicad-9-but-not-to-kicad-10/68030) **[partly UNVERIFIED]** |
| **kicad-happy** | Claude Code / Codex skills: KiCad file analysis, BOM, LCSC/DigiKey/Mouser lookup, SPICE, EMC rules | **Best pattern reference.** It is skills plus deterministic Python and needs no KiCad install. | [github.com/aklofas/kicad-happy](https://github.com/aklofas/kicad-happy) (fetched 2026-10-19) |
| Flux, Quilter, DeepPCB, CELUS, Circuit Mind, JITX | Commercial AI-PCB tools. Each stops somewhere (Quilter/DeepPCB route only; CELUS/Circuit Mind go only as far as the schematic) | Not needed for v1 | [JLCPCB survey](https://jlcpcb.com/blog/ai-tools-for-pcb-design) (vendor blog, 2026-09-28) |
| KiCad MCP servers | Several (lamaalrajih/kicad-mcp, mixelpixx, kcaa) of uneven maturity | Experimental | [KiCad forum thread](https://forum.kicad.info/t/i-built-an-mcp-server-that-lets-ai-assistants-help-with-kicad-pcb-design/66451) |

**How good are LLMs at circuits?** They are not good at full board design yet:
- **HWE-Bench** ([arXiv 2603.18102](https://arxiv.org/html/2603.18102v1), 2026-03-18) has 300 board-level tasks. The best model produced a fully correct design only **8.15%** of the time (Claude Sonnet 4.5), while static rule checks averaged 71.84%. Failures were pin-mux conflicts, hallucinated connections on ambiguous pins, and context overload on large ICs. Well-known buses (CAN, RS485, I²C) were handled well.
- **PCBInnoBench** ([NeurIPS 2026 poster](https://neurips.cc/virtual/2026/poster/139034)) has 372 KiCad modification tasks. The best agent passed **22.0%** with expert guidance and **7.3%** without.

Pattern: the right unit is *small, well-known sub-circuit + checker in the loop*. Free-form design is not.

## 2. Do we need a PCB? No, not for v1

- SO-100/101 uses an off-the-shelf bus-servo driver board plus daisy-chain cables ([SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100), fetched 2026-10-19). Open Duck Mini kits ship a Pi Zero 2W, a BNO055, a 2S 18650 pack with BMS, XT30 connectors and a servo board ([kit listing](https://aifitlab.com/products/openduckmini-open-source-version-of-the-bdx-droid), secondary).
- Harness-as-code: **WireViz** turns YAML into GraphViz SVG plus a wire BOM ([PyPI](https://pypi.org/project/wireviz), [FOSDEM 2025 talk](https://ftp.fau.de/fosdem/2025/h1309/fosdem-2025-4612-wireviz-beautiful-wiring-documentation.vtt)). It targets single harnesses, which matches a servo daisy chain.

## 3. Firmware and the software HAL

- Servo bus: LeRobot's generic `SerialMotorsBus` (the Feetech module is now a shim) ([lerobot](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/feetech.py)). There are also ros2_control drivers for the STS3215: [sts_hardware_interface](https://deepwiki.com/adityakamath/sts_hardware_interface) and [feetech_ros2_driver](https://index.ros.org/p/feetech_ros2_driver/github-JafarAbdi-feetech_ros2_driver) **[summaries]**.
- Firmware without hardware: Wokwi covers ESP-IDF, Pico SDK, Arduino and MicroPython ([docs](https://docs.wokwi.com/vscode/getting-started)). Renode + Robot Framework in CI is proven ([Antmicro, 2024-10](https://antmicro.com/blog/2024/10/renode-github-action-for-automated-testing-in-simulation); [Google OSS blog, 2023-08](https://opensource.googleblog.com/2023/08/chromeos-ec-testing-suite-renode-for-consumer-products.html)). Neither simulates an STS3215 bus, so the sim HAL (MuJoCo) remains our main test target.
- I found **no measured, first-person report** of Claude writing reliable bus-servo firmware. This is a gap. Assume an agent can write the HAL in Python on the SBC, and gate it against the MuJoCo HAL plus a bench test.

## 4. BOM and sourcing automation

- APIs: Nexar/Octopart GraphQL needs app registration and has a limited free tier (APIv3 was retired 2022-06-30) ([Octopart docs](https://octopart.com/api/docs)). DigiKey/Mouser/LCSC are reachable through **Ki-nTree** ([PyPI](https://pypi.org/project/kintree/1.0.7)). `jlcsearch` needs no key (via kicad-happy).
- Practice: the SO-ARM100 README keeps a hand-maintained multi-currency table (USD/EUR/RMB/JPY) with per-region links and a total row. That is the *de facto* standard and what strangers can actually use.
- Agent pitfalls are hallucinated part numbers, stale prices, and missing shipping and tariffs. The kicad-happy pattern is the fix: **every row must resolve against a live lookup, or the build fails**, and each row is stamped `{price, currency, region, url, retrieved}`. AliExpress/Taobao have no API, so those rows stay `verified: false` until a human or browser check.

## 5. Power and electrical analysis

No dedicated tool exists, and the analysis is simple first-principles Python:
- Bus current: 16 × stall (≈2 A @ 6 V per retailer datasheet **[UNVERIFIED; check the Feetech original]**) gives 32 A worst case, against a realistic duty.
- Also check BMS/C-rate, buck rating, AWG voltage drop, and runtime = Wh·η / mean W.

This belongs in `oh` as a generic `power` tool, fed by the actuator duty cycles from the virtual-prototyping phase (reference motions produce per-joint torque and current time series).

## 6. Build-guide generation

No off-the-shelf exploded-view or assembly-doc generator turned up for build123d. Open projects hand-write guides (SO-101 lives in [LeRobot docs](https://huggingface.co/docs/lerobot/so101)). Generating per-step part lists, renders and the BOM from the assembly tree is achievable with our own tools. See [05-open-source-robot-practice.md](05-open-source-robot-practice.md) for what makes guides work.

## Implications for Open Humanoid

1. **P6 = generated, not designed.** Add `oh wiring <id>`, which emits a WireViz YAML, an SVG, a pin/ID table and a power budget from the spec. Use stock boards. No custom PCB in v1.
2. **Optional later PCB in atopile**, gated by `kicad-cli` ERC/DRC plus our own checks. Never accept an unchecked LLM netlist (8% full-design success).
3. **Sourcing gate:** a BOM row without a resolved source, date and region counts as `unverified`. `oh bom` already counts unverified rows, so make R5 Buy fail when any line in the budget-critical set is unverified.
4. **Copy kicad-happy's shape for our skills:** each skill is a thin SKILL.md over deterministic Python that the agent calls, so the LLM never does arithmetic or lookups "in its head".
