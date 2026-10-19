"""Provenance classes for every constant the report relies on (commander item 4).

Classes: measured | sourced_estimate | extrapolated | assumption (| gate for pass/fail thresholds).
Sources are the thresholds file, the servo model file, and the catalog.
"""
from __future__ import annotations

from .. import catalog
from ..actuators.servo import _models_yaml
from . import config

KIND_TO_CLASS = {"measured": "measured", "independent": "measured (single unit, third party)", "datasheet": "sourced_estimate",
                 "sourced_estimate": "sourced_estimate", "derived": "extrapolated", "extrapolated": "extrapolated", "assumption": "assumption",
                 "assumed": "assumption", "gate": "gate"}


def _walk(prefix: str, node, out: list) -> None:
    if isinstance(node, dict):
        if "class" in node and ("source" in node or "value" in node):
            out.append({"constant": prefix, "value": node.get("value", {k: v for k, v in node.items() if k not in ("class", "source", "note")}),
                        "class": KIND_TO_CLASS.get(node["class"], node["class"]), "source": node.get("source", node.get("note", ""))})
            return
        for k, v in node.items():
            _walk(f"{prefix}.{k}" if prefix else k, v, out)


def thresholds_table() -> list[dict]:
    out: list[dict] = []
    _walk("", config.thresholds(), out)
    return out


def actuator_table(actuator_ids: list[str]) -> list[dict]:
    y = _models_yaml()
    out = []
    bam = y["BAM_SOURCE"]
    out.append({"constant": "BAM STS3215 7.4 V parameters (kt, R, armature, friction, delay)", "value": f"model {bam['default_model']}",
                "class": "measured", "source": f"{bam['repo']} @ {bam['commit'][:7]}, {bam['license']}; identified on a pendulum bench at a 7.4 V parameter-folder voltage, one servo class"})
    out.append({"constant": "firmware kp / error_gain / pwm_max", "value": bam["firmware"], "class": "measured", "source": bam["firmware"]["source"]})
    for k, v in y["protection"].items():
        out.append({"constant": f"protection.{k}", "value": v["v"], "class": KIND_TO_CLASS.get(v["kind"], v["kind"]), "source": v["source"]})
    for aid in actuator_ids:
        m = y["models"].get(aid)
        if not m:
            out.append({"constant": f"{aid} (generic datasheet model)", "value": "stall, no-load speed from the catalog", "class": "assumption",
                        "source": "no identification; ideal-DC current assumption; wide uncertainty"})
            continue
        for key in ("stall_nm", "stall_current_a", "rated_continuous_nm", "noload_rad_s", "mass_kg"):
            if key in m:
                out.append({"constant": f"{aid}.{key}", "value": m[key]["v"], "class": KIND_TO_CLASS.get(m[key]["kind"], m[key]["kind"]),
                            "source": m[key]["source"]})
        out.append({"constant": f"{aid}.thermal (Rth, tau)", "value": [m["thermal"]["rth_k_per_w"], m["thermal"]["tau_s"]],
                    "class": KIND_TO_CLASS.get(m["thermal"]["kind"], m["thermal"]["kind"]), "source": m["thermal"]["source"]})
        out.append({"constant": f"{aid}.dynamics (armature, friction, delay)", "value": f"from {m.get('bam_file') or m.get('dynamics_from')}",
                    "class": "measured" if m.get("bam_file") else "extrapolated",
                    "source": "BAM 7.4 V fit" + ("" if m.get("bam_file") else " borrowed for a different servo (same 1:345 gearbox assumed)")})
        out.append({"constant": f"{aid}.model quality", "value": m["quality"], "class": "extrapolated" if m["quality"] != "measured_7v4" else "measured",
                    "source": m["label"]})
    return out


def part_table(robot) -> list[dict]:
    rows = []
    seen = set()
    for it in robot.concept.get("parts", {}).get("onboard", []) + robot.concept.get("parts", {}).get("offboard", []):
        if it["part"] in seen:
            continue
        seen.add(it["part"])
        p = catalog.get(it["part"])
        rows.append({"constant": f"catalog {it['part']} (price, mass, dims)", "value": {"mass_kg": p.get("mass_kg"), "dimensions_mm": p.get("dimensions_mm"),
                     "price_usd": p["price_usd"]["typical"]}, "class": "sourced_estimate" if p["verified"] or "http" in p["source"] else "assumption",
                     "source": p["source"][:300]})
    return rows


def collect(robot) -> list[dict]:
    return thresholds_table() + actuator_table(sorted(set(robot.acts.values()))) + part_table(robot)
