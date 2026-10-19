# C. Producing reference motions for actuator sizing before a controller exists

Access date for every source: 2026-10-19. `null` = not found in a primary source. Effort/maturity ratings are my judgement from the cited repo pages, not measured.

Sizing output needed: per-joint torque and speed time series (peak, RMS, torque-speed operating points) for walking at the target speed. Universal recipe for every method below: get q(t), then (a) replay in MuJoCo with a stiff PD/position actuator and log `qfrc_actuator`, or (b) call MuJoCo inverse dynamics (`mj_inverse`) on q, qdot, qddot incl. contacts. MuJoCo docs: https://mujoco.readthedocs.io/en/stable/ (general reference; not re-fetched for specifics).

## Comparison

| Method | License | Effort | Maturity | How it yields torque/speed |
|---|---|---|---|---|
| Open Duck Mini reference generator (placo walk engine + polynomial fit) | null (no LICENSE stated on repo page); placo MIT | Low | Early (123 stars, 23 commits, TODO says RL training validation pending) | Joint pos/vel references (JSON, `polynomial_coefficients.pkl`) -> replay in MuJoCo, log torque |
| ZMP/LIPM preview control (Kajita) + IK (e.g. ToddlerBot `zmp_walk.py`) | ToddlerBot MIT | Low-medium | Classical; ToddlerBot code is working | CoM/ZMP plan -> analytic leg IK -> q(t) -> `mj_inverse` |
| Quick RL in MuJoCo Playground (MJX) | Apache-2.0 | Medium (needs GPU/JAX) | High; Berkeley Humanoid/G1/T1 envs, zero-shot hardware claims | Roll out trained policy, log `qfrc_actuator`/applied torque directly |
| brax / MJX (engine under Playground) | Apache-2.0 | Medium | High | Same as above; also the batch sim for randomised sizing sweeps |
| MuJoCo Warp | Apache-2.0 | Medium-high | Young, very active (pushed 2026-10-17); BAM supports it | GPU batch sim for sweeps; same logging |
| mujoco_mpc (predictive sampling / iLQG) | Apache-2.0 | High (C++ build; Windows untested per README) | Research prototype | MPC rollout gives torque/ctrl history; no biped task shipped |
| Crocoddyl (FDDP/DDP, Pinocchio) | BSD-3-Clause | High | High as a library, but no biped example in README; need to write contact-phase model | Optimal control returns joint torque directly (inverse-dynamics formulation) |
| Direct trajectory optimization (custom, e.g. Pinocchio + CasADi/IPOPT) | BSD-2 (Pinocchio) | High | Mature theory, custom code | Torque is a decision variable |

## Evidence

- **Open Duck Mini generator**: README says "reference motion generator for imitation learning, based on Placo"; `auto_waddle.py` generates (random or `--sweep` over commands), `fit_poly.py` writes `polynomial_coefficients.pkl`, recordings are JSON; supports `open_duck_mini_v2`. https://github.com/apirrone/Open_Duck_reference_motion_generator . Consumption by RL: `PolyReferenceMotion` loads the pickle in https://github.com/apirrone/Open_Duck_Playground/blob/main/playground/common/poly_reference_motion.py (reference vector holds joint positions and velocities, foot contacts, base lin/ang vel). Command range used by the env: lin_vel_x +-0.15, lin_vel_y +-0.2 m/s (https://github.com/apirrone/Open_Duck_Playground/blob/main/playground/open_duck_mini_v2/joystick.py#L93-L94) - a small-biped speed envelope. Placo: https://github.com/Rhoban/placo (MIT). The pickle is a binary asset: treat as untrusted, don't unpickle from unknown sources.
- **ZMP/LIPM**: ToddlerBot `ZMPWalk` plans CoM with linear MPC on [x,y,vx,vy] at constant CoM height (LIPM-style), cycle_time default per config, foot_step_height 0.05, control_dt 0.02, then analytic 6-DOF leg IK and replays in MuJoCo to build a lookup table of qpos/velocities/contacts per command: https://github.com/hshi74/toddlerbot/blob/main/toddlerbot/algorithms/zmp_walk.py . Kajita et al., "Biped walking pattern generation by using preview control of ZMP", ICRA 2003 (IEEE 1241826, https://ieeexplore.ieee.org/document/1241826 - page could not be fetched; citation from memory, no numbers used).
- **MuJoCo Playground**: Zakka et al., https://arxiv.org/abs/2502.08844 - open-source framework on MJX; abstract claims policies trainable "in minutes on a single GPU", zero-shot sim-to-real; humanoid envs present in repo for berkeley_humanoid, g1, h1, t1, op3, apollo: https://github.com/google-deepmind/mujoco_playground/tree/main/mujoco_playground/_src/locomotion . Per-humanoid training time: null (not on fetched pages). Repo Apache-2.0, 2.2k stars, pushed 2026-10-07 (GitHub API).
- **brax**: Apache-2.0, 3.2k stars, pushed 2026-10-07: https://github.com/google/brax . **MuJoCo Warp**: Apache-2.0, pushed 2026-10-17: https://github.com/google-deepmind/mujoco_warp (BAM exposes a MuJoCo Warp API: https://github.com/Rhoban/bam).
- **mujoco_mpc**: planners iLQG, gradient descent, predictive sampling; shown tasks quadruped, bimanual, humanoid mocap tracking; official setup macOS/Ubuntu only, Windows "should work" untested; "research prototype", not an officially supported Google product; Apache-2.0: https://github.com/google-deepmind/mujoco_mpc
- **Crocoddyl**: optimal control under contact sequences, FDDP/OdynSQP/Intro/Ipopt solvers on Pinocchio, BSD-3-Clause, 1.3k stars, conda-forge/PyPI packaging, README shows quadruped gaits not biped: https://github.com/loco-3d/crocoddyl . Pinocchio BSD-2-Clause: https://github.com/stack-of-tasks/pinocchio
- **Simulation speed of MJX on a CPU-only laptop**: null.

## Caveats for sizing
- Reference-driven peaks depend on gait choice: a placo/LIPM gait is gentle (constant CoM height) and will underestimate torque from RL gaits; RL policies carry push recovery that raises peaks. ToddlerBot's policy used its own sim-fitted actuator limits; Berkeley Humanoid Lite used ~30% of actuator torque limit in walking (https://arxiv.org/html/2504.17249). Size with a margin over both.
- Always include the joint armature/reflected inertia in inverse dynamics (STS3215 armature ~0.022-0.028; file A).

## Recommendation for Open Humanoid
Do sizing in two tiers. Tier 1 (days, no GPU): generate gaits with the Open Duck reference generator (placo) re-targeted to the 0.5 m, 16-DOF kinematics, or ToddlerBot's `zmp_walk.py` pattern (LIPM preview/MPC + analytic IK), replay in MuJoCo, and log `qfrc_actuator` and joint speeds for a speed sweep of 0.1-0.3 m/s to get first peak/RMS torque per joint and check against the STS3215 torque-speed envelope from file A. Tier 2 (once the MJCF is stable): clone the Open Duck Mini Playground env (Apache-2.0), swap in the Open Humanoid MJCF and DR from file B, train a joystick policy on MJX, and re-derive torques under pushes and randomisation; size to the 95th-99th percentile with margin. Skip mujoco_mpc and Crocoddyl for now (Windows build effort, no biped example), revisit Crocoddyl only if a torque-optimal gait is needed to squeeze a joint's gear ratio.
