# Simulation

Default engine: MuJoCo (ADR 0004).

| Stage | Model source | Command | Status |
|---|---|---|---|
| Kinematic (pre-CAD) | Primitives from spec + sizing | `oh sim build <id>` → `variants/<id>/generated/sim/<id>.xml` | ✅ |
| Smoke test | Holds stand pose 3 s, reports tilt + torque usage | `oh sim test <id>` | ✅ |
| Interactive viewer | | `oh sim view <id>` | ✅ |
| CAD-derived | `variants/<id>/cad/export/robot.xml` | planned (T-0008) | — |
| Locomotion RL | MJX / MuJoCo Playground style env, domain randomization | planned (T-0005) | — |

Planned layout:
```
sim/
  envs/        # generic humanoid env built from any variant's model + spec (no Adam constants)
  train/       # training entry points, configs per gait
  scenarios/   # push recovery, slopes, stairs, payload, falls
  eval/        # metrics: distance walked, CoT, falls/min, torque/thermal headroom
```
Trained policies go in `variants/<id>/sim/policies/` with a card: training config, seeds, eval metrics, commit.
