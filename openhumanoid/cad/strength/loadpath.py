"""Load path: which printed part receives which load, and how it is passed on to its neighbours.

Topology (static, from the model):
    root[link]      the printed part bolted to the joint's horn (receives the horn reaction)
    idler[link]     the printed part carrying the idler bearing of that joint (receives the bearing reaction)
    housing[joint]  the printed part whose pocket holds the servo of `joint`  (receives the distal wrench of that joint)
    pin[joint]      the printed part carrying the pin the idler bearing rides on (receives minus the bearing reaction)
    parent[part]    tree of the printed parts of one link, built from the fastener sites (`Site.mates`), rooted at root[link]
Per scenario every printed part gets a list of applied loads (point, force, moment) in its LINK frame, in equilibrium with the
reaction it hands to its parent (or the horn reaction for the root). Self weight is added by the section engine (partial volumes).

Idler joints: the horn carries the axial force, the torque and a radial force, the idler bearing the rest of the radial force and the
whole non-axial moment (a couple across the fork). A joint without an idler carries everything through the horn.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh

from .chain import Scenario, joint_wrenches
from .model import JointRec, Model, PartRec

BEARING_WIDTH = {"MR105ZZ": 4.0, "MR85ZZ": 2.5, "MR83ZZ": 3.0, "623ZZ": 4.0, "685ZZ": 5.0, "625ZZ": 5.0, "MR126ZZ": 4.0, "606ZZ": 6.0, "688ZZ": 5.0}


@dataclass
class Load:
    point: np.ndarray        # link frame, mm
    F: np.ndarray            # N
    M: np.ndarray            # N.mm about `point`
    label: str = ""
    patch: dict | None = None    # how the load enters the part for FEA: {'type': 'sphere'|'annulus'|'sites', ...} (link frame)


@dataclass
class Edge:
    child: str
    parent: str
    sites: list              # SiteRec of both parts that belong to this connection
    centroid: np.ndarray     # link frame
    wrench_F: np.ndarray = None      # load the child hands to the parent, at the centroid (link frame)
    wrench_M: np.ndarray = None


@dataclass
class PartLoads:
    part: str
    link: str
    loads: list[Load] = field(default_factory=list)
    total_F: np.ndarray = None       # sum of everything applied to the part's subtree (incl. own weight), link frame
    total_M: np.ndarray = None       # about the link origin
    g_link: np.ndarray = None        # inertial field in the link frame (m/s2)
    reaction_to_parent: Edge | None = None


_PQ: dict[int, trimesh.proximity.ProximityQuery] = {}


def _min_dist_points(mesh: trimesh.Trimesh, pts: np.ndarray) -> np.ndarray:
    q = _PQ.get(id(mesh))
    if q is None:
        q = _PQ[id(mesh)] = trimesh.proximity.ProximityQuery(mesh)
    _, d, _ = q.on_surface(np.asarray(pts, float))
    return np.asarray(d)


class Topology:
    def __init__(self, model: Model, exclude: list[str] | None = None):
        self.m = model
        self.exclude = set(exclude or [])
        self.root: dict[str, str] = {}
        self.idler: dict[str, str] = {}
        self.housing: dict[str, str] = {}
        self.cover: dict[str, str] = {}
        self.pin: dict[str, str] = {}
        self.hw_owner: dict[str, str] = {}
        self.parent: dict[str, str | None] = {}
        self.edges: dict[tuple[str, str], list] = {}
        self.order: dict[str, list[str]] = {}
        self._build()

    def resolve(self, name: str | None) -> str | None:
        if name is None or name in self.m.parts:
            return name
        for prefix, table in (("housing_", self.housing), ("cover_", self.cover)):
            if name.startswith(prefix) and name[len(prefix):] in table:
                return table[name[len(prefix):]]
        return name

    def _contact_score(self, hw: PartRec, cand: list[PartRec], tol: float = 0.7, n: int = 400) -> dict[str, float]:
        """Share of surface samples of a purchased part within `tol` mm of each candidate printed part."""
        pts, _ = trimesh.sample.sample_surface(hw.mesh, n, seed=1)
        fk0 = self.m.fk({})
        w = pts @ fk0[hw.link][0].T + fk0[hw.link][1]
        out = {}
        for c in cand:
            Rc, tc = fk0[c.link]
            d = _min_dist_points(c.mesh, (w - tc) @ Rc)
            out[c.id] = float((d < tol).mean())
        return out

    def _build(self) -> None:
        m = self.m
        # ---- housings / covers: servo case in the host link
        for jn, j in m.joints.items():
            host_printed = m.parts_in(j.host_link, True)
            sv = m.parts.get(f"servo_{jn}")
            if sv is None or not host_printed:
                continue
            sc = self._contact_score(sv, host_printed)
            ranked = sorted(sc.items(), key=lambda kv: -kv[1])
            if ranked and ranked[0][1] > 0.02:
                self.housing[jn] = ranked[0][0]
                self.hw_owner[sv.id] = ranked[0][0]
                if len(ranked) > 1 and ranked[1][1] > 0.02:
                    self.cover[jn] = ranked[1][0]
        # ---- root / idler / pin in the child link
        for jn, j in m.joints.items():
            L = j.child_link
            printed = m.parts_in(L, True)
            if not printed:
                continue
            horn = m.parts.get(f"horn_{jn}")
            site_mates = {p.id: sum(1 for s in p.sites if s.mates == f"servo_{jn}") for p in printed}
            if horn is not None:
                sc = self._contact_score(horn, printed, tol=0.8)
                best = max(sc.items(), key=lambda kv: kv[1])
                root = best[0] if best[1] > 0.02 else max(site_mates.items(), key=lambda kv: kv[1])[0]
            else:
                root = max(site_mates.items(), key=lambda kv: kv[1])[0]
            self.root[L] = root
            for hid in (f"horn_{jn}", f"shaft_{jn}", f"shaftb_{jn}"):
                if hid in m.parts:
                    self.hw_owner[hid] = root
            if j.idler_bearing:
                br = m.parts.get(f"bearing_{jn}")
                if br is not None:
                    sc = self._contact_score(br, printed, tol=0.5)
                    ranked = sorted(sc.items(), key=lambda kv: -kv[1])
                    self.idler[L] = ranked[0][0]
                    self.hw_owner[br.id] = ranked[0][0]
                    host_printed = m.parts_in(j.host_link, True)
                    sc2 = self._contact_score(br, host_printed, tol=0.12)
                    r2 = sorted(sc2.items(), key=lambda kv: -kv[1])
                    if r2 and r2[0][1] > 0:
                        self.pin[jn] = r2[0][0]
        # ---- other purchased parts: nearest printed part of the same link
        for pid, p in m.parts.items():
            if p.printed or pid in self.hw_owner:
                continue
            printed = m.parts_in(p.link, True)
            if not printed:
                continue
            d = [(_min_dist_points(c.mesh, p.com[None, :])[0], c.id) for c in printed]
            self.hw_owner[pid] = min(d)[1]
        # ---- site ownership and the names fasteners mate with (a helper names the part 'housing_<joint>' even when it is a bracket)
        for pid, pr in m.parts.items():
            for st in pr.sites:
                st.part = pid
                st.mates = self.resolve(st.mates)
        # ---- tree of printed parts per link
        for L in m.links:
            printed = [p.id for p in m.parts_in(L, True)]
            if not printed:
                continue
            adj: dict[str, set] = {p: set() for p in printed}
            groups: dict[tuple[str, str], list] = {}
            for pid in printed:
                for s in m.parts[pid].sites:
                    if s.mates in adj and s.mates != pid:
                        adj[pid].add(s.mates)
                        adj[s.mates].add(pid)
                        groups.setdefault(tuple(sorted((pid, s.mates))), []).append(s)
            root = self.root.get(L) or printed[0]
            order = [root]
            self.parent[root] = None
            seen = {root}
            i = 0
            while i < len(order):
                cur = order[i]
                i += 1
                for nb in sorted(adj[cur]):
                    if nb not in seen:
                        seen.add(nb)
                        self.parent[nb] = cur
                        order.append(nb)
            for p in printed:
                if p not in seen:
                    self.parent[p] = None
                    order.append(p)
            self.order[L] = order
            for k, v in groups.items():
                self.edges[k] = v


def solve(model: Model, topo: Topology, sc: Scenario, mass_override: dict[str, float] | None = None) -> tuple[dict[str, PartLoads], dict]:
    """Loads on every printed part for scenario `sc`. Returns (part loads, diagnostics)."""
    mo = mass_override or {}
    fk = model.fk(sc.q)
    W = joint_wrenches(model, sc, mo)
    diag: dict = {"joint_tau_nm": {j: d["tau"] / 1000.0 for j, d in W.items()}, "equilibrium_residual": {}}
    loads: dict[str, PartLoads] = {}
    for L in model.links:
        R, _ = fk[L]
        for p in model.parts_in(L, True):
            loads[p.id] = PartLoads(p.id, L, [], g_link=R.T @ sc.g_eff)

    def to_link(link: str, pw: np.ndarray) -> np.ndarray:
        R, t = fk[link]
        return R.T @ (pw - t)

    def vec_link(link: str, v: np.ndarray) -> np.ndarray:
        return fk[link][0].T @ v

    # ---- purchased parts' inertial loads (weights)
    for pid, owner in topo.hw_owner.items():
        hp = model.parts[pid]
        mass = mo.get(pid, hp.mass_kg)
        if mass <= 0 or owner not in loads:
            continue
        own_link = loads[owner].link
        Rh, th = fk[hp.link]
        pw = Rh @ hp.com + th
        loads[owner].loads.append(Load(to_link(own_link, pw), vec_link(own_link, mass * sc.g_eff), np.zeros(3), f"weight of {pid}"))
    # ---- external contacts -> nearest printed part of that link
    for c in sc.contacts:
        printed = model.parts_in(c.link, True)
        pl = to_link(c.link, c.point)
        d = [(_min_dist_points(p.mesh, pl[None, :])[0], p.id) for p in printed if p.id not in topo.exclude] or [(0, printed[0].id)]
        tgt = min(d)[1]
        loads[tgt].loads.append(Load(pl, vec_link(c.link, c.force), np.zeros(3), c.label or "contact", {"type": "sphere", "r": 4.0}))
    # ---- servo wrenches onto housings; bearing reactions onto idler plates and pins.
    # The distal wrench W_j of a joint reaches the host side through TWO paths when the joint has an idler: the servo (horn shaft + case) and the
    # pin the idler bearing rides on. The pin carries -R_b at the bearing centre; the housing gets W_j minus that.
    for jn, j in model.joints.items():
        w = W[jn]
        F_house, M_house = w["F"].copy(), w["M"].copy()
        if j.idler_bearing and j.child_link in topo.idler:
            a = w["axis"]
            Ph = fk[j.child_link][0] @ (j.horn_seat - fk0_origin(model, j.child_link)) + fk[j.child_link][1]
            wb = BEARING_WIDTH.get(j.idler_bearing, 4.0)
            cb = fk[j.child_link][0] @ (j.idler_seat - wb * j.servo_z / 2 - fk0_origin(model, j.child_link)) + fk[j.child_link][1]
            Fv, Mj, O = w["F"], w["M"], w["O"]
            Mh = Mj + np.cross(O - Ph, Fv)
            Mperp = Mh - a * float(Mh @ a)
            Lb = float((cb - Ph) @ a)
            if abs(Lb) > 1.0:
                Rb = -np.cross(Mperp, a) / Lb
                idl = topo.idler[j.child_link]
                il = loads[idl].link
                loads[idl].loads.append(Load(to_link(il, cb), vec_link(il, Rb), np.zeros(3), f"idler bearing reaction of {jn}", {"type": "annulus", "c": to_link(il, cb), "axis": vec_link(il, a), "r0": 4.0, "r1": 5.8, "half": 2.6}))
                pin = topo.pin.get(jn)
                if pin and pin in loads:
                    pl_ = loads[pin].link
                    loads[pin].loads.append(Load(to_link(pl_, cb), vec_link(pl_, -Rb), np.zeros(3), f"pin load from the idler bearing of {jn}", {"type": "annulus", "c": to_link(pl_, cb), "axis": vec_link(pl_, a), "r0": 0.0, "r1": 3.0, "half": 2.6}))
                    F_house = F_house + Rb                         # remove the pin's share (-R_b) from the wrench the servo case receives
                    M_house = M_house + np.cross(cb - O, Rb)
                diag.setdefault("bearing_reaction_n", {})[jn] = float(np.linalg.norm(Rb))
        hsg = topo.housing.get(jn)
        if hsg and hsg in loads:
            hl = loads[hsg].link
            loads[hsg].loads.append(Load(to_link(hl, w["O"]), vec_link(hl, F_house), vec_link(hl, M_house), f"distal wrench of {jn}"))
    # ---- tree: totals and the wrench each child hands to its parent
    for L, order in topo.order.items():
        R, t = fk[L]
        o_ref = np.zeros(3)         # link origin as the reference point for totals
        tot: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for pid in reversed(order):
            pl = loads[pid]
            part = model.parts[pid]
            F = np.zeros(3)
            Mo = np.zeros(3)
            for ld in pl.loads:
                F = F + ld.F
                Mo = Mo + np.cross(ld.point - o_ref, ld.F) + ld.M
            mw = mo.get(pid, part.mass_kg)
            fw = mw * pl.g_link
            F = F + fw
            Mo = Mo + np.cross(part.com - o_ref, fw)
            for ch, pa in topo.parent.items():
                if pa == pid and ch in tot and model.parts[ch].link == L:
                    cF, cM = tot[ch]
                    C = edge_of(model, topo, ch, pid).centroid
                    # the child's total wrench (about o_ref) is applied to the parent at the connection centroid
                    mC = cM + np.cross(o_ref - C, cF)
                    pl.loads.append(Load(C, cF, mC, f"carried from {ch}", {"type": "sites", "points": [st.p for st in edge_of(model, topo, ch, pid).sites if st.part == pid] or [C], "r": 3.0}))
                    F = F + cF
                    Mo = Mo + np.cross(C - o_ref, cF) + mC
            tot[pid] = (F, Mo)
            pl.total_F, pl.total_M = F, Mo
            pa = topo.parent.get(pid)
            if pa is not None and model.parts[pa].link == L:
                g = edge_of(model, topo, pid, pa)
                C = g.centroid
                ed = Edge(pid, pa, g.sites, C, F.copy(), Mo + np.cross(o_ref - C, F))
                pl.reaction_to_parent = ed
                # reaction on this child (equal and opposite) is part of its own applied set
                pl.loads.append(Load(C, -F, -ed.wrench_M, f"reaction from {pa} (connection)", {"type": "sites", "points": [st.p for st in g.sites if st.part == pid] or [C], "r": 3.0}))
        # horn reaction on the root
        rt = order[0]
        j = model.joint_of_link(L)
        if j is not None:
            Fr, Mr = tot[rt]
            hs = fk0_to_link(model, j.horn_seat, L) + horn_thickness(model, j) * (j.servo_z / np.linalg.norm(j.servo_z))      # plate underside, on the horn top
            mP = Mr + np.cross(o_ref - hs, Fr)
            loads[rt].loads.append(Load(hs, -Fr, -mP, f"horn reaction of {j.name}", {"type": "annulus", "c": hs, "axis": j.servo_z / np.linalg.norm(j.servo_z), "r0": 4.5, "r1": 9.5, "half": 1.5, "inward": True}))
            Fsum = np.zeros(3)
            for pid2 in order:
                for ld in loads[pid2].loads:
                    if not ld.label.startswith(("carried from", "reaction from")):
                        Fsum = Fsum + ld.F
                Fsum = Fsum + mo.get(pid2, model.parts[pid2].mass_kg) * loads[pid2].g_link
            diag["equilibrium_residual"][j.name] = float(np.linalg.norm(Fsum))
    return loads, diag


def horn_thickness(model: Model, j: JointRec) -> float:
    """Thickness (mm) of the horn disc of joint j along the axis (the plate sits on top of it: the horn reaction acts on the plate underside)."""
    h = model.parts.get(f"horn_{j.name}")
    if h is None:
        return 3.0
    a = j.servo_z / np.linalg.norm(j.servo_z)
    ext = np.asarray(h.mesh.vertices) @ a
    return float(ext.max() - ext.min())


def fk0_origin(model: Model, link: str) -> np.ndarray:
    """Interfaces-world origin of the link frame at the zero pose (interfaces.yaml coordinates; the assembly world is shifted by if_offset)."""
    return model.fk({})[link][1] + model.if_offset


def fk0_to_link(model: Model, p_world0: np.ndarray, link: str) -> np.ndarray:
    return p_world0 - fk0_origin(model, link)


def edge_of(model: Model, topo: Topology, child: str, parent: str) -> Edge:
    key = tuple(sorted((child, parent)))
    cache = getattr(topo, "_edge_cache", None)
    if cache is None:
        cache = topo._edge_cache = {}
    if key not in cache:
        sites = topo.edges.get(key, [])
        pts = np.array([s.p for s in sites]) if sites else model.parts[child].com[None, :]
        cache[key] = Edge(child, parent, sites, pts.mean(axis=0))
    ed = cache[key]
    # an edge object is re-used between scenarios: keep the child/parent orientation of the call
    ed.child, ed.parent = child, parent
    return ed
