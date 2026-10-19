"""Loader for the one thresholds/constants file (openhumanoid/concept/thresholds.yaml)."""
from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

import yaml

PATH = Path(__file__).resolve().parent / "thresholds.yaml"


@lru_cache(maxsize=1)
def _load() -> dict:
    return yaml.safe_load(PATH.read_text(encoding="utf-8"))


def thresholds() -> dict:
    return copy.deepcopy(_load())


def gate(name: str) -> float:
    return float(_load()["gates"][name]["value"])


def motions() -> dict:
    return copy.deepcopy(_load()["motions"])


def walk_spec() -> dict:
    return motions()["walk"]


def value(path: str):
    """'thermal.ambient_c' -> the .value of that node (or the node itself if it has none)."""
    node = _load()
    for part in path.split("."):
        node = node[part]
    return node["value"] if isinstance(node, dict) and "value" in node else node
