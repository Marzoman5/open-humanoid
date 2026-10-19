"""CLI: python -m openhumanoid.concept <command>   (the commander wires it into `oh` later; openhumanoid/cli.py is untouched)

    evaluate <concept.yaml> [--quick] [--samples N] [--table-height M] [--out DIR]
    compare <report.json> [<report.json> ...]
    sweep <concept.yaml> [--heights 0.40 0.45 ...]       height sweep, nominal gates only
    validate-thermal                                      replay the two Robonine runs
    thresholds                                            print the thresholds file
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass


def cmd_evaluate(a) -> int:
    from .evaluate import evaluate
    rep = evaluate(a.concept, out_root=Path(a.out) if a.out else None, samples=a.samples, quick=a.quick, table_height=a.table_height)
    v = rep["verdict"]
    print(f"{rep['candidate']}: {v['status']} | worst joint {rep['nominal']['worst_joint']} margin {rep['nominal']['worst_margin']} "
          f"| robust={v['robust_to_all_bounds']} benchmark-mass={v['passes_at_benchmark_mass']} | {rep['wall_seconds']} s")
    for r in v["reasons"][:6]:
        print("  -", r)
    print("  ->", rep.get("_out"))
    return 0 if v["status"] == "PASS" else 2


def cmd_compare(a) -> int:
    rows = []
    for f in a.reports:
        r = json.loads(Path(f).read_text(encoding="utf-8"))
        p, c = r.get("power", {}), r["cost"]
        rows.append((r["candidate"], r["verdict"]["status"], r["nominal"]["worst_joint"], r["nominal"]["worst_margin"], p.get("bus", {}).get("peak_total_a"),
                     p.get("runtime_min"), c["total_usd"]["typical"], c["total_usd"]["high"], r["mass"]["total_kg"]))
    print(f"{'candidate':34} {'verdict':7} {'worst joint':16} {'margin':>7} {'peak A':>7} {'run min':>8} {'cost':>7} {'cost hi':>8} {'kg':>6}")
    for x in rows:
        print(f"{x[0]:34} {x[1]:7} {x[2]:16} {x[3]:>7} {str(x[4]):>7} {str(x[5]):>8} {x[6]:>7} {x[7]:>8} {x[8]:>6}")
    return 0


def cmd_sweep(a) -> int:
    from .evaluate import Mods, run_bundle
    from .robot import load_concept
    c0 = load_concept(a.concept)
    heights = a.heights or [0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
    out = []
    print(f"{'h (m)':>6} {'mass kg':>8} {'verdict':>8} {'worst margin':>13}  worst joint / first failures")
    for h in heights:
        c = dict(c0)
        c["height_m"] = h
        b = run_bundle(c, Mods(), table_height=a.table_height, thermal=False)
        w, j = b.worst
        out.append({"height_m": h, "mass_kg": round(b.robot.total_mass, 3), "passes": b.passes, "worst_margin": round(w, 3), "worst_joint": j, "failing": b.failing()[:4]})
        print(f"{h:>6.2f} {b.robot.total_mass:>8.2f} {'PASS' if b.passes else 'FAIL':>8} {w:>13.2f}  {j} | {'; '.join(b.failing()[:2])}")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


def cmd_validate_thermal(a) -> int:
    from .thermal_validation import replay
    r = replay(a.actuator)
    print(json.dumps(r, indent=1))
    return 0 if r["reproduces_both"] else 3


def cmd_thresholds(a) -> int:
    import yaml
    print(yaml.safe_dump(config.thresholds(), sort_keys=False, width=140))
    return 0


def main(argv=None) -> int:
    _utf8()
    ap = argparse.ArgumentParser(prog="python -m openhumanoid.concept", description="P2 concept-loop instruments")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("evaluate"); s.add_argument("concept"); s.add_argument("--quick", action="store_true", help="nominal gates only (no bounds sweep / Monte Carlo / mass cases)")
    s.add_argument("--samples", type=int); s.add_argument("--table-height", type=float); s.add_argument("--out"); s.set_defaults(f=cmd_evaluate)
    s = sub.add_parser("compare"); s.add_argument("reports", nargs="+"); s.set_defaults(f=cmd_compare)
    s = sub.add_parser("sweep"); s.add_argument("concept"); s.add_argument("--heights", nargs="*", type=float); s.add_argument("--table-height", type=float)
    s.add_argument("--out"); s.set_defaults(f=cmd_sweep)
    s = sub.add_parser("validate-thermal"); s.add_argument("--actuator", default="sts3215-12v"); s.set_defaults(f=cmd_validate_thermal)
    s = sub.add_parser("thresholds"); s.set_defaults(f=cmd_thresholds)
    a = ap.parse_args(argv)
    try:
        return a.f(a)
    except (RuntimeError, FileNotFoundError, ValueError, KeyError) as e:
        print("error:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
