"""Assembly container for the geometry gate, range-of-motion sweep and assembly-access check.

An `Assembly` is a tree of `Link`s (geom.Link: origin in the parent frame, single-axis joints at the link origin, parts in the link
frame) plus bookkeeping. It reuses `export.world_locations` for forward kinematics, so a link tree built by any template or by hand
works with every check.

Conventions: link frames are axis-aligned with the world at the zero pose unless `rot_deg` says otherwise; coincident gimbal axes are
modelled as a chain of massless links (like the sim's MJCF).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import build123d as bd

from .core import Site, bboxes_overlap
from .geom import Link, Part


@dataclass
class Placed:
    link: str
    part: Part
    shape: bd.Shape          # in the world frame at the pose it was placed for
    loc: bd.Location         # link world location


@dataclass
class Assembly:
    name: str
    links: dict[str, Link]
    interfaces: dict | None = None
    bed_mm: tuple[float, float, float] | None = None
    allowed_pairs: set[frozenset] = field(default_factory=set)       # part-id pairs that touch/overlap by design
    stand_pose: dict[str, float] = field(default_factory=dict)       # joint -> rad
    notes: list[str] = field(default_factory=list)

    # ---------------------------------------------------------------- basics
    def joints(self) -> dict[str, dict]:
        """name -> {link, axis, range (deg)}"""
        out = {}
        for ln, L in self.links.items():
            for j in L.joints:
                out[j["name"]] = {**j, "link": ln}
        return out

    def parts(self, include_hardware: bool = True) -> list[tuple[str, Part]]:
        return [(ln, p) for ln, L in self.links.items() for p in L.parts if include_hardware or not p.hardware]

    def part(self, pid: str) -> tuple[str, Part]:
        for ln, p in self.parts():
            if p.id == pid:
                return ln, p
        raise KeyError(pid)

    def allow(self, a: str, b: str) -> None:
        self.allowed_pairs.add(frozenset((a, b)))

    def children_of(self, link: str) -> list[str]:
        return [n for n, L in self.links.items() if L.parent == link]

    def subtree(self, link: str) -> set[str]:
        out, stack = set(), [link]
        while stack:
            n = stack.pop()
            out.add(n)
            stack += self.children_of(n)
        return out

    # ---------------------------------------------------------------- kinematics
    def world(self, q: dict[str, float] | None = None) -> dict[str, bd.Location]:
        from .export import world_locations

        qq = dict(self.stand_pose)
        qq.update(q or {})
        return world_locations(self.links, qq)

    def placed(self, q: dict[str, float] | None = None, kinds: tuple[str, ...] | None = None, links: set[str] | None = None) -> list[Placed]:
        locs = self.world(q)
        out = []
        for ln, L in self.links.items():
            if links is not None and ln not in links:
                continue
            for p in L.parts:
                if kinds and p.kind not in kinds:
                    continue
                out.append(Placed(ln, p, locs[ln] * p.shape, locs[ln]))
        return out

    def world_sites(self, q: dict[str, float] | None = None) -> list[tuple[str, Site]]:
        locs = self.world(q)
        out = []
        for ln, L in self.links.items():
            for p in L.parts:
                for s in p.sites:
                    out.append((p.id, Site(**{**s.__dict__, "frame": locs[ln] * s.frame, "part": s.part or p.id})))
        return out

    # ---------------------------------------------------------------- reports
    def bom(self) -> dict:
        """Purchased components and fasteners aggregated from parts and sites."""
        comp: dict[str, int] = {}
        fast: dict[str, int] = {}
        for _, p in self.parts():
            if p.process == "purchased" and p.catalog:
                comp[p.catalog] = comp.get(p.catalog, 0) + 1
            for s in p.sites:
                if s.kind == "screw":
                    k = f"screw {s.thread}x{int(s.length_mm)}"
                    fast[k] = fast.get(k, 0) + 1
                elif s.kind == "insert":
                    k = f"insert {s.thread}"
                    fast[k] = fast.get(k, 0) + 1
                elif s.kind == "magnet":
                    fast["magnet 6x3"] = fast.get("magnet 6x3", 0) + 1
        return {"components": comp, "fasteners": fast}

    def printed(self) -> list[tuple[str, Part]]:
        return [(ln, p) for ln, p in self.parts(False) if p.process == "fdm" and not p.keepout]


def rot_deg(a: float) -> float:
    return math.degrees(a)


def pair_key(a: str, b: str) -> frozenset:
    return frozenset((a, b))


def candidates(placed: list[Placed], pad: float = 0.0):
    """Index pairs whose bounding boxes (grown by pad) overlap: the cheap broad phase for all pairwise checks."""
    out = []
    n = len(placed)
    for i in range(n):
        for k in range(i + 1, n):
            if bboxes_overlap(placed[i].shape, placed[k].shape, pad):
                out.append((i, k))
    return out
