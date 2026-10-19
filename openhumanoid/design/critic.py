"""Deterministic glue around the design-critic subagent (.claude/agents/design-critic.md).

The critic (an LLM) only judges gestalt; this module applies the *rules* so they are not left to a model:
  - UNCERTAIN counts as no-pass (VERIFICATION A9: a VLM critic is often unsure, rarely confidently wrong)
  - the pairwise preference counts only if it is consistent across the two presentation orders (position bias)
  - a gestalt criterion passes only if every report passes it
  - numeric hard-gate failures from `oh design metrics` override the critic (VLMs measure ~27 points worse than code)
  - at most MAX_ROUNDS critic rounds per design step (CADCodeVerify: no gain after round 2)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

MAX_ROUNDS = 3
GESTALT = ["G1", "G2", "G3", "G4", "G6"]   # G5 (pairwise) is derived below
VERDICTS = {"PASS", "FAIL", "UNCERTAIN"}


def extract_json(text: str) -> dict:
    """Last ```json fenced block (or the last top-level {...}) in a critic reply."""
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, flags=re.S)
    if blocks:
        return json.loads(blocks[-1])
    start, end = text.rfind("{"), text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("no JSON object found in critic reply")


def _norm(v: str | None) -> str:
    v = (v or "UNCERTAIN").strip().upper()
    return v if v in VERDICTS else "UNCERTAIN"


def combine(reports: list[dict], step: str = "D1", state_path: Path | None = None, metrics_path: Path | None = None) -> dict:
    """Merge critic reports (normally two: the candidate shown first, then second) into one verdict."""
    crit: dict = {}
    for g in GESTALT:
        vs = [_norm(r.get("criteria", {}).get(g, {}).get("verdict")) for r in reports]
        crit[g] = {"verdict": "PASS" if vs and all(v == "PASS" for v in vs) else ("FAIL" if "FAIL" in vs else "UNCERTAIN"),
                   "per_report": vs,
                   "evidence": [r.get("criteria", {}).get(g, {}).get("evidence", "") for r in reports]}
    prefs = [r.get("pairwise", {}).get("preferred") for r in reports if r.get("pairwise")]
    orders = [r.get("order") for r in reports if r.get("pairwise")]
    if not prefs:
        g5 = {"verdict": "NA", "reason": "no baseline given"}
    else:
        wins = [str(p).lower() == "candidate" for p in prefs]
        both_orders = {"cand_first", "cand_second"} <= set(orders)
        if all(wins) and both_orders:
            g5 = {"verdict": "PASS", "reason": "candidate preferred in both presentation orders"}
        elif any(str(p).lower() == "baseline" for p in prefs) and not any(wins):
            g5 = {"verdict": "FAIL", "reason": "baseline preferred"}
        else:
            g5 = {"verdict": "UNCERTAIN", "reason": f"inconsistent or single-order preference {prefs} {orders}; counts as no-pass"}
    crit["G5"] = g5
    reads = [r.get("reads_as", "unfinished") for r in reports]
    reads_as = reads[0] if len(set(reads)) == 1 else "unfinished"
    numeric_fail: list[str] = []
    if metrics_path and Path(metrics_path).exists():
        import yaml
        from .metrics import RUBRIC_PATH
        gates = {m["id"]: m["gate"] for m in yaml.safe_load(RUBRIC_PATH.read_text(encoding="utf-8"))["metrics"]}
        ev = json.loads(Path(metrics_path).read_text(encoding="utf-8"))["evaluation"]
        numeric_fail = [i for i in ev["failed"] if gates.get(i) == "hard"]
    rounds = 1
    if state_path:
        st = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        rounds = st.get(step, 0) + 1
        st[step] = rounds
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(st, indent=2), encoding="utf-8")
    ok_gestalt = all(c["verdict"] in ("PASS", "NA") for c in crit.values())
    passed = ok_gestalt and reads_as == "product" and not numeric_fail
    changes = []
    for r in reports:
        for c in r.get("top_changes", []):
            if c not in changes:
                changes.append(c)
    return {"step": step, "round": rounds, "max_rounds": MAX_ROUNDS, "pass": passed,
            "criteria": crit, "reads_as": reads_as, "numeric_hard_failures": numeric_fail,
            "top_changes": changes[:3],
            "next": ("PASS: stop and hand to the human review stop" if passed
                     else ("round cap reached: keep best-so-far and escalate to the human reviewer"
                           if rounds >= MAX_ROUNDS else "apply ONLY the top changes tied to failed criteria, re-render, re-run metrics and the critic"))}
