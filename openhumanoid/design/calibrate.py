"""Calibration: run the metrics over the reference / counter-example set and check the bands separate sleek from toy.

`oh design calibrate` -> docs/design-method/calibration.json (+ the separation table printed). The reference profiles are
approximations (see their `sources`); the numbers are only as good as those.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import metrics
from .meshio import load_subject

REF_DIR = Path(__file__).parent / "references"
SAMPLE = Path(__file__).parent / "sample" / "sample_sleek_050.yaml"
ADAM_CAD = "cad/export/robot.xml"   # variants/adam/<this>: the Roblox-look counter-example, if present


def subjects(repo_root: Path | None = None) -> list[tuple[str, str, object]]:
    out = [("human_canon", "reference", REF_DIR / "human_canon.yaml"),
           ("optimus_like", "reference", REF_DIR / "optimus_like.yaml"),
           ("atlas_like", "reference", REF_DIR / "atlas_like.yaml"),
           ("toy_chibi", "counter_example", REF_DIR / "toy_chibi.yaml"),
           ("sample_sleek_050", "candidate", SAMPLE)]
    if repo_root:
        p = Path(repo_root) / "variants" / "adam" / ADAM_CAD
        if p.exists():
            out.append(("adam_cad_v0", "counter_example", p))
    return out


def run(repo_root: Path | None = None, out_path: Path | None = None) -> dict:
    rubric = metrics.load_rubric()
    res = {}
    for name, kind, path in subjects(repo_root):
        subj = load_subject(path, name)
        m = metrics.compute(subj)
        ev = metrics.evaluate(m, rubric)
        res[name] = {"kind": kind, "source": str(path).replace("\\", "/").split("openhumanoid/")[-1], "measured": m, "evaluation": ev}
    # separation: per metric, do all references pass while at least one counter-example fails?
    sep = {}
    for item in rubric["metrics"]:
        i = item["id"]
        refs = [res[n]["evaluation"]["criteria"][i]["verdict"] for n in res if res[n]["kind"] == "reference"]
        cex = {n: res[n]["evaluation"]["criteria"][i]["verdict"] for n in res if res[n]["kind"] == "counter_example"}
        if "NA" in refs or not refs:
            continue
        sep[i] = {"refs_all_pass": all(v == "PASS" for v in refs), "counter_examples_failing": [n for n, v in cex.items() if v == "FAIL"],
                  "discriminates": all(v == "PASS" for v in refs) and any(v == "FAIL" for v in cex.values())}
    summary = {n: {"kind": r["kind"], "n_pass": r["evaluation"]["n_pass"], "n_scored": r["evaluation"]["n_scored"],
                   "pass_fraction": r["evaluation"]["pass_fraction"], "failed": r["evaluation"]["failed"]} for n, r in res.items()}
    sleek = [v["pass_fraction"] for v in summary.values() if v["kind"] in ("reference",)]
    toy = [v["pass_fraction"] for v in summary.values() if v["kind"] == "counter_example"]
    report = {"generated_by": "oh design calibrate", "rubric_version": rubric["version"], "calibration": rubric["calibration"],
              "summary": summary, "separation": sep,
              "gap": {"lowest_reference_pass_fraction": min(sleek), "highest_counter_example_pass_fraction": max(toy),
                      "separates": min(sleek) > max(toy)},
              "subjects": res}
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def table(report: dict) -> str:
    lines = ["| subject | kind | passed | failed criteria |", "|---|---|---|---|"]
    for n, s in report["summary"].items():
        lines.append(f"| {n} | {s['kind']} | {s['n_pass']}/{s['n_scored']} | {', '.join(s['failed']) or '-'} |")
    return "\n".join(lines)
