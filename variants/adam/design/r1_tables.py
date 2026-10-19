"""R5 table-height check for the R1 concepts (T-20261019-36f9): the frozen 150 g pickup at the provisional coffee-table heights through the
concept engine's own planner and ideal-demand playback, with a DIAGNOSIS run per table where the table top's contact is switched off
(challenge-3 row 5: root-cause the 0.40 m spike).

Run:  .venv/Scripts/python variants/adam/design/r1_tables.py <concept.yaml> [--tables 0.30 0.35 0.40 0.45 0.50] [--height 0.60]
Out:  variants/adam/design/r1_results/tables_<candidate>[_<height>].json and a printed table.

Per table: planner validity; strict + calibrated worst margin over stand + pickup; the pickup's peak torque fraction and the joint; the same
with the table top's contype/conaffinity = 0 (the object still rests on it? no: with the table off the object falls, so the contact-off run
answers ONLY "is the spike a hand/arm-table collision", not whether the grasp works); and the largest hand/forearm-table contact force.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np

from openhumanoid.concept import envelopes as E
from openhumanoid.concept import evaluate as EV
from openhumanoid.concept.playback import PlayConfig
from openhumanoid.concept.robot import load_concept

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r1_calibrated import FACTORS  # noqa: E402

OUT = Path(__file__).resolve().parent / "r1_results"


def _table_off(model):
    gid = model.geom("table_top").id
    model.geom_contype[gid] = 0
    model.geom_conaffinity[gid] = 0


def _peak(robot, dem, vin):
    m = E.joint_metrics(robot, dem, np.full(len(robot.names), vin))
    i = int(np.argmax(m["peak_frac_stall"]))
    return float(m["peak_frac_stall"][i]), robot.names[i]


def _contact_force(robot, ref):
    """Largest normal force between the table top and any robot geom during the ideal playback (re-simulated with mujoco)."""
    from openhumanoid.concept import playback as PB
    lg = PB.play(robot, ref, PlayConfig(mode="ideal", log_contacts=True)) if "log_contacts" in PlayConfig.__dataclass_fields__ else None
    return None if lg is None else getattr(lg, "table_force_max", None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("concept")
    ap.add_argument("--tables", nargs="+", type=float, default=[0.30, 0.35, 0.40, 0.45, 0.50])
    ap.add_argument("--height", type=float, default=None)
    a = ap.parse_args(argv)
    c = load_concept(a.concept)
    if a.height:
        c = copy.deepcopy(c)
        c["height_m"] = a.height
    rows = []
    for t in a.tables:
        b = EV.run_bundle(c, EV.Mods(), table_height=t, thermal=False, motions=["stand", "pickup"])
        inv = {k: v[:160] for k, v in b.invalid.items() if k.startswith("pickup")}
        worst = min(((x["worst_margin"], x["joint"]) for x in b.rows.values()), default=(None, None))
        row = {"table_m": t, "pickup_valid": not inv, "invalid": inv, "strict_worst_margin": round(worst[0], 3) if worst[0] is not None else None,
               "worst_joint": worst[1]}
        if "pickup" in b.dem and b.dem["pickup"].valid:
            pk, pj = _peak(b.robot, b.dem["pickup"], b.vin)
            row.update(peak_frac_stall=round(pk, 3), peak_joint=pj, cal_peak_margin=round(0.70 * FACTORS["peak"] / max(pk, 1e-9), 3))
            d_off = E.ideal_demand(b.robot, b.refs["pickup"], PlayConfig(mode="ideal", model_hook=_table_off))
            if d_off.valid:
                pk2, pj2 = _peak(b.robot, d_off, b.vin)
                row.update(peak_frac_stall_table_contact_off=round(pk2, 3), peak_joint_table_contact_off=pj2)
            else:
                row["table_contact_off"] = f"invalid: {d_off.invalid_reason[:120]}"
            row["meta"] = {k: v for k, v in b.refs["pickup"].meta.items() if k in ("squat_deg", "table_height_m", "grasp_ik_m", "pregrasp_ik_m", "lift_ik_m", "jaw_axis_off_horizontal_deg")}
        rows.append(row)
        print(json.dumps(row), flush=True)
    OUT.mkdir(exist_ok=True)
    suffix = f"_{a.height:.2f}" if a.height else ""
    (OUT / f"tables_{c['id']}{suffix}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
