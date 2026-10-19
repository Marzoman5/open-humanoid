# 0014: Concept gates are calibrated against robots that work; provisional until bench-measured

- **Status:** accepted by commander under the maintainer's overnight authority; **PROVISIONAL** until the bench identification of STS3215 (12 V + 7.4 V) · **Date:** 2026-10-19 · **Scope:** toolkit (method) + variant:adam
- **Evidence:** challenge #2 rows 1–3 (`variants/adam/reviews/challenge-2-concept-results.md`); calibration results `variants/adam/generated/concept/calibration/`; `docs/concept-engine.md`

## Context
The concept gates (p95 peak ≤ 70% of datasheet stall, RMS ≤ vendor-rated continuous, torque-speed envelope ≤ 90%) failed every Adam candidate, and also failed **Open Duck Mini**, a 0.42 m, 14× STS3215 robot that walks on real hardware. Running our frozen gait on ODM's own MuJoCo model through the identical gate code gave worst-joint values of:
- 1.06 peak/stall (gate 0.70), so **×1.52**
- 1.94–2.52 RMS/rated (gate 1.0), so **×1.94–2.52** depending on the retailer "rated" label
- 1.06 envelope (gate 0.90), so **×1.18**
- overload passes

ODM's own training sim gives each servo 3.23 N·m; BAM's electrical model gives 3.7 N·m. The gates used the 1.91 N·m datasheet stall. The real stall and real continuous torque are unmeasured.

## Decision
1. **Principle:** a gate set that fails a robot proven to work on hardware is miscalibrated. Gates are calibrated first against known-working robots, then replaced by bench measurements.
2. **Until the bench test:** every concept is reported under two gate sets:
   - **strict** (datasheet), unchanged in `openhumanoid/concept/thresholds.yaml`
   - **ODM-calibrated** (strict gates relaxed by the measured factors: peak ×1.52, RMS ×1.94 using the 0.637 N·m rated label, envelope ×1.18), via `sweep.relaxed_feasibility`

   R1 ranks candidates on the calibrated set, and must also report the strict set.
3. **After the bench test:** stall, torque-speed, armature, and a 15-minute thermal-hold continuous torque are measured on one 12 V and one 7.4 V STS3215. They replace the datasheet values and the ODM factors. All candidates are re-run, and the R1 decision is re-confirmed or changed.
4. Thresholds are never tuned to make a candidate pass. Only measured calibration evidence changes them, recorded in an ADR.

## Consequences
- (+) Decisions rest on reality (a robot that walks) instead of retailer labels.
- (−) One known robot, one gait: a thin calibration. R1 is provisional until the bench result, which sits on the critical path.
