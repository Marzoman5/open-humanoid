"""Adam baseline v2 (T-20261019-4ab5): LOOK of the v2 candidates, with the leg hard points taken from REAL CAD for L5c.

The packaging study (T-20261019-c1aa) drew the relocated knee / ankle as 32 x 28 x 32 mm "slim joint" keep-outs (an estimate). Here the
L5c leg is the CAD of variants/adam/cad/linkages/l5c.py: its true cross-section at every 2 mm of height (mesh / plane intersection of every
part, pins and nuts included) is boxed per functional band (knee servo stack, thigh rod, knee joint, shank rod, calf servo stack, ankle joint: the max section extent over each band) in segment leg_core_l, replacing the layout's knee / ankle boxes.
Everything else (pelvis, hip, heel, arms, chest) is the packaging layout.py with the same levers. Shells: packaging/capsule.py (B4 rules,
parametric), display cant by the R2a visible-gap rule. Metrics: openhumanoid.design.metrics (the `oh design metrics` code).

Candidates
  V0       R1 hardware, B4 rules (= packaging study V0)
  V2a      R1 + longer arms (L9a)                                   <- v2 without L5c
  V2b-est  R1 + L5c (packaging-study slim-joint ESTIMATE) + L9a
  V2b-cad  R1 + L5c (CAD-measured leg) + L9a                         <- v2 with L5c
Each with the plain B4 rules and with the round-3 critic refinements (styling only; packaging/rounds.py r3).

Run:  .venv/Scripts/python variants/adam/design/v2/look.py [--only V2a V2b-cad] [--refine r3|none|both] [--render]
Out:  variants/adam/design/v2/look/<key>/{profiles.yaml, design_metrics.json}, results/look.{json,md}; renders docs/design-method/R2a-v2/<key>/
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PK = HERE.parent / "packaging"
sys.path.insert(0, str(PK))
sys.path.insert(0, str(REPO / "variants/adam/cad/linkages"))
sys.path.insert(0, str(REPO))

import capsule as C  # noqa: E402
import layout as LY  # noqa: E402
import rounds as RD  # noqa: E402
import study as ST  # noqa: E402

OUT = HERE / "look"
RES = HERE / "results"
B = LY.Levers()
CANDS = {"V0": (B, False, "R1 hardware (B4 rules)"),
         "V2a": (replace(B, upper=0.20, fore=0.23), False, "v2 without L5c: R1 + longer arms (L9a)"),
         "V2b-est": (replace(B, knee_up=True, ankle_up=True, upper=0.20, fore=0.23), False, "R1 + L5c (packaging slim-joint estimate) + L9a"),
         "V2b-cad": (replace(B, knee_up=True, ankle_up=True, upper=0.20, fore=0.23), True, "v2 with L5c: R1 + L5c (CAD-measured leg) + L9a")}
_ORIG_LAYOUT = LY.layout
_CAD = {"on": False, "slabs": None}
REPLACED = ("knee_servo_l", "knee_joint_l", "ankle_pitch_servo_l", "ankle_joint_l")


def cad_slabs() -> list[dict]:
    """True sections of the L5c CAD leg (left leg, y relative to the leg plane) -> hard-point slabs (layout.py format, y + HIP_Y). The heel
    (ankle-roll housing) and the hip-pitch housing stay as their layout boxes, so the foot link contributes only the ankle-crank bearings."""
    import numpy as np
    import l5c
    from openhumanoid.cad.core import mesh_of
    asm = l5c.build()
    edges = []
    for p in asm.placed({}):
        if p.link == "hip" or p.part.keepout or (p.link == "foot" and not p.part.id.startswith("bearing_ankle_pin_out")):
            continue
        m = mesh_of(p.shape, tol=0.2, ang=0.3)
        edges.append(np.asarray(m.vertices)[np.asarray(m.edges_unique)])
    E = np.concatenate(edges)
    za, zb = E[:, 0, 2], E[:, 1, 2]

    def sec(z):
        sel = (np.minimum(za, zb) <= z) & (np.maximum(za, zb) >= z) & (np.abs(zb - za) > 1e-9)
        if not sel.any():
            return None
        e = E[sel]
        t = (z - e[:, 0, 2]) / (e[:, 1, 2] - e[:, 0, 2])
        pts = e[:, 0, :] + t[:, None] * (e[:, 1, :] - e[:, 0, :])
        return float(pts[:, 0].min()), float(pts[:, 0].max()), float(pts[:, 1].min()), float(pts[:, 1].max())
    z_top = LY.layout(B, 21.0)["L"]["h"] - get_hs() - 1.0          # below the hip-pitch housing box
    P = l5c.P
    hk = 14.9                                                       # housing half-height across the servo width (servo_housing outer_y)
    zks, zcs, zk, zan = P["knee_servo_z"], P["calf_servo_z"], l5c.Z_KNEE, l5c.Z_ANK
    bands = [("knee_servo_l", zks - hk, min(zks + hk + 11.6, z_top)),        # knee servo stack + its input crank / pin bosses (to the pin boss top, under the hip fork web)
             ("knee_rod_l", zk + 12.0, zks - hk),                            # thigh beam + knee coupler
             ("knee_joint_l", zk - 21.5, zk + 12.0),                         # knee clevis, output crank, bridge
             ("shank_rod_l", zcs + hk, zk - 21.5),                           # drop block + calf crank top
             ("ankle_pitch_servo_l", zcs - hk, zcs + hk),                    # calf servo stack + ankle input crank
             ("ankle_joint_l", zan - 14.0, zcs - hk)]                         # ankle tongue, ankle coupler, output crank bearings
    out = []
    for bid, z0, z1 in bands:
        ss = [s for s in (sec(z) for z in np.linspace(z0 + 0.6, z1 - 0.6, max(3, int((z1 - z0) / 1.0)))) if s is not None]   # band edges kept off the neighbour boxes
        x0, x1 = float(min(s[0] for s in ss)), float(max(s[1] for s in ss))
        y0, y1 = float(min(s[2] for s in ss)), float(max(s[3] for s in ss))
        out.append(LY._box(bid, "leg_core_l", (x0, x1), (y0 + LY.HIP_Y, y1 + LY.HIP_Y), (float(z0), float(z1))))
    return out


def get_hs() -> float:
    S0 = LY.servo("sts3215-12v")
    return S0.AX + LY.HOUS


def _layout(lv, cant=21.0):
    lay = _ORIG_LAYOUT(lv, cant)
    if _CAD["on"] and lv.knee_up and lv.ankle_up:
        if _CAD["slabs"] is None:
            _CAD["slabs"] = cad_slabs()
        lay["hard_points"] = [b for b in lay["hard_points"] if b["id"] not in REPLACED] + _CAD["slabs"]
        lay["L"]["notes"] = list(lay["L"].get("notes", [])) + ["L5c leg hard points = CAD sections of variants/adam/cad/linkages/l5c.py"]
    return lay


LY.layout = _layout
C.LY.layout = _layout


def run(key: str, refine_tag: str, render: bool) -> dict:
    from openhumanoid.design import metrics, studio
    from openhumanoid.design.meshio import load_subject
    lv, cad, label = CANDS[key]
    _CAD["on"] = cad
    refine = dict(RD.ROUNDS.get(refine_tag) or {}) if refine_tag != "none" else {}
    if cad:
        refine["leg_cy_follow"] = True        # off-centre covers that hug the lateral L5c crank stack (capsule.py REFINE flag)
    gap = ST.baseline_gap()
    cant = 21.0 if key == "V0" else C.gap_rule_cant(lv, gap)
    while True:                                   # the refined shells must still keep the gap (rounds.py rule)
        prof = C.build(lv, cant, name=f"adam-v2-{key}-{refine_tag}", refine=refine)
        if C.min_gap(prof) >= gap or cant >= 30:
            break
        cant += 0.5
    fails = C.hp_fails(prof)
    L = prof.pop("_L")
    tag = f"{key}_{refine_tag}"
    d = OUT / tag
    d.mkdir(parents=True, exist_ok=True)
    pp = d / "profiles.yaml"
    pp.write_text(f"# Adam baseline v2 look candidate {key} ({label}), styling {refine_tag} (T-20261019-4ab5, PROVISIONAL)\n"
                  f"# levers: {lv.tag()}; legs: {'CAD sections of variants/adam/cad/linkages/l5c.py' if cad else 'layout.py boxes'}\n"
                  "# Written by variants/adam/design/v2/look.py (packaging capsule.py + layout.py); re-run, do not edit.\n"
                  + yaml.safe_dump(prof, sort_keys=False, width=160), encoding="utf-8")
    subj = load_subject(pp, tag)
    refs = dict(studio.reference_mask(r, "front") for r in ST.REFS)
    rep = metrics.write_report(subj, d / "design_metrics.json", ref_masks=refs)
    crit = rep["evaluation"]["criteria"]
    row = {"key": key, "styling": refine_tag, "label": label, "levers": asdict(lv), "cad_legs": cad, "cant_deg": cant, "hp_fails": fails,
           "metrics": {k: (round(crit[k]["value"], 3) if isinstance(crit[k]["value"], (int, float)) else crit[k]["value"]) for k in crit},
           "verdicts": {k: crit[k]["verdict"] for k in crit}, "n_pass": rep["evaluation"]["n_pass"], "n_scored": rep["evaluation"]["n_scored"],
           "failed": rep["evaluation"]["failed"], "profiles": str(pp.relative_to(REPO))}
    m = row["metrics"]
    print(f"{tag}: cant {cant}  HP fails {len(fails)}  pass {row['n_pass']}/{row['n_scored']}  P3 {m.get('P3')}  P8a {m.get('P8a')}  P8b {m.get('P8b')}  "
          f"P10a {m.get('P10a')}  failed {row['failed']}", flush=True)
    if render and not fails:
        import render_pack as RP
        RP.OUT = REPO / "docs" / "design-method" / "R2a-v2"
        RP.render(pp, tag, f"design-{key}")
    return row


def to_md(rows) -> str:
    keys = ST.KEYS[:-1]
    L = ["<!-- written by variants/adam/design/v2/look.py (T-20261019-4ab5); re-run, do not edit -->", "# Adam v2 look metrics (PROVISIONAL)", "",
         "Same B4 rules (packaging/capsule.py), cant by the R2a visible-gap rule, `oh design metrics` code. ✗ = outside the band. "
         "V2b-cad legs = the CAD sections of the L5c leg; V2b-est = the packaging study's slim-joint estimate.", "",
         "| candidate | styling | cant ° | HP | " + " | ".join(keys) + " | pass |", "|" + "---|" * (len(keys) + 5)]
    for r in [ST.b4_row()] + rows:
        m, vv = r.get("metrics", {}), r.get("verdicts", {})
        cells = ["-" if m.get(k) is None else f"{m.get(k)}{' ✗' if vv.get(k) == 'FAIL' else ''}" for k in keys]
        L.append(f"| {r['key']} | {r.get('styling', 'hand (R2a)')} | {r.get('cant_deg', '')} | {'pass' if not r.get('hp_fails') else len(r['hp_fails'])} | "
                 + " | ".join(cells) + f" | {r.get('n_pass')}/{r.get('n_scored')} |")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--refine", default="both", choices=["none", "r3", "both"])
    ap.add_argument("--render", nargs="*", default=[], help="tags to render, e.g. V2a_r3 V2b-cad_r3")
    a = ap.parse_args(argv)
    RES.mkdir(parents=True, exist_ok=True)
    pj = RES / "look.json"
    prev = {f"{r['key']}_{r['styling']}": r for r in json.loads(pj.read_text(encoding="utf-8"))["rows"]} if pj.exists() else {}
    for key in CANDS:
        if a.only and key not in a.only:
            continue
        for rt in (["none", "r3"] if a.refine == "both" else [a.refine]):
            prev[f"{key}_{rt}"] = run(key, rt, f"{key}_{rt}" in a.render)
    rows = list(prev.values())
    pj.write_text(json.dumps({"rows": rows}, indent=1, default=str), encoding="utf-8")
    (RES / "look.md").write_text(to_md(rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
