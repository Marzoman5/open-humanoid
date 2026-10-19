#!/usr/bin/env python3
"""PreCompact hook (manual | auto), ADR 0011: write a handoff stub for the session's task before the context is summarised,
so a compaction never loses state. Never blocks compaction. Skips sessions without a registered task, and skips if a handoff
for the task was written in the last two minutes (repeated compactions don't spam files).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import log, run, session_task  # noqa: E402


def handle(payload: dict, root: Path, cfg: dict):
    if cfg.get("precompact_handoff", True) is False:
        return None
    task = session_task(root, payload.get("session_id"))
    if not task:
        return None
    from openhumanoid import coord  # older branches lack handoff(auto=...): then the AttributeError fails open
    recent = coord.latest_handoff(task["id"])
    if recent and time.time() - recent.stat().st_mtime < 120:
        return None
    path = coord.handoff(task["id"], str(task.get("owner") or "auto"), auto=True)
    log(root, "precompact", f"wrote {path.relative_to(root).as_posix()} ({payload.get('trigger')})")
    return None


if __name__ == "__main__":
    run("precompact", handle, budget_s=float(os.environ.get("OH_HOOK_BUDGET_S", "1.8")))
