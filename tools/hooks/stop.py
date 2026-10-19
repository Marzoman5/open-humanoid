#!/usr/bin/env python3
"""Stop hook (ADR 0011): don't let a session declare "done" while its task is in_progress and the phase gate has no
PASS record at HEAD. Blocks ONCE per stop attempt (honours `stop_hook_active`; Claude Code also caps repeated blocks).

Sessions with no registered task (the commander, a human-driven chat) are never blocked.
Which gates: the task's front-matter `gates: [G-...]` if present, else every implemented gate whose `phase` equals the task's `phase`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import log, run  # noqa: E402


def handle(payload: dict, root: Path, cfg: dict):
    if payload.get("stop_hook_active") or cfg.get("stop_gate", "block") == "off":
        return None
    from openhumanoid import coord, gate

    task = coord.session_task(payload.get("session_id"))
    if not task or task.get("status") != "in_progress":
        return None
    gates = task.get("gates") or gate.gates_for_phase(task.get("phase"))
    if not gates:
        return None
    variant = next((p.split("/")[1] for p in map(str, task.get("paths", [])) if p.replace("\\", "/").startswith("variants/")
                    and len(p.split("/")) > 1 and p.split("/")[1] not in ("*", "_template")), gate.default_variant())
    states = {g: gate.gate_state(g, variant) for g in gates}
    missing = {g: s for g, s in states.items() if s != "PASS"}
    if not missing:
        return None
    detail = ", ".join(f"{g}={s}" for g, s in missing.items())
    reason = (f"Task {task['id']} is in_progress and its phase gate(s) have no PASS record at HEAD: {detail}. "
              f"Commit your work, then run `oh gate <id> {variant}` for each (see `oh gate --status {variant}`) and fix what fails. "
              f"If you are genuinely done without a gate, set the task to `review` (`oh coord set {task['id']} review`) or `blocked` and say why. "
              "(This check blocks once; it will not repeat.)")
    log(root, "stop", f"BLOCK {task['id']}: {detail}")
    if cfg.get("stop_gate", "block") == "warn":
        return {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": reason}}
    return {"decision": "block", "reason": reason}


if __name__ == "__main__":
    run("stop", handle, budget_s=float(os.environ.get("OH_HOOK_BUDGET_S", "1.8")))
