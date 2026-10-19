# Module interface standard (v0.1, draft)

The standard way modules attach to each other and to the body, so a hand from one person fits an arm from another. **Draft: finalized by task T-0006 once Adam's first joint module exists.** Changes need an ADR.

## Mechanical: size classes

Interfaces come in size classes so a 50 cm robot and a 1.7 m robot don't share one bolt pattern.

| Class | Typical robot height | Bolt pattern | Pilot | Fasteners |
|---|---|---|---|---|
| **S** | 0.3–0.8 m | 4× on Ø32 mm PCD | Ø20 mm boss | M3 into heat-set inserts |
| **M** | 0.8–1.4 m | 6× on Ø60 mm PCD | Ø40 mm | M4 |
| **L** | 1.4–2.0 m | 8× on Ø90 mm PCD | Ø60 mm | M5 |

An interface face has a pilot boss (centering), the bolt pattern, an anti-rotation key at 0°, and a cable pass-through (≥ 30% of pilot diameter).

## Electrical

| Signal | Class S | Class M/L |
|---|---|---|
| Power | Battery voltage (3S–4S) | 24–48 V |
| Data | Servo half-duplex TTL bus (daisy-chain) | CAN-FD |
| Connector | JST-PH 3-pin (servo bus) + optional JST-GH 4-pin I²C | XT30 + JST-GH CAN |

## Software

Every module with actuators or sensors declares in `module.yaml`:
- joint names (spec convention) and actuator catalog IDs
- the HAL driver it needs (`feetech_sts`, `dynamixel`, `can_bldc` …)
- optional plugin(s) it provides (e.g. `gripper_basic`)
