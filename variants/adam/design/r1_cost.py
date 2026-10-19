"""R1 budget paths: delivered cost per concept configuration at the VERIFIED 2026-10-19 quotes (T-20261019-36f9).

Run:  .venv/Scripts/python variants/adam/design/r1_cost.py            (prints the markdown tables used in the R1 package)
      .venv/Scripts/python variants/adam/design/r1_cost.py --json PATH (also writes the numbers)

Prices, tax, shipping, tariff exposure and the contingency rule are imported from variants/adam/sourcing/totals.py (T-0002; every price
there has a vendor URL in QUOTES.md). Nothing is re-priced here: this file only changes the LINE LIST per configuration (servo count,
compute, regulator, pack, charger, gamepad, spares) so the two budget paths can be compared side by side.

Accounting, identical to QUOTES.md section 1:
  parts      = sum(price x qty) incl. the adders every build needs (charger PSU, fuse) and the gamepad when listed
  delivered  = parts + spares + 7.53% sales tax on (parts + spares) + estimated shipping
  R1 total   = delivered x 1.10 (10% contingency)          <- the number that is tested against the $550 cap
  sticker    = parts only (no spares, tax, shipping, contingency): shown so the maintainer sees how far the definition moves the answer
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("adam_totals", HERE.parent / "sourcing" / "totals.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)  # type: ignore[union-attr]

P = dict(T.P)
# Lines not in totals.py, from the catalog (price_usd.typical, verified flag in brackets), used only by the options below.
EXTRA = {
    "lipo3s_1300": (26.99, 26.99),     # catalog lipo-3s-1300-tattu, verified: true (RaceDayQuads / WREKD, QUOTES.md section 3)
    "charger_b3": (9.0, 9.0),          # catalog charger-b3-3s, verified: false (QUOTES.md section 5: "not re-quoted")
    "imu_icm": (8.0, 8.0),             # catalog imu-icm42688, verified: false
    # NOT in the catalog yet (a sourcing task must add it): Raspberry Pi 5 1 GB, Adafruit #6447, $49.50, page says in stock, read 2026-10-19
    # by the R1 compute check (https://www.adafruit.com/product/6447); PiShop lists it at $45.00 but out of stock.
    "pi5_1gb": (49.50, 49.50),
    # Pi Zero 2 W: the only in-stock US route on 2026-10-19 is the PiShop starter kit, $74.95 (https://www.pishop.us/product/raspberry-pi-zero-2-w-starter-kit/)
    "zero2w_kit": (74.95, 74.95),
}
for k, v in EXTRA.items():
    P.setdefault(k, v)
EST = set(T.EST) | {"charger_b3", "imu_icm"}
# cheap_buck: the DFR0831 (4 A, 7-24 V in, verified) instead of the Pololu D36V50F5 (5.5 A) for a Pi 5. Raspberry Pi specifies 5 V / 5 A for full
# USB current and runs with reduced USB current from a 3 A supply; Adam's Pi 5 has no USB load (camera on CSI, IMU on I2C, servo bus on UART),
# measured Pi 5 load ~9 W = 1.8 A (Jeff Geerling, stress-ng). A risk to confirm at bring-up, not a verified rating.

COMMON = {"sd": 1, "adapter": 1, "cam": 1, "camcable": 1, "switch": 1, "fasteners": 1, "bearings": 1, "wiring": 1, "psu": 1, "fuse": 1}


def config(name: str, *, servo: str, n_servo: int, n_sts3250: int = 0, compute: str = "pi5", pack: str = "lipo3s_1300", imu: str = "imu",
           charger: str = "charger", gamepad: bool = True, cheap_buck: bool = False, spares: int | None = None, pla_kg: float = 0.758, note: str = "",
           spares_mix: dict | None = None) -> dict:
    lines = dict(COMMON)
    lines[servo] = n_servo
    if n_sts3250:
        lines["sts3250"] = n_sts3250
    lines[compute] = 1
    lines["buck_d36" if compute in ("pi5", "pi5_1gb") and not cheap_buck else ("buck_d24" if servo == "servo7v4" else "buck_dfr")] = 1
    lines[pack] = 1
    lines[imu] = 1
    lines[charger] = 1
    if charger == "charger_b3":
        lines.pop("psu", None)        # the B3 is a wall-plug charger: no separate DC supply
    if gamepad:
        lines["gamepad"] = 1
    lines["pla_kg"] = pla_kg
    if spares is None:                 # QUOTES.md section 6 rule: ~13% (3 per 23, 2 per 14)
        spares = max(1, round(0.13 * (n_servo + n_sts3250)))
    sp = dict(spares_mix) if spares_mix is not None else ({servo: spares} if spares else {})
    return {"name": name, "lines": lines, "spares": sp, "note": note}


def total(c: dict, scen: str = "CHEAP") -> dict:
    i = 0 if scen == "FAST" else 1
    lines = c["lines"]
    parts = sum(P[k][i] * q for k, q in lines.items())
    est = sum(P[k][i] * q for k, q in lines.items() if k in EST)
    spares = sum(P[k][i] * q for k, q in c["spares"].items())
    tax = (parts + spares) * T.TAX
    ship = T.SHIP[scen]
    delivered = parts + spares + tax + ship
    r1 = delivered * (1 + T.CONTINGENCY)
    exposed = sum(P[k][i] * q for k, q in lines.items() if k in T.CHINA_NON_DDP[scen]) + sum(P[k][i] * q for k, q in c["spares"].items() if k in T.CHINA_NON_DDP[scen])
    servo_cost = sum(P[k][i] * q for k, q in lines.items() if k.startswith(("servo", "sts"))) + spares
    return {"scenario": scen, "parts_sticker": round(parts, 2), "estimate_lines": round(est, 2), "spares": round(spares, 2), "tax": round(tax, 2), "ship": ship,
            "delivered": round(delivered, 2), "r1_total": round(r1, 2), "fits_550": r1 <= 550.0, "tariff_worst": round((delivered + exposed * T.TARIFF_EXPOSURE) * (1 + T.CONTINGENCY), 2),
            "servo_share": round(servo_cost / (parts + spares), 3)}


def per_servo_r1(scen: str = "CHEAP", servo: str = "servo12") -> float:
    """What one more servo costs at the R1 accounting (price x (1 + 13% spares) x tax x contingency)."""
    i = 0 if scen == "FAST" else 1
    return P[servo][i] * 1.13 * (1 + T.TAX) * (1 + T.CONTINGENCY)


def max_servos_under(cap: float, base: dict, scen: str = "CHEAP", servo: str = "servo12") -> int:
    """Largest servo count n for which `base` (same lines, n servos, ~13% spares) stays at or under `cap` at the R1 accounting."""
    best = 0
    for n in range(0, 40):
        c = json.loads(json.dumps(base))
        c["lines"][servo] = n
        c["spares"] = {servo: max(0, round(0.13 * n))} if n else {}
        if total(c, scen)["r1_total"] <= cap:
            best = n
    return best


# Printed structure: the concept engine's nominal structure mass (11.9 kg/m^3 x h^3, the Open Duck Mini back-out) + 15% print waste:
# 0.55 m -> 1.98 kg x 1.15 = 2.28 kg PLA+; 0.60 m -> 2.57 kg x 1.15 = 2.96 kg (totals.py's 0.758 kg was sized for 0.45 m).
PLA_055, PLA_060 = 2.28, 2.96
LEAN = dict(gamepad=False, charger="charger_b3", imu="imu_icm", compute="pi5_1gb", cheap_buck=True)
CONFIGS = [
    # ---------------- path 1: full requirements
    config("P1 RECOMMENDED: 23 DOF, 19 STS3215-12V + 4 STS3250 (knees, hip roll), 0.60 m, Pi 5 1 GB + D36V50F5, 3S 1300, BNO085, B6neo, gamepad",
           servo="servo12", n_servo=19, n_sts3250=4, compute="pi5_1gb", pla_kg=PLA_060, spares_mix={"servo12": 2, "sts3250": 1}, note="path 1"),
    config("P1 rec. with a phone instead of the gamepad (R9 allows it)", servo="servo12", n_servo=19, n_sts3250=4, compute="pi5_1gb", pla_kg=PLA_060, gamepad=False,
           spares_mix={"servo12": 2, "sts3250": 1}),
    config("P1 runner-up: 23 DOF, 21 STS3215-12V + 2 STS3250 (knees), 0.55 m, Pi 5 1 GB", servo="servo12", n_servo=21, n_sts3250=2, compute="pi5_1gb", pla_kg=PLA_055,
           spares_mix={"servo12": 2, "sts3250": 1}),
    config("P1 if the bench is favourable: 23 DOF, 23 STS3215-12V, 0.55 m, Pi 5 1 GB", servo="servo12", n_servo=23, compute="pi5_1gb", pla_kg=PLA_055),
    # ---------------- path 2: the $550 cap
    config("P2 RECOMMENDED (cheapest that keeps every engine-checked MUST): 21 servos, 6-DOF legs, no waist, neck 2, 3-DOF arms, 1 gripper, 0.55 m, lean",
           servo="servo12", n_servo=21, pla_kg=PLA_055, **LEAN),
    config("P2 rec. with no spares", servo="servo12", n_servo=21, pla_kg=PLA_055, spares=0, **LEAN),
    config("P2 16 servos (5-DOF legs, neck yaw, 2-DOF arms, 1 gripper), 0.55 m, lean, no spares", servo="servo12", n_servo=16,
           pla_kg=PLA_055, spares=0, **LEAN),
    config("P2 cap held on the sticker: 14 servos (5-DOF legs, neck yaw, ONE arm: shoulder pitch + roll + gripper), 0.55 m, lean, no spares", servo="servo12",
           n_servo=14, pla_kg=PLA_055, spares=0, **LEAN),
    # ---------------- references
    config("ref: 23 x STS3215-12V, 0.758 kg filament (QUOTES.md basis), Pi Zero 2 W board price (out of stock)", servo="servo12", n_servo=23, compute="zero2w"),
    config("ref: 23 x STS3215-7.4V on 2S, 0.60 m, Pi 5 1 GB", servo="servo7v4", n_servo=23, pack="lipo2s", compute="pi5_1gb", pla_kg=PLA_060),
]


def markdown(rows: list[dict]) -> str:
    L = ["| Configuration | Servos | Sticker parts | Spares | Tax | Ship (est) | Delivered | **R1 total (+10%)** | Fits $550? | Fast-US R1 total | Worst tariff case | Estimate lines |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        c, f = r["cheap"], r["fast"]
        L.append(f"| {r['name']} | {r['servos']} | ${c['parts_sticker']:.0f} | ${c['spares']:.0f} | ${c['tax']:.0f} | ${c['ship']:.0f} | ${c['delivered']:.0f} | **${c['r1_total']:.0f}** | "
                 f"{'yes' if c['fits_550'] else 'NO'} | ${f['r1_total']:.0f} | ${c['tariff_worst']:.0f} | ${c['estimate_lines']:.0f} |")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    rows = []
    for c in CONFIGS:
        n = sum(q for k, q in c["lines"].items() if k.startswith(("servo", "sts")))
        rows.append({"name": c["name"], "servos": n, "lines": c["lines"], "spares_lines": c["spares"], "cheap": total(c, "CHEAP"), "fast": total(c, "FAST")})
    print(markdown(rows))
    lean = config("lean base", servo="servo12", n_servo=0, gamepad=False, charger="charger_b3", imu="imu_icm")
    lean_p51 = config("lean base pi5 1gb", servo="servo12", n_servo=0, compute="pi5_1gb", cheap_buck=True, gamepad=False, charger="charger_b3", imu="imu_icm")
    lean_zero = config("lean base zero", servo="servo12", n_servo=0, compute="zero2w", gamepad=False, charger="charger_b3", imu="imu_icm")
    out = {"rows": rows,
           "per_servo_r1_cheap": round(per_servo_r1(), 2), "per_servo_r1_fast": round(per_servo_r1("FAST"), 2),
           "max_servos_under_550_lean_pi5": max_servos_under(550, lean), "max_servos_under_550_lean_zero": max_servos_under(550, lean_zero),
           "max_servos_under_550_lean_pi5_1gb": max_servos_under(550, lean_p51), "lean_non_servo_r1_pi5_1gb": total(lean_p51)["r1_total"],
           "lean_non_servo_r1_pi5": total(lean)["r1_total"], "lean_non_servo_r1_zero": total(lean_zero)["r1_total"]}
    print()
    print(f"One more 12 V STS3215 at the R1 accounting: ${out['per_servo_r1_cheap']:.2f} (CHEAP) / ${out['per_servo_r1_fast']:.2f} (FAST)")
    print(f"Non-servo floor at the R1 accounting (lean: phone, B3, ICM-42688, camera, 3S 1300): Pi 5 ${out['lean_non_servo_r1_pi5']:.0f}, Pi Zero 2 W ${out['lean_non_servo_r1_zero']:.0f}")
    print(f"Pi 5 1 GB + DFR0831 lean floor ${out['lean_non_servo_r1_pi5_1gb']:.0f}; most servos under $550: {out['max_servos_under_550_lean_pi5_1gb']}")
    print(f"Most 12 V servos that fit $550 at the R1 accounting on that floor: Pi 5 {out['max_servos_under_550_lean_pi5']}, Pi Zero 2 W {out['max_servos_under_550_lean_zero']}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
