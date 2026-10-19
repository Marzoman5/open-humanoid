"""Best-effort extraction of the files a shell command line would write or delete.

Used by the PreToolUse hook so a Bash redirect, `sed -i` or `rm` can't sidestep the Edit/Write protections.
It is a guard rail, not a sandbox: it can't see inside `python -c "open(...)"` or an unknown tool, and it
doesn't try to. CI re-running every gate is the backstop. Pure stdlib.
"""
from __future__ import annotations

import posixpath
import re

SEPARATORS = {";", "&&", "||", "|", "|&", "&", "\n", "(", ")", ";;"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>", ">&"}
SKIP_TARGETS = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "nul", "-", "$null", ""}
WRAPPERS = {"sudo", "env", "command", "time", "nohup", "nice", "builtin", "exec"}
PS_CMDLETS = {"set-content": "w", "add-content": "w", "out-file": "w", "clear-content": "w", "new-item": "w", "tee-object": "w",
              "remove-item": "d", "rename-item": "d", "copy-item": "w", "move-item": "d",
              "sc": "w", "ac": "w", "ri": "d", "del": "d", "erase": "d", "ni": "w", "ci": "w", "mi": "d"}
PS_VALUE_FLAGS = {"-value", "-encoding", "-itemtype", "-stream", "-filter", "-include", "-exclude", "-width", "-inputobject",
                  "-newname", "-name", "-erroraction", "-ea", "-force", "-recurse", "-confirm", "-whatif", "-nonewline", "-append"}
PS_PATH_FLAGS = {"-path", "-literalpath", "-filepath", "-destination"}


def tokenize(cmd: str) -> list[tuple[str, str]]:
    """Return [(kind, text)] where kind is 'w' (word) or 'op'. Heredoc bodies are skipped. Quotes are removed."""
    toks: list[tuple[str, str]] = []
    i, n = 0, len(cmd)
    cur: list[str] = []
    has_word = False
    pending_heredocs: list[tuple[str, bool]] = []

    def flush():
        nonlocal cur, has_word
        if has_word:
            toks.append(("w", "".join(cur)))
        cur, has_word = [], False

    while i < n:
        c = cmd[i]
        if c == "'":
            j = cmd.find("'", i + 1)
            j = n if j < 0 else j
            cur.append(cmd[i + 1:j])
            has_word = True
            i = j + 1
        elif c == '"':
            i += 1
            has_word = True
            while i < n and cmd[i] != '"':
                if cmd[i] == "\\" and i + 1 < n and cmd[i + 1] in '"\\$`':
                    cur.append(cmd[i + 1])
                    i += 2
                else:
                    cur.append(cmd[i])
                    i += 1
            i += 1
        elif c == "\\" and i + 1 < n and cmd[i + 1] in " \"'$;&|<>()":
            cur.append(cmd[i + 1])
            has_word = True
            i += 2
        elif c in " \t\r":
            flush()
            i += 1
        elif c == "\n":
            flush()
            toks.append(("op", "\n"))
            i += 1
            # skip heredoc bodies that were declared on the line we just finished
            while pending_heredocs:
                delim, strip_tabs = pending_heredocs.pop(0)
                while i < n:
                    j = cmd.find("\n", i)
                    line = cmd[i:n if j < 0 else j]
                    i = n if j < 0 else j + 1
                    if (line.lstrip("\t") if strip_tabs else line).rstrip("\r") == delim:
                        break
        elif c == "#" and not has_word:
            j = cmd.find("\n", i)
            i = n if j < 0 else j
        elif c in "<>&|;()":
            # fd number directly before a redirect (2>file) belongs to the operator, not a word
            fd = ""
            if c in "<>" and has_word and "".join(cur).isdigit():
                fd, cur, has_word = "".join(cur), [], False
            else:
                flush()
            three, two = cmd[i:i + 3], cmd[i:i + 2]
            if three in ("<<<", "<<-", "&>>"):
                op = three
            elif two in ("&&", "||", ">>", ">|", "|&", "&>", ">&", "<<", ";;", "<&"):
                op = two
            else:
                op = c
            i += len(op)
            if op in ("<<", "<<-"):
                j = i
                while j < n and cmd[j] in " \t":
                    j += 1
                k = j
                while k < n and cmd[k] not in " \t\r\n;&|<>()":
                    k += 1
                pending_heredocs.append((cmd[j:k].strip("'\""), op == "<<-"))
            toks.append(("op", op))
            _ = fd
        else:
            cur.append(c)
            has_word = True
            i += 1
    flush()
    return toks


def _segments(toks):
    seg: list[tuple[str, str]] = []
    for kind, text in toks:
        if kind == "op" and text in SEPARATORS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append((kind, text))
    if seg:
        yield seg


def _plain(path: str) -> bool:
    return path not in SKIP_TARGETS and "$" not in path and "`" not in path and not path.startswith("&")


def _opts_split(args: list[str]) -> tuple[list[str], list[str]]:
    opts = [a for a in args if a.startswith("-") and len(a) > 1]
    pos = [a for a in args if not (a.startswith("-") and len(a) > 1)]
    return opts, pos


def write_targets(cmd: str, cwd: str = ".") -> list[tuple[str, str]]:
    """[(path, kind)] for files `cmd` would write ('w') or remove/move away ('d'). Paths are resolved against `cwd`
    (tracking simple `cd` steps). Variables ($X) and /dev/null style targets are skipped."""
    out: list[tuple[str, str]] = []
    cur_cwd = cwd

    def add(p: str, kind: str):
        if not _plain(p):
            return
        if posixpath.isabs(p) or re.match(r"^[A-Za-z]:[\\/]", p) or p.startswith("~"):
            out.append((p, kind))
        else:
            out.append((posixpath.normpath(posixpath.join(cur_cwd.replace("\\", "/"), p.replace("\\", "/"))), kind))

    for seg in _segments(tokenize(cmd)):
        words: list[str] = []
        i = 0
        while i < len(seg):
            kind, text = seg[i]
            if kind == "op" and text in REDIRECTS and i + 1 < len(seg) and seg[i + 1][0] == "w":
                target = seg[i + 1][1]
                if not (text == ">&" and (target.isdigit() or target == "-")):
                    add(target, "w")
                i += 2
                continue
            if kind == "op":  # <, <<, <<< and friends: input only
                if text in ("<", "<<<", "<&") and i + 1 < len(seg):
                    i += 1
                i += 1
                continue
            words.append(text)
            i += 1
        # leading env assignments and wrappers
        while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]) or words[0] in WRAPPERS):
            words.pop(0)
        if not words:
            continue
        name = posixpath.basename(words[0].replace("\\", "/")).lower()
        if name.endswith(".exe"):
            name = name[:-4]
        args = words[1:]
        opts, pos = _opts_split(args)
        if name == "cd" and pos:
            cur_cwd = pos[0] if posixpath.isabs(pos[0]) else posixpath.join(cur_cwd.replace("\\", "/"), pos[0])
        elif name == "tee":
            for p in pos:
                add(p, "w")
        elif name in ("sed", "gsed"):
            if any(o.startswith("-i") or o == "--in-place" or o.startswith("--in-place=") for o in opts):
                has_script_opt = any(o in ("-e", "-f") or o.startswith(("--expression", "--file")) for o in opts)
                files = pos if has_script_opt else pos[1:]
                for p in files:
                    add(p, "w")
        elif name in ("rm", "rmdir", "unlink", "shred", "truncate", "touch"):
            for p in pos:
                add(p, "d" if name not in ("touch", "truncate") else "w")
        elif name in ("mv",):
            for p in pos:
                add(p, "d")  # the source disappears and the destination is written: both count
        elif name in ("cp", "install", "ln"):
            if pos:
                add(pos[-1], "w")
        elif name == "dd":
            for a in args:
                if a.startswith("of="):
                    add(a[3:], "w")
        elif name in PS_CMDLETS:
            kind = PS_CMDLETS[name]
            lowered = [a.lower() for a in args]
            skip_next = False
            for idx, a in enumerate(args):
                if skip_next:
                    skip_next = False
                    continue
                la = lowered[idx]
                if la in PS_VALUE_FLAGS:
                    skip_next = la in {"-value", "-encoding", "-itemtype", "-stream", "-filter", "-include", "-exclude", "-width",
                                       "-inputobject", "-newname", "-name", "-erroraction", "-ea"}
                elif la in PS_PATH_FLAGS:
                    if idx + 1 < len(args):
                        add(args[idx + 1], kind)
                        skip_next = True
                elif not a.startswith("-"):
                    for part in a.split(","):
                        add(part, kind)
    return out
