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
from _common import log, run  # noqa: E402

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


def handle(payload: dict, root: Path, cfg: dict):
    from openhumanoid import coord, gate

    sid, source = payload.get("session_id") or "", payload.get("source", "startup")
    task = coord.session_task(sid)
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
        h = coord.latest_handoff(task["id"])
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
    if cfg.get("smoke_on_session_start", True):
        variant = variant_for(task, gate.default_variant())
        try:
            res = gate.smoke(variant)
            bad = [r for r in res if r["status"] != "pass"]
            L.append(f"\nSmoke gate ({variant}): " + ("PASS" if not bad else "FAIL — fix this first, the previous session left something broken"))
            L += [f"  {r['gate']:12} {r['status'].upper():5} {r['summary']}" for r in res]
        except Exception as e:  # never let smoke break the session start
            L.append(f"\nSmoke gate could not run: {type(e).__name__}: {e}")
            log(root, "sessionstart", f"smoke error: {e!r}")

    L.append("\nEnforced by hooks (docs/harness.md): no writes to generated/, pipeline/, schemas/, contracts; claimed paths are warned on; "
             "'done' needs a PASS gate record at HEAD (`oh gate --status`).")
    text = "\n".join(L)
    return text[:MAX_CHARS] + ("\n… (truncated)" if len(text) > MAX_CHARS else "")


if __name__ == "__main__":
    run("sessionstart", handle, budget_s=float(os.environ.get("OH_HOOK_SMOKE_BUDGET_S", "100")))
