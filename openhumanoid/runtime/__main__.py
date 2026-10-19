"""CLI: python -m openhumanoid.runtime <command>   (the commander wires it into `oh`; openhumanoid/cli.py is untouched)

    scenarios [names...] [--quick]     run the software-in-the-loop acceptance scenarios and print a pass/fail table
    run                                run the sim with the command front ends (--web PORT, --tcp PORT, --realtime)
    bench [--seconds N]                control-loop compute time (standing, walking, dancing) and a Raspberry Pi 5 estimate
    pushscan [stand|walk] [dirs...]    largest recoverable push impulse per direction
    info                               model summary (joints, limits, mass)
    describe                           print the Command API as JSON
"""
from __future__ import annotations

import argparse
import json
import sys
import time


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass


def cmd_info(a) -> int:
    from .scenarios import get_model
    m = get_model(a.concept)
    print(json.dumps(m.summary(), indent=1))
    for n, lo, hi, r in zip(m.names, m.lo, m.hi, m.ratio):
        print(f"  {n:<18} [{lo:+.2f}, {hi:+.2f}]  servo {m.robot.acts[n]}")
    return 0


def cmd_describe(a) -> int:
    from .commands import COMMANDS
    print(json.dumps(COMMANDS, indent=1))
    return 0


def cmd_scenarios(a) -> int:
    from . import scenarios as S
    names = a.names or list(S.ALL)
    rows, fails = [], 0
    for n in names:
        t0 = time.time()
        r = S.ALL[n]()
        rs = r if isinstance(r, list) else [r]
        for x in rs:
            print(x.row() + f"   [{time.time() - t0:.0f} s]", flush=True)
            fails += 0 if x.passed else 1
    print(f"{fails} failing")
    return 1 if fails else 0


def cmd_bench(a) -> int:
    from .bench import bench
    print(json.dumps(bench(a.seconds), indent=1))
    return 0


def cmd_pushscan(a) -> int:
    from . import scenarios as S
    kind = a.kind
    for d in a.dirs or list(S.DIRS):
        print(kind, d, S.largest_push(kind, d), flush=True)
    return 0


def cmd_run(a) -> int:
    from .frontends.web import JsonLineServer, WebServer
    from .scenarios import make_sim
    rt, hal = make_sim()
    if a.web:
        w = WebServer(rt.bus, a.host, a.web, a.token).start()
        print(f"phone UI on http://{a.host}:{w.port}/")
    if a.tcp:
        t = JsonLineServer(rt.bus, a.host, a.tcp).start()
        print(f"JSON-lines API on {a.host}:{t.port}")
    t0 = time.time()
    try:
        while a.seconds is None or hal.t < a.seconds:
            rt.step()
            if a.realtime:
                dt = hal.t - (time.time() - t0)
                if dt > 0:
                    time.sleep(dt)
    except KeyboardInterrupt:
        pass
    print(json.dumps(rt.status(), indent=1))
    return 0


def main(argv=None) -> int:
    _utf8()
    p = argparse.ArgumentParser(prog="python -m openhumanoid.runtime")
    p.add_argument("--concept", default="variants/adam/concepts/R1-P1r-0p55-3s-sts3250-knee-hiproll.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scenarios")
    s.add_argument("names", nargs="*")
    s.set_defaults(fn=cmd_scenarios)
    s = sub.add_parser("bench")
    s.add_argument("--seconds", type=float, default=20.0)
    s.set_defaults(fn=cmd_bench)
    s = sub.add_parser("pushscan")
    s.add_argument("kind", choices=("stand", "walk"))
    s.add_argument("dirs", nargs="*")
    s.set_defaults(fn=cmd_pushscan)
    s = sub.add_parser("run")
    s.add_argument("--web", type=int, default=0)
    s.add_argument("--tcp", type=int, default=0)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--token", default=None)
    s.add_argument("--seconds", type=float, default=None)
    s.add_argument("--realtime", action="store_true")
    s.set_defaults(fn=cmd_run)
    sub.add_parser("info").set_defaults(fn=cmd_info)
    sub.add_parser("describe").set_defaults(fn=cmd_describe)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
