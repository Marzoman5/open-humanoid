"""Multi-agent coordination: tasks with path claims, status changes, handoffs.

Task files are Markdown with YAML front matter (coordination/tasks/T-NNNN.md). They are plain
text, so they merge in git and humans can edit them. See coordination/README.md for the protocol.
"""
from __future__ import annotations

import json
import re
import secrets
import subprocess
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

import yaml

from .paths import coordination_dir, repo_root

STATUSES = ["open", "claimed", "in_progress", "review", "blocked", "done"]
ACTIVE = {"claimed", "in_progress", "review"}
FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
# Legacy sequential ids (T-0007) stay valid. New ids are T-<yyyymmdd>-<4 hex> so two branches creating
# tasks at once can never pick the same number (no shared counter, no renumbering at merge).
ID_RE = re.compile(r"^T-(?:\d{4}|\d{8}-[0-9a-f]{4})$")


def tasks_dir() -> Path:
    d = coordination_dir() / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read(path: Path) -> tuple[dict, str]:
    m = FM.match(path.read_text(encoding="utf-8"))
    if not m:
        raise ValueError(f"{path}: missing YAML front matter")
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def write(path: Path, meta: dict, body: str) -> None:
    path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False).strip() + "\n---\n" + body, encoding="utf-8")


def all_tasks() -> list[tuple[Path, dict, str]]:
    return [(p, *read(p)) for p in sorted(tasks_dir().glob("T-*.md"))]


def find(task_id: str) -> Path:
    if not ID_RE.match(task_id):
        raise ValueError(f"'{task_id}' is not a task id (expected T-0007 or T-20261019-3fa2)")
    p = tasks_dir() / f"{task_id}.md"
    if not p.exists():
        raise FileNotFoundError(f"No task {task_id}")
    return p


def _norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def paths_overlap(a: str, b: str) -> bool:
    """True if two claimed paths could touch the same file. Directory prefixes and globs both count."""
    a, b = _norm(a), _norm(b)
    if fnmatch(a, b) or fnmatch(b, a):
        return True
    ca, cb = a.split("*")[0], b.split("*")[0]
    return ca.startswith(cb) or cb.startswith(ca)


def conflicts(task_id: str, paths: list[str]) -> list[tuple[str, str, str]]:
    out = []
    for _, meta, _ in all_tasks():
        if meta["id"] == task_id or meta.get("status") not in ACTIVE:
            continue
        for p in paths:
            for q in meta.get("paths", []):
                if paths_overlap(p, q):
                    out.append((meta["id"], meta.get("owner") or "?", f"{p} ~ {q}"))
    return out


def _log(body: str, line: str) -> str:
    if "## Log" not in body:
        body = body.rstrip() + "\n\n## Log\n"
    return body.rstrip() + f"\n- {_now()} {line}\n"


def new_id(now: datetime | None = None) -> str:
    """A collision-proof task id: T-<yyyymmdd>-<4 hex>. Sorts by creation day, readable, no shared counter."""
    day = (now or datetime.now()).strftime("%Y%m%d")
    taken = {p.stem for p in tasks_dir().glob("T-*.md")}
    for _ in range(100):
        tid = f"T-{day}-{secrets.token_hex(2)}"
        if tid not in taken:
            return tid
    raise RuntimeError("could not find a free task id")


def new(title: str, stream: str, paths: list[str], depends: list[str] | None = None, size: str = "M",
        goal: str = "", done_when: str = "", phase: str | None = None) -> Path:
    tid = new_id()
    meta = {"id": tid, "title": title, "status": "open", "stream": stream, "phase": phase, "owner": None,
            "paths": paths, "depends_on": depends or [], "size": size, "created": _now()}
    body = (f"\n## Goal\n{goal or 'TODO'}\n\n## Done when\n{done_when or '- [ ] TODO'}\n\n## Notes\n\n## Log\n"
            f"- {_now()} created\n")
    path = tasks_dir() / f"{tid}.md"
    write(path, meta, body)
    return path


def claim(task_id: str, agent: str, force: bool = False, session: str | None = None) -> list[tuple[str, str, str]]:
    path = find(task_id)
    meta, body = read(path)
    if meta.get("status") in ACTIVE and meta.get("owner") not in (None, agent) and not force:
        raise RuntimeError(f"{task_id} already claimed by {meta['owner']}")
    unmet = [d for d in meta.get("depends_on", []) if read(find(d))[0].get("status") != "done"]
    c = conflicts(task_id, meta.get("paths", []))
    if (c or unmet) and not force:
        msg = []
        if c:
            msg.append("path conflicts: " + "; ".join(f"{t} ({o}): {why}" for t, o, why in c))
        if unmet:
            msg.append("unfinished dependencies: " + ", ".join(unmet))
        raise RuntimeError(f"Cannot claim {task_id}: " + " | ".join(msg) + " (use --force only if a human agreed)")
    meta.update(status="claimed", owner=agent, claimed=_now())
    write(path, meta, _log(body, f"claimed by {agent}" + (" (forced)" if force else "")))
    if session:
        register_session(session, task_id)
    return c


# --- session -> task map (local to this checkout, never committed) --------------------------------
# Hooks only get a session id from Claude Code. `oh coord claim --session <id>` records which task that
# session works on, so a hook can look up the task's claimed paths without scanning every task file.

def sessions_file() -> Path:
    d = coordination_dir() / ".local"
    d.mkdir(parents=True, exist_ok=True)
    return d / "sessions.json"


def load_sessions() -> dict[str, str]:
    try:
        return json.loads(sessions_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def register_session(session: str, task_id: str) -> None:
    m = load_sessions()
    m[session] = task_id
    sessions_file().write_text(json.dumps(m, indent=1, sort_keys=True), encoding="utf-8")


def session_task(session: str | None) -> dict | None:
    """The task front matter for a session id, or None (= unclaimed session, e.g. the commander)."""
    if not session:
        return None
    tid = load_sessions().get(session)
    if not tid:
        return None
    try:
        return read(find(tid))[0]
    except (OSError, ValueError, FileNotFoundError):
        return None


def set_status(task_id: str, status: str, agent: str | None = None, note: str = "") -> None:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    path = find(task_id)
    meta, body = read(path)
    meta["status"] = status
    if status == "open":
        meta["owner"] = None
    write(path, meta, _log(body, f"{status}" + (f" by {agent}" if agent else "") + (f": {note}" if note else "")))


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=repo_root(), capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def handoff(task_id: str, agent: str, auto: bool = False) -> Path:
    """Write a handoff template. `auto=True` (PreCompact hook) pre-fills what the repo already knows:
    branch, HEAD, uncommitted files and recent commits, so a stub is useful even if nobody fills it in."""
    meta, _ = read(find(task_id))
    d = coordination_dir() / "handoffs"
    d.mkdir(exist_ok=True)
    path = d / f"{datetime.now():%Y-%m-%d-%H%M}-{task_id}-{agent}.md"
    if auto:
        dirty = _git("status", "--short") or "(clean)"
        branch, head = _git("branch", "--show-current"), _git("rev-parse", "--short", "HEAD")
        lines = [
            f"# Handoff (AUTO STUB): {task_id} {meta['title']}", "",
            f"- **Agent:** {agent}", f"- **When:** {_now()}", f"- **Task status:** {meta['status']}",
            f"- **Branch/commit:** {branch} @ {head}",
            "- **Written by:** PreCompact hook, because the conversation was about to be compacted. Refine it after compaction.", "",
            "## Uncommitted files", "```", dirty, "```", "",
            "## Recent commits", "```", _git("log", "--oneline", "-8"), "```", "",
            "## Done so far", "- (unknown: fill in)", "", "## Next steps (in order)", "1. (unknown: fill in)", ""]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
    path.write_text(
        f"# Handoff: {task_id} {meta['title']}\n\n- **Agent:** {agent}\n- **When:** {_now()}\n- **Task status:** {meta['status']}\n"
        f"- **Branch/commit:** \n\n## Done so far\n- \n\n## Next steps (in order)\n1. \n\n## Gotchas / decisions made\n- \n\n"
        f"## Files touched\n- \n\n## How to verify\n```bash\n\n```\n", encoding="utf-8")
    return path


def latest_handoff(task_id: str) -> Path | None:
    hs = sorted((coordination_dir() / "handoffs").glob(f"*-{task_id}-*.md"))
    return hs[-1] if hs else None


def status_data() -> dict:
    """Machine-readable board for hooks and scripts (`oh coord status --json`)."""
    rows = all_tasks()
    sessions = load_sessions()
    by_task: dict[str, list[str]] = {}
    for sid, tid in sessions.items():
        by_task.setdefault(tid, []).append(sid)
    tasks = []
    for _, m, _ in rows:
        tasks.append({"id": m["id"], "title": m.get("title", ""), "status": m.get("status", "open"),
                      "stream": m.get("stream"), "phase": m.get("phase"), "owner": m.get("owner"),
                      "paths": m.get("paths", []), "depends_on": m.get("depends_on", []),
                      "gates": m.get("gates", []), "sessions": by_task.get(m["id"], [])})
    act = [t for t in tasks if t["status"] in ACTIVE]
    clashes = [{"a": a["id"], "b": b["id"], "paths": [p, q]} for i, a in enumerate(act) for b in act[i + 1:]
               for p in a["paths"] for q in b["paths"] if paths_overlap(p, q)]
    done = {t["id"] for t in tasks if t["status"] == "done"}
    ready = [t["id"] for t in tasks if t["status"] == "open" and all(d in done for d in t["depends_on"])]
    return {"profile": active_profile(), "tasks": tasks, "conflicts": clashes, "ready": ready}


def status_report() -> str:
    rows = all_tasks()
    lines = [f"Profile: {active_profile()}", "", f"{'ID':16} {'STATUS':12} {'STREAM':12} {'OWNER':14} TITLE"]
    for _, m, _ in sorted(rows, key=lambda r: (STATUSES.index(r[1].get("status", "open")), r[1]["id"])):
        lines.append(f"{m['id']:16} {m.get('status',''):12} {str(m.get('stream','')):12} {str(m.get('owner') or '-'):14} {m['title']}")
    # Conflict scan among active tasks
    act = [m for _, m, _ in rows if m.get("status") in ACTIVE]
    clashes = []
    for i, a in enumerate(act):
        for b in act[i + 1:]:
            for p in a.get("paths", []):
                for q in b.get("paths", []):
                    if paths_overlap(p, q):
                        clashes.append(f"  ! {a['id']} and {b['id']} overlap: {p} ~ {q}")
    lines += ["", "Conflicts:" if clashes else "No path conflicts among active tasks."] + clashes
    ready = [m["id"] for _, m, _ in rows if m.get("status") == "open"
             and all(read(find(d))[0].get("status") == "done" for d in m.get("depends_on", []))]
    lines.append("Ready to claim: " + (", ".join(ready) or "none"))
    return "\n".join(lines)


def active_profile() -> str:
    p = coordination_dir() / "active-profile"
    return p.read_text(encoding="utf-8").strip() if p.exists() else "solo"
