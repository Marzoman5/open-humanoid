# B. Domain randomization ranges used by comparable projects

Access date for all sources: 2026-10-19. Line anchors refer to the `main`/`HEAD` branch on that date and may drift (no commit SHAs recorded; values re-verified 2026-10-19 against `main`/`master` HEAD, line numbers from fetch summaries are +-2 and block-level). `null` = not randomised or not stated. Machine-readable version: [domain_randomization_ranges.yaml](domain_randomization_ranges.yaml).

Conventions: "x U(a,b)" = multiply nominal by uniform sample; "+ U(a,b)" = add offset; "= U(a,b)" = replace.

## Summary table

| Param | Open Duck Mini | ToddlerBot (defaults) | MJ Playground Berkeley Humanoid | MJ Playground G1 | MJ Playground Booster T1 | Berkeley Humanoid Lite (biped) | K-Scale ZBot |
|---|---|---|---|---|---|---|---|
| Floor friction | = U(0.5,1.0) | U(0.4,1.0) | = U(0.4,1.0) | = U(0.4,1.0) | = U(0.2,0.6) | U(0.4,1.2) static & dynamic | x U(0.1,2.0) |
| Joint frictionloss | x U(0.9,1.1) | x U(0.8,1.2) | x U(0.9,1.1) | x U(0.5,2.0) | x U(0.9,1.1) | null | x U(0.5,1.5) |
| Armature | x U(1.0,1.05) | x U(0.8,1.2) | x U(1.0,1.05) | x U(1.0,1.05) | x U(1.0,1.05) | null | ksim default x U(0.95,1.05) |
| Joint damping | null | x U(0.8,1.2) | null | null | null | in kd gain below | x U(0.95,1.05) |
| Link mass | x U(0.9,1.1) | null (other_mass 0) | x U(0.9,1.1) | x U(0.9,1.1) | x U(0.98,1.02) | null | null |
| Torso/base mass | + U(-0.1,0.1) kg | + U(-0.2,0.2) kg | + U(-1,1) kg | + U(-1,1) kg | + U(-1,1) kg | + U(-1,2) kg | + U(-0.5,0.5) kg |
| Torso CoM | + U(-0.05,0.05) m xyz | null | null | null | null | null | null |
| Default joint pos | + U(-0.03,0.03) rad | arm +-0.1 | + U(-0.05,0.05) | + U(-0.05,0.05) | + U(-0.05,0.05) | + U(-0.05,0.05) | + U(-0.05,0.05) |
| kp | x U(0.9,1.1) | x U(0.9,1.1) | null | null | x U(0.9,1.1) | x U(0.8,1.2) | null |
| kd | null | x U(0.9,1.1) | null | null | joint damping x U(0.5,2.0) on 4 ankle DOFs | x U(0.8,1.2) | null |
| Motor strength (tau_max etc.) | null | tau_max, qdot_max, brake, kd_min: x U(0.9,1.1) | null | null | null | null | null |
| Backlash | fixed +-0.5 deg joint | U(0.02,0.1) (units null) | null | null | null | null | null |
| Action latency | randint(0,3) exclusive -> 0-2 ctrl steps (<=~40 ms; config says 0-3) | n_steps_delay=1 (fixed) | null | null | null | null | null |
| Push | 0.1-1.0 m/s every 5-10 s | 1-3 (force) 0.2 s every 2 s, off by default | 0.1-2.0 m/s every 5-10 s | 0.1-2.0 m/s every 5-10 s | 0.1-1.0 m/s every 5-10 s | force/torque +-2 at reset; interval push commented out | 0-0.5 (XYPushEvent force_range; units not verified) every 2-4 s |

## Sources per project

### Open Duck Mini (STS3215 biped) - closest analogue
- Licence: the Open_Duck_Playground repo has no LICENSE file (GitHub licence field null); `randomize.py` carries an Apache-2.0 header (DeepMind + Pirrone/Nguyen copyright).
- DR: https://github.com/apirrone/Open_Duck_Playground/blob/main/playground/common/randomize.py#L43-L95 - floor friction `U(0.5,1.0)` (was 0.4-1.0), frictionloss x`U(0.9,1.1)`, armature x`U(1.0,1.05)`, torso CoM `+U(-0.05,0.05)` xyz, link mass x`U(0.9,1.1)`, torso mass `+U(-0.1,0.1)` (was 0.2), qpos0 `+U(-0.03,0.03)` (was 0.05), kp x`U(0.9,1.1)` (was 0.8-1.2), gain/bias updated together. Backlash joints excluded from frictionloss randomisation (L31-L33).
- Env: https://github.com/apirrone/Open_Duck_Playground/blob/main/playground/open_duck_mini_v2/joystick.py#L51-L92 - ctrl_dt 0.02, sim_dt 0.002, action_scale 0.25; action delay and IMU delay config 0-3 but `jax.random.randint` upper bound is exclusive, so 0-2 steps; uniform obs noise scales hip_pos 0.03, knee_pos 0.05, ankle_pos 0.08 rad, joint_vel 2.5 rad/s, gravity 0.1, linvel 0.1, gyro 0.1, accelerometer 0.05 (linvel noise is commented out in `_get_obs`, not applied); push interval 5-10 s, magnitude 0.1-1.0 (added to base xy velocity).
- Actuator baseline: kp 17.8, forcerange +-3.35 (file A).

### ToddlerBot
- https://github.com/hshi74/toddlerbot/blob/main/toddlerbot/locomotion/mjx_config.py#L203-L275 (dataclass defaults, line numbers approximate +-1). `walk.gin` checked 2026-10-19: it sets `add_head_pose=True`, leaves `add_push` commented out, and does not override the ranges below or n_steps_delay; the other 14 task gin files (crawl, get_up, etc.) not checked.
- Ranges: friction U(0.4,1.0); damping, armature, frictionloss x U(0.8,1.2); body_mass_range [-0.2,0.2], hand_mass [0,0.1]; kp, kd, tau_max, q_dot_tau_max, q_dot_max, kd_min, tau_brake_max, tau_q_dot_max all x U(0.9,1.1); passive_active_ratio x U(0.5,1.5); backlash_activation 0.1, backlash_range [0.02,0.1] (units not stated); torso roll/pitch +-0.1 rad; push (add_push default False) interval 2.0 s, duration 0.2 s, torso/other force 1.0-3.0 (units null).
- Noise (NoiseConfig, L251-L275): level 0.05, dof_pos 1.0, dof_vel 2.0, gyro low-pass std 0.25 rad/s with bias random walk 2e-4, quaternion rotvec std 0.10 rad.
- Action: action_scale 0.25, n_steps_delay 1, cycle_time 0.72 s (L100-L106).
- Most complete motor-strength/torque-speed randomisation of the set (a strong template for STS3215 torque-speed uncertainty).

### MuJoCo Playground humanoids (Apache-2.0)
- Berkeley Humanoid: randomize https://github.com/google-deepmind/mujoco_playground/blob/main/mujoco_playground/_src/locomotion/berkeley_humanoid/randomize.py#L28-L66 ; env noise/push https://github.com/google-deepmind/mujoco_playground/blob/main/mujoco_playground/_src/locomotion/berkeley_humanoid/joystick.py#L41-L91 : noise (uniform, x level 1.0) hip 0.03, kfe 0.05, ffe 0.08, faa 0.03 rad, joint_vel 1.5, gravity 0.05, linvel 0.1, gyro 0.2; push every 5-10 s, 0.1-2.0.
- G1: https://github.com/google-deepmind/mujoco_playground/blob/main/mujoco_playground/_src/locomotion/g1/randomize.py#L27-L64 (frictionloss x U(0.5,2.0), rest as table) and https://github.com/google-deepmind/mujoco_playground/blob/main/mujoco_playground/_src/locomotion/g1/joystick.py#L43-L93 (joint_pos 0.03, joint_vel 1.5, gravity 0.05, linvel 0.1, gyro 0.2; push 0.1-2.0).
- Booster T1: https://github.com/google-deepmind/mujoco_playground/blob/main/mujoco_playground/_src/locomotion/t1/randomize.py#L30-L81 (floor friction U(0.2,0.6), mass x U(0.98,1.02), kp x U(0.9,1.1), ankle kd x U(0.5,2.0) on 4 joints) and .../t1/joystick.py#L42-L92 (push 0.1-1.0). Booster T1 is a Booster Robotics humanoid; "Booster" is treated as the T1 env.
- None of the three randomise latency, motor strength, or IMU bias; ctrl_dt 0.02 s, sim_dt 0.002 s. Source comments disagree with code in places (T1 floor-friction comment says U(0.4,1.0) but code is 0.2-0.6; G1 frictionloss comment says 0.9-1.1 but code is 0.5-2.0); table uses code values. Kd for T1 is `dof_damping` on DOFs 21,22,27,28, not actuator kd.

### Berkeley Humanoid (paper, Isaac Lab)
- Table 6 in https://arxiv.org/html/2407.21781 : friction 0.2-1.25, restitution 0-0.1, base mass -1 to +1, link mass x0.9-1.1, joint friction x0.9-1.1, armature x1.0-1.05, default joint pos +-0.05; noise lin vel 0.1, ang vel 0.2, IMU 0.05, joint vel 1.5, joint pos 0.03-0.08. No PD-gain randomisation and no latency randomisation (paper treats latency as negligible); no push magnitude stated.

### Berkeley Humanoid Lite (paper + code)
- Paper https://arxiv.org/html/2504.17249 gives no DR table (null).
- Code (biped): https://github.com/HybridRobotics/Berkeley-Humanoid-Lite/blob/HEAD/source/berkeley_humanoid_lite/berkeley_humanoid_lite/tasks/locomotion/velocity/config/biped/env_cfg.py#L50-L71 (obs noise: ang_vel +-0.3, gravity +-0.05, joint_pos +-0.05, joint_vel +-2.0 uniform) and #L225-L297 (static/dynamic friction 0.4-1.2, base mass +(-1,2) kg, default pos +-0.05, actuator stiffness & damping x U(0.8,1.2), reset joint pos scale 0.5-1.5, reset external force/torque +-2.0 on base; the `push_robot` interval event (interval 10-15 s; magnitude not checked) is commented out; the stiffness/damping term is named `scale_all_actuator_torque_constant`). Policy at 25 Hz in paper; ~30% of actuator torque limit used.

### K-Scale (ksim-zbot, ZBot walking; MIT ksim)
- https://github.com/kscalelabs/ksim-zbot/blob/master/ksim_zbot/zbot2/walking/walking.py (default branch `master`, last push 2025-05-04; no line anchors verified) : floor friction x U(0.1,2.0), static friction x U(0.5,1.5), joint damping x U(0.95,1.05), torso ("Top_Brace") mass + U(-0.5,0.5), zero pos +-0.05, XYPushEvent every 2-4 s with force_range 0-0.5 and TorquePushEvent ang_vel_range 0-0.5 (units not verified), obs noise (Gaussian std) joint_pos 0.1, vel 2.5, IMU acc 0.5, gyro 0.5, gravity vec 0.08. Servo type of ZBot: null (not verified).
- Library defaults: https://github.com/kscalelabs/ksim/blob/master/ksim/randomization.py (armature 0.95-1.05, mass mult 0.95-1.05, damping 0.9-1.1, CoM scale 0.01, inertia scale 0.02; verified). `PositionActuators` supports random `kp_scale`/`kd_scale` and torque/action noise: https://github.com/kscalelabs/ksim/blob/HEAD/ksim/actuators.py (ZBot env does not use them in the lines checked).

## Observations
- Convergent defaults: floor friction ~0.4-1.0, link mass +-10%, torso +-1 kg (scale down for a 0.5 m robot: ODM uses +-0.1 kg), armature 1.0-1.05, frictionloss +-10%, default pose +-0.03-0.05 rad, kp +-10%.
- Only ODM randomises latency (0-2 steps at 50 Hz effective); only ToddlerBot randomises motor strength/torque-speed and backlash.
- Obs noise for small robots is larger (ODM joint_vel 2.5 vs 1.5 for large ones; ZBot joint_pos 0.1).

## Recommendation for Open Humanoid
Adopt Open Duck Mini's randomize.py as the baseline (same servo, same scale), and add what it lacks from ToddlerBot: per-joint motor-strength multiplier x U(0.9,1.1) on torque limit and no-load speed, plus damping/frictionloss x U(0.8,1.2) until BAM-identified values are available. Keep ODM-style action delay at 50 Hz (ODM effective 0-2 steps, <=~40 ms; extend to 0-3 inclusive if you want 60 ms) and obs noise at ODM levels (joint_vel 2.5 rad/s, gyro 0.1). Scale torso mass jitter to +-0.1 kg for a robot under ~2-3 kg (project mass target must be checked; null here). Use pushes of 0.1-1.0 m/s every 5-10 s. Treat all ranges as starting points: none of these projects publishes an ablation isolating each parameter's effect on transfer (null).
