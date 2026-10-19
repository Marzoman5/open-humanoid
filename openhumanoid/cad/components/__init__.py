"""Parametric models of every purchased part a humanoid contains, with the functional features CAD needs (output axis, horn pattern,
idler position, mounting holes, cable exit, keep-out), and a provenance record for every dimension.

    from openhumanoid.cad.components import get
    servo = get("sts3215-12v")                 # or "sts3215", "sts3250", catalog ids
    servo.frames["axis"], servo.frames["back_axis"], servo.holes, servo.keepout
    horn = get("horn-25t"); bearing = get("bearing:MR85ZZ"); get("screw:M3x8"); get("insert:M3"); get("magnet:6x3")
    get("rpi-zero-2w"), get("lipo-3s-2200"), get("waveshare-bus-servo-adapter"), get("buck-5v-5a"), get("imu-bno085"), get("xt60")

Conventions (all components):
* Millimetres. Each component is modelled in its own frame; place with `component.placed(loc)` / `loc * component.shape`.
* Installed hardware (screw, insert, magnet, bearing) has its origin on the surface it sits in, local +z pointing OUT of the
  host part, the hardware body at z < 0 (a screw head sits at z > 0).
* Servo frame: origin on the output axis at the horn-face plane, +z out of the horn face, +x toward the long end of the body, y width.
* Boards: origin at the lower-left corner of the underside, +z up, +x along the long edge.

Provenance: `component.provenance[name] = {"src": ..., "conf": ...}`; `component.estimates()` lists everything that is only
an engineering estimate. Those are the dimensions the fit gauge must confirm.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import build123d as bd
import yaml

from ..core import loc_from

DATA = Path(__file__).parent / "data"


@lru_cache(maxsize=None)
def load_data(name: str) -> dict:
    return yaml.safe_load((DATA / f"{name}.yaml").read_text(encoding="utf-8"))


def val(entry):
    """Unwrap a {v, src, conf} entry (or return a plain value)."""
    return entry["v"] if isinstance(entry, dict) and "v" in entry else entry


def prov(entry, name: str, out: dict) -> None:
    if isinstance(entry, dict) and "conf" in entry:
        out[name] = {"src": entry.get("src", ""), "conf": entry["conf"]}


@dataclass
class HoleSpec:
    """A hole/thread on a component: `frame` origin on the surface, +z out of the material."""
    id: str
    frame: bd.Location
    thread: str
    depth: float
    kind: str = "tapped"          # tapped | clear | insert | pocket
    d: float = 0.0                # nominal diameter of the hole or thread


@dataclass
class Component:
    id: str
    kind: str                       # servo | horn | bearing | screw | insert | magnet | board | battery | connector | switch
    shape: bd.Shape                 # nominal body in the local frame
    mass_kg: float = 0.0
    frames: dict[str, bd.Location] = field(default_factory=dict)
    holes: list[HoleSpec] = field(default_factory=list)
    keepout: bd.Shape | None = None         # body + plug/cable/margin room
    params: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    catalog_id: str | None = None

    def placed(self, loc: bd.Location) -> "Component":
        return Component(self.id, self.kind, loc * self.shape, self.mass_kg,
                         {k: loc * v for k, v in self.frames.items()},
                         [HoleSpec(h.id, loc * h.frame, h.thread, h.depth, h.kind, h.d) for h in self.holes],
                         None if self.keepout is None else loc * self.keepout, dict(self.params), self.provenance, self.catalog_id)

    def estimates(self) -> list[str]:
        return sorted(k for k, v in self.provenance.items() if v["conf"] == "estimate")

    def bbox_mm(self) -> tuple[float, float, float]:
        bb = self.shape.bounding_box()
        return (bb.size.X, bb.size.Y, bb.size.Z)


_ALIASES = {"sts3215": "sts3215-12v", "sts3250": "sts3250-12v", "sts3215-7v4": "sts3215-7v4", "imu": "imu-bno085",
            "pi-zero-2w": "rpi-zero-2w", "pi5": "rpi-5-4gb", "pi-5": "rpi-5-4gb", "lipo": "lipo-3s-2200", "buck": "buck-5v-5a",
            "switch": "power-switch-xt60", "bus-adapter": "waveshare-bus-servo-adapter", "horn": "horn-25t"}


def get(component_id: str, **kw) -> Component:
    """Build a component by id. `kw` are model options (e.g. `get("screw:M3x10")` parses its own suffix)."""
    from . import electronics, hardware, servo

    cid = _ALIASES.get(component_id, component_id)
    if cid.startswith("sts") or cid in ("sts3215-12v", "sts3215-7v4", "sts3250-12v"):
        return servo.build(cid, **kw)
    if cid.startswith("horn"):
        return hardware.horn(**kw)
    if cid.startswith("bearing:"):
        return hardware.bearing(cid.split(":", 1)[1], **kw)
    if cid.startswith("screw:"):
        return hardware.screw(cid.split(":", 1)[1], **kw)
    if cid.startswith("insert:"):
        return hardware.insert(cid.split(":", 1)[1], **kw)
    if cid.startswith("magnet:"):
        return hardware.magnet(cid.split(":", 1)[1], **kw)
    if cid in load_data("electronics"):
        return electronics.build(cid, **kw)
    raise KeyError(f"unknown component '{component_id}'. Known: {', '.join(list_components())}")


def list_components() -> list[str]:
    ids = ["sts3215-12v", "sts3215-7v4", "sts3250-12v", "horn-25t"]
    ids += [f"bearing:{b}" for b in load_data("hardware")["bearings"]]
    ids += [f"screw:{t}x<len>" for t in load_data("hardware")["screws"]]
    ids += [f"insert:{t}" for t in load_data("hardware")["inserts"]]
    ids += ["magnet:6x3"]
    ids += [k for k in load_data("electronics") if k != "units"]
    return ids


__all__ = ["Component", "HoleSpec", "get", "list_components", "load_data", "val", "loc_from"]
