"""Policy loader (strength.yaml) and the material model (research/methods/print_materials.yaml).

Material model
--------------
Each material has an XY strength (load along the filaments, layers parallel to the load) and a Z strength (load across the layers,
the delamination direction). For a normal stress on a plane whose normal makes an angle phi with the BUILD direction,

    allowable(phi) = knockdown / sqrt( sin^2(phi)/sigma_xy^2 + cos^2(phi)/sigma_z^2 )

(phi = 0: the plane is parallel to the layers, the load pulls layers apart -> Z; phi = 90 deg -> XY). Shear and bearing allowables
are fractions of the same value. This is a quadratic (Hill-type) interpolation, not a measured law; coupons replace it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from ...paths import repo_root

POLICY_PATH = Path(__file__).with_name("strength.yaml")
MATERIALS_PATH = "research/methods/print_materials.yaml"

ALIASES = {
    "petg": "PETG", "pla": "PLA", "pla-plus": "PLA_plus", "pla_plus": "PLA_plus", "pla+": "PLA_plus", "asa": "ASA", "abs": "ABS",
    "cf-nylon": "CF_nylon", "cf_nylon": "CF_nylon", "pa12-cf": "CF_nylon", "pa-cf": "CF_nylon", "tpu": "TPU",
}


@lru_cache(maxsize=1)
def policy() -> dict:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def pv(d, *path, default=None):
    """Walk the policy dict and unwrap a {v: ...} leaf."""
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur["v"] if isinstance(cur, dict) and "v" in cur else cur


@dataclass(frozen=True)
class Material:
    key: str
    name: str
    sigma_xy: float            # MPa, datasheet
    sigma_z: float
    E_xy: float
    E_z: float
    density: float             # g/cm3
    elong_xy: float | None
    elong_z: float | None
    endurance_fraction: float
    endurance_kind: str
    structural: bool = True

    # ---- allowables (MPa) -----------------------------------------------------------------------------------------
    def knock(self) -> float:
        return float(pv(policy(), "knockdown", "process", default=0.8))

    def tensile(self, phi_deg: float) -> float:
        """Normal-stress allowable on a plane whose normal is phi_deg away from the build direction (0 = pulls layers apart)."""
        s, c = math.sin(math.radians(phi_deg)), math.cos(math.radians(phi_deg))
        return self.knock() / math.sqrt((s / self.sigma_xy) ** 2 + (c / self.sigma_z) ** 2)

    def shear(self, phi_deg: float) -> float:
        return float(pv(policy(), "knockdown", "shear_over_tensile", default=0.5)) * self.tensile(phi_deg)

    def bearing(self, phi_deg: float) -> float:
        return float(pv(policy(), "knockdown", "hole_bearing_over_tensile", default=1.0)) * self.tensile(phi_deg)

    def endurance(self, phi_deg: float, cycles: float | None = None) -> float:
        """Allowable max stress in a pulsating cycle at `cycles` (default: design life), S-N slope k from the policy."""
        f = policy()["fatigue"]
        n = cycles or float(pv(f, "design_life_cycles"))
        k, n_ref = float(pv(f, "sn_inverse_slope_k")), float(pv(f, "reference_cycles"))
        lift = max(1.0, (n_ref / n) ** (1.0 / k))
        return self.endurance_fraction * self.tensile(phi_deg) * lift

    def modulus(self, phi_deg: float = 90.0) -> float:
        s, c = math.sin(math.radians(phi_deg)), math.cos(math.radians(phi_deg))
        return 1.0 / math.sqrt((s / self.E_xy) ** 2 + (c / self.E_z) ** 2)


@lru_cache(maxsize=1)
def _raw() -> dict:
    return yaml.safe_load((repo_root() / MATERIALS_PATH).read_text(encoding="utf-8"))["materials"]


def canonical(name: str) -> str:
    n = (name or "").strip()
    return ALIASES.get(n.lower(), n)


def material(name: str) -> Material:
    """Material by part.material string ('petg', 'pla-plus', 'CF_nylon', ...)."""
    key = canonical(name)
    raw = _raw()
    if key in ("ABS", "ASA"):
        raw_m = raw["ABS_ASA"][key]
    elif key in raw:
        raw_m = raw[key]
    else:
        raise KeyError(f"unknown printed material '{name}'. Known: {sorted(list(raw) + ['ABS', 'ASA'])}")
    if key == "TPU":
        return Material(key, raw_m["product"], 3.0, 3.0, float(raw_m["modulus_xy"]), float(raw_m["modulus_xy"]), float(raw_m["density"]),
                        raw_m.get("elongation_break_xy"), None, 0.0, "n/a", structural=False)
    ef = policy()["fatigue"]["endurance_fraction"].get(key, {"v": 0.10, "kind": "assumption"})
    return Material(
        key=key, name=str(raw_m.get("product", key)), sigma_xy=float(raw_m["tensile_xy"]), sigma_z=float(raw_m["tensile_z"]),
        E_xy=float(raw_m["modulus_xy"]), E_z=float(raw_m["modulus_z"]), density=float(raw_m["density"]),
        elong_xy=raw_m.get("elongation_break_xy"), elong_z=raw_m.get("elongation_break_z"),
        endurance_fraction=float(ef["v"]), endurance_kind=str(ef.get("kind", "assumption")))


def all_structural() -> list[str]:
    return ["PLA", "PLA_plus", "PETG", "ASA", "ABS", "CF_nylon"]
