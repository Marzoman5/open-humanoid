#!/usr/bin/env python3
"""SessionStart hook (startup | resume | clear | compact | fork), ADR 0011.

Prints what a fresh or compacted session needs, which Claude Code adds to the context: the session id and how to claim
a task for it, the coordination board, this session's task and its newest handoff, `git log -5`, and a smoke-gate run
(`oh gate --smoke`: validate + size + stand test). It REPORTS failures and never blocks: exit 0 always.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import log, run, session_task, venv_python  # noqa: E402

MAX_CHARS = 9000  # Claude Code truncates hook context at 10k


def git(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def variant_for(task: dict | None, default: str) -> str:
    for p in (task or {}).get("paths", []):
        m = re.match(r"^variants/([a-z0-9][a-z0-9-]*)/", str(p).replace("\\", "/"))
        if m and m.group(1) != "_template":
            return m.group(1)
    return default


def smoke_lines(root: Path, variant: str) -> list[str]:
    """Run `oh gate --smoke` in the toolkit's own interpreter. The hook itself may be running under a bare system Python with
    no jsonschema/numpy/mujoco, so never import the toolkit's heavy parts here. A missing toolkit gives a clear 'skipped',
    never a false FAIL."""
    py = venv_python(root) or Path(sys.executable)
    env = {**os.environ, "OPENHUMANOID_ROOT": str(root), "PYTHONIOENCODING": "utf-8"}
    try:
        r = subprocess.run([str(py), "-m", "openhumanoid", "gate", "--smoke", variant], cwd=root, env=env, capture_output=True, timeout=90)
    except subprocess.TimeoutExpired:
        return [f"\nSmoke gate ({variant}): skipped, it took longer than 90 s. Run `oh gate --smoke {variant}` yourself."]
    except OSError as e:
        return [f"\nSmoke gate ({variant}): skipped, could not start {py}: {e}"]
    out = r.stdout.decode("utf-8", "replace").strip()
    err = r.stderr.decode("utf-8", "replace")
    missing = any(m in err or m in out for m in ("ModuleNotFoundError", "ImportError", "No module named"))
    if r.returncode not in (0, 2) or missing:  # gate checks that crash on an import are recorded as FAIL on stdout, not stderr
        why = next((ln.strip() for ln in reversed((err + out).splitlines()) if "No module named" in ln or "Error" in ln),
                   f"exit {r.returncode}")
        why = why.split("check crashed:")[-1].strip()
        return [f"\nSmoke gate ({variant}): skipped, toolkit venv not found or incomplete "
                f"(run `python -m venv .venv` then `.venv/Scripts/pip install -e \".[sim,dev]\"`). Interpreter: {py}. Last error: {why}"]
    lines = [ln for ln in out.splitlines() if ln.strip()]
    status = "PASS" if r.returncode == 0 else "FAIL: fix this first, the previous session left something broken"
    return [f"\nSmoke gate ({variant}): {status}"] + lines


def handle(payload: dict, root: Path, cfg: dict):
    sid, source = payload.get("session_id") or "", payload.get("source", "startup")
    task = session_task(root, sid)
    try:
        from openhumanoid import coord, gate
        coord.status_data, gate.smoke  # a branch that predates the harness lacks these: degrade, don't fail
    except (ImportError, AttributeError):
        coord = gate = None
    L = [f"== Open Humanoid session context ({source}) =="]

    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if env_file and sid:
        try:
            with open(env_file, "a", encoding="utf-8") as fh:
                fh.write(f"export CLAUDE_SESSION_ID={sid}\n")
        except OSError:
            pass
    L.append(f"Session id: {sid or '?'}. To work a task: `oh coord claim <task> --agent <name> --session {sid or '<id>'}` then commit the claim "
             "(this registers your claimed paths with the hooks).")

    if coord is None:
        L.append("\nThis checkout's branch predates the harness (no `oh gate`, no session claims): merge main to get them. "
                 "Protected-path rules still apply.")
    else:
        # Board (compact: active + ready)
        data = coord.status_data()
        active = [t for t in data["tasks"] if t["status"] in coord.ACTIVE or t["status"] == "blocked"]
        L.append(f"\nProfile: {data['profile']} · board (active/blocked) — run `oh coord status` for all:")
        for t in active:
            L.append(f"  {t['id']} {t['status']:11} {str(t['owner'] or '-'):14} {t['title']}")
        L.append("  Ready to claim: " + (", ".join(data["ready"]) or "none"))
        if data["conflicts"]:
            L.append("  ! path conflicts: " + "; ".join(f"{c['a']}~{c['b']}" for c in data["conflicts"]))

    # This session's task + handoff
    if task:
        L.append(f"\nYOUR TASK: {task['id']} [{task.get('status')}] {task.get('title')}\n  paths: {', '.join(task.get('paths', []))}")
        h = coord.latest_handoff(task["id"]) if coord else None
        L.append(f"  newest handoff: {h.relative_to(root).as_posix() if h else 'none yet'}")
        if h:
            body = h.read_text(encoding="utf-8").strip().splitlines()
            L += ["  ---"] + ["  " + ln for ln in body[:30]] + (["  … (truncated)"] if len(body) > 30 else [])
    else:
        L.append("\nThis session has no registered task (commander/unclaimed sessions are exempt from claimed-path warnings).")
        hs = sorted((root / "coordination" / "handoffs").glob("*.md"))
        if hs:
            L.append(f"  newest handoff overall: {hs[-1].relative_to(root).as_posix()}")

    L.append("\nBranch: " + (git(root, "branch", "--show-current") or "?") + "\ngit log -5:\n" + "\n".join("  " + ln for ln in git(root, "log", "--oneline", "-5").splitlines()))

    # Smoke gate: reports, never blocks
    if cfg.get("smoke_on_session_start", True) and (root / "openhumanoid" / "gate.py").exists():
        variant = variant_for(task, gate.default_variant() if gate else "adam")
        L += smoke_lines(root, variant)

    L.append("\nEnforced by hooks (docs/harness.md): no writes to generated/, pipeline/, schemas/, contracts; claimed paths are warned on; "
             "'done' needs a PASS gate record at HEAD (`oh gate --status`).")
    text = "\n".join(L)
    return text[:MAX_CHARS] + ("\n… (truncated)" if len(text) > MAX_CHARS else "")


if __name__ == "__main__":
    run("sessionstart", handle, budget_s=float(os.environ.get("OH_HOOK_SMOKE_BUDGET_S", "100")))
