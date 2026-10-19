"""Checks for the L5c parallelogram leg (T-20261019-4ab5): geometry gate, COUPLED range-of-motion sweep, assembly access, front-view
widths against R1's 52 mm forks, and clay renders. Uses the CAD foundation's own checks (geometry_gate, rom, access, render).

The ROM sweep of openhumanoid/cad/rom.py steps ONE joint at a time; a parallelogram is a closed chain, so the crank and the coupler
links (modelled as tree links with slave joints, see l5c.py) must move together with the joint. `coupled()` builds that pose and the
foundation's own pair test (`rom._collisions`) is run on it, with the same clash threshold, moving gap and designed fits.

Run:  .venv/Scripts/python variants/adam/cad/linkages/check.py [--quick] [--no-gate] [--no-access] [--render]
Out:  variants/adam/cad/linkages/results/{rom.json, gate.json, access.json, widths.json, summary.md}, renders in docs/design-method/R2a-v2/cad/
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import l5c  # noqa: E402
from openhumanoid.cad import access, dfm, geometry_gate, rom  # noqa: E402
from openhumanoid.cad.core import bbox_tuple  # noqa: E402

OUT = HERE / "results"
SLAVES = {"knee_l": ("knee_drv_l", "knee_cpl_l"), "ankle_pitch_l": ("ankle_drv_l", "ankle_cpl_l")}


def coupled(q_deg: dict) -> dict:
    """Joint angles (rad) with the parallelogram slaves set: drv = q, cpl = -q."""
    q = {}
    for j, a in q_deg.items():
        q[j] = math.radians(a)
        if j in SLAVES:
            q[SLAVES[j][0]] = math.radians(a)
            q[SLAVES[j][1]] = -math.radians(a)
    return q


def hits(asm, q_deg, gap_check=True):
    gap = float(dfm.load_dfm()["moving_gap_min_mm"]["v"])
    return rom._collisions(asm, coupled(q_deg), None, geometry_gate.CLASH_MM3, gap_check, gap)


def sweep(asm, joint, lo, hi, base=None, step=5.0, refine=0.25, gap_check=True) -> dict:
    """Coupled sweep of one joint from 0 to each end; reports the last free angle and the first offending pairs."""
    base = dict(base or {})
    out = {"joint": joint, "range_deg": [lo, hi], "limit_pos": None, "limit_neg": None, "events": [], "within_spec": True}
    h0 = hits(asm, {**base, joint: 0.0}, gap_check)
    if h0:
        out["events"].append({"angle_deg": 0.0, "pairs": h0})
        out["within_spec"] = False
        return out
    for d, end, key in ((1, hi, "limit_pos"), (-1, lo, "limit_neg")):
        if (d > 0 and end <= 0) or (d < 0 and end >= 0):
            continue
        free = 0.0
        n = int(math.ceil(abs(end) / step))
        for s in range(1, n + 1):
            a = d * min(s * step, abs(end))
            h = hits(asm, {**base, joint: a}, gap_check)
            if h:
                f, c = free, a
                while abs(c - f) > refine:
                    m = (f + c) / 2
                    if hits(asm, {**base, joint: m}, gap_check):
                        c = m
                    else:
                        f = m
                out[key] = round(f, 2)
                out["events"].append({"angle_deg": round(c, 2), "pairs": hits(asm, {**base, joint: c}, gap_check)})
                if abs(f) < abs(end) - 1e-6:
                    out["within_spec"] = False
                break
            free = a
    return out


def sections(asm, skip_links=("hip", "pelvis"), z_lo=4, z_hi=262, step=2) -> dict:
    """Front-view y extent and side-view x extent of the TRUE cross-section at each z (mesh/plane intersection of every part, hardware
    solids included, keep-outs excluded), zero pose. z -> (y_min, y_max, width, x_min, x_max, depth)."""
    import numpy as np
    from openhumanoid.cad.core import mesh_of
    meshes = []
    for p in asm.placed({}):
        if p.link in skip_links or p.part.keepout:
            continue
        m = mesh_of(p.shape, tol=0.2, ang=0.3)
        meshes.append(np.asarray(m.vertices)[np.asarray(m.edges_unique)])        # (E, 2, 3)
    E = np.concatenate(meshes)
    za, zb = E[:, 0, 2], E[:, 1, 2]
    out = {}
    for z in range(z_lo, z_hi, step):
        sel = (np.minimum(za, zb) <= z) & (np.maximum(za, zb) >= z) & (np.abs(zb - za) > 1e-9)
        if not sel.any():
            continue
        e = E[sel]
        t = (z - e[:, 0, 2]) / (e[:, 1, 2] - e[:, 0, 2])
        pts = e[:, 0, :] + t[:, None] * (e[:, 1, :] - e[:, 0, :])
        out[z] = tuple(round(float(v), 2) for v in (pts[:, 1].min(), pts[:, 1].max(), np.ptp(pts[:, 1]), pts[:, 0].min(), pts[:, 0].max(), np.ptp(pts[:, 0])))
    return out


def band_max(sec, z0, z1):
    sel = [v for z, v in sec.items() if z0 <= z <= z1]
    if not sel:
        return None
    return {"width_mm": max(v[2] for v in sel), "y": [min(v[0] for v in sel), max(v[1] for v in sel)], "depth_mm": max(v[5] for v in sel)}


def widths(asm) -> dict:
    sec = sections(asm)
    zk, za = l5c.Z_KNEE, l5c.Z_ANK
    zks, zcs = l5c.P["knee_servo_z"], l5c.P["calf_servo_z"]
    return {"sections": {str(k): v for k, v in sec.items()},
            "knee_joint (z knee +-10)": band_max(sec, zk - 10, zk + 10),
            "ankle_joint (z ankle +-10)": band_max(sec, za - 10, za + 10),
            "knee_servo_level (thigh)": band_max(sec, zks - 15, zks + 15),
            "calf_servo_level": band_max(sec, zcs - 15, zcs + 15),
            "thigh_mid (between knee servo and knee)": band_max(sec, zk + 15, zks - 16),
            "d_knee_mm": asm.meta["d_knee"], "d_ankle_mm": asm.meta["d_ankle"]}


def r1_widths() -> dict:
    """The same sections on the R1 CAD-foundation leg (variants/adam/cad/leg_v2.py, 22-DOF layout_v2 stand-in, 0.60 m-class landmarks)."""
    from openhumanoid.cad import cli
    asm, ctx = cli._load_builder(str(REPO / "variants/adam/cad/leg_v2.py"), "adam")
    ifs = ctx.interfaces
    zk = ifs.axis_origin("knee_l")[2]
    za = ifs.axis_origin("ankle_pitch_l")[2]
    zh = ifs.axis_origin("hip_pitch_l")[2]
    off = zh            # leg_v2 world frame: the hip-pitch axis is at z = 0 (interfaces give heights above the ground)
    sec_w = sections(asm, skip_links=("pelvis", "hip_yaw_l_link", "hip_roll_l_link"), z_lo=int(4 - off), z_hi=int(-20))
    sec = {round(z + off): v for z, v in sec_w.items()}
    return {"sections": {str(k): v for k, v in sec.items()}, "z_hip": zh, "z_knee": zk, "z_ankle": za,
            "note": "R1 CAD-foundation leg (layout_v2 stand-in at its own landmarks; forks at the joints); widths are absolute mm",
            "knee_joint (z knee +-10)": band_max(sec, zk - 10, zk + 10), "ankle_joint (z ankle +-10)": band_max(sec, za - 10, za + 10),
            "thigh_mid": band_max(sec, zk + 30, zh - 40), "shank_mid": band_max(sec, za + 30, zk - 30)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="10 deg steps, 1 deg refine")
    ap.add_argument("--no-gate", action="store_true")
    ap.add_argument("--no-access", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="subset: rom widths gate access render")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    asm = l5c.build()
    print(f"built {len(asm.parts())} parts in {time.time() - t0:.1f} s; notes: {asm.notes}", flush=True)
    only = set(a.only or ["widths", "rom", "gate", "access"] + (["render"] if a.render else []))
    if a.no_gate:
        only.discard("gate")
    if a.no_access:
        only.discard("access")
    summary = {}
    if "widths" in only:
        w = widths(asm)
        try:
            w["R1_leg_v2"] = r1_widths()
        except Exception as e:      # noqa: BLE001 - reported, not hidden
            w["R1_leg_v2"] = {"error": repr(e)}
        (OUT / "widths.json").write_text(json.dumps(w, indent=1), encoding="utf-8")
        summary["widths"] = {k: v for k, v in w.items() if k != "sections"}
        summary["widths"]["R1_leg_v2"] = {k: v for k, v in w["R1_leg_v2"].items() if k != "sections"}
        print(json.dumps(summary["widths"], indent=1), flush=True)
    if "rom" in only:
        step, ref = (10.0, 1.0) if a.quick else (5.0, 0.25)
        R = l5c.RANGES
        res = {"zero_pose": hits(asm, {})}
        res["hip_pitch_l"] = sweep(asm, "hip_pitch_l", *R["hip_pitch"], step=step, refine=ref)
        res["knee_l"] = sweep(asm, "knee_l", *R["knee"], step=step, refine=ref)
        res["ankle_pitch_l"] = sweep(asm, "ankle_pitch_l", *R["ankle_pitch"], step=step, refine=ref)
        # ankle through its range at a deep knee, and the coupled poses (fractions of range, foot levelled: rom.DEFAULT_POSES)
        res["ankle_at_knee_90"] = sweep(asm, "ankle_pitch_l", *R["ankle_pitch"], base={"knee_l": 90.0}, step=step, refine=ref)
        poses = {}
        for nm in ("squat", "deep_squat", "step_forward", "pickup"):
            qd = {k: math.degrees(v) for k, v in rom.pose_angles(asm, nm).items() if k in ("hip_pitch_l", "knee_l", "ankle_pitch_l")}
            h = hits(asm, qd)
            poses[nm] = {"q_deg": {k: round(v, 1) for k, v in qd.items()}, "pairs": h, "ok": not [c for c in h if c["kind"] == "clash"]}
        res["poses"] = poses
        res["ok"] = all(res[j]["within_spec"] for j in ("hip_pitch_l", "knee_l", "ankle_pitch_l", "ankle_at_knee_90")) and all(p["ok"] for p in poses.values()) and not res["zero_pose"]
        (OUT / "rom.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        summary["rom"] = {k: ({kk: vv for kk, vv in v.items() if kk != "events"} | {"first": [e["pairs"][:3] for e in v.get("events", [])][:2]}
                              if isinstance(v, dict) and "joint" in v else v) for k, v in res.items() if k != "poses"}
        summary["rom"]["poses"] = {k: {"ok": v["ok"], "q": v["q_deg"], "pairs": v["pairs"][:3]} for k, v in poses.items()}
        print(json.dumps(summary["rom"], indent=1, default=str), flush=True)
    if "gate" in only:
        g = geometry_gate.run_gate(asm, fast=False)
        (OUT / "gate.json").write_text(json.dumps(g, indent=1, default=str), encoding="utf-8")
        txt = geometry_gate.summarize(g)
        (OUT / "gate.txt").write_text(txt, encoding="utf-8")
        summary["gate_ok"] = g.get("ok")
        print(txt[:3000], flush=True)
    if "access" in only:
        pl = access.analyse(asm)
        (OUT / "access.json").write_text(json.dumps(pl, indent=1, default=str), encoding="utf-8")
        txt = access.summarize(pl)
        (OUT / "access.txt").write_text(txt, encoding="utf-8")
        summary["access"] = {k: pl.get(k) for k in ("ok", "unreachable_screws", "stuck_parts", "cyclic_parts")}
        print(txt[:3000], flush=True)
    if "render" in only:
        from openhumanoid.cad import render
        out = REPO / "docs" / "design-method" / "R2a-v2" / "cad"
        for tag, qd in (("zero", {}), ("knee90", {"hip_pitch_l": -45.0, "knee_l": 90.0, "ankle_pitch_l": -45.0}),
                        ("knee110_ankle25", {"knee_l": 110.0, "ankle_pitch_l": 25.0})):
            asm.stand_pose = coupled(qd)
            render.render_views(asm, out / tag, pose=None)
        asm.stand_pose = {}
    summary["seconds"] = round(time.time() - t0, 1)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
