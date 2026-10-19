"""Tests for the enforcement harness (ADR 0011): task ids, gates, provenance, session claims, and every hook script.

Hook scripts are exercised as real subprocesses fed sample Claude Code JSON on stdin, against a throwaway copy of the
repo skeleton, so nothing here touches the real coordination/ or generated/ files.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / "tools" / "hooks"
sys.path.insert(0, str(HOOKS))

import shellwrites  # noqa: E402

try:
    import mujoco  # noqa: F401
    HAVE_MUJOCO = True
except ImportError:
    HAVE_MUJOCO = False


# --- a throwaway repo ------------------------------------------------------------------------------

def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


TASK = """---
id: {id}
title: {title}
status: {status}
stream: {stream}
phase: {phase}
owner: tester
paths: {paths}
depends_on: []
gates: {gates}
size: S
created: 2026-10-19 00:00
---

## Goal
x

## Log
- 2026-10-19 00:00 created
"""


def write_task(root: Path, tid: str, status="in_progress", stream="mech", phase="W1", paths=("modules/joints/",), gates=(), title="t"):
    (root / "coordination" / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "coordination" / "tasks" / f"{tid}.md").write_text(
        TASK.format(id=tid, title=title, status=status, stream=stream, phase=phase, paths=json.dumps(list(paths)), gates=json.dumps(list(gates))),
        encoding="utf-8")


def register(root: Path, session: str, tid: str):
    d = root / "coordination" / ".local"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "sessions.json"
    m = json.loads(f.read_text()) if f.exists() else {}
    m[session] = tid
    f.write_text(json.dumps(m))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copy(REPO / "AGENTS.md", root / "AGENTS.md")
    for d in ("schemas", "catalog", "pipeline"):
        shutil.copytree(REPO / d, root / d)
    shutil.copytree(REPO / "variants" / "adam", root / "variants" / "adam", ignore=shutil.ignore_patterns("generated", "cad", "reviews", "renders"))
    (root / "coordination" / "handoffs").mkdir(parents=True)
    (root / "coordination" / "active-profile").write_text("solo")
    (root / ".gitignore").write_text("coordination/.local/\n")
    monkeypatch.setenv("OPENHUMANOID_ROOT", str(root))
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    return root


def run_hook(root: Path, script: str, payload: dict | str, expect_exit: int | None = None):
    body = payload if isinstance(payload, str) else json.dumps({"session_id": "s-worker", "cwd": str(root), **payload})
    env = {k: v for k, v in os.environ.items() if k not in ("OPENHUMANOID_ROOT",)}
    t0 = time.time()
    r = subprocess.run([sys.executable, str(HOOKS / script)], input=body.encode(), capture_output=True, env=env, timeout=120)
    out = r.stdout.decode("utf-8", "replace")
    if expect_exit is not None:
        assert r.returncode == expect_exit, (r.returncode, out, r.stderr.decode())
    return r.returncode, out, r.stderr.decode("utf-8", "replace"), time.time() - t0


def edit(root, path, tool="Write", sid="s-worker"):
    return run_hook(root, "pretooluse.py", {"session_id": sid, "tool_name": tool, "tool_input": {"file_path": str(root / path)}})


def bash(root, cmd, sid="s-worker"):
    return run_hook(root, "pretooluse.py", {"session_id": sid, "tool_name": "Bash", "tool_input": {"command": cmd}})


# --- task ids ----------------------------------------------------------------------------------------

def test_new_task_ids_are_collision_proof(repo):
    from openhumanoid import coord
    ids = {coord.new_id() for _ in range(50)}
    assert len(ids) > 40  # random suffix, not a counter
    assert all(re.fullmatch(r"T-\d{8}-[0-9a-f]{4}", i) for i in ids)
    p1 = coord.new("one", "framework", ["a/"])
    p2 = coord.new("two", "framework", ["b/"])
    assert p1 != p2 and p1.exists() and p2.exists()


def test_legacy_ids_stay_valid_and_sort_before_new(repo):
    from openhumanoid import coord
    write_task(repo, "T-0007")
    write_task(repo, "T-20261019-3fa2")
    assert coord.find("T-0007").exists() and coord.find("T-20261019-3fa2").exists()
    with pytest.raises(ValueError):
        coord.find("T-7")
    with pytest.raises(ValueError):
        coord.find("../etc/passwd")
    assert sorted(["T-20261019-3fa2", "T-0007", "T-20261020-0001"]) == ["T-0007", "T-20261019-3fa2", "T-20261020-0001"]
    assert [m["id"] for _, m, _ in coord.all_tasks()] == ["T-0007", "T-20261019-3fa2"]


def test_new_id_never_reuses_an_existing_file(repo, monkeypatch):
    from openhumanoid import coord
    write_task(repo, "T-20261019-aaaa")
    seq = iter(["aaaa", "bbbb"])
    monkeypatch.setattr(coord.secrets, "token_hex", lambda n: next(seq))
    from datetime import datetime
    assert coord.new_id(datetime(2026, 10, 19)) == "T-20261019-bbbb"


def test_claim_with_session_and_status_json(repo, capsys):
    from openhumanoid import cli, coord
    write_task(repo, "T-0007", status="open", paths=("modules/",))
    assert cli.main(["coord", "claim", "T-0007", "--agent", "w1", "--session", "sess-1"]) == 0
    assert coord.load_sessions() == {"sess-1": "T-0007"}
    assert coord.session_task("sess-1")["owner"] == "w1"
    assert coord.session_task("nope") is None
    capsys.readouterr()
    assert cli.main(["coord", "status", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    t = data["tasks"][0]
    assert t["id"] == "T-0007" and t["status"] == "claimed" and t["sessions"] == ["sess-1"] and t["paths"] == ["modules/"]
    assert {"profile", "conflicts", "ready"} <= set(data)


def test_claim_session_defaults_to_env(repo, monkeypatch):
    from openhumanoid import cli, coord
    write_task(repo, "T-0008", status="open")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "from-env")
    cli.main(["coord", "claim", "T-0008", "--agent", "w"])
    assert coord.load_sessions() == {"from-env": "T-0008"}


def test_auto_handoff_stub(repo):
    from openhumanoid import coord
    write_task(repo, "T-0009")
    p = coord.handoff("T-0009", "tester", auto=True)
    text = p.read_text(encoding="utf-8")
    assert "AUTO STUB" in text and "Recent commits" in text and "init" in text


# --- provenance --------------------------------------------------------------------------------------

def test_classify_source(repo):
    from openhumanoid import provenance as pv
    assert pv.classify_source("https://example.com/datasheet.pdf") == "url"
    assert pv.classify_source("estimate: guess") == "estimate"
    assert pv.classify_source("AGENTS.md") == "file"
    assert pv.classify_source("AGENTS.md#anchor") == "file"
    assert pv.classify_source("no/such/file.md") == "bad_file"
    assert pv.classify_source("measurement:AGENTS.md") == "measurement"
    assert pv.classify_source("measurement:nothing.json") == "bad_measurement"
    assert pv.classify_source("") == "empty" and pv.classify_source(None) == "empty"


def test_spec_provenance_counts(repo):
    from openhumanoid import provenance as pv
    spec = {"analysis": {"safety_factor": 1.25, "dynamic_factor": {"walk": 1.6, "run": 2.8}, "peak_fraction": 0.85},
            "mass_model": {"waste_factor": 1.3},
            "provenance": {"analysis.safety_factor": "AGENTS.md", "analysis.dynamic_factor": {"source": "https://x.org/paper"},
                           "analysis.peak_fraction": "estimate: guess", "mass_model.waste_factor": "no/such/file"}}
    r = pv.check_spec(spec)["counts"]
    assert r == {"spec_constants": 5, "spec_missing": 0, "spec_bad": 1, "spec_estimates": 1}
    del spec["provenance"]["analysis.safety_factor"]
    assert pv.check_spec(spec)["counts"]["spec_missing"] == 1
    assert pv.tuned_constants({"analysis": {"a": 1, "b": {"c": 2}, "flag": True}, "other": {"x": 1}}) == ["analysis.a", "analysis.b.c"]


def test_catalog_provenance_flags_inconsistent_parts(repo):
    from openhumanoid import catalog, provenance as pv
    catalog.load_catalog.cache_clear()
    base = pv.check_catalog()["counts"]
    assert base["catalog_missing"] == 0 and base["catalog_parts"] > 20
    f = next((repo / "catalog").rglob("sts3215-7v4.yaml"))
    part = yaml.safe_load(f.read_text(encoding="utf-8"))
    part["verified"] = True  # claims verified but the source is still an estimate
    f.write_text(yaml.safe_dump(part), encoding="utf-8")
    catalog.load_catalog.cache_clear()
    assert pv.check_catalog()["counts"]["catalog_bad"] == 1
    part.pop("source")
    f.write_text(yaml.safe_dump(part), encoding="utf-8")
    catalog.load_catalog.cache_clear()
    assert pv.check_catalog()["counts"]["catalog_missing"] == 1
    catalog.load_catalog.cache_clear()


def test_spec_schema_accepts_provenance_and_both_versions(repo):
    from openhumanoid.spec import load_raw, validate
    raw = load_raw("adam")
    assert validate(raw) == []
    raw["schema_version"] = "0.2"
    raw["provenance"] = {"analysis.safety_factor": "AGENTS.md", "mass_model": {"source": "estimate: x", "note": "n"}}
    assert validate(raw) == []
    raw["provenance"] = {"analysis.safety_factor": {"note": "no source"}}
    assert validate(raw) != []
    raw["schema_version"] = "9.9"
    assert validate(raw) != []


def test_check_provenance_cli(repo, capsys):
    from openhumanoid import cli
    assert cli.main(["check", "provenance", "adam"]) == 0  # warn-first: thresholds in gates.yaml decide the exit code
    out = capsys.readouterr().out
    assert "tuned constants" in out and "not yet enforced" in out


# --- gates -------------------------------------------------------------------------------------------

def test_gates_yaml_defines_required_gates():
    gates = yaml.safe_load((REPO / "pipeline" / "gates.yaml").read_text(encoding="utf-8"))["gates"]
    impl = {g for g, d in gates.items() if d["status"] == "implemented"}
    assert impl == {"G-validate", "G-size", "G-sim-stand", "G-tests", "G-provenance"}
    assert {g for g, d in gates.items() if d["status"] == "placeholder"} == {"G-envelopes", "G-silhouette-R2a", "G-geometry", "G-cad-sim"}
    th = gates["G-envelopes"]["thresholds"]
    assert th["p95_peak_max_fraction_of_stall"] == 0.70 and th["thermal_walk_minutes"] == 10


def test_placeholder_gate_never_writes_a_record(repo):
    from openhumanoid import cli, gate
    assert cli.main(["gate", "G-envelopes", "adam"]) == gate.NOT_IMPLEMENTED
    assert not gate.record_path("G-envelopes", "adam").exists()
    with pytest.raises(KeyError):
        gate.run_gate("G-nope", "adam")


def test_gate_record_lifecycle(repo):
    from openhumanoid import cli, gate
    assert cli.main(["gate", "G-validate", "adam"]) == 0
    rec = gate.read_record("G-validate", "adam")
    assert rec["status"] == "pass" and rec["sha"] == git(repo, "rev-parse", "HEAD") and rec["written_by"] == "oh gate"
    assert {"metrics", "timestamp", "dirty", "thresholds"} <= set(rec)
    assert gate.gate_state("G-validate", "adam") == "PASS"
    # committing the record itself keeps it current
    git(repo, "add", "-A", "-f")
    git(repo, "commit", "-qm", "record")
    assert gate.gate_state("G-validate", "adam") == "PASS"
    # a code change after the record makes it STALE
    (repo / "README.md").write_text("changed\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "code change")
    assert gate.gate_state("G-validate", "adam") == "STALE"
    # a record written on a dirty tree never counts
    (repo / "README.md").write_text("dirty again\n")
    gate.run_gate("G-validate", "adam")
    assert gate.read_record("G-validate", "adam")["dirty"] is True
    assert gate.gate_state("G-validate", "adam") == "DIRTY"
    assert gate.gate_state("G-size", "adam") == "NONE"


def test_gate_fail_is_recorded_and_a_crash_is_a_fail(repo):
    from openhumanoid import gate
    spec = repo / "variants" / "adam" / "spec.yaml"
    spec.write_text(spec.read_text(encoding="utf-8").replace("kinematics:", "kinematicz:", 1), encoding="utf-8")
    rec = gate.run_gate("G-validate", "adam")
    assert rec["status"] == "fail" and gate.read_record("G-validate", "adam")["status"] == "fail"
    assert gate.run_gate("G-validate", "no-such-variant")["status"] == "fail"


def test_gate_status_command(repo, capsys):
    from openhumanoid import cli
    cli.main(["gate", "G-validate", "adam"])
    capsys.readouterr()
    assert cli.main(["gate", "--status", "adam"]) == 0
    out = capsys.readouterr().out
    assert "G-validate" in out and "PASS" in out and "PLACEHOLDER" in out
    cli.main(["gate", "--status", "--json", "adam"])
    rows = {r["gate"]: r for r in json.loads(capsys.readouterr().out)}
    assert rows["G-validate"]["state"] == "DIRTY" or rows["G-validate"]["state"] == "PASS"
    assert rows["G-envelopes"]["state"] == "PLACEHOLDER"


def test_g_tests_and_g_provenance_run(repo):
    from openhumanoid import gate
    (repo / "tests").mkdir()
    (repo / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    assert gate.run_gate("G-tests", "adam")["status"] == "pass"
    (repo / "tests" / "test_ok.py").write_text("def test_ok():\n    assert False\n")
    assert gate.run_gate("G-tests", "adam")["status"] == "fail"
    assert gate.run_gate("G-provenance", "adam")["status"] == "pass"


@pytest.mark.skipif(not HAVE_MUJOCO, reason="mujoco not installed")
def test_smoke_gate_passes_for_adam_and_records_nothing(repo, capsys):
    from openhumanoid import cli, gate
    t0 = time.time()
    assert cli.main(["gate", "--smoke", "adam"]) == 0
    assert time.time() - t0 < 60
    assert "smoke PASS" in capsys.readouterr().out
    assert not gate.records_dir("adam").exists()  # smoke is a health check, not evidence


# --- shell write detection ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd,expected", [
    ("echo hi > variants/adam/generated/x.txt", ["variants/adam/generated/x.txt"]),
    ("echo hi >> out.log", ["out.log"]),
    ("cat a | tee -a generated/y", ["generated/y"]),
    ("sed -i 's/a/b/' pipeline/gates.yaml", ["pipeline/gates.yaml"]),
    ("sed -n 1,5p file.txt", []),
    ("rm -rf variants/adam/generated/sim", ["variants/adam/generated/sim"]),
    ("mv a.txt b.txt", ["a.txt", "b.txt"]),
    ("cp src.txt dst.txt", ["dst.txt"]),
    ("ls > /dev/null 2>&1", []),
    ("cmd 2>&1 | head", []),
    ("echo $HOME > $OUT", []),
    ("cd sub && echo x > f.txt", ["sub/f.txt"]),
    ("echo 'a > b' && echo ok", []),
    ("cat <<EOF > notes.md\nhello > not_a_target\nEOF", ["notes.md"]),
    ("Set-Content -Path pipeline/gates.yaml -Value 'x'", ["pipeline/gates.yaml"]),
    ("Remove-Item variants/adam/generated -Recurse -Force", ["variants/adam/generated"]),
    ("FOO=1 sudo rm x", ["x"]),
    ("git status && python -m openhumanoid size adam", []),
])
def test_write_targets(cmd, expected):
    got = [p for p, _ in shellwrites.write_targets(cmd, ".")]
    assert [g.removeprefix("./") for g in got] == expected


# --- PreToolUse --------------------------------------------------------------------------------------

@pytest.fixture
def worker(repo):
    write_task(repo, "T-0100", status="claimed", paths=("modules/joints/", "variants/adam/cad/"))
    register(repo, "s-worker", "T-0100")
    return repo


def test_pretooluse_denies_generated_for_everyone(worker):
    code, out, err, dt = edit(worker, "variants/adam/generated/sizing.json")
    assert code == 2 and "generated" in err and "oh" in err
    assert dt < 2.0
    assert edit(worker, "variants/adam/generated/bom.csv", tool="MultiEdit")[0] == 2
    assert edit(worker, "variants/adam/generated/x.md", sid="commander")[0] == 2  # the commander can't hand-edit generated either


def test_pretooluse_protects_contracts_and_gate_config(worker):
    for rel in ("schemas/spec.schema.json", "cad/EXPORT_CONTRACT.md", "modules/INTERFACE.md", "pipeline/gates.yaml",
                "pipeline/hooks.yaml", ".claude/settings.json", "tools/hooks/pretooluse.py"):
        assert edit(worker, rel)[0] == 2, rel
    nb = run_hook(worker, "pretooluse.py", {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": str(worker / "schemas" / "x.ipynb")}})
    assert nb[0] == 2


def test_pretooluse_commander_is_asked_not_blocked(worker):
    code, out, _, _ = edit(worker, "schemas/spec.schema.json", sid="commander-unclaimed")
    assert code == 0
    d = json.loads(out)["hookSpecificOutput"]
    assert d["permissionDecision"] == "ask" and "ADR" in d["permissionDecisionReason"]
    write_task(worker, "T-0101", stream="coordination", paths=("coordination/",))
    register(worker, "s-boss", "T-0101")
    assert json.loads(edit(worker, "pipeline/gates.yaml", sid="s-boss")[1])["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_pretooluse_adr_task_that_lists_the_path_may_edit_it(worker):
    write_task(worker, "T-0102", status="in_progress", paths=("schemas/spec.schema.json", "docs/decisions/0013-provenance.md"))
    register(worker, "s-adr", "T-0102")
    assert edit(worker, "schemas/spec.schema.json", sid="s-adr") [:2] == (0, "")
    assert edit(worker, "schemas/catalog-part.schema.json", sid="s-adr")[0] == 2  # only the listed file
    write_task(worker, "T-0103", status="in_progress", paths=("./", "*"))
    register(worker, "s-all", "T-0103")
    assert edit(worker, "schemas/spec.schema.json", sid="s-all")[0] == 2  # a catch-all claim authorises nothing protected
    # generated stays protected even when listed
    write_task(worker, "T-0104", status="in_progress", paths=("variants/adam/generated/",))
    register(worker, "s-gen", "T-0104")
    assert edit(worker, "variants/adam/generated/sizing.json", sid="s-gen")[0] == 2


def test_pretooluse_warns_outside_claim_and_allows_inside(worker):
    assert edit(worker, "modules/joints/knee/module.yaml")[:2] == (0, "")
    assert edit(worker, "variants/adam/cad/leg.py")[:2] == (0, "")
    assert edit(worker, "coordination/tasks/T-0100.md")[:2] == (0, "")  # coordination is always allowed
    code, out, _, _ = edit(worker, "software/core/api.py")
    assert code == 0
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "outside the paths claimed by T-0100" in ctx
    assert edit(worker, "software/core/api.py", sid="unclaimed-commander")[:2] == (0, "")  # commander exempt


def test_pretooluse_enforce_mode_denies_outside_claim(worker):
    cfg = yaml.safe_load((worker / "pipeline" / "hooks.yaml").read_text(encoding="utf-8"))
    cfg["claimed_paths"] = "enforce"
    (worker / "pipeline" / "hooks.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert edit(worker, "software/core/api.py")[0] == 2
    assert edit(worker, "modules/joints/knee/module.yaml")[0] == 0


def test_pretooluse_bash_targets(worker):
    assert bash(worker, "echo x > variants/adam/generated/log.txt")[0] == 2
    assert bash(worker, "sed -i 's/0.7/0.9/' pipeline/gates.yaml")[0] == 2
    assert bash(worker, "rm -rf variants/adam/generated/sim")[0] == 2
    assert bash(worker, "cd variants/adam/generated && echo x > a.txt")[0] == 2
    assert bash(worker, "python - <<'EOF' > schemas/new.json\nprint(1)\nEOF")[0] == 2
    assert bash(worker, "ls > /dev/null 2>&1 && echo ok")[:2] == (0, "")
    assert bash(worker, "oh gate --status adam")[:2] == (0, "")
    assert bash(worker, "git checkout -- variants/adam/generated")[:2] == (0, "")  # reverting generated output is legitimate
    assert bash(worker, "echo x > /tmp/outside-the-repo.txt")[:2] == (0, "")
    code, out, _, _ = bash(worker, "echo x > docs/notes.md")
    assert code == 0 and "outside the paths" in out


def test_pretooluse_powershell_tool(worker):
    code = run_hook(worker, "pretooluse.py", {"tool_name": "PowerShell", "tool_input": {"command": "Set-Content -Path pipeline/gates.yaml -Value x"}})[0]
    assert code == 2


def test_pretooluse_fails_open(worker, tmp_path):
    assert run_hook(worker, "pretooluse.py", "this is not json", expect_exit=0)[1] == ""
    assert run_hook(worker, "pretooluse.py", "", expect_exit=0)[1] == ""
    assert run_hook(worker, "pretooluse.py", {"tool_name": "Write", "tool_input": None, "cwd": str(tmp_path)}, expect_exit=0)[1] == ""
    # outside any checkout: nothing to enforce
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    assert run_hook(worker, "pretooluse.py", {"cwd": str(nowhere), "tool_name": "Write", "tool_input": {"file_path": str(nowhere / "generated" / "x")}},
                    expect_exit=0)[1] == ""
    # corrupted sessions map and task file: fail open and log
    (worker / "coordination" / ".local" / "sessions.json").write_text("{not json")
    assert edit(worker, "software/core/api.py")[0] == 0
    (worker / "coordination" / ".local" / "sessions.json").write_text(json.dumps({"s-worker": "T-0100"}))
    (worker / "coordination" / "tasks" / "T-0100.md").write_text("garbage without front matter")
    # a task file that can't be parsed means "no known claim": the commander path. Generated stays denied, nothing crashes.
    assert edit(worker, "variants/adam/generated/sizing.json")[0] == 2
    assert edit(worker, "software/core/api.py")[:2] == (0, "")


def test_pretooluse_kill_switch_and_disabled_config(worker):
    assert edit(worker, "variants/adam/generated/sizing.json")[0] == 2
    off = worker / "coordination" / ".local" / "hooks.off"
    off.write_text("")
    assert edit(worker, "variants/adam/generated/sizing.json")[0] == 0
    off.unlink()
    cfg = yaml.safe_load((worker / "pipeline" / "hooks.yaml").read_text(encoding="utf-8"))
    cfg["enabled"] = False
    (worker / "pipeline" / "hooks.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert edit(worker, "variants/adam/generated/sizing.json")[0] == 0


def test_protection_survives_a_deleted_hooks_config(worker):
    (worker / "pipeline" / "hooks.yaml").unlink()
    assert edit(worker, "variants/adam/generated/sizing.json")[0] == 2  # built-in defaults


def test_pretooluse_is_fast(worker):
    times = [edit(worker, "modules/joints/a.yaml")[3] for _ in range(3)]
    assert min(times) < 2.0


# --- Stop ----------------------------------------------------------------------------------------------

def test_stop_blocks_once_without_a_passing_gate(repo):
    write_task(repo, "T-0200", status="in_progress", phase="W1", gates=("G-validate",))
    register(repo, "s-worker", "T-0200")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "task")
    code, out, _, dt = run_hook(repo, "stop.py", {"hook_event_name": "Stop", "stop_hook_active": False}, expect_exit=0)
    d = json.loads(out)
    assert d["decision"] == "block" and "G-validate=NONE" in d["reason"] and "oh gate" in d["reason"]
    assert dt < 3
    # honours stop_hook_active: blocks only once
    assert run_hook(repo, "stop.py", {"stop_hook_active": True}, expect_exit=0)[1] == ""
    # a PASS record at HEAD lets it through
    from openhumanoid import gate
    assert gate.run_gate("G-validate", "adam")["status"] == "pass"
    git(repo, "add", "-A", "-f")
    git(repo, "commit", "-qm", "gate record")
    assert run_hook(repo, "stop.py", {"stop_hook_active": False}, expect_exit=0)[1] == ""


def test_stop_uses_the_phase_gates_and_skips_other_sessions(repo):
    write_task(repo, "T-0201", status="in_progress", phase="P0", gates=())
    register(repo, "s-worker", "T-0201")
    out = run_hook(repo, "stop.py", {"stop_hook_active": False})[1]
    assert "G-size=NONE" in json.loads(out)["reason"] and "G-sim-stand=NONE" in json.loads(out)["reason"]
    assert run_hook(repo, "stop.py", {"session_id": "commander"}, expect_exit=0)[1] == ""  # unclaimed: never blocked
    write_task(repo, "T-0201", status="review", phase="P0")
    assert run_hook(repo, "stop.py", {}, expect_exit=0)[1] == ""  # review/done tasks aren't blocked
    write_task(repo, "T-0201", status="in_progress", phase="NO-GATES-FOR-THIS")
    assert run_hook(repo, "stop.py", {}, expect_exit=0)[1] == ""


def test_stop_config_off_and_warn(repo):
    write_task(repo, "T-0202", status="in_progress", gates=("G-validate",))
    register(repo, "s-worker", "T-0202")
    cfg = yaml.safe_load((repo / "pipeline" / "hooks.yaml").read_text(encoding="utf-8"))
    cfg["stop_gate"] = "warn"
    (repo / "pipeline" / "hooks.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    d = json.loads(run_hook(repo, "stop.py", {})[1])
    assert "decision" not in d and "G-validate" in d["hookSpecificOutput"]["additionalContext"]
    cfg["stop_gate"] = "off"
    (repo / "pipeline" / "hooks.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert run_hook(repo, "stop.py", {})[1] == ""


# --- PreCompact ----------------------------------------------------------------------------------------

def test_precompact_writes_a_handoff_stub_once(repo):
    write_task(repo, "T-0300", status="in_progress", title="Leg module")
    register(repo, "s-worker", "T-0300")
    code, out, _, dt = run_hook(repo, "precompact.py", {"hook_event_name": "PreCompact", "trigger": "auto"}, expect_exit=0)
    files = list((repo / "coordination" / "handoffs").glob("*-T-0300-*.md"))
    assert len(files) == 1 and "AUTO STUB" in files[0].read_text(encoding="utf-8") and dt < 3
    run_hook(repo, "precompact.py", {"trigger": "auto"}, expect_exit=0)
    assert len(list((repo / "coordination" / "handoffs").glob("*-T-0300-*.md"))) == 1  # rate-limited
    run_hook(repo, "precompact.py", {"session_id": "commander", "trigger": "manual"}, expect_exit=0)
    assert len(list((repo / "coordination" / "handoffs").glob("*.md"))) == 1  # unclaimed sessions get no stub


# --- SessionStart --------------------------------------------------------------------------------------

def test_session_start_context_without_smoke(repo):
    cfg = yaml.safe_load((repo / "pipeline" / "hooks.yaml").read_text(encoding="utf-8"))
    cfg["smoke_on_session_start"] = False
    (repo / "pipeline" / "hooks.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    write_task(repo, "T-0400", status="in_progress", title="Knee work", paths=("modules/joints/knee/",))
    register(repo, "s-worker", "T-0400")
    (repo / "coordination" / "handoffs" / "2026-10-19-0100-T-0400-tester.md").write_text("# Handoff\n- done: the thing\n", encoding="utf-8")
    for source in ("startup", "resume", "compact", "fork"):
        code, out, _, _ = run_hook(repo, "session_start.py", {"hook_event_name": "SessionStart", "source": source}, expect_exit=0)
        assert "Session id: s-worker" in out and "--session s-worker" in out
        assert "YOUR TASK: T-0400" in out and "modules/joints/knee/" in out
        assert "2026-10-19-0100-T-0400-tester.md" in out and "done: the thing" in out
        assert "git log -5" in out and "init" in out
    out = run_hook(repo, "session_start.py", {"session_id": "commander", "source": "startup"}, expect_exit=0)[1]
    assert "no registered task" in out and "T-0400" in out  # the board still lists it


@pytest.mark.skipif(not HAVE_MUJOCO, reason="mujoco not installed")
def test_session_start_runs_the_smoke_gate(repo):
    code, out, _, dt = run_hook(repo, "session_start.py", {"source": "startup"}, expect_exit=0)
    assert "Smoke gate (adam): PASS" in out and "G-sim-stand" in out
    assert dt < 60


def test_session_start_never_blocks_on_a_broken_smoke(repo):
    cfg = yaml.safe_load((repo / "pipeline" / "gates.yaml").read_text(encoding="utf-8"))
    cfg["smoke"] = ["G-validate"]
    (repo / "pipeline" / "gates.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    spec = repo / "variants" / "adam" / "spec.yaml"
    spec.write_text(spec.read_text(encoding="utf-8").replace("kinematics:", "kinematicz:", 1), encoding="utf-8")
    code, out, err, _ = run_hook(repo, "session_start.py", {"source": "startup"}, expect_exit=0)
    assert "FAIL" in out and "G-validate" in out


def test_session_start_exports_the_session_id(repo, tmp_path):
    cfg = yaml.safe_load((repo / "pipeline" / "hooks.yaml").read_text(encoding="utf-8"))
    cfg["smoke_on_session_start"] = False
    (repo / "pipeline" / "hooks.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    envfile = tmp_path / "env.sh"
    body = json.dumps({"session_id": "abc-123", "cwd": str(repo), "source": "startup"})
    env = {**os.environ, "CLAUDE_ENV_FILE": str(envfile)}
    subprocess.run([sys.executable, str(HOOKS / "session_start.py")], input=body.encode(), env=env, capture_output=True, timeout=60)
    assert "export CLAUDE_SESSION_ID=abc-123" in envfile.read_text()


# --- settings.json ---------------------------------------------------------------------------------------

def test_settings_json_wires_every_hook():
    s = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))["hooks"]
    assert set(s) == {"PreToolUse", "SessionStart", "Stop", "PreCompact"}
    pre = s["PreToolUse"][0]
    assert set(pre["matcher"].split("|")) == {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "PowerShell"}
    assert set(s["SessionStart"][0]["matcher"].split("|")) == {"startup", "resume", "compact", "fork"}
    for ev, script in (("PreToolUse", "pretooluse.py"), ("SessionStart", "session_start.py"), ("Stop", "stop.py"), ("PreCompact", "precompact.py")):
        h = s[ev][0]["hooks"][0]
        assert h["type"] == "command" and h["args"][0].endswith(f"tools/hooks/{script}") and (HOOKS / script).exists()
        assert h["timeout"] >= 5
