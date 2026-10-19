# Low-cost humanoids and actuators: summary (T-20261019-568a, 2026-10-19)

The commander saved this from the research agent's report; the subagent harness refused report-file writes. Details: `humanoids.md`, `bumi-why-cheap.md`, `actuators.md`, `feasibility.md` (+ `.py`, `-output.txt`), `verification.yaml` (33 claims: 28 verified, 5 corrected, 0 removed).

## Why is Adam 2 ft and ≤ $1,600 when Noetix Bumi is ~3 ft and "$1,370"?
- **Physics and parts.** A ~1 m humanoid needs quasi-direct-drive (QDD) class joints. Bumi's own BSD-3 training config limits joints to 60 N·m (hip pitch, knee), 27 (hip yaw/roll, waist), 13 (ankles) and 5.5 (arms). The cheapest torque-capable integrated joints cost ~$110–255 at retail (RobStride RS05–RS04), so Bumi-class actuators alone would be ~$3.0–3.3k retail. Adam's $21–74 Feetech servos are 2–5 N·m hobby parts: that's why Adam is small and cheap.
- **The $1,370 isn't a US price.** It's the CNY 9,998 JD.com presale price in China (Chinese delivery address; quote-only abroad). One US reseller lists Bumi at $5,995 (quote-confirmed; authorisation unclear). No independent hands-on or walking test exists. Official spec: 98 cm, ~17 kg (launch press said 12 kg; mass unresolved), 21 DOF, 0.5 m/s, 48 V.
- **Why it's cheap (partly inference):** venture-funded (~CNY 300 M Pre-B; ~$145 M Series B reported), with founder-admitted low margins; in-house boards and drivers; domestic supply chain; a modest spec (no moving hands, 0.5 m/s, "quasi-consumer").
- FF Nova: 0.50 m, 2.8 kg, 20 DOF, $2,490. Smaller and dearer than Adam. The zyrestore product is a $44.99 dropship toy, not a humanoid.

## Are we missing something?
Nothing that makes a 0.9 m robot cheap for a US hobbyist. New and useful:
1. **RobStride RS06** (36/11 N·m, 621 g, ~$210), plus RS00/RS05, a strong cheap class for **Eve**.
2. Noetix publishes a BSD-3 SDK, Isaac Lab config, URDF and per-joint torque limits: free design data for Eve.
3. A ~1 m, 21-DOF humanoid is commercially viable, at venture-funded prices.

## Feasibility of a ~0.9 m Adam (our scaling, not engine-simulated)
23 DOF + 2 grippers on RobStride RS06/RS02/RS00/RS05 + STS for the wrists/neck/grippers; ~11.7–12.8 kg. **Delivered ≈ $5.4–6.7k**, 3.4–4.2× the $1,600 lock (the actuators alone exceed it). That's consistent with comparable builds: Berkeley Humanoid Lite 0.8 m $4.3k BOM, AGILOped 1.1 m $6.4k, Roboto Origin ~1.25 m ~$7k, Unitree R1 $4.9–5.9k before shipping. Even 0.7 m doesn't fit (actuators ~$1.8–2.1k).

## Recommendation
- **Keep Adam at ~0.55 m within the lock.** Proceed with the bench servos and CAD as planned; nothing here invalidates the packaging study.
- **A bigger BLDC humanoid is Eve's class (~$5–7k).** Optional de-risking for Eve (maintainer's call): one RS06 + one RS02 + a USB-CAN adapter (~$450) to start measuring a QDD model.
- If a ~3 ft robot to hack on is wanted sooner, buying a Bumi (~$6k if obtainable) and building a 0.9 m Adam (~$5.4–6.7k) cost about the same: Bumi brings an SDK and sim assets, a build gives open hardware; neither is verified to walk well.

## Still unknown (measurable only)
Bumi's motor maker, true mass, margin and durability; RobStride delivered and duty cost; RS06 thermal behaviour and backlash; push-recovery margin at 12 kg.
