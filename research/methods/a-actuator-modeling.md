# A. Actuator modeling for sim-to-real with hobby servos

Access date for every source below: 2026-10-19. `null` = not found in a primary source.

## Findings

### 1. BAM (Rhoban Better Actuator Models) - the only public STS3215 identification
- Repo, Apache-2.0, supports MuJoCo CPU and MuJoCo Warp; ships identified models for Dynamixel MX-64/MX-106/XL-320/XL330, eRob80, **Feetech STS3215**: https://github.com/Rhoban/bam (2026-10-19)
- Paper (ICRA 2025): Duclusaud et al., "Extended Friction Models for the Physics Simulation of Servo Actuators", https://arxiv.org/abs/2410.08650 (HTML: https://arxiv.org/html/2410.08650). Models: M1 Coulomb-viscous (baseline); M2 +Stribeck; M3 +load-dependent; M4 Stribeck+load-dependent; M5 +directional (motor vs external load); M6 +quadratic load (harmonic drives). Parameter counts 5/3/7/9/11 for M2-M6 as extracted from the HTML page (not re-derived; M3=3 looks odd, treat as unverified).
- Reported error reduction vs Coulomb-viscous (MAE on validation logs; paper gives factors, % are derived): MX-64 2.93x (~66%), MX-106 2.02x (~50%), eRob80:100 2.34x with M6 (~57%), eRob80:50 1.51x (~34%, no clear gain beyond M3). Best model for MX-64/MX-106 is inferred as M5 (per-model MAE only in Fig. 5, not in text). STS3215 is not mentioned in the paper - https://arxiv.org/html/2410.08650
- 2R-arm sim-vs-real: best model gives MAE "more than twice as low" as baseline (Dynamixel M4, eRob M6); M5 overfit and did not help. No RL policy transfer tested in the paper. https://arxiv.org/html/2410.08650
- Limitations stated: temperature, radial forces, dwell time not modelled (backlash: not mentioned in the limitations read, null). https://arxiv.org/html/2410.08650
- Voltage model: Dynamixel voltage clipped to +-Umax, torque from DC-motor equations (kt, R). https://arxiv.org/html/2410.08650
- **STS3215 7.4 V class** (`bam/feetech/actuator.py`): voltage-controlled, vin=7.4, firmware kp=32, error_gain=0.166, max_pwm=0.97, default max velocity 3400*2pi/4096 = 5.22 rad/s, and the firmware rate-limits its internal target (stateful model): https://github.com/Rhoban/bam/blob/HEAD/bam/feetech/actuator.py
- **12 V note**: BAM also ships `bam/params/waveshare_st3025` (m1-m6) for the *Waveshare ST3025 12 V serial bus servo* (`bam/waveshare/actuator.py` vin=12.0). It is a different servo, NOT an STS3215; m4: kt 1.666, R 3.326, armature 0.00399, friction_base 0.0423, friction_viscous 0.0231 (no command_delay field). No 12 V STS3215 identification found in BAM (other folders are Dynamixel/eRob): https://github.com/Rhoban/bam/tree/main/bam/params
- Identified STS3215 parameters (m1 / m4 / m6 JSON, 7.4 V only; 12 V STS3215 = null): https://github.com/Rhoban/bam/tree/HEAD/bam/params/feetech_sts3215_7_4V
  - m1: kt 1.178, R 2.479, armature 0.0261, max_velocity 5.29 rad/s, command_delay 1.05 ms, friction_base 0.0515, viscous 0.0599
  - m4: kt 1.265, R 2.472, armature 0.0234, max_velocity 5.07 rad/s, command_delay 4.94 ms, friction_base 0.0519, load_friction_base 0.208, viscous 0.0338
  - m6: kt 1.275, R 2.753, armature 0.0216, max_velocity 5.10 rad/s, command_delay 4.98 ms, viscous 0.0282
  - m4 also: error_gain_ratio 1.18, q_offset -0.066 rad, friction_stribeck 0.0111, load_friction_stribeck 4.9e-5, dtheta_stribeck 0.443, alpha 9.99 (all verified against m4.json at HEAD, 2026-10-19).
  - What 'm4' is: BAM friction model M4 = Stribeck + load-dependent friction (paper Sec. III). Supply voltage used in the identification experiments: null (folder/code say 7.4 V; the experiment log voltage is not stated in files read).
  - Units of kt/friction are not stated in the JSON (null); STS3215-specific error reduction vs M1: null (not published in the README/paper).

### 2. Open Duck Mini (STS3215 biped, Playground env) - pragmatic MuJoCo model
- **Two parameter sets exist in the repo; the one the flat-terrain scene actually loads is NOT kp 17.8.** `scene_flat_terrain.xml` includes `open_duck_mini_v2.xml`, whose active `sts3215` class is `damping=0.56 frictionloss=0.068 armature=0.027`, `<position kp="13.37" kv="0.0" forcerange="-3.23 3.23"/>` (commented alternative kp 17.12). The backlash scene (`open_duck_mini_v2_backlash.xml`) has active kp 17.11, forcerange +-3.23, damping 0.56, frictionloss 0.068, armature 0.027, and *comments out* damping 0.60 / frictionloss 0.052 / armature 0.028 / kp 17.8 / +-3.35. Files: https://github.com/apirrone/Open_Duck_Playground/tree/main/playground/open_duck_mini_v2/xmls (read 2026-10-19, branch main; values from fetched file summaries, line numbers null).
- The set 0.60 / 0.052 / 0.028 / kp 17.8 / +-3.35 is the standalone `joints_properties.xml` class `sts3215` (verified): https://github.com/Apirrone/Open_Duck_Playground/blob/main/playground/open_duck_mini_v2/xmls/joints_properties.xml . That file's comments in the other XMLs say its content was merged in, so it is a reference/alternative, not the active scene value. Supply voltage for either set: null. Whether the numbers were derived from BAM: unsupported (no 'bam' string in the Playground README or open_duck_mini_v2.xml).
- Backlash modelled as an extra free joint of +-0.5 deg (0.0087266 rad), damping 0.01, armature 0.01, frictionloss 0 (separate `_backlash` scenes): verified in joints_properties.xml and the backlash XML.
- Latency modelled in the env: `action_min_delay=0, action_max_delay=3` and `imu_min_delay=0, imu_max_delay=3` in `noise_config` (joystick.py ~L62-L65), sampled with `jax.random.randint(minval, maxval)` whose upper bound is exclusive, so sampled indices are 0,1,2 (not 0-3). With ctrl_dt=0.02 s that is at most ~40 ms if index = delay in steps (index-to-delay mapping not traced). https://github.com/apirrone/Open_Duck_Playground/blob/main/playground/open_duck_mini_v2/joystick.py
- Error reduction from this model vs a naive one: null (not reported).
- Note: a torque-limited P servo (MuJoCo `<position>` actuator), not an explicit torque-speed curve. Values were hand-tuned (several kp variants 13.37 / 17.11 / 17.12 / 17.8 coexist in the repo).

### 3. ToddlerBot (Dynamixel, not Feetech) - best documented explicit identification workflow
- Paper: https://arxiv.org/html/2502.00893. Motor test bed backdrives at constant speed, line-fits torque vs speed for damping and friction loss; armature from spin-down energy; a chirp-tracking fit (adapted from Grandia et al.) jointly optimizes 9 parameters; passive-active ratio 3 (~58% gearbox efficiency). Result: average joint tracking error 1.3 deg in sim after fitting.
- XC330 (Table 3): damping 0.0036 N·m·s/rad, armature 0.0040 kg·m², frictionloss 0.036 N·m, tau_max 0.76 N·m, qdot_max 6.50 rad/s, brake torque 1.75 N·m. Measured backlash ~0.25 deg; paper says XC330 "has higher tracking errors and backlash".
- Sim vs real walking tracking: position 0.082 m vs 0.133 m; lin vel 0.016 vs 0.032 m/s; ang vel 0.056 vs 0.113 rad/s (real/sim ~1.6-2.0x). https://arxiv.org/html/2502.00893
- Code: MIT (hardware CC BY-NC-SA 4.0): https://github.com/hshi74/toddlerbot ; actuator model parameters per motor type live in `toddlerbot/descriptions/sysID_*` and randomised via the `tau_max_range`, `q_dot_max_range`, `kd_min_range` fields (see file b; the `sysID_*` path is not re-verified).

### 4. MuJoCo position actuator (kp/kv) vs explicit torque models
- MuJoCo `<position>`: force = kp*(ctrl - q) - kv*qdot, clamped by `forcerange`; no speed-dependent torque falloff, no voltage, no delay unless added by the user. Reference: https://mujoco.readthedocs.io/en/stable/XMLreference.html#actuator-position (not re-fetched in detail; qualitative).
- Explicit torque model (compute torque in Python/JAX from q, qdot, voltage, and write `ctrl` to a `<motor>`): needed for torque-speed droop (back-EMF), voltage-dependent torque, Stribeck/load friction (BAM M2-M6), firmware rate limiting. BAM provides exactly this for STS3215 (see 1).
- Berkeley Humanoid (research humanoid, not hobby) went the other way: torque source, 1 kHz, "no delay", rotor inertia as joint armature. https://arxiv.org/html/2407.21781
- Berkeley Humanoid Lite measured cycloidal backlash: maximum observed 0.0229 rad (separately, SD 0.0042 rad), gearbox mechanical efficiency ~90%; no DR table in the text read. https://arxiv.org/html/2504.17249

## Gaps
- No public ablation of "kp/kv position actuator vs BAM" for STS3215 walking policies (null).
- No 12 V STS3215 BAM parameters (null); verify supply voltage of the Open Humanoid bus.

## Recommendation for Open Humanoid
For the 0.5 m, 16x STS3215 biped, start sizing and first policies with the Open Duck Mini servo class (repo has several sets: active scene kp 13.37 / +-3.23 N·m / damping 0.56 / frictionloss 0.068 / armature 0.027; standalone alternative kp 17.8 / +-3.35 / 0.60 / 0.052 / 0.028; all at unstated voltage, 7.4 V presumed), because it is a proven STS3215 walker, and randomise kp +-10% and friction/armature as in file b. In parallel, run BAM's STS3215 pipeline on one real servo at the project's bus voltage (BAM ships 7.4 V only), and replace the position actuator with a BAM-style explicit model (M4 as default; M6 only if validation justifies the extra parameters, as M5/M6 overfit on Dynamixels) that includes the identified ~5 ms command delay (7.4 V m4/m6), ~5.1 rad/s no-load speed and back-EMF torque droop. Model backlash as a +-0.5 deg slack joint only where the gear train needs it. For torque sizing, trust peak torque at a given joint speed from the BAM voltage model rather than the flat forcerange, since the flat clamp will under-report speed-limited joints (knees at walking speed).
