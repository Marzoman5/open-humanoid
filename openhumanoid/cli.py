"""`oh`: the Open Humanoid command line. Every command prints a short summary (token-friendly)
and writes full results to files."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

from . import __version__


def _spec(ref):
    from .spec import load_spec
    return load_spec(ref)


def cmd_validate(a):
    from .catalog import validate_catalog
    from .spec import load_raw, validate
    errs = validate(load_raw(a.variant))
    cerrs = validate_catalog()
    for e in errs + cerrs:
        print("✗", e)
    print("spec ok" if not errs else f"spec: {len(errs)} error(s)", "| catalog ok" if not cerrs else f"| catalog: {len(cerrs)} error(s)")
    return 1 if errs or cerrs else 0


def cmd_size(a):
    from .reports import write_sizing
    from .sizing import size
    spec = _spec(a.variant)
    d = write_sizing(spec, size(spec))
    print(f"{spec['name']}: {'FEASIBLE' if d['feasible'] else 'INFEASIBLE'} ({d['reason']}) | h={d['height_m']:.2f} m")
    if d.get("limiting_factor"):
        print(f"  taller limited by: {d['limiting_factor']}")
    if "cost_usd" in d:
        acts = sorted(set(d["actuators"].values()))
        print(f"  mass≈{d['mass']['total_kg']:.2f} kg | cost≈${d['cost_usd']['total']:.0f} | actuators: {', '.join(acts)} x{len(d['actuators'])}")
        print(f"  optional added: {d['optional_added'] or '-'} | dropped: {d['optional_dropped'] or '-'}")
        for g, gc in d["gaits"].items():
            print(f"  gait {g:5} {'ok ' if gc['ok'] else 'NO '} worst {gc['worst_joint']} {gc['worst_margin']}x ({gc['limit']})")
    print(f"  -> {spec['_dir']}/generated/sizing.md")
    return 0 if d["feasible"] else 2


def cmd_bom(a):
    from .reports import write_bom
    from .simgen import load_sizing
    spec = _spec(a.variant)
    s = load_sizing(spec)
    if not s.get("actuators"):
        print("sizing infeasible; run `oh size` and fix the spec first")
        return 2
    r = write_bom(spec, s)
    t = r["totals"]
    print(f"{spec['name']} BOM: ${t['typical']:.2f} typical (range ${t['low']:.0f}-${t['high']:.0f}) | "
          f"{r['unverified']}/{len(r['rows'])} lines unverified -> {spec['_dir']}/generated/bom.md")
    return 0


def cmd_sim(a):
    from . import simgen
    spec = _spec(a.variant)
    if a.action == "build":
        print("wrote", simgen.write_mjcf(spec))
    elif a.action == "test":
        simgen.write_mjcf(spec)
        r = simgen.smoke_test(spec, a.seconds)
        print(json.dumps(r, indent=2) if a.json else
              f"{spec['name']} sim: {'PASS' if r['ok'] else 'FAIL'} ({r['reason']}) | mass {r.get('mass_kg')} kg | "
              f"pelvis z {r.get('pelvis_z_start')}->{r.get('pelvis_z_end')} | tilt {r.get('tilt_deg')} deg | "
              f"worst holding torque {r.get('worst_joint')} at {r['peak_torque_fraction_of_stall'][r['worst_joint']]:.0%} of stall")
        return 0 if r["ok"] else 2
    elif a.action == "view":
        simgen.view(spec)
    return 0


def cmd_render(a):
    from .render import render
    spec = _spec(a.variant)
    if getattr(a, "studio", False):
        files = render(spec, studio=True, refs=a.ref, zebra=a.zebra)
        print(f"{spec['name']}: studio rig ({len(files)} files) -> {files[0].parent}")
        return 0
    files = render(spec)
    print(f"{spec['name']}: {len(files)} images -> {files[-1]} (contact sheet)")
    return 0


def cmd_cad(a):
    from . import cad
    spec = _spec(a.variant)
    if a.action == "build":
        r = cad.build_variant(spec)
        t = r["totals"]
        print(f"{spec['name']} CAD: {r['printed_parts']} printed parts -> {r['dir']}")
        print(f"  mass {t['total_kg']} kg (printed {t['printed_kg']} kg, purchased {t['purchased_kg']} kg)")
        for n in r["notes"]:
            print("  note:", n)
    else:
        r = cad.check_variant(spec, a.min_mm3)
        print(f"{spec['name']} CAD check ({r['pose']} pose): {len(r['clashes'])} clashes, {len(r['oversize'])} parts too big for the bed, "
              f"{len(r['unknown'])} pairs not checkable (boolean failed)")
        for x in r["clashes"]:
            print(f"  clash {x[0]} x {x[1]}: {x[2]} mm3")
        for x in r["oversize"]:
            print(f"  oversize {x[0]}: {x[1]} mm")
        for n in r["notes"]:
            print("  note:", n)
        return 0 if not r["clashes"] and not r["oversize"] else 2
    return 0


def cmd_catalog(a):
    from . import catalog
    parts = catalog.load_catalog().values()
    for p in sorted(parts, key=lambda p: (p["category"], catalog.price(p))):
        if a.category and p["category"] != a.category:
            continue
        extra = ""
        if p["category"] == "actuator":
            x = p["actuator"]
            extra = f"stall {x['stall_torque_nm']:.2f} N·m, {x['no_load_speed_rad_s']:.1f} rad/s, {x['voltage_v']} V, fb={x['feedback']}"
        print(f"{p['category']:11} {p['id']:26} ${catalog.price(p):>7.2f} {'✓' if p['verified'] else '~'} {extra}")
    return 0


def cmd_new(a):
    from .paths import variants_dir
    dst = variants_dir() / a.id
    if dst.exists():
        print(f"{dst} already exists")
        return 1
    shutil.copytree(variants_dir() / "_template", dst)
    spec = (dst / "spec.yaml").read_text(encoding="utf-8").replace("__ID__", a.id).replace("__NAME__", a.name or a.id.title())
    spec = spec.replace("extends: adam", f"extends: {a.extends}") if a.extends else spec.replace("extends: adam\n", "")
    (dst / "spec.yaml").write_text(spec, encoding="utf-8")
    print(f"created {dst}. Edit spec.yaml, then: oh validate {a.id} && oh size {a.id}")
    return 0


def cmd_coord(a):
    from . import coord
    if a.action == "status":
        print(json.dumps(coord.status_data(), indent=1) if a.json else coord.status_report())
    elif a.action == "new":
        p = coord.new(a.title, a.stream, a.paths or [], a.depends or [], a.size, a.goal or "", phase=a.phase)
        print("created", p)
    elif a.action == "claim":
        session = a.session or os.environ.get("CLAUDE_SESSION_ID")
        coord.claim(a.task, a.agent, a.force, session)
        print(f"{a.task} claimed by {a.agent}. Commit this change now."
              + (f" (session {session[:8]} registered: hooks now know your claimed paths)" if session else
                 " (no --session given: hooks can't tell which paths you claimed, so they won't enforce them)"))
    elif a.action == "set":
        coord.set_status(a.task, a.status, a.agent, a.note or "")
        print(f"{a.task} -> {a.status}")
    elif a.action == "done":
        coord.set_status(a.task, "done", a.agent, a.note or "")
        print(f"{a.task} -> done")
    elif a.action == "release":
        coord.set_status(a.task, "open", a.agent, a.note or "released")
        print(f"{a.task} released")
    elif a.action == "handoff":
        print("fill in:" if not a.auto else "auto stub:", coord.handoff(a.task, a.agent, auto=a.auto))
    elif a.action == "resume":
        h = coord.latest_handoff(a.task)
        print(h.read_text(encoding="utf-8") if h else f"no handoff for {a.task}")
    return 0


def cmd_gate(a):
    from . import gate
    if a.smoke or a.status:
        variant = a.args[0] if a.args else None
        if a.status:
            if a.json:
                print(json.dumps(gate.status_rows(variant), indent=1))
            else:
                print(gate.status_text(variant))
            return 0
        res = gate.smoke(variant)
        for r in res:
            print(f"  {r['gate']:12} {r['status'].upper():5} {r['summary']}")
        bad = [r["gate"] for r in res if r["status"] != "pass"]
        print(f"smoke {'PASS' if not bad else 'FAIL: ' + ', '.join(bad)} ({gate.default_variant() if not variant else variant}; not recorded: smoke is a health check, run `oh gate <id>` for evidence)")
        return 0 if not bad else 2
    if not a.args:
        for g, d in gate.load_gates().items():
            print(f"{g:18} {d.get('status'):12} {','.join(map(str, gate._as_list(d.get('phase')))):8} {d.get('description', '').strip()[:90]}")
        return 0
    r = gate.run_gate(a.args[0], a.args[1] if len(a.args) > 1 else None)
    if r["status"] == "not_implemented":
        print(r["summary"])
        return gate.NOT_IMPLEMENTED
    print(f"{r['gate']} [{r['variant']}] {r['status'].upper()}: {r['summary']}")
    print(f"  record: variants/{r['variant']}/generated/gates/{r['gate']}.json @ {(r['sha'] or '?')[:8]}{' (DIRTY tree: commit, then re-run for a record that counts)' if r['dirty'] else ''}")
    return 0 if r["status"] == "pass" else 2


def cmd_check(a):
    from . import gate, provenance
    rep = provenance.check(a.variant)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        print(provenance.format_report(rep))
    # Warn-first: the exit code only reflects the threshold in pipeline/gates.yaml (G-provenance).
    th = gate.load_gates().get("G-provenance", {}).get("thresholds", {})
    c = rep["counts"]
    over = [k for k, lim in (("catalog_missing", th.get("max_catalog_missing", 0)), ("catalog_bad", th.get("max_catalog_bad", 0)),
                             ("spec_missing", th.get("max_spec_missing", 10**6)), ("spec_bad", th.get("max_spec_bad", 10**6)),
                             ("spec_estimates", th.get("max_spec_estimates", 10**6)), ("catalog_estimates", th.get("max_catalog_estimates", 10**6)))
            if c[k] > lim]
    print("provenance gate threshold: " + ("EXCEEDED: " + ", ".join(over) if over else "ok (warnings above are not yet enforced)"))
    return 2 if over else 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    ap =argparse.ArgumentParser(prog="oh", description="Open Humanoid toolkit")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("validate", help="validate a variant spec + the catalog"); s.add_argument("variant"); s.set_defaults(f=cmd_validate)
    s = sub.add_parser("size", help="torque/speed sizing, actuator selection, max height for budget"); s.add_argument("variant"); s.set_defaults(f=cmd_size)
    s = sub.add_parser("bom", help="bill of materials from sizing"); s.add_argument("variant"); s.set_defaults(f=cmd_bom)
    s = sub.add_parser("sim", help="MuJoCo: build | test | view")
    s.add_argument("action", choices=["build", "test", "view"]); s.add_argument("variant")
    s.add_argument("--seconds", type=float, default=3.0); s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_sim)
    s = sub.add_parser("render", help="review images: MuJoCo sim sheet, or --studio design rig (ADR 0010)")
    s.add_argument("variant"); s.add_argument("--studio", action="store_true", help="pyvista clay/silhouette/reference rig")
    s.add_argument("--ref", action="append", help="reference overlay (name=path.yaml), repeatable")
    s.add_argument("--zebra", action="store_true"); s.set_defaults(f=cmd_render)
    from .design.cli import register as register_design
    register_design(sub)
    s = sub.add_parser("runtime", help="robot runtime / software-in-the-loop (scenarios | run | bench | pushscan | info | describe)",
                       add_help=False)
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(f=lambda a: __import__("openhumanoid.runtime.__main__", fromlist=["main"]).main(a.rest))
    s = sub.add_parser("concept", help="P2 concept engine (python -m openhumanoid.concept ...)", add_help=False)
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(f=lambda a: __import__("openhumanoid.concept.__main__", fromlist=["main"]).main(a.rest))
    s = sub.add_parser("cad", help="spec-driven CAD (build123d): build | check")
    s.add_argument("action", choices=["build", "check"]); s.add_argument("variant")
    s.add_argument("--min-mm3", type=float, default=20.0, help="ignore overlaps smaller than this"); s.set_defaults(f=cmd_cad)
    s = sub.add_parser("catalog", help="list catalog parts"); s.add_argument("--category"); s.set_defaults(f=cmd_catalog)
    s = sub.add_parser("new", help="create a variant from variants/_template")
    s.add_argument("id"); s.add_argument("--name"); s.add_argument("--extends"); s.set_defaults(f=cmd_new)

    s = sub.add_parser("gate", help="run a pipeline gate and record the result (pipeline/gates.yaml); --smoke, --status")
    s.add_argument("args", nargs="*", help="<gate-id> [variant]; with --smoke/--status: [variant]")
    s.add_argument("--smoke", action="store_true", help="validate + size + sim stand, short, nothing recorded")
    s.add_argument("--status", action="store_true", help="latest record per gate and whether it is at HEAD")
    s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_gate)
    s = sub.add_parser("check", help="consistency checks (provenance)")
    s.add_argument("what", choices=["provenance"]); s.add_argument("variant", nargs="?", default="adam")
    s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_check)

    c = sub.add_parser("coord", help="multi-agent coordination")
    c.add_argument("action", choices=["status", "new", "claim", "set", "done", "release", "handoff", "resume"])
    c.add_argument("task", nargs="?", help="task id (T-0007 or T-20261019-3fa2) or title for `new`")
    c.add_argument("status", nargs="?", help="for `set`")
    c.add_argument("--agent"); c.add_argument("--stream", default="framework"); c.add_argument("--paths", nargs="*")
    c.add_argument("--depends", nargs="*"); c.add_argument("--size", default="M"); c.add_argument("--goal"); c.add_argument("--phase")
    c.add_argument("--note"); c.add_argument("--force", action="store_true")
    c.add_argument("--json", action="store_true", help="status: machine-readable board")
    c.add_argument("--session", help="claim: Claude Code session id, so hooks can map the session to the task's paths (default $CLAUDE_SESSION_ID)")
    c.add_argument("--auto", action="store_true", help="handoff: pre-filled stub (used by the PreCompact hook)")
    c.set_defaults(f=cmd_coord)

    a = ap.parse_args(argv)
    if a.cmd == "coord" and a.action == "new":
        a.title = a.task
    if a.cmd == "coord" and a.action in ("claim", "handoff") and not a.agent:
        ap.error("--agent is required")
    try:
        return a.f(a) or 0
    except (RuntimeError, FileNotFoundError, ValueError, KeyError) as e:
        print("error:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
