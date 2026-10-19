# Software runtime (planned, P6)

```
plugins/ (all optional):  rl_walking │ llm_mcp │ teleop │ scripted_motion │ gripper │ mapping …
core/   (always):         robot model ← spec │ joint control │ safety & limits │ state estimation │ logging
hal/    (one active):     sim (MuJoCo) │ feetech_sts │ dynamixel │ can_bldc …
```

Design rules:
- **Core never imports a plugin.** Plugins register via entry points or a `plugins:` list in the spec.
- **One API, sim or real.** `hal: sim` runs everything against MuJoCo, so plugins are tested in sim first.
- **Safety lives in core:** joint limits from the spec, torque/temperature/voltage cutoffs, fall detection, and an e-stop path that no plugin can bypass.
- **The LLM is a plugin** (`llm_mcp`): it exposes the robot as MCP tools (`walk`, `turn`, `look_at`, `pose`, `get_camera_frame`, `say`, `status`). It runs off-board by default.
- Target platforms: Linux SBCs (Pi Zero 2 W and up), desktop for sim. Microcontroller HAL bridges (ESP32) are optional.
