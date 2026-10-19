"""Kinematic templates as data (ADR 0009/0012).

A template (`templates/<id>.yaml`) is the link/joint tree of a robot family. A spec picks one with
`kinematics.template` and lists the joints it wants by template joint name. `simgen` builds the MJCF from the
template plus those joints; a joint the template does not define is an error (it used to be skipped silently).

Lengths in templates are small arithmetic expressions over the geometry names (the spec's proportions times
height, plus the template's own `derived:` values). They are evaluated by a restricted AST walker, never `eval`.
"""
from __future__ import annotations

import ast
import operator
from functools import lru_cache
from pathlib import Path

import yaml

_DIR = Path(__file__).resolve().parent
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow}
_FUNCS = {"min": min, "max": max, "abs": abs}


def safe_eval(expr, names: dict[str, float]) -> float:
    """Evaluate an arithmetic expression over `names`. Numbers pass straight through."""
    if isinstance(expr, (int, float)):
        return float(expr)

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id not in names:
                raise KeyError(f"unknown name '{n.id}' in template expression '{expr}'")
            return float(names[n.id])
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
            return float(_FUNCS[n.func.id](*[ev(a) for a in n.args]))
        raise ValueError(f"unsupported expression '{expr}'")

    return ev(ast.parse(str(expr), mode="eval"))


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    path = _DIR / f"{name}.yaml"
    if not path.exists():
        have = sorted(p.stem for p in _DIR.glob("*.yaml"))
        raise FileNotFoundError(f"No kinematic template '{name}' (have: {', '.join(have)})")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_template(name: str) -> dict:
    """Return a fresh copy of the template dict."""
    import copy
    return copy.deepcopy(_load(name))


def available() -> list[str]:
    return sorted(p.stem for p in _DIR.glob("*.yaml"))


def template_joint_names(name: str) -> list[str]:
    return list(_load(name)["joints"])


def joint_host_map() -> dict[str, str]:
    """base joint name -> body name, merged over all templates (used by older helpers such as render.py)."""
    out: dict[str, str] = {}
    for n in available():
        for b in _load(n)["bodies"]:
            for j in b.get("joints", []):
                out.setdefault(j, b["name"])
    return out


def resolve_geometry(tpl: dict, geom: dict[str, float], height: float) -> dict[str, float]:
    """Spec geometry (metres) + the template's derived values -> the name table used by body expressions."""
    names = dict(geom)
    names["h"] = float(height)
    for k, expr in tpl.get("derived", {}).items():
        names[k] = safe_eval(expr, names)
    return names


def check_joints(tpl: dict, base_names: list[str]) -> None:
    """Raise if the spec asks for joints the template cannot place."""
    unknown = [n for n in base_names if n not in tpl["joints"]]
    if unknown:
        raise ValueError(f"template '{tpl['id']}' has no joint(s) {unknown}; it defines {sorted(tpl['joints'])}. "
                         f"Pick a template that has them or add the joints to the template.")
