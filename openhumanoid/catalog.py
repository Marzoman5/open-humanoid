"""Parts catalog: one YAML per part under catalog/<category>/."""
from __future__ import annotations

import json
from functools import lru_cache

import yaml

from .paths import catalog_dir, schemas_dir

FEEDBACK_LEVEL = {"none": 0, "position": 1, "position_current": 2, "torque": 3}


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict]:
    parts: dict[str, dict] = {}
    for f in sorted(catalog_dir().rglob("*.yaml")):
        p = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not p or "id" not in p:
            continue
        if p["id"] in parts:
            raise ValueError(f"Duplicate catalog id {p['id']} ({f})")
        p["_file"] = str(f.relative_to(catalog_dir().parent)).replace("\\", "/")
        parts[p["id"]] = p
    return parts


def get(part_id: str) -> dict:
    cat = load_catalog()
    if part_id not in cat:
        raise KeyError(f"Part '{part_id}' not in catalog. Add catalog/<category>/{part_id}.yaml")
    return cat[part_id]


def actuators() -> list[dict]:
    return [p for p in load_catalog().values() if p["category"] == "actuator"]


def validate_catalog() -> list[str]:
    import jsonschema

    schema = json.loads((schemas_dir() / "catalog-part.schema.json").read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema)
    errs = []
    for pid, p in load_catalog().items():
        clean = {k: val for k, val in p.items() if not k.startswith("_")}
        errs += [f"{p['_file']}: {'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in v.iter_errors(clean)]
        if p["category"] == "actuator" and "actuator" not in p:
            errs.append(f"{p['_file']}: actuator parts need an 'actuator' block")
    return errs


def price(p: dict, which: str = "typical") -> float:
    pr = p["price_usd"]
    return float(pr.get(which, pr["typical"]))
