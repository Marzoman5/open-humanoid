"""G-strength driver: build the model, the load cases and the load path, run the analytic checks, aggregate, report.

    result = run(model, cfg)            ->  {'rows': [...], 'parts': {...}, 'scenarios': [...], 'context': {...}, 'ok': bool}
"""
from __future__ import annotations

import time

import numpy as np

from . import loadcases, loadpath
from .analytic import PartAnalyzer, Row, sf_of
from .fasteners import bearing_seat_check, clamp_checks, connection_checks, horn_checks
from .joints import build_connection
from .loadpath import Topology
from .model import Model
from .policy import policy


def run(model: Model, cfg: dict, only_cases: list[str] | None = None, only_parts: list[str] | None = None, verbose: bool = False,
        analyzers: dict | None = None) -> dict:
    t0 = time.time()
    excl = set(cfg.get("exclude_parts", []))
    topo = Topology(model, list(excl))
    scs, ctx = loadcases.build(model, cfg, only_cases)
    mo = loadcases.actuator_masses(model, cfg)
    printed = [p for p in model.printed_parts() if p.id not in excl and (not only_parts or p.id in only_parts)]
    ana = analyzers if analyzers is not None else {}
    for p in printed:
        ana.setdefault(p.id, PartAnalyzer(p))
    stall = loadcases.joint_stall(model, cfg)
    conns: dict = {}
    rows: list[Row] = []
    scen_info = []
    for sc in scs:
        loads, diag = loadpath.solve(model, topo, sc, mo)
        scen_info.append({"name": sc.name, "class": sc.cls, "desc": sc.desc, "kind": sc.kind, "prov": sc.prov, "info": {k: v for k, v in sc.info.items() if not isinstance(v, np.ndarray)},
                          "joint_tau_nm": {k: round(v, 3) for k, v in diag["joint_tau_nm"].items()},
                          "equilibrium_residual_n": max(diag["equilibrium_residual"].values()) if diag["equilibrium_residual"] else 0.0})
        for p in printed:
            pl = loads[p.id]
            rows += ana[p.id].evaluate(pl, sc.name, sc.cls)
            # horn / seat / connections
            for jn, j in model.joints.items():
                if topo.root.get(j.child_link) == p.id:
                    rows += horn_checks(model, topo, j, pl, p, sc.name, sc.cls)
                if topo.idler.get(j.child_link) == p.id:
                    rows += bearing_seat_check(model, j, p, pl, sc.name, sc.cls)
            ed = pl.reaction_to_parent
            if ed is not None and ed.wrench_F is not None:
                key = (ed.child, ed.parent)
                if key not in conns:
                    sites = topo.edges.get(tuple(sorted(key)), [])
                    conns[key] = build_connection(model, ed.child, ed.parent, sites)
                con = conns[key]
                if con is not None and con.bolts:
                    rows += connection_checks(model, topo, con, pl, sc.name, sc.cls, model.parts)
        if verbose:
            print(f"  {sc.name}: {time.time() - t0:.0f}s", flush=True)
    # per joint torque-path checks at the stall torque of each joint (SF class stall)
    for jn, j in model.joints.items():
        root = topo.root.get(j.child_link)
        if root and root in ana and not (only_parts and root not in only_parts):
            part = model.parts[root]
            pl = loadpath.PartLoads(root, j.child_link, [loadpath.Load(j.horn_seat - model.fk({})[j.child_link][1] - model.if_offset, np.zeros(3), j.servo_z * 0.0, "horn reaction (stall)")],
                                    g_link=np.zeros(3))
            rows += horn_checks(model, topo, j, pl, part, f"torque_stall_{jn}", "stall", tau_cap_nmm=stall[jn] * 1000.0)
    for p in printed:
        rows += clamp_checks(model, topo, p)
    return aggregate(rows, scen_info, ctx, topo, time.time() - t0, [p.id for p in printed])


def aggregate(rows: list[Row], scen_info: list[dict], ctx: dict, topo, wall: float, part_ids: list[str]) -> dict:
    parts: dict[str, dict] = {}
    for pid in part_ids:
        pr = [r for r in rows if r.part == pid]
        gated = [r for r in pr if r.gate]
        info = [r for r in pr if not r.gate]
        w = min(gated, key=lambda r: r.margin) if gated else None
        wi = min(info, key=lambda r: r.margin) if info else None
        parts[pid] = {
            "worst": w.to_dict() if w else None,
            "worst_unprotected": wi.to_dict() if wi else None,
            "ok": bool(w is None or w.margin >= 1.0),
            "by_check": {c: min((r for r in gated if r.check == c), key=lambda r: r.margin).to_dict() for c in sorted({r.check for r in gated})},
        }
    ok = all(v["ok"] for v in parts.values())
    return {"ok": ok, "parts": parts, "scenarios": scen_info, "context": ctx, "n_rows": len(rows), "wall_s": round(wall, 1),
            "rows": [r.to_dict() for r in rows if r.margin < 3.0 or r.check in ("section", "fatigue")][:20000]}
