"""Write the packaging-for-look concept YAMLs (T-20261019-c1aa) into variants/adam/concepts/PK-*.yaml, each = the R1 recommended
engine concept (R1x-ckh23-knee110: 23 DOF, STS3250 hip roll + knees, STS3215 12 V elsewhere, knee 0-110) plus ONE lever, and the
combined package. Keys starting with x_ are read only by packaging/engine.py (rail servos, pack host); run them through it:

  .venv/Scripts/python variants/adam/design/packaging/engine.py variants/adam/concepts/PK-<id>.yaml --pushmax

Plain `python -m openhumanoid.concept evaluate` on a PK file with rail servos fails on the unknown part id (safe failure: the
servos are not in catalog/ until a catalog task adds them).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CONC = HERE.parents[1] / "concepts"
BASE = yaml.safe_load((CONC / "R1x-ckh23-knee110.yaml").read_text(encoding="utf-8"))
RAIL = {"sts3045m": 6.0, "scs0009": 6.0}
LINK = {"ratio": 1.0, "efficiency": 0.95, "note": "1:1 parallelogram (crank, rod, two M3 ball links): speed kept; 5% loss is an ASSUMPTION"}


def joints_without(*names):
    return [j for j in BASE["joints"] if (j if isinstance(j, str) else j["name"]) not in names]


def make(id_, desc, **kw):
    c = copy.deepcopy(BASE)
    c["id"], c["description"] = id_, desc
    for k, v in kw.items():
        if k == "drop":
            c["joints"] = [j for j in c["joints"] if (j if isinstance(j, str) else j["name"]) not in v]
        elif k == "actuators":
            c["actuators"] = {**c["actuators"], **v}
        else:
            c[k] = v
    return c


SMALL_ARM = {"shoulder_pitch": "sts3045m", "shoulder_roll": "sts3045m", "elbow": "sts3045m", "gripper": "scs0009"}
SMALL_NECK = {"neck_yaw": "scs0009", "neck_pitch": "scs0009"}
CONCEPTS = [
    make("PK-L1d-small-arm", "Lever 1: whole arm on small servos on a 6 V rail (shoulder pitch/roll + elbow STS3045M, gripper SCS0009).",
         actuators=SMALL_ARM, x_rail_servos=RAIL),
    make("PK-L2-nowaist", "Lever 2: no waist-yaw servo (R7 by neck yaw + turning in place).", drop=["waist_yaw"]),
    make("PK-L3b-lumbar", "Lever 3: no waist yaw, pack moved low (lumbar); engine: pack mass in the pelvis segment (optimistic COM end).",
         drop=["waist_yaw"], x_pack_host="pelvis"),
    make("PK-L5-linkages", "Lever 5: knee servo in the thigh + ankle-pitch servo in the calf, each through a 1:1 parallelogram (5% loss).",
         transmissions={"knee": dict(LINK, host="thigh"), "ankle_pitch": dict(LINK, host="shank")}),
    make("PK-L6-small-neck", "Lever 6: neck yaw + pitch on SCS0009 micro servos (6 V rail).", actuators=SMALL_NECK, x_rail_servos=RAIL),
    make("PK-L7-5dof", "Lever 7: 5-DOF legs (no ankle roll), R1 actuators otherwise.", drop=["ankle_roll"]),
]


def combined(id_, desc, *, five_dof=False, arm=True, neck=True, links=True, waist=False, pack_low=True):
    kw = {}
    act = {}
    if arm:
        act.update(SMALL_ARM)
    if neck:
        act.update(SMALL_NECK)
    if act:
        kw["actuators"] = act
        kw["x_rail_servos"] = RAIL
    drop = ([] if waist else ["waist_yaw"]) + (["ankle_roll"] if five_dof else [])
    if drop:
        kw["drop"] = drop
    if links:
        kw["transmissions"] = {"knee": dict(LINK, host="thigh"), "ankle_pitch": dict(LINK, host="shank")}
    if pack_low:
        kw["x_pack_host"] = "pelvis"
    return make(id_, desc, **kw)


HEADER = ("# Packaging-for-look study (T-20261019-c1aa), PROVISIONAL (bench pending). DATA for variants/adam/design/packaging/engine.py,\n"
          "# which wraps r1_calibrated.py (strict / half / ODM-calibrated gates, R10). Written by packaging/concepts.py; re-run, do not edit.\n"
          "# Base: R1x-ckh23-knee110 (the R1 recommended hardware). Pack in the engine stays the R1 engine pack (Tattu 1300 value; the\n"
          "# build pack is the GNB 1850, runtime scaled as in R1). x_rail_servos = servos on a 6 V Pololu D36V50F6 rail (in-process model).\n")


def write_all(extra: list[dict] | None = None) -> list[Path]:
    out = []
    for c in CONCEPTS + (extra or []):
        p = CONC / f"{c['id']}.yaml"
        p.write_text(HEADER + yaml.safe_dump(c, sort_keys=False, width=140), encoding="utf-8")
        out.append(p)
    return out


if __name__ == "__main__":
    for p in write_all([combined("PK-C1-package", "Combined package C1: small arm + neck servos (6 V rail), no waist yaw, pack low, "
                                 "knee + ankle-pitch servos relocated through 1:1 parallelograms, 6-DOF legs."),
                        combined("PK-C1-5dof", "Combined package C1 with 5-DOF legs (no ankle roll).", five_dof=True),
                        dict(combined("PK-C1-arm2x", "C1 SENSITIVITY: rail-servo armature x2 (STS3045M 0.004 kg m^2 = the BAM "
                                      "Waveshare ST3025 value)."), x_rail_armature_scale=2.0)]):
        print(p.relative_to(HERE.parents[3]))
    sys.exit(0)
