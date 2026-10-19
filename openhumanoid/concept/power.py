"""Battery pack model (open-circuit voltage curve, internal resistance, sag) and the pack/regulator helpers.

The trade study that compares voltage/pack/actuator mixes lives in `tradestudy.py`; this module is the physics
both it and the playback loop share.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import catalog

# Typical per-cell LiPo open-circuit voltage vs state of charge (generic curve; no per-pack data). Assumption.
_SOC = np.array([0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
_VOC = np.array([3.30, 3.50, 3.62, 3.70, 3.75, 3.79, 3.83, 3.88, 3.95, 4.02, 4.10, 4.20])
CUTOFF_V_CELL = 3.3          # discharge cutoff used for runtime (3.0 V is the damage limit; 3.3 leaves margin)
USABLE_FRACTION_DEFAULT = 0.85
MIN_RESISTANCE_PER_AH = 0.015   # ohm*Ah per cell: r_cell ~ 15 mOhm / capacity_Ah (typical LiPo); assumption
CONNECTOR_RESISTANCE = 0.008    # XT60 + switch + harness, ohm; assumption


@dataclass
class Pack:
    cells: int
    capacity_ah: float
    r_cell: float                 # ohm per cell
    r_fixed: float = CONNECTOR_RESISTANCE
    soc: float = 1.0
    max_discharge_a: float = 1e9  # C-rating * capacity, for the over-current check
    mass_kg: float = 0.0
    part_id: str = ""

    @property
    def r_total(self) -> float:
        return self.cells * self.r_cell + self.r_fixed

    @property
    def energy_wh(self) -> float:
        return self.capacity_ah * self.cells * 3.7          # nominal 3.7 V/cell

    def voc(self, soc: float | None = None) -> float:
        return float(self.cells * np.interp(self.soc if soc is None else soc, _SOC, _VOC))

    def voltage(self, i_a: float, soc: float | None = None) -> float:
        return self.voc(soc) - i_a * self.r_total

    def step(self, i_a: float, dt: float) -> float:
        self.soc = max(0.0, self.soc - i_a * dt / (self.capacity_ah * 3600.0))
        return self.voltage(i_a)

    def copy(self) -> "Pack":
        return Pack(**{k: getattr(self, k) for k in self.__dataclass_fields__})


def pack_from_catalog(part_id: str, soc: float = 1.0) -> Pack:
    p = catalog.get(part_id)
    s = p.get("specs", {})
    cells, ah = int(s["cells"]), s["capacity_mah"] / 1000.0
    r_cell = s.get("internal_resistance_mohm_per_cell")
    r_cell = r_cell / 1000.0 if r_cell else MIN_RESISTANCE_PER_AH / ah
    c = s.get("c_rating", 20)
    return Pack(cells, ah, r_cell, soc=soc, max_discharge_a=c * ah, mass_kg=p.get("mass_kg", 0.0), part_id=part_id)


def compute_power_w(part_id: str, load: str = "typical") -> float:
    """Typical on-board compute draw in watts (catalog specs.power_w). Pi 5 under inference load is higher than idle."""
    s = catalog.get(part_id).get("specs", {})
    return float(s.get("power_w_typical", s.get("power_w", 3.0)))


def regulator_efficiency(part_id: str | None) -> float:
    if not part_id:
        return 0.9
    return float(catalog.get(part_id).get("specs", {}).get("efficiency", 0.9))
