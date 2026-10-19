"""Provenance checks (ADR 0011 §3, ADR 0013): every number says where it came from.

* Catalog: every part carries `source` and `verified`. An `estimate:` source must stay `verified: false`;
  a verified part must point at something checkable (a URL or a vendor URL).
* Spec: every numeric constant under `analysis:` and `mass_model:` (the tuned ones) needs an entry in the
  spec's `provenance:` map, keyed by dotted path. A prefix key covers its children.

A `source` is one of: an http(s) URL · a path to a file in this repo (optionally `#anchor`) ·
`measurement:<repo path>` · `estimate: <why>` (honest, counted separately, never "verified").

`oh check provenance` prints the problems (warn-first). The pass/fail threshold lives in pipeline/gates.yaml (G-provenance).
"""
from __future__ import annotations

from pathlib import Path

from .paths import repo_root

TUNED_SECTIONS = ("analysis", "mass_model")


def classify_source(src) -> str:
    """'url' | 'file' | 'measurement' | 'estimate' | 'bad_file' | 'bad_measurement' | 'empty'."""
    if not isinstance(src, str) or not src.strip():
        return "empty"
    s = src.strip()
    low = s.lower()
    if low.startswith("estimate"):
        return "estimate"
    if low.startswith(("http://", "https://")):
        return "url"
    if low.startswith("measurement:"):
        target = s.split(":", 1)[1].strip().split("#")[0]
        return "measurement" if target and (repo_root() / target).exists() else "bad_measurement"
    target = s.split("#")[0].strip()
    return "file" if (repo_root() / target).exists() else "bad_file"


def _source_of(entry) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return entry.get("source")
    return None


def tuned_constants(spec_raw: dict) -> list[str]:
    """Dotted paths of every numeric leaf under the tuned sections."""
    out: list[str] = []

    def walk(prefix: str, node):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(f"{prefix}.{k}", v)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            out.append(prefix)

    for sec in TUNED_SECTIONS:
        if isinstance(spec_raw.get(sec), dict):
            walk(sec, spec_raw[sec])
    return out


def _covering_entry(path: str, prov: dict):
    parts = path.split(".")
    for n in range(len(parts), 0, -1):
        key = ".".join(parts[:n])
        if key in prov:
            return prov[key]
    return None


def check_spec(spec_raw: dict) -> dict:
    prov = spec_raw.get("provenance") or {}
    problems, counts = [], {"spec_constants": 0, "spec_missing": 0, "spec_bad": 0, "spec_estimates": 0}
    for path in tuned_constants(spec_raw):
        counts["spec_constants"] += 1
        entry = _covering_entry(path, prov)
        if entry is None:
            counts["spec_missing"] += 1
            problems.append(f"spec: {path} has no provenance entry (add provenance: {{{path}: <file|url|measurement:file|estimate: why>}})")
            continue
        kind = classify_source(_source_of(entry))
        if kind == "estimate":
            counts["spec_estimates"] += 1
            problems.append(f"spec: {path} is a declared estimate. Replace it with a measurement or source when you have one")
        elif kind in ("empty", "bad_file", "bad_measurement"):
            counts["spec_bad"] += 1
            problems.append(f"spec: {path} provenance does not resolve ({kind}): {_source_of(entry)!r}")
    return {"counts": counts, "problems": problems}


def check_catalog() -> dict:
    from .catalog import load_catalog
    problems, counts = [], {"catalog_parts": 0, "catalog_verified": 0, "catalog_missing": 0, "catalog_bad": 0, "catalog_estimates": 0}
    for pid, p in load_catalog().items():
        counts["catalog_parts"] += 1
        src, ver = p.get("source"), p.get("verified")
        f = p.get("_file", pid)
        if not isinstance(src, str) or not src.strip() or not isinstance(ver, bool):
            counts["catalog_missing"] += 1
            problems.append(f"catalog: {f} needs both `source` and `verified: true|false`")
            continue
        kind = classify_source(src)
        has_url = kind == "url" or any(isinstance(v, dict) and str(v.get("url", "")).startswith("http") for v in p.get("vendors", []))
        if ver:
            counts["catalog_verified"] += 1
            if kind == "estimate":
                counts["catalog_bad"] += 1
                problems.append(f"catalog: {f} is marked verified but its source is an estimate")
            elif not has_url and kind not in ("file", "measurement"):
                counts["catalog_bad"] += 1
                problems.append(f"catalog: {f} is verified but cites no URL, file or measurement")
        elif kind == "estimate" or not (has_url or kind in ("file", "measurement")):
            counts["catalog_estimates"] += 1
    return {"counts": counts, "problems": problems}


def check(variant: str | None = None) -> dict:
    """Catalog + (optionally) one variant's raw spec."""
    from .spec import load_raw
    cat = check_catalog()
    rep = {"counts": dict(cat["counts"]), "problems": list(cat["problems"])}
    spec = check_spec(load_raw(variant)) if variant else {"counts": {"spec_constants": 0, "spec_missing": 0, "spec_bad": 0, "spec_estimates": 0}, "problems": []}
    rep["counts"].update(spec["counts"])
    rep["problems"] += spec["problems"]
    return rep


def format_report(rep: dict, limit: int = 25) -> str:
    c = rep["counts"]
    lines = [f"catalog: {c['catalog_parts']} parts · {c['catalog_verified']} verified · {c['catalog_estimates']} unverified estimates · "
             f"{c['catalog_missing']} missing source/verified · {c['catalog_bad']} inconsistent",
             f"spec: {c['spec_constants']} tuned constants · {c['spec_missing']} without provenance · {c['spec_bad']} unresolvable · "
             f"{c['spec_estimates']} declared estimates"]
    lines += [f"  ! {p}" for p in rep["problems"][:limit]]
    if len(rep["problems"]) > limit:
        lines.append(f"  … {len(rep['problems']) - limit} more (see --json)")
    return "\n".join(lines)
