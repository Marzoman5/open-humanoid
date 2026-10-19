"""`python -m openhumanoid.cad strength <builder.py> [--variant adam] [--out DIR]`: the G-strength check.

Per printed part, per load case class: the margin (allowable / (SF x demand)), the failure mode, PASS/FAIL. Exit status is non-zero when any
gated check fails, so the same command works as a gate. `--fea PART[,PART]` additionally runs the FEA of the named parts on their worst
analytic load case with a two-density mesh convergence check.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .policy import policy

CLASS_ORDER = ["walk", "push", "stall", "fall", "handling", "fall_rigid"]


def build_model(builder: str, variant: str, config: str | None, cache: str | None = None):
    from ..cli import _load_builder
    from .loadcases import load_config
    from .model import Model

    if cache and Path(cache).exists():
        model = Model.load(cache)
        asm = ctx = None
    else:
        asm, ctx = _load_builder(builder, variant)
        cfg_p = config or str(Path(ctx.variant_dir) / "cad" / "strength.yaml")
        cfg0 = load_config(cfg_p)
        profiles = cfg0.get("print_profiles", {})
        model = Model.from_assembly(asm, ctx.interfaces, profiles)
        if cache:
            model.save(cache)
    return model


def table(result: dict) -> str:
    rows = result["rows"]
    parts = list(result["parts"])
    head = f"{'part':24s}" + "".join(f"{c:>11s}" for c in CLASS_ORDER) + "  verdict   worst gated case / check / mode"
    out = [head, "-" * len(head)]
    for p in parts:
        line = f"{p:24s}"
        for c in CLASS_ORDER:
            rr = [r for r in rows if r["part"] == p and r["cls"] == c]
            line += f"{min(r['margin'] for r in rr):11.2f}" if rr else f"{'-':>11s}"
        v = result["parts"][p]
        w = v["worst"]
        line += f"  {'PASS' if v['ok'] else 'FAIL':7s}  " + (f"{w['case']} / {w['check']} / {w['mode'][:60]}" if w else "")
        out.append(line)
    return "\n".join(out)


def markdown_table(result: dict) -> str:
    rows = result["rows"]
    out = ["| part | " + " | ".join(CLASS_ORDER) + " | verdict | worst gated check |", "|---|" + "---|" * (len(CLASS_ORDER) + 2)]
    for p, v in result["parts"].items():
        cells = []
        for c in CLASS_ORDER:
            rr = [r for r in rows if r["part"] == p and r["cls"] == c]
            cells.append(f"{min(r['margin'] for r in rr):.2f}" if rr else "-")
        w = v["worst"]
        out.append(f"| {p} | " + " | ".join(cells) + f" | {'PASS' if v['ok'] else 'FAIL'} | " + (f"{w['case']}: {w['check']} ({w['mode'][:70]})" if w else "") + " |")
    return "\n".join(out)


def run_cli(a) -> int:
    from . import loadcases, runner

    t0 = time.time()
    model = build_model(a.builder, a.variant, a.config, a.cache)
    from ..spec import load_spec

    cfg_path = a.config or str(Path(load_spec(a.variant)["_dir"]) / "cad" / "strength.yaml")
    cfg = loadcases.load_config(cfg_path)
    only_parts = a.part.split(",") if a.part else None
    only_cases = a.case.split(",") if a.case else None
    res = runner.run(model, cfg, only_cases=only_cases, only_parts=only_parts, verbose=a.verbose)
    print(table(res))
    n_fail = sum(1 for v in res["parts"].values() if not v["ok"])
    print(f"\nG-strength: {'PASS' if res['ok'] else 'FAIL'}  ({len(res['parts']) - n_fail}/{len(res['parts'])} parts pass, {len(res['scenarios'])} load cases, {time.time() - t0:.0f} s)")
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "strength_report.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        (out / "strength_table.md").write_text(markdown_table(res) + "\n", encoding="utf-8")
    if a.fea:
        from .fea_run import run_fea

        fr = run_fea(model, cfg, res, a.fea.split(","), Path(a.out) if a.out else None)
        if a.out:
            (Path(a.out) / "fea_report.json").write_text(json.dumps(fr, indent=1, default=str), encoding="utf-8")
    return 0 if res["ok"] else 1


def add_parser(sp) -> None:
    s = sp.add_parser("strength", help="G-strength: analytic + FEA strength check of the printed parts")
    s.add_argument("builder")
    s.add_argument("--variant", default="adam")
    s.add_argument("--config", help="variants/<id>/cad/strength.yaml (default)")
    s.add_argument("--out")
    s.add_argument("--part", help="comma list: only these parts")
    s.add_argument("--case", help="comma list of substrings: only matching load cases")
    s.add_argument("--fea", help="comma list of parts to run through FEA (worst analytic case, mesh convergence)")
    s.add_argument("--cache", help="pickle of the strength model (skips the CAD build when it exists)")
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(fn=run_cli)
