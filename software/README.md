# Software runtime (P6): software-in-the-loop built, hardware HAL stubbed

```
plugins/ (all optional):  rl_walking │ llm_mcp │ teleop │ scripted_motion │ gripper │ mapping …
core/   (always):         robot model ← spec │ joint control │ safety & limits │ state estimation │ logging
hal/    (one active):     sim (MuJoCo) │ feetech_sts │ dynamixel │ can_bldc …
```

**Where the code lives:** `openhumanoid/runtime/` (the reusable, variant-agnostic core + HALs + front ends), configuration for Adam in
[`configs/adam.yaml`](configs/adam.yaml), documentation and results in [`docs/software.md`](../docs/software.md), tests in `tests/test_runtime.py`.

| Layer in the plan | Built as | Status |
|---|---|---|
| core: robot model | `runtime/model.py` (from the concept/spec) | done |
| core: safety & limits | `runtime/safety.py` (limits, rate, thermal/battery/overload, fall + safe-fall pose, latched e-stop) | done, tested in sim |
| core: state estimation | `runtime/estimator.py` (IMU attitude, kinematic COM, contact, DCM) | done |
| core: joint control / behaviours | `runtime/control.py`, `locomotion.py` (stand, walk, wave, dance, pickup, look-at) | done; walking is the interim LIPM/DCM controller, RL (P5) replaces it |
| core: logging | `runtime/runtime.py` `Recorder` (per-cycle npz) | done |
| hal: sim | `runtime/hal/sim.py` (MuJoCo + the concept-engine servo model + battery + IMU) | done |
| hal: feetech_sts | `runtime/hal/feetech.py` (+ LeRobot adapter, mock bus) | **stub, never run on a servo** |
| plugins: teleop | `runtime/frontends/` (gamepad mapper, phone web UI) | done (gamepad needs `pygame`) |
| plugins: llm_mcp | not built; the JSON-lines TCP API is its transport | API ready, plugin out of scope |
| plugins: rl_walking | not built (P5) | the `Gait` interface (velocity in, joint targets out) is the slot |

Design rules (unchanged):
- **Core never imports a plugin.** Plugins register via entry points or a `plugins:` list in the spec.
- **One API, sim or real.** `hal: sim` runs everything against MuJoCo, so plugins are tested in sim first.
- **Safety lives in core:** joint limits from the spec, torque/temperature/voltage cutoffs, fall detection, and an e-stop path that no plugin can bypass (`Safety.filter` is the only route to the HAL).
- **The LLM is a plugin** (`llm_mcp`): it exposes the robot as MCP tools (`walk`, `turn`, `look_at`, `pose`, `get_camera_frame`, `say`, `status`). It runs off-board by default.
- Target platforms: Linux SBCs (Pi Zero 2 W and up), desktop for sim. Microcontroller HAL bridges (ESP32) are optional.
