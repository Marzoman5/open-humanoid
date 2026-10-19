"""Multi-agent coordination: tasks with path claims, status changes, handoffs.

Task files are Markdown with YAML front matter (coordination/tasks/T-NNNN.md). They are plain
text, so they merge in git and humans can edit them. See coordination/README.md for the protocol.
"""
from __future__ import annotations

import re
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

import yaml

from .paths import coordination_dir

STATUSES = ["open", "claimed", "in_progress", "review", "blocked", "done"]
ACTIVE = {"claimed", "in_progress", "review"}
FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


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


def new(title: str, stream: str, paths: list[str], depends: list[str] | None = None, size: str = "M",
        goal: str = "", done_when: str = "", phase: str | None = None) -> Path:
    nums = [int(p.stem.split("-")[1]) for p in tasks_dir().glob("T-*.md")]
    tid = f"T-{(max(nums) + 1) if nums else 1:04d}"
    meta = {"id": tid, "title": title, "status": "open", "stream": stream, "phase": phase, "owner": None,
            "paths": paths, "depends_on": depends or [], "size": size, "created": _now()}
    body = (f"\n## Goal\n{goal or 'TODO'}\n\n## Done when\n{done_when or '- [ ] TODO'}\n\n## Notes\n\n## Log\n"
            f"- {_now()} created\n")
    path = tasks_dir() / f"{tid}.md"
    write(path, meta, body)
    return path


def claim(task_id: str, agent: str, force: bool = False) -> list[tuple[str, str, str]]:
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
    return c


def set_status(task_id: str, status: str, agent: str | None = None, note: str = "") -> None:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    path = find(task_id)
    meta, body = read(path)
    meta["status"] = status
    if status == "open":
        meta["owner"] = None
    write(path, meta, _log(body, f"{status}" + (f" by {agent}" if agent else "") + (f": {note}" if note else "")))


def handoff(task_id: str, agent: str) -> Path:
    meta, _ = read(find(task_id))
    d = coordination_dir() / "handoffs"
    d.mkdir(exist_ok=True)
    path = d / f"{datetime.now():%Y-%m-%d-%H%M}-{task_id}-{agent}.md"
    path.write_text(
        f"# Handoff: {task_id} {meta['title']}\n\n- **Agent:** {agent}\n- **When:** {_now()}\n- **Task status:** {meta['status']}\n"
        f"- **Branch/commit:** \n\n## Done so far\n- \n\n## Next steps (in order)\n1. \n\n## Gotchas / decisions made\n- \n\n"
        f"## Files touched\n- \n\n## How to verify\n```bash\n\n```\n", encoding="utf-8")
    return path


def latest_handoff(task_id: str) -> Path | None:
    hs = sorted((coordination_dir() / "handoffs").glob(f"*-{task_id}-*.md"))
    return hs[-1] if hs else None


def status_report() -> str:
    rows = all_tasks()
    lines = [f"Profile: {active_profile()}", "", f"{'ID':7} {'STATUS':12} {'STREAM':12} {'OWNER':14} TITLE"]
    for _, m, _ in sorted(rows, key=lambda r: (STATUSES.index(r[1].get("status", "open")), r[1]["id"])):
        lines.append(f"{m['id']:7} {m.get('status',''):12} {str(m.get('stream','')):12} {str(m.get('owner') or '-'):14} {m['title']}")
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
