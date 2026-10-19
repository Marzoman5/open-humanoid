# Humanoid benchmarks (accessed 2026-10-19)

Source of truth with citations: `benchmarks.yaml`. v = vendor/spec-sheet claim, m = paper-measured, `-` = unknown (not guessed).

## Comparison

| Robot | h (m) | mass (kg) | DOF leg/arm/total | Actuators | Compute | Battery | Cost USD | Zero-shot s2r walk | Sim |
|---|---|---|---|---|---|---|---|---|---|
| ToddlerBot | 0.56 v | 3.4 m | 6/7/30 | Dynamixel XC330/XC430/XM430 | Orin NX 16G | 14.8 V, Wh - | <6,000 (2025) | yes | MuJoCo/MJX |
| Open Duck Mini v2 | 0.42 v | - | -/0/14 | Feetech STS3215 x14 | Pi Zero 2W | 2S 3000 mAh (~22 Wh derived) | ~400 target | partial | Isaac Gym, MuJoCo |
| Zeroth-01 | - | - | -/-/- (16 servos, secondary) | STS3215/50 x16 (secondary) | Milk-V Duo S | - | BOM from 350 | null | K-Sim |
| BH Lite | 0.8 | 16 | -/5/22 | printed cycloidal 6512/5010 | N95 PC | 6S 4000 mAh (~89 Wh derived) | 4,312 BOM | yes | Isaac Gym |
| Berkeley Humanoid | 0.85 | 16 (no arms) | 6/0/12 | custom QDD 5013-10413 | i7-1255U | DJI TB50 | ~9,955 (2024) | yes | Isaac Lab |
| ROBOTIS OP3 | 0.51 | 3.5 | -/-/20 | XM430-W350 | NUC i3 | 11.1 V 3300 mAh | - | null | - |
| Hiwonder AiNex | - | 2.45 (retailer) | -/-/24 | HX-35H/HX-35HM bus servos | Pi 5 | 11.1 V 3500 mAh | - | null | - |
| Unitree R1 | 1.23 | 29 | -/-/26 | proprietary | - | ~1 h | 5,900 | null | - |
| Booster T1 | 1.18 | 30 | -/-/23 | proprietary (knee 130 Nm) | AGX Orin | 10.5 Ah | ~30,000 | null | - |
| Asimov 1 | 1.2 | 35 | 6/5/25 | - | Radxa CM5 | 13S4P | ~15,000 (secondary) | null | - |
| Unitree G1 | 1.32 | 35 | 6/5/23 | proprietary (knee 90 Nm) | 8-core | 9 Ah, ~2 h | 13,500 | null | - |
| Unitree H1 | 1.8 | 47 | 5/4/- | proprietary (knee 360 Nm) | - | 864 Wh | ~90,000 | null | - |
| Poppy | - | - | -/-/- | Dynamixel MX-28 | Pi | - | - (unverified) | null | - |

Walking speed: not reported for any robot except H1's vendor "moving speed" record of 3.3 m/s. Bez/HR-OS could not be identified from primary sources. Not researched to a citable level: RoboBuilder, KHR, BD-1, Roboto Origin, Digit/Cassie, Pollen/HF. K-Bot only from an unofficial source.

## Lessons (concise)
- **ToddlerBot** (closest class): chirp-based motor system-ID (1.3 deg error) enabled zero-shot walking. Motor heating drifted the robot out of the policy distribution (model has no temperature term). Printed parts crack on impact (~7 falls to a break); best no-fall streak 19 min. XC330 (1 Nm) has the worst backlash.
- **Open Duck Mini**: STS3215 x14, 2S pack, Pi Zero 2W. Sim2real walking "starting to work" (partial). v1 needed XL330 -> XC330 for power and had joint play. Actuator identification via Rhoban BAM is UNVERIFIED for Open Duck Mini (BAM, from the same group, ships an STS3215 7.4V model; no source links the two). Overcurrent trip figure and load-derating advice were unsupported and removed (see VERIFICATION.md). No public mass or thermal data.
- **Zeroth-01**: STS3215, cheap BOM, but alpha/beta quality; company shut down Nov 2025 (36kr: failed financing, refunds, IP to be open-sourced). Servo count: 16 per secondary sources; no 18 found; repo/docs do not state it. Design reference only.
- **BH Lite**: PPO policy transferred zero-shot using ~30% of torque limit; printed gearbox backlash rose with wear but stayed usable over 60 h; heat lowers efficiency.
- **Berkeley Humanoid**: zero-shot with narrow randomization; 38 falls, 2 minor damage; torque-saturation nonlinearity and thermal protection flagged as unmodeled.
- **OP3 / AiNex / Poppy**: no RL data. OP3 is a mass/size anchor. Poppy shows Dynamixel cost dominating.
- **Unitree / Booster / Asimov**: vendor specs only; used for scaling.

## Scaling fits
Method: log-log least squares (numpy), script in OS temp dir (`fit.py`). Reproducible from the points below.

### Mass vs height, mass = k * h^n
Points (N = 9, re-verified against sources 2026-10-19): ToddlerBot 0.56 m / 3.4 kg; OP3 0.51 / 3.5; BH Lite 0.8 / 16; Berkeley Humanoid 0.85 / 16 (no arms; 22 kg with arms per paper); Booster T1 1.18 / 30; Asimov 1 1.2 / 35; Unitree R1 1.23 / 29 (corrected from 1.21/25); G1 1.32 / 35; H1 1.8 / 47.

| Fit | N | k | n | R^2 | Mass at 0.5 m |
|---|---|---|---|---|---|
| all, free n | 9 | 18.5 | 2.28 | 0.93 | 3.8 kg |
| without Berkeley Humanoid | 8 | 18.0 | 2.31 | 0.93 | 3.6 kg |
| n fixed = 3 | 9 | 18.8 | 3 | 0.84 | 2.35 kg |
| h < 1 m only | 4 | 30.1 | 3.42 | 0.96 | 2.8 kg |
| Berkeley Humanoid at 22 kg (with arms) | 9 | 19.1 | 2.25 | 0.90 | 4.0 kg |

- Mass at 0.5 m: fit gives 2.3 to 3.8 kg (4.0 if BH counted with arms). Nearest real robots: OP3 3.5 kg at 0.51 m (vendor, no skin) and ToddlerBot 3.4 kg at 0.56 m (measured, 3484 g total in payload test); both exceed the n=3 fit, so scaling-law lower values look optimistic. Only two points are near 0.5 m; the sub-1 m gap (0.56 to 0.8 m) has no data.
- Measured 0.5 m robots (ToddlerBot 3.4, OP3 3.5 kg) bracket the free fit. N is small, the data mix vendor claims and different payloads, and the sub-1 m fit has only 4 points, so n there is not meaningful.
- Adam's structure-only 6.4*h^3 gives 0.80 kg at 0.5 m. This is structure only. Add 16 STS3215 at 55 g each (0.88 kg, vendor) plus battery, compute and wiring. The benchmark totals (2.3 to 3.8 kg) imply 1.5 to 3 kg of non-structure mass, so a ~1.7 kg all-up target would be optimistic and ~2.5 to 3.5 kg is the evidence-backed range.

### Knee torque vs height
Points (N = 5): ToddlerBot 0.56 m / 3.0 Nm (stall); Berkeley Humanoid 0.85 / 81.1 (peak); T1 1.18 / 130; G1 1.32 / 90; H1 1.8 / 360. Free fit: k = 51, n = 3.73, R^2 = 0.85; at 0.5 m this predicts 3.9 Nm (n fixed at 3: 6.7 Nm). Without ToddlerBot the fit is unstable (n = 1.86, R^2 = 0.72, N = 4, extrapolates to ~25 Nm at 0.5 m, i.e. meaningless). The ToddlerBot point is the XM430-W210 stall spec (3.0 Nm), not a peak; G1 90 Nm is "strongest joint motor" per vendor; torque points unchanged by verification. Hip: only two points (ToddlerBot 1.8 Nm at 0.56 m; Berkeley Humanoid 62.6 Nm at 0.85 m), so no fit.
- Mixes stall and peak specs and very different gear designs, so treat as indicative. Expected requirement ~2.4 to 4 Nm knee at 0.5 m (ToddlerBot's own estimate at 0.56 m is 2.35 Nm).
- STS3215 reference (vendor): 1.9 Nm at 6 V (copper gears), 2.9 Nm at 12 V (steel gears), 55 g.

## Top findings for a 0.5 m STS3215 robot
1. Real 0.5 m robots weigh 3.4 to 3.5 kg; scaling gives 2.3 to 3.8 kg all-up.
2. Knee need ~2.4 to 4 Nm vs STS3215 1.9 Nm (7.4 V) to 2.9 Nm (12 V steel gear) stall: thin margin.
3. Zero-shot sim-to-real needs an identified actuator model (ToddlerBot chirp sysid; BAM provides an STS3215 7.4V model, but its use in Open Duck Mini is unverified).
4. Heating drifts policies; log servo temperature and derate.
5. Only Open Duck Mini (0.42 m) is a direct STS3215 analogue and its sim2real is partial; Zeroth is unreliable.

Honesty: n is 4 to 9, mixed vendor/measured data, many fields null.
