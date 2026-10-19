"""Machine-checked gates (ADR 0011). `pipeline/gates.yaml` defines them; only `oh gate` writes
`variants/<id>/generated/gates/<gate>.json`. A phase is done only when a PASS record exists at HEAD.

A record is *current* when its git SHA is HEAD, or when every file changed since that SHA is a gate record
or coordination bookkeeping (so committing the record itself doesn't invalidate it). Records written on a
dirty tree are kept but never count as current.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml

from .paths import repo_root

GATES_FILE = "pipeline/gates.yaml"
NOT_IMPLEMENTED = 3  # exit code for placeholder gates: they never write a record, so they can never PASS


def gates_path() -> Path:
    return repo_root() / GATES_FILE


def load_config() -> dict:
    return yaml.safe_load(gates_path().read_text(encoding="utf-8")) or {}


def load_gates() -> dict[str, dict]:
    return load_config().get("gates", {})


def default_variant() -> str:
    return load_config().get("default_variant", "adam")


# --- git state -------------------------------------------------------------------------------------

def _git(*args: str, timeout: float = 10) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=repo_root(), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def head_sha() -> str | None:
    return _git("rev-parse", "HEAD")


def is_dirty() -> bool:
    """Uncommitted changes, ignoring generated/ (gates and tools rewrite those themselves)."""
    out = _git("status", "--porcelain")
    if out is None:
        return False
    for line in out.splitlines():
        path = line[3:].replace("\\", "/")
        if "/generated/" not in path and not path.startswith("coordination/.local/"):
            return True
    return False


def _bookkeeping_only(files: list[str]) -> bool:
    return all(("/generated/gates/" in f or f.startswith("coordination/")) for f in files)


# --- records ---------------------------------------------------------------------------------------

def variant_dir(variant: str) -> Path:
    return repo_root() / "variants" / variant


def records_dir(variant: str) -> Path:
    return variant_dir(variant) / "generated" / "gates"


def record_path(gate: str, variant: str) -> Path:
    return records_dir(variant) / f"{gate}.json"


def read_record(gate: str, variant: str) -> dict | None:
    try:
        return json.loads(record_path(gate, variant).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def is_current(rec: dict | None) -> bool:
    """True if `rec` is a clean-tree PASS that still describes HEAD."""
    if not rec or rec.get("status") != "pass" or rec.get("dirty"):
        return False
    head, sha = head_sha(), rec.get("sha")
    if not head or not sha:
        return False
    if head == sha:
        return True
    changed = _git("diff", "--name-only", sha, "HEAD")
    return changed is not None and _bookkeeping_only([c for c in changed.splitlines() if c])


def gate_state(gate: str, variant: str) -> str:
    """'PASS' | 'FAIL' | 'STALE' (pass, but code changed since) | 'DIRTY' (pass on an uncommitted tree) | 'NONE'."""
    rec = read_record(gate, variant)
    if not rec:
        return "NONE"
    if rec.get("status") != "pass":
        return "FAIL"
    if rec.get("dirty"):
        return "DIRTY"
    return "PASS" if is_current(rec) else "STALE"


def gates_for_phase(phase: str | None) -> list[str]:
    if not phase:
        return []
    return [g for g, d in load_gates().items() if d.get("status") == "implemented" and phase in _as_list(d.get("phase"))]


def _as_list(v) -> list:
    return v if isinstance(v, list) else ([] if v is None else [v])


# --- checks ----------------------------------------------------------------------------------------
# A check returns (passed, metrics, summary). Thresholds come from gates.yaml (agents can't edit it: hook-protected).

Check = Callable[[str, dict], "tuple[bool, dict, str]"]


def _spec(variant: str) -> dict:
    from .spec import load_spec
    return load_spec(variant)


def check_validate(variant: str, th: dict):
    from .catalog import validate_catalog
    from .spec import load_raw, validate
    spec_errs, cat_errs = validate(load_raw(variant)), validate_catalog()
    ok = len(spec_errs) <= th.get("max_spec_errors", 0) and len(cat_errs) <= th.get("max_catalog_errors", 0)
    return ok, {"spec_errors": len(spec_errs), "catalog_errors": len(cat_errs), "first_errors": (spec_errs + cat_errs)[:5]}, \
        f"spec {len(spec_errs)} / catalog {len(cat_errs)} error(s)"


def _size(variant: str, write: bool = True):
    from .reports import write_sizing
    from .sizing import size
    spec = _spec(variant)
    res = size(spec)
    d = write_sizing(spec, res)
    return spec, d


def check_size(variant: str, th: dict):
    spec, d = _size(variant)
    cap = spec["goals"]["budget_usd"].get("hard_cap", spec["goals"]["budget_usd"]["target"])
    cost = d.get("cost_usd", {}).get("total")
    walk_ok = d.get("gaits", {}).get("walk", {}).get("ok", False)
    worst = min((g["worst_margin"] for g in d.get("gaits", {}).values() if g["required"]), default=0.0)
    metrics = {"feasible": d["feasible"], "height_m": d["height_m"], "cost_usd": cost, "budget_cap_usd": cap,
               "walk_ok": walk_ok, "worst_required_gait_margin": worst, "mass_kg": d.get("mass", {}).get("total_kg")}
    ok = bool(d["feasible"]) and (cost is not None and cost <= cap * th.get("max_cost_fraction_of_cap", 1.0)) \
        and walk_ok and worst >= th.get("min_gait_margin", 1.0)
    return ok, metrics, f"{'feasible' if d['feasible'] else 'INFEASIBLE'} ({d['reason']}), cost ${cost}, worst margin {worst}x"


def check_sim_stand(variant: str, th: dict, seconds: float | None = None):
    from . import simgen
    spec = _spec(variant)
    if not (variant_dir(variant) / "generated" / "sizing.json").exists():
        _size(variant)
    simgen.write_mjcf(spec)
    r = simgen.smoke_test(spec, seconds or th.get("seconds", 3.0))
    if "tilt_deg" not in r:
        return False, {"reason": r.get("reason")}, r.get("reason", "sim failed")
    worst = r["peak_torque_fraction_of_stall"][r["worst_joint"]]
    metrics = {"stood": r["ok"], "pelvis_z_start": r["pelvis_z_start"], "pelvis_z_end": r["pelvis_z_end"], "tilt_deg": r["tilt_deg"],
               "worst_joint": r["worst_joint"], "worst_torque_fraction_of_stall": worst, "seconds": r["seconds"], "mass_kg": r["mass_kg"]}
    ok = (r["ok"] and r["tilt_deg"] <= th.get("max_tilt_deg", 35)
          and r["pelvis_z_end"] >= th.get("min_pelvis_z_fraction", 0.7) * r["pelvis_z_start"]
          and worst <= th.get("max_hold_torque_fraction", 1.0))
    return ok, metrics, f"{r['reason']}, tilt {r['tilt_deg']} deg, worst hold {r['worst_joint']} {worst:.0%} of stall"


def check_tests(variant: str, th: dict):
    import os
    env = dict(os.environ, OH_IN_GATE="1")  # tests that call `oh gate` skip themselves to avoid recursion
    t0 = time.time()
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"], cwd=repo_root(),
                       capture_output=True, text=True, env=env, timeout=th.get("timeout_s", 900))
    tail = [ln for ln in r.stdout.strip().splitlines() if ln.strip()][-1:] or [""]
    return r.returncode == 0, {"returncode": r.returncode, "summary": tail[0], "seconds": round(time.time() - t0, 1)}, tail[0]


def check_provenance(variant: str, th: dict):
    from . import provenance
    rep = provenance.check(variant)
    c = rep["counts"]
    ok = (c["catalog_missing"] <= th.get("max_catalog_missing", 0)
          and c["catalog_bad"] <= th.get("max_catalog_bad", 0)
          and c["spec_missing"] <= th.get("max_spec_missing", 10**6)
          and c["spec_bad"] <= th.get("max_spec_bad", 10**6)
          and c["spec_estimates"] <= th.get("max_spec_estimates", 10**6)
          and c["catalog_estimates"] <= th.get("max_catalog_estimates", 10**6))
    return ok, {**c, "first_problems": rep["problems"][:8]}, \
        f"catalog {c['catalog_missing']} missing / {c['catalog_estimates']} estimates, spec {c['spec_missing']} missing / {c['spec_estimates']} estimates"


CHECKS: dict[str, Check] = {
    "G-validate": check_validate,
    "G-size": check_size,
    "G-sim-stand": check_sim_stand,
    "G-tests": check_tests,
    "G-provenance": check_provenance,
}


# --- running ---------------------------------------------------------------------------------------

def run_gate(gate: str, variant: str | None = None, write: bool = True, **kw) -> dict:
    """Run one gate. Writes the record (the only code path that does) unless `write=False`.

    Placeholder gates return {'status': 'not_implemented'} and never write anything.
    """
    gates = load_gates()
    if gate not in gates:
        raise KeyError(f"unknown gate '{gate}'. Known: {', '.join(gates)}")
    cfg = gates[gate]
    variant = variant or default_variant()
    if cfg.get("status") != "implemented" or gate not in CHECKS:
        return {"gate": gate, "variant": variant, "status": "not_implemented",
                "summary": f"{gate} is a placeholder ({cfg.get('description', '').strip()}). It cannot pass until implemented."}
    t0 = time.time()
    try:
        passed, metrics, summary = CHECKS[gate](variant, cfg.get("thresholds", {}), **kw)
    except Exception as e:  # a crashing check is a FAIL with the error recorded, never a silent pass
        passed, metrics, summary = False, {"error": f"{type(e).__name__}: {e}"}, f"check crashed: {type(e).__name__}: {e}"
    rec = {"gate": gate, "variant": variant, "status": "pass" if passed else "fail", "summary": summary, "metrics": metrics,
           "thresholds": cfg.get("thresholds", {}), "sha": head_sha(), "dirty": is_dirty(),
           "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"), "seconds": round(time.time() - t0, 2),
           "written_by": "oh gate"}
    if write:
        records_dir(variant).mkdir(parents=True, exist_ok=True)
        rec_text = json.dumps(rec, indent=2) + "\n"
        record_path(gate, variant).write_text(rec_text, encoding="utf-8")
    return rec


def smoke(variant: str | None = None) -> list[dict]:
    """validate + size + sim stand, short. Does NOT write gate records: smoke is a health check, not evidence."""
    variant = variant or default_variant()
    names = load_config().get("smoke", ["G-validate", "G-size", "G-sim-stand"])
    out = []
    for g in names:
        kw = {"seconds": load_config().get("smoke_sim_seconds", 1.0)} if g == "G-sim-stand" else {}
        out.append(run_gate(g, variant, write=False, **kw))
    return out


def status_rows(variant: str | None = None) -> list[dict]:
    variant = variant or default_variant()
    rows = []
    for g, cfg in load_gates().items():
        rec = read_record(g, variant)
        rows.append({"gate": g, "implemented": cfg.get("status") == "implemented", "phase": cfg.get("phase"),
                     "state": gate_state(g, variant) if cfg.get("status") == "implemented" else "PLACEHOLDER",
                     "status": rec.get("status") if rec else None, "sha": (rec or {}).get("sha"),
                     "dirty": (rec or {}).get("dirty"), "timestamp": (rec or {}).get("timestamp"),
                     "summary": (rec or {}).get("summary")})
    return rows


def status_text(variant: str | None = None) -> str:
    variant = variant or default_variant()
    head = (head_sha() or "?")[:8]
    lines = [f"Gate status for '{variant}' (HEAD {head}):", f"{'GATE':16} {'STATE':12} {'RECORD SHA':11} SUMMARY"]
    for r in status_rows(variant):
        lines.append(f"{r['gate']:16} {r['state']:12} {(r['sha'] or '-')[:8]:11} {r['summary'] or ''}")
    lines.append("PASS = pass record that still describes HEAD · STALE = code changed since · DIRTY = ran on uncommitted changes")
    return "\n".join(lines)
