"""Delivered-total calculator for the Adam concept candidates (T-0002, quotes dated 2026-10-19).

Run:  .venv/Scripts/python variants/adam/sourcing/totals.py          (prints the markdown tables used in QUOTES.md)

Two price scenarios per part, both taken from LIVE pages read on 2026-10-19 (see QUOTES.md for URLs):
  FAST   = fastest US-stocked / duty-included source
  CHEAP  = cheapest source with a visible, in-stock price (not the cheapest listing anywhere: sold-out prices are excluded)
Lines whose price is an ESTIMATE (no readable live page) are flagged in EST and counted separately.
Candidate part lists mirror variants/adam/concepts/*.yaml (parts.onboard + offboard + printed-structure kg from the generated reports).
"""
from __future__ import annotations

TAX = 0.0753          # population-weighted US combined sales tax, Tax Foundation, 1 Jul 2026 (0 in OR/NH/MT/DE/AK)
CONTINGENCY = 0.10
TARIFF_EXPOSURE = 0.375   # 25% legacy Sec.301 electronics + 12.5% Sec.301 'forced-labor' tier, secondary sources only; applies ONLY to non-DDP China-origin lines
SHIP = {"FAST": 45.0, "CHEAP": 60.0}   # ESTIMATE: ~5 paid small orders x $9 (+$15 for the Seeed servo order); only OpenELAB's rates were actually read

P = {  # part -> (FAST, CHEAP)
    "servo12": (27.99, 20.90),      # OpenELAB C018 flat DDP | Seeed C047 at 10+
    "servo7v4": (23.99, 20.99),     # OpenELAB C001 | Seeed C001 at 10+
    "sts3250": (73.99, 73.99),      # OpenELAB only credible quote (pre-order)
    "zero2w": (17.25, 16.35),       # PiShop | CanaKit  (ALL OUT OF STOCK)
    "pi5": (110.0, 110.0),          # PiShop in stock
    "sd": (14.95, 9.97),            # PiShop snippet | CDW snippet
    "adapter": (11.30, 4.99),       # eBay snippet | Waveshare
    "imu": (29.50, 29.50),          # Adafruit
    "cam": (29.25, 29.25),          # Adafruit / PiShop
    "camcable": (5.95, 3.16),       # Adafruit 3157 | Adafruit 5819
    "lipo3s": (27.60, 27.60),       # Aloft (stock unclear)
    "lipo2s": (16.0, 16.0),         # ESTIMATE, no US quote found
    "buck_dfr": (6.21, 4.90),       # RobotShop | DFRobot (7 V min in: 3S only)
    "buck_d24": (26.95, 26.95),     # Pololu D24V22F5 (2S-compatible)
    "buck_d36": (39.95, 39.95),     # Pololu / RobotShop
    "switch": (6.0, 6.0),           # ESTIMATE
    "fasteners": (20.0, 20.0),      # ESTIMATE
    "bearings": (12.0, 12.0),       # ESTIMATE
    "wiring": (10.0, 10.0),         # ESTIMATE
    "charger": (49.95, 39.99),      # Evike | WREKD (sold out)
    "psu": (29.99, 29.99),          # 65 W PD, deal-site snapshot
    "fuse": (4.5, 4.25),            # Del City holder + fuse estimate
    "gamepad": (38.68, 38.68),      # Logitech F710 SHI
    "pla_kg": (21.99, 18.0),        # MatterHackers PolyLite | catalog estimate
}
EST = {"lipo2s", "switch", "fasteners", "bearings", "wiring", "psu", "fuse", "gamepad", "pla_kg", "sd", "adapter", "camcable"}
# lines that are sourced from China and may carry duty NOT included in the shown price in the CHEAP scenario
CHINA_NON_DDP = {"CHEAP": {"servo12", "servo7v4", "adapter"}, "FAST": set()}

CAND = {
    "A 3S/12V STS3215": dict(lines={"servo12": 23, "zero2w": 1, "sd": 1, "adapter": 1, "imu": 1, "cam": 1, "camcable": 1, "lipo3s": 1, "buck_dfr": 1,
                                    "switch": 1, "fasteners": 1, "bearings": 1, "wiring": 1, "charger": 1, "pla_kg": 0.758},
                             spares={"servo12": 3}),
    "B 2S/7.4V STS3215": dict(lines={"servo7v4": 23, "zero2w": 1, "sd": 1, "adapter": 1, "imu": 1, "cam": 1, "camcable": 1, "lipo2s": 1, "buck_d24": 1,
                                     "switch": 1, "fasteners": 1, "bearings": 1, "wiring": 1, "charger": 1, "pla_kg": 0.758},
                              spares={"servo7v4": 3}),
    "C 3S + 2x STS3250 + Pi 5": dict(lines={"servo12": 21, "sts3250": 2, "pi5": 1, "sd": 1, "adapter": 1, "imu": 1, "cam": 1, "camcable": 1, "lipo3s": 1, "buck_d36": 1,
                                            "switch": 1, "fasteners": 1, "bearings": 1, "wiring": 1, "charger": 1, "pla_kg": 0.758},
                                     spares={"servo12": 2, "sts3250": 1}),
    "D 3S/12V + transmissions": dict(lines={"servo12": 23, "zero2w": 1, "sd": 1, "adapter": 1, "imu": 1, "cam": 1, "camcable": 1, "lipo3s": 1, "buck_dfr": 1,
                                            "switch": 1, "fasteners": 1, "bearings": 1, "wiring": 1, "charger": 1, "pla_kg": 0.758},
                                     spares={"servo12": 3}),
    "E duck-like 14 DOF (reference)": dict(lines={"servo7v4": 14, "zero2w": 1, "sd": 1, "adapter": 1, "imu": 1, "lipo2s": 1, "buck_d24": 1, "switch": 1, "wiring": 1,
                                                  "charger": 1, "pla_kg": 0.616},
                                           spares={"servo7v4": 2}),
}
# adders required by every candidate (challenge-2 row 14)
ADDERS = {"psu": 1, "fuse": 1, "gamepad": 1}


def total(name, scen):
    i = 0 if scen == "FAST" else 1
    c = CAND[name]
    lines = dict(c["lines"])
    for k, q in ADDERS.items():
        lines[k] = lines.get(k, 0) + q
    parts = sum(P[k][i] * q for k, q in lines.items())
    est = sum(P[k][i] * q for k, q in lines.items() if k in EST)
    spares = sum(P[k][i] * q for k, q in c["spares"].items())
    gamepad = P["gamepad"][i]
    tax = (parts + spares) * TAX
    ship = SHIP[scen]
    delivered = parts + spares + tax + ship
    with_cont = delivered * (1 + CONTINGENCY)
    core = (parts - gamepad + (tax * (parts - gamepad) / (parts + spares)) + ship) * (1 + CONTINGENCY)   # without spares and gamepad
    exposed = sum(P[k][i] * q for k, q in lines.items() if k in CHINA_NON_DDP[scen]) + sum(P[k][i] * q for k, q in c["spares"].items() if k in CHINA_NON_DDP[scen])
    tariff = exposed * TARIFF_EXPOSURE
    servo_sub = sum(P[k][i] * q for k, q in lines.items() if k.startswith(("servo", "sts"))) + spares
    return dict(parts=parts, est=est, spares=spares, tax=tax, ship=ship, delivered=delivered, with_cont=with_cont, core=core, tariff=tariff,
                worst=(delivered + tariff) * (1 + CONTINGENCY), servo_sub=servo_sub)


def floor(name, servo_override=None):
    """Lowest conceivable sticker: CHEAP prices, no gamepad (use a phone), no spares, no tax, no shipping, no contingency."""
    lines = dict(CAND[name]["lines"])
    lines["psu"] = 1
    lines["fuse"] = 1
    tot = 0.0
    for k, q in lines.items():
        p = servo_override if (servo_override and k in ("servo12", "servo7v4")) else P[k][1]
        tot += p * q
    return tot


if __name__ == "__main__":
    print("| Candidate | Floor sticker (CHEAP prices, no gamepad/spares/tax/ship/contingency) | Floor with WowRobo $13.99 servos (sold out, unconfirmed) |")
    print("|---|---|---|")
    for n in CAND:
        print(f"| {n} | ${floor(n):.0f} | ${floor(n, 13.99):.0f} |")
    print()
    print("| Candidate | Scenario | Parts | of which ESTIMATE | Spares | Tax 7.53% | Ship (est) | Delivered | +10% contingency | Fits $550? | Without spares+gamepad (+10%) | Tariff exposure if not DDP |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for n in CAND:
        for s in ("FAST", "CHEAP"):
            t = total(n, s)
            fit = "yes" if t["with_cont"] <= 550 else "NO"
            print(f"| {n} | {s} | ${t['parts']:.0f} | ${t['est']:.0f} | ${t['spares']:.0f} | ${t['tax']:.0f} | ${t['ship']:.0f} | ${t['delivered']:.0f} | **${t['with_cont']:.0f}** | {fit} | ${t['core']:.0f} | +${t['tariff']:.0f} (worst ${t['worst']:.0f}) |")
