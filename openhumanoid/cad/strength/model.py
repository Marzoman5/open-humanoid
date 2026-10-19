"""Numpy snapshot of a CAD assembly for the strength checks: link kinematics, part meshes, mass properties, fastener sites, joint interfaces.

`Model.from_assembly(asm, interfaces)` takes what a builder file returns (an `openhumanoid.cad.assembly.Assembly`) plus the joint
interface data (`interfaces.yaml`), and converts everything to numpy/trimesh so the load, analytic and FEA code never touches OCC.
It can be pickled (`save`/`load`) so that iterating on loads does not rebuild the CAD (the leg build takes about 40 s).

Builder contract (documented in docs/strength.md): purchased parts are named `servo_<joint>`, `horn_<joint>`, `bearing_<joint>`
(`shaft_`, `shaftb_` too) and carry `Part.mass_kg`; printed parts are `Part.process == "fdm"` and carry `Part.material` and `Part.print_up`.
Fastener Sites carry `part` and `mates`; the horn-mount sites mate with `servo_<joint>`.
"""
from __future__ import annotations

import math
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import trimesh

from .policy import material as get_material, pv, policy


# ------------------------------------------------------------------------------------------------------------------ records
@dataclass
class SiteRec:
    id: str
    kind: str                 # screw | insert | magnet
    part: str
    thread: str
    length: float
    mates: str | None
    p: np.ndarray             # position in the LINK frame (mm)
    z: np.ndarray             # unit vector pointing OUT of the material (screw head side)


@dataclass
class PartRec:
    id: str
    link: str
    kind: str
    process: str              # fdm | purchased
    material: str
    catalog: str | None
    mass_kg: float            # purchased: catalog mass; printed: volume * density * fill fraction
    print_up: np.ndarray      # build direction in the link frame
    mesh: trimesh.Trimesh     # link frame, mm
    volume: float             # mm3
    com: np.ndarray           # centre of mass (mm), link frame
    sites: list[SiteRec] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    profile: dict = field(default_factory=dict)      # perimeters, infill_pct, fill_fraction (from the variant strength config)

    @property
    def printed(self) -> bool:
        return self.process == "fdm"


@dataclass
class LinkRec:
    name: str
    parent: str | None
    pos: np.ndarray           # origin in the parent frame at zero pose (mm)
    rot_deg: tuple
    joints: list[dict]        # [{name, axis: 'x'|'y'|'z', range}]


@dataclass
class JointRec:
    name: str
    child_link: str
    parent_link: str
    host_link: str            # link that holds the servo case
    axis_dir: np.ndarray      # world, zero pose
    axis_origin: np.ndarray   # world, zero pose (mm)
    actuator: str
    servo_origin: np.ndarray  # servo frame origin (horn-face plane on the axis), world, zero pose
    servo_z: np.ndarray       # horn direction
    servo_x: np.ndarray       # long end direction
    horn_seat: np.ndarray     # world point where the horn underside sits
    horn_bolt_circle_d: float
    horn_n_holes: int
    horn_screw: str
    center_screw: str
    idler_bearing: str | None
    idler_seat: np.ndarray | None
    stall_nm: float = 0.0
    servo_mass_kg: float = 0.0


def rot_axis(axis: str, ang: float) -> np.ndarray:
    c, s = math.cos(ang), math.sin(ang)
    return {"x": np.array([[1, 0, 0], [0, c, -s], [0, s, c]]),
            "y": np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]),
            "z": np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])}[axis]


def rot_xyz_deg(r) -> np.ndarray:
    """build123d Rot(rx, ry, rz) in degrees: rotation about x, then y, then z (extrinsic)."""
    return rot_axis("z", math.radians(r[2])) @ rot_axis("y", math.radians(r[1])) @ rot_axis("x", math.radians(r[0]))


# ------------------------------------------------------------------------------------------------------------------- model
@dataclass
class Model:
    name: str
    links: dict[str, LinkRec]
    parts: dict[str, PartRec]
    joints: dict[str, JointRec]
    bed_mm: tuple | None = None
    notes: list = field(default_factory=list)
    if_offset: np.ndarray = field(default_factory=lambda: np.zeros(3))   # interface-world = assembly-world + if_offset

    # ---- kinematics ---------------------------------------------------------------------------------------------
    def fk(self, q: dict[str, float] | None = None) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        """link -> (R 3x3, t mm) of the link frame in the world at joint angles q (rad)."""
        q = q or {}
        out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for n, L in self.links.items():
            Rp, tp = out[L.parent] if L.parent else (np.eye(3), np.zeros(3))
            R = Rp @ rot_xyz_deg(L.rot_deg)
            t = tp + Rp @ L.pos
            for j in L.joints:
                R = R @ rot_axis(j["axis"], q.get(j["name"], 0.0))
            out[n] = (R, t)
        return out

    def link_order(self) -> list[str]:
        return list(self.links)

    def children(self, link: str) -> list[str]:
        return [n for n, L in self.links.items() if L.parent == link]

    def subtree(self, link: str) -> list[str]:
        out, stack = [], [link]
        while stack:
            n = stack.pop()
            out.append(n)
            stack += self.children(n)
        return out

    def chain_to_root(self, link: str) -> list[str]:
        out = []
        n = link
        while n:
            out.append(n)
            n = self.links[n].parent
        return out

    def joint_of_link(self, link: str) -> JointRec | None:
        for j in self.joints.values():
            if j.child_link == link:
                return j
        return None

    def parts_in(self, link: str, printed: bool | None = None) -> list[PartRec]:
        return [p for p in self.parts.values() if p.link == link and (printed is None or p.printed == printed)]

    def printed_parts(self) -> list[PartRec]:
        return [p for p in self.parts.values() if p.printed]

    def world_axis(self, joint: str, fk) -> tuple[np.ndarray, np.ndarray]:
        """(origin, direction) of the joint axis in the world at the pose `fk`: the axis passes through the child link origin and is
        fixed in the PARENT-side frame for rotation purposes, so the direction is the child frame's axis before the joint rotation."""
        j = self.joints[joint]
        R, t = fk[j.child_link]
        ax = [jj for jj in self.links[j.child_link].joints if jj["name"] == joint][0]["axis"]
        d = R @ {"x": np.array([1.0, 0, 0]), "y": np.array([0, 1.0, 0]), "z": np.array([0, 0, 1.0])}[ax]
        return t.copy(), d

    # ---- persistence --------------------------------------------------------------------------------------------
    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load(path: str | Path) -> "Model":
        with open(path, "rb") as f:
            return pickle.load(f)

    # ---- construction -------------------------------------------------------------------------------------------
    @staticmethod
    def from_assembly(asm, ifs, profiles: dict | None = None) -> "Model":
        """`ifs` is an `openhumanoid.cad.interfaces.Interfaces`. `profiles`: {part id or '*': {perimeters, infill_pct, material}}."""
        from ..core import mesh_of

        profiles = profiles or {}
        links = {n: LinkRec(n, L.parent, np.array(L.pos_mm, float), tuple(L.rot_deg), [dict(j) for j in L.joints]) for n, L in asm.links.items()}
        parts: dict[str, PartRec] = {}
        pol = policy()
        default_fill = float(pv(pol, "print_profile", "mass_fill_fraction"))
        for ln, L in asm.links.items():
            for p in L.parts:
                m = mesh_of(p.shape, tol=0.03, ang=0.15)
                prof = dict(profiles.get("*", {}))
                prof.update(profiles.get(p.id, {}))
                printed = p.process == "fdm" and not p.keepout
                mat_name = prof.get("material", p.material)
                vol = float(m.volume) if m.is_watertight else float(p.shape.volume)
                com = np.array(m.center_mass if m.is_watertight else m.centroid, float)
                if printed:
                    dens = get_material(mat_name).density            # g/cm3
                    fill = float(prof.get("fill_fraction", default_fill))
                    mass = vol * 1e-3 * dens * fill * 1e-3          # mm3 -> cm3 -> g -> kg
                else:
                    mass = float(p.mass_kg or 0.0)
                up = np.array(p.print_up if p.print_up is not None else (0.0, 0.0, 1.0), float)
                up /= np.linalg.norm(up)
                sites = []
                for s in p.sites:
                    o = s.frame.position
                    zq = (s.frame * __import__("build123d").Location((0, 0, 1))).position
                    sites.append(SiteRec(s.id, s.kind, s.part or p.id, s.thread, float(s.length_mm), s.mates,
                                         np.array([o.X, o.Y, o.Z]), np.array([zq.X - o.X, zq.Y - o.Y, zq.Z - o.Z])))
                parts[p.id] = PartRec(p.id, ln, p.kind, "fdm" if printed else "purchased", mat_name, p.catalog, mass, up, m, vol, com,
                                      sites, dict(p.meta or {}), prof)
        joints: dict[str, JointRec] = {}
        for jn, jd in asm.joints().items():
            ij = ifs.d["joints"].get(jn)
            if ij is None:
                continue
            a = ij["actuator"]
            from ... import catalog as _cat

            cat = _cat.get(a["id"])
            stall = float((cat.get("actuator") or {}).get("stall_torque_nm", 0.0))
            f = a["frame"]
            idl = ij.get("idler")
            joints[jn] = JointRec(
                name=jn, child_link=jd["link"], parent_link=ij["parent_link"], host_link=a["host_link"],
                axis_dir=np.array(ij["axis"]["direction"], float), axis_origin=np.array(ij["axis"]["origin_mm"], float), actuator=a["id"],
                servo_origin=np.array(f["origin_mm"], float), servo_z=np.array(f["z_dir"], float), servo_x=np.array(f["x_dir"], float),
                horn_seat=np.array(ij["horn"]["seat_origin_mm"], float), horn_bolt_circle_d=float(ij["horn"]["bolt_circle_d_mm"]),
                horn_n_holes=int(ij["horn"]["n_holes"]), horn_screw=str(ij["horn"]["screw"]), center_screw=str(ij["horn"]["center_screw"]),
                idler_bearing=idl["bearing"] if idl else None, idler_seat=np.array(idl["seat_origin_mm"], float) if idl else None,
                stall_nm=stall, servo_mass_kg=float(a.get("mass_kg", 0.0)))
        root = [n for n, L in asm.links.items() if L.parent is None][0]
        off = np.array(ifs.link_origin(root), float) - np.array(asm.links[root].pos_mm, float)
        return Model(asm.name, links, parts, joints, tuple(asm.bed_mm) if asm.bed_mm else None, list(asm.notes), off)
