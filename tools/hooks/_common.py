"""Shared plumbing for the Claude Code hooks (ADR 0011). Cross-platform, stdlib only at import time.

Hard rules for every hook in this folder:
  * FAIL OPEN. Any exception, timeout or missing dependency means "do nothing, exit 0". A broken hook must never
    lock out the commander, a worker or a human. Failures go to coordination/.local/hooks.log.
  * FAST. PreToolUse/Stop/PreCompact have a ~2 s budget (a watchdog exits 0 when it runs out); only the
    SessionStart smoke run may take longer.
  * NO SURPRISES. Block only with exit 2 / a documented JSON decision, and only with a reason that says what to do instead.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REEXEC_FLAG = "OH_HOOK_REEXEC"


def find_root(start: str | None) -> Path | None:
    """Nearest ancestor of `start` (default: this file) holding AGENTS.md and schemas/ = the checkout we are in."""
    for base in (start, str(HERE)):
        if not base:
            continue
        p = Path(base).resolve()
        for q in (p, *p.parents):
            if (q / "AGENTS.md").exists() and (q / "schemas").is_dir():
                return q
    return None


def log(root: Path | None, event: str, msg: str) -> None:
    try:
        d = (root or HERE.parent.parent) / "coordination" / ".local"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "hooks.log"
        if f.exists() and f.stat().st_size > 200_000:
            f.replace(d / "hooks.log.1")
        with f.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {event}: {msg}\n")
    except Exception:
        pass


def read_payload() -> dict:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _venv_python(root: Path) -> Path | None:
    for rel in (".venv/Scripts/python.exe", ".venv/bin/python"):
        p = root / rel
        if p.exists():
            return p
    return None


def ensure_deps(root: Path | None, raw_stdin: bytes | None = None) -> None:
    """The hooks reuse `openhumanoid` (PyYAML etc.). If this interpreter lacks PyYAML, re-run the same script under the
    repo's .venv python (once) with the same stdin. If that isn't possible either, raise so we fail open."""
    try:
        import yaml  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get(REEXEC_FLAG) or root is None:
        raise RuntimeError("PyYAML not importable and no venv to fall back to")
    py = _venv_python(root)
    if py is None:
        raise RuntimeError("PyYAML not importable and no .venv found")
    r = subprocess.run([str(py), *sys.argv], input=raw_stdin or b"", capture_output=True, env={**os.environ, REEXEC_FLAG: "1"}, timeout=60)
    sys.stdout.buffer.write(r.stdout)
    sys.stderr.buffer.write(r.stderr)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(r.returncode)


def load_hook_config(root: Path) -> dict:
    import yaml
    f = root / "pipeline" / "hooks.yaml"
    try:
        return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def use_repo(root: Path) -> None:
    """Make `import openhumanoid` resolve to THIS checkout, whatever the cwd is."""
    os.environ["OPENHUMANOID_ROOT"] = str(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def emit(stream, text: str) -> None:
    """Write UTF-8 bytes. On Windows the default text encoding is cp1252, which Claude Code reads as UTF-8 and garbles ('·' -> U+FFFD)."""
    stream.flush()
    stream.buffer.write(text.encode("utf-8", errors="replace"))
    stream.buffer.flush()


def run(event: str, handler, budget_s: float) -> None:
    """Run `handler(payload, root, cfg)` fail-open under a wall-clock watchdog. The handler returns an optional dict
    (printed as JSON) or str (printed as text); raising SystemExit(2) is not used: block via the returned decision."""
    payload = read_payload()
    root = find_root(payload.get("cwd") or os.getcwd())
    t = threading.Timer(budget_s, lambda: (log(root, event, f"watchdog: exceeded {budget_s}s, failing open"), os._exit(0)))
    t.daemon = True
    t.start()
    try:
        if root is None:
            return
        ensure_deps(root, json.dumps(payload).encode("utf-8"))
        use_repo(root)
        cfg = load_hook_config(root)
        if cfg.get("enabled", True) is False or (root / "coordination" / ".local" / "hooks.off").exists():
            return  # human kill switch: touch coordination/.local/hooks.off
        out = handler(payload, root, cfg)
        if isinstance(out, dict) and "block_stderr" in out:  # exit-2 block: stderr is what the agent reads
            emit(sys.stderr, out["block_stderr"])
            t.cancel()
            sys.exit(2)
        if out:
            emit(sys.stdout, out if isinstance(out, str) else json.dumps(out))
    except SystemExit:
        raise
    except BaseException:
        log(root, event, "ERROR (failed open): " + traceback.format_exc().strip().splitlines()[-1])
    finally:
        t.cancel()
    sys.exit(0)
