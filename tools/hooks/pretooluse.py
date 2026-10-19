#!/usr/bin/env python3
"""PreToolUse hook (ADR 0011): protect generated files, gate thresholds and contracts; keep workers inside their claim.

Matches Edit|Write|MultiEdit|NotebookEdit (file_path / notebook_path) and Bash|PowerShell (redirects, tee, sed -i, rm, mv, cp, ...).

  * Protected paths (pipeline/hooks.yaml `protected:`): DENY (exit 2 + a reason that says what to do instead).
    - a worker session may edit a protected file only if its claimed task's `paths` list it (an ADR task);
    - the commander / an unclaimed session gets an ASK instead, so a human confirms and is never locked out.
  * Outside the session's claimed paths: WARN (configurable: claimed_paths: enforce). Commander sessions (no claim, or
    task stream in `commander_streams`) are exempt.
Fails open on any error (see _common.py).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ACTIVE_STATUSES, log, run, session_task  # noqa: E402
from shellwrites import write_targets  # noqa: E402

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}

# Used when pipeline/hooks.yaml is missing or has no `protected:` list, so deleting the config can't disable protection.
DEFAULT_PROTECTED = [
    {"name": "generated", "patterns": ["**/generated/**"], "worker": "deny", "commander": "deny", "covered_by_claim_ok": False,
     "hint": "Never hand-edit generated/. Change the spec or the generator and re-run the `oh` command that produces it (`oh gate <id>` writes gates/*.json)."},
    {"name": "gate-config", "patterns": ["pipeline/**", "tools/hooks/**", ".claude/settings.json", "coordination/.local/hooks.off"],
     "worker": "deny", "commander": "ask", "covered_by_claim_ok": True,
     "hint": "Gate thresholds and the enforcement harness can't be loosened by the agent being gated. Open an ADR task whose `paths` name this file, or ask the maintainer."},
    {"name": "contracts", "patterns": ["schemas/**", "cad/EXPORT_CONTRACT.md", "modules/INTERFACE.md", "**/INTERFACE.md"],
     "worker": "deny", "commander": "ask", "covered_by_claim_ok": True,
     "hint": "Interfaces are frozen (AGENTS.md). Changing one needs an ADR in docs/decisions/ and a schema_version bump: claim an ADR task that lists this path."},
]


def glob_to_re(pat: str) -> re.Pattern:
    out, i = "", 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pat.startswith("**", i):
            out += ".*"
            i += 2
        elif pat[i] == "*":
            out += "[^/]*"
            i += 1
        elif pat[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pat[i])
            i += 1
    return re.compile("^" + out + "$", re.I if os.name == "nt" else 0)


def matches(rel: str, pat: str) -> bool:
    return bool(glob_to_re(pat).match(rel))


def to_rel(path: str, root: Path, cwd: str) -> str | None:
    """Path relative to the checkout root with forward slashes, or None when it is outside the repo."""
    try:
        p = Path(os.path.expanduser(path))
        if not p.is_absolute():
            p = Path(cwd) / p
        rel = os.path.relpath(os.path.normpath(str(p)), str(root))
    except ValueError:  # different drive on Windows
        return None
    rel = rel.replace("\\", "/")
    if rel == ".." or rel.startswith("../") or os.path.isabs(rel):
        return None
    return rel


def covered(rel: str, task_paths: list[str]) -> bool:
    for p in task_paths or []:
        n = str(p).replace("\\", "/")
        while n.startswith("./"):
            n = n[2:]
        if n in ("", ".", "*", "**", "/"):
            continue  # a catch-all claim never authorises protected files
        if n.endswith("/"):
            if matches(rel, n + "**") or rel + "/" == n:
                return True
        elif any(ch in n for ch in "*?"):
            if matches(rel, n) or matches(rel, n + "/**"):
                return True
        elif rel == n or rel.startswith(n + "/"):
            return True
    return False


def claim_of(payload: dict, cfg: dict, root: Path):
    """(task_meta | None, is_commander). Commander = no registered active claim, or a task in a commander stream."""
    meta = session_task(root, payload.get("session_id"))
    if not meta or meta.get("status") not in ACTIVE_STATUSES:
        return None, True
    if meta.get("stream") in cfg.get("commander_streams", ["coordination"]):
        return meta, True
    return meta, False


def handle(payload: dict, root: Path, cfg: dict):
    tool, ti = payload.get("tool_name"), payload.get("tool_input") or {}
    cwd = payload.get("cwd") or str(root)
    raw: list[str] = []
    if tool in FILE_TOOLS:
        p = ti.get("file_path") or ti.get("notebook_path") or ti.get("path")
        raw = [p] if p else []
    elif tool in SHELL_TOOLS:
        cmd = ti.get("command") or ""
        if not any(ch in cmd for ch in (">", "tee", "sed", "rm", "mv", "cp", "Set-", "Add-", "Out-", "Remove-", "New-", "Copy-", "Move-", "Clear-", "touch", "truncate", "dd", "install", "ln", "del", "ri ", "sc ", "ac ")):
            return None
        raw = [p for p, _ in write_targets(cmd, cwd)]
    if not raw:
        return None

    meta, commander = claim_of(payload, cfg, root)
    rules = cfg.get("protected") or DEFAULT_PROTECTED
    always = [a for a in cfg.get("always_allowed", ["coordination/"])]
    mode = cfg.get("claimed_paths", "warn")

    deny, ask, warn = [], [], []
    for path in raw:
        rel = to_rel(path, root, cwd)
        if rel is None:
            continue
        hit = next((r for r in rules if any(matches(rel, pt) for pt in r["patterns"])), None)
        if hit:
            if not commander and hit.get("covered_by_claim_ok") and covered(rel, meta.get("paths", [])):
                continue  # an ADR / harness task explicitly owns this path
            action = hit.get("commander" if commander else "worker", "deny")
            msg = f"{rel} is protected ({hit['name']}). {hit.get('hint', '')}"
            {"deny": deny, "ask": ask, "warn": warn}.get(action, deny).append(msg)
            continue
        if commander or mode == "off" or covered(rel, always):
            continue
        if not covered(rel, meta.get("paths", [])):
            msg = (f"{rel} is outside the paths claimed by {meta['id']} ({', '.join(meta.get('paths', [])) or 'none'}). "
                   "Add the path to the task after checking `oh coord status`, or open a task for its owner.")
            (deny if mode == "enforce" else warn).append(msg)

    if deny:
        log(root, "pretooluse", f"DENY {tool}: {deny[0]}")
        return {"block_stderr": "BLOCKED by the Open Humanoid harness (docs/harness.md):\n- " + "\n- ".join(deny + ask) + "\n"}
    if ask:
        log(root, "pretooluse", f"ASK {tool}: {ask[0]}")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                       "permissionDecisionReason": "Protected by the Open Humanoid harness: " + " | ".join(ask)}}
    if warn:
        log(root, "pretooluse", f"WARN {tool}: {warn[0]}")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "Harness warning (not blocked): " + " | ".join(warn)}}
    return None


if __name__ == "__main__":
    run("pretooluse", handle, budget_s=float(os.environ.get("OH_HOOK_BUDGET_S", "1.8")))
