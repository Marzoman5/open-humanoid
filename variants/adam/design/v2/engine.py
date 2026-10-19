"""Adam baseline v2 (T-20261019-4ab5): engine runs on the strict, half-calibrated and ODM-calibrated gate sets, using the concept engine's
own functions through variants/adam/design/r1_calibrated.py (`run`: gait sweep, nominal + the 13 bounds, R10 at the required 0.45 N.s,
the largest recoverable push). Thresholds are never changed; nothing under generated/ is written by this script.

Subcommands
  calibrated <concept.yaml ...> [--heights 0.55 0.60] [--no-bounds]      -> results/cal_<id>.{json,md}
  backlash <concept.yaml> --extra-deg KNEE ANKLE [--servo-deg 0.5]         -> results/backlash_<id>.json
      SENSITIVITY (needs closed loop, P5; never a gate): servo-in-the-loop playback of the frozen walk with a per-joint backlash
      (play operator, openhumanoid.actuators.servo.ServoBank) = servo gear backlash + the linkage play from
      variants/adam/cad/linkages/analysis.py on the knee and ankle-pitch joints only, against the servo backlash alone.

Run:  .venv/Scripts/python variants/adam/design/v2/engine.py calibrated variants/adam/concepts/V2a-0p55-longarm.yaml --heights 0.55 0.60
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(REPO))

import r1_calibrated as R1C  # noqa: E402

RES = HERE / "results"


def cmd_calibrated(a) -> int:
    from openhumanoid.concept.robot import load_concept
    for cp in a.concepts:
        rs = [R1C.run(cp, h, bounds=not a.no_bounds, pushmax=True) for h in a.heights]
        cid = load_concept(cp)["id"]
        (RES / f"cal_{cid}.json").write_text(json.dumps(rs, indent=1, default=R1C._js), encoding="utf-8")
        md = R1C.to_md(rs).replace("variants/adam/design/r1_calibrated.py (T-20261019-36f9)", "variants/adam/design/v2/engine.py via r1_calibrated.py (T-20261019-4ab5)")
        (RES / f"cal_{cid}.md").write_text(md, encoding="utf-8")
    return 0


def cmd_backlash(a) -> int:
    from dataclasses import replace
    from openhumanoid.concept import evaluate as EV
    from openhumanoid.concept.playback import PlayConfig, learn_offsets, play
    from openhumanoid.concept.robot import load_concept
    c = load_concept(a.concept)
    best, _ = EV.gait_sweep(c, None)
    c = EV.apply_gait(c, best)
    b = EV.run_bundle(c, EV.Mods(), thermal=False, pushes=False)
    robot = b.robot
    ref = b.refs["walk_forward"]
    servo = math.radians(a.servo_deg)
    out = {"concept": c["id"], "gait": {k: best[k] for k in ("stance_knee_flex_deg", "step_time_s")},
           "label": "SENSITIVITY: open-loop servo-in-the-loop replay with frozen feedforward (needs closed loop, P5); not a gate", "cases": {}}
    names = robot.names
    for tag, ek, ea in (("servo_only", 0.0, 0.0), ("servo+linkage_nominal", a.extra_deg[0], a.extra_deg[1]),
                        ("servo+linkage_worst", a.extra_deg[2] if len(a.extra_deg) > 2 else 2 * a.extra_deg[0],
                         a.extra_deg[3] if len(a.extra_deg) > 3 else 2 * a.extra_deg[1])):
        bl = np.array([servo + (math.radians(ek) if n.startswith("knee") else math.radians(ea) if n.startswith("ankle_pitch") else 0.0) for n in names])
        cfg = PlayConfig(mode="servo", backlash_rad=bl)
        try:
            off, _ = learn_offsets(robot, ref, cfg, iters=3)
            lg = play(robot, ref, replace(cfg, cmd_offset=off))
        except ValueError as e:      # the replay fell during feed-forward learning (log lengths differ): report it, do not hide it
            out["cases"][tag] = {"backlash_deg": {"knee": round(math.degrees(servo) + ek, 3), "ankle_pitch": round(math.degrees(servo) + ea, 3)},
                                 "fell": True, "note": f"replay diverged / fell while learning the feed-forward offsets ({e})"}
            print(tag, out["cases"][tag], flush=True)
            continue
        sl = lg.sl()
        err = np.degrees(np.abs(lg.q - lg.q_ref)[sl])
        per = {n: round(float(np.sqrt((err[:, i] ** 2).mean())), 2) for i, n in enumerate(names) if n.startswith(("knee", "ankle_pitch", "hip_pitch"))}
        out["cases"][tag] = {"backlash_deg": {"knee": round(math.degrees(servo) + ek, 3), "ankle_pitch": round(math.degrees(servo) + ea, 3), "others": a.servo_deg},
                             "rms_err_deg": round(float(np.sqrt((err ** 2).mean())), 3), "max_err_deg": round(float(err.max()), 3),
                             "rms_err_deg_by_joint": per, "fell": bool(lg.fell), "tether_mean_pct_bw": round(100 * lg.extras["assist_mean_bw"], 3)}
        print(tag, out["cases"][tag], flush=True)
    (RES / f"backlash_{c['id']}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("calibrated")
    p.add_argument("concepts", nargs="+")
    p.add_argument("--heights", nargs="+", type=float, default=[0.55, 0.60])
    p.add_argument("--no-bounds", action="store_true")
    p = sub.add_parser("backlash")
    p.add_argument("concept")
    p.add_argument("--extra-deg", nargs="+", type=float, required=True, help="linkage play added at the knee, ankle (nominal) [knee, ankle worst]")
    p.add_argument("--servo-deg", type=float, default=0.5)
    a = ap.parse_args(argv)
    RES.mkdir(parents=True, exist_ok=True)
    return {"calibrated": cmd_calibrated, "backlash": cmd_backlash}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
