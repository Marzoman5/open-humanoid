"""Assembly access check (design for assembly).

For every screw, a straight tool corridor (a cylinder along the screw axis, hex-key/driver size from components/data) must be
free of geometry at the moment the screw is installed; for every part there must be a straight insertion path into its final position
against what is already assembled. From those two kinds of constraint the checker derives an assembly ORDER (a precedence graph,
topologically sorted, then simulated step by step) and a subassembly tree (parts grouped by kinematic link, each link also tested as a
bench subassembly). Parts that cannot be assembled in any order, and fasteners that can never be reached, are flagged.

Model assumptions (stated so the result is read correctly):
* a part moves into place by a pure translation along a world axis or one of its own screw axes (no rotation, no snap-in);
* a screw is installed right after the later of its two parts is placed (later never has fewer obstructions);
* heat-set inserts and magnets are installed before assembly (they are listed as prep steps, not corridor-checked);
* `Assembly.allowed_pairs` contacts/overlaps (press fits, servo in pocket) do not block the path unless the overlap grows.

API:  plan = access.analyse(asm, q=None)  ->  dict with "ok", "order", "subassemblies", "unreachable_screws", "stuck_parts",
      "serviceability". `access.summarize(plan)` is the printable report.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import build123d as bd

from .assembly import Assembly, Placed
from .core import Site, axis_of, bboxes_overlap, bbox_tuple, overlap_volume

CLASH = 2.0
PATH_LEN = 90.0
PATH_STEP = 2.0
AXES = [(0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)]


def _manifold(shape: bd.Shape):
    """manifold3d solid from a tessellation (0.1 mm); about 35x faster than an OCC common on these brackets. None if the tessellation
    is not a closed manifold (caller falls back to OCC)."""
    import manifold3d as m3d
    import numpy as np

    from .core import mesh_of

    m = mesh_of(shape, tol=0.1)
    man = m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(m.vertices, dtype=np.float32), tri_verts=np.asarray(m.faces, dtype=np.uint32)))
    return None if man.is_empty() else man


@dataclass
class Unit:
    id: str
    shapes: list[bd.Shape]
    parts: list[str]
    link: str | None = None
    _mans: list | None = field(default=None, repr=False)

    def bbox(self):
        bbs = [bbox_tuple(s) for s in self.shapes]
        lo = tuple(min(b[0][i] for b in bbs) for i in range(3))
        hi = tuple(max(b[1][i] for b in bbs) for i in range(3))
        return lo, hi

    def mans(self):
        if self._mans is None:
            self._mans = [_manifold(s) for s in self.shapes]
        return self._mans


def _bb_overlap(a, b, pad=0.0) -> bool:
    return all(a[0][i] - pad <= b[1][i] and b[0][i] - pad <= a[1][i] for i in range(3))


def _swept_bbox(bb, d, length):
    lo, hi = bb
    lo2 = tuple(lo[i] + d[i] * length for i in range(3))
    hi2 = tuple(hi[i] + d[i] * length for i in range(3))
    return tuple(min(lo[i], lo2[i]) for i in range(3)), tuple(max(hi[i], hi2[i]) for i in range(3))


def _overlap(ma, sa, mb, sb, dx=(0.0, 0.0, 0.0)) -> float:
    """Overlap volume of body a (moved by dx) with body b. Manifold meshes when both exist, OCC otherwise."""
    if ma is not None and mb is not None:
        return float((ma.translate(dx) ^ mb).volume()) if any(dx) else float((ma ^ mb).volume())
    return overlap_volume(bd.Location(dx) * sa if any(dx) else sa, sb)


def path_blocked_by(mover: Unit, d, static: Unit, mate_overlap: bool, length: float = PATH_LEN, step: float = PATH_STEP) -> bool:
    """Does moving `mover` from its final pose by t*d (t in (0, length]) hit `static`? Final-pose overlap (a designed press fit) only
    counts as blocking if it grows."""
    if not _bb_overlap(_swept_bbox(mover.bbox(), d, length), static.bbox(), 0.0):
        return False
    mm, sm = mover.mans(), static.mans()
    base = 0.0
    if mate_overlap:
        base = sum(max(_overlap(mm[i], mover.shapes[i], sm[k], static.shapes[k]), 0.0) for i in range(len(mm)) for k in range(len(sm))
                   if bboxes_overlap(mover.shapes[i], static.shapes[k]))
    bbs = [bbox_tuple(s) for s in mover.shapes]
    sbs = [bbox_tuple(s) for s in static.shapes]
    t = step
    while t <= length + 1e-9:
        dx = (d[0] * t, d[1] * t, d[2] * t)
        for i, bm in enumerate(bbs):
            moved_bb = (tuple(bm[0][j] + dx[j] for j in range(3)), tuple(bm[1][j] + dx[j] for j in range(3)))
            for k, sb in enumerate(sbs):
                if not _bb_overlap(moved_bb, sb):
                    continue
                if _overlap(mm[i], mover.shapes[i], sm[k], static.shapes[k], dx) > max(CLASH, base + CLASH):
                    return True
        t += step
    return False


def free_directions(mover: Unit, statics: list[Unit], allowed: set[frozenset], dirs: list) -> list:
    out = []
    for d in dirs:
        blocked = False
        for s in statics:
            if path_blocked_by(mover, d, s, any(frozenset((a, b)) in allowed for a in mover.parts for b in s.parts)):
                blocked = True
                break
        if not blocked:
            out.append(d)
    return out


def _unit_dirs(unit: Unit, sites: list[Site]) -> list:
    dirs = list(AXES)
    for s in sites:
        if s.part in unit.parts and s.kind == "screw":
            _, z = axis_of(s.frame)
            v = (-z.X, -z.Y, -z.Z)          # a part moves along the direction its screw travels: opposite to the tool side
            if not any(max(abs(v[i] - e[i]) for i in range(3)) < 1e-3 for e in dirs):
                dirs.insert(0, v)
    return dirs


def corridor_blockers(site: Site, units: dict[str, Unit], owner_unit: str) -> list[str]:
    cor = site.corridor()
    cm = _manifold(cor)
    out = []
    for uid, u in units.items():
        sh, ms = u.shapes, u.mans()
        for s, m in zip(sh, ms):
            if not bboxes_overlap(cor, s):
                continue
            if _overlap(cm, cor, m, s) > CLASH * 0.5:
                out.append(uid)
                break
    return out


def _plan(units: dict[str, Unit], sites: list[Site], allowed: set, link_rank: dict, uid_list: list[str]) -> dict:
    """Precedence graph -> topological order -> step-by-step simulation, for the given units only."""
    before: dict[str, set[str]] = {u: set() for u in units}
    reasons: dict[tuple[str, str], str] = {}

    def add(a_before: str, b_after: str, why: str):
        if a_before == b_after:
            return
        before[b_after].add(a_before)
        reasons.setdefault((a_before, b_after), why)

    # path-based precedence: v needs a free direction; if a lone neighbour u kills them all, v must come before u
    for v in uid_list:
        dirs = _unit_dirs(units[v], sites)
        near = [u for u in uid_list if u != v and _bb_overlap(units[v].bbox(), units[u].bbox(), PATH_LEN)]
        for u in near:
            if not free_directions(units[v], [units[u]], allowed, dirs):
                add(v, u, f"{u} would block every insertion path of {v}")
    # fastener corridors: whatever blocks a corridor must come after the screw is installed (after both parts)
    unreachable = []
    for s in sites:
        if s.kind != "screw" or not s.needs_access or s.part not in units:
            continue
        owner = s.part
        mate = s.mates if s.mates in units else None
        for b in corridor_blockers(s, units, owner):
            if b == owner or b == mate:
                unreachable.append({"site": s.id, "part": owner, "mate": mate, "blocked_by": b,
                                    "why": "the part itself / its mate covers the tool corridor"})
                continue
            add(owner, b, f"{b} blocks the tool corridor of screw {s.id} on {owner}")
            if mate:
                add(mate, b, f"{b} blocks the tool corridor of screw {s.id} (mate {mate})")
    # topological order (soft preference: keep each link's parts together, parents first)
    key = lambda u: (link_rank.get(units[u].link, 99), uid_list.index(u))  # noqa: E731
    order, done, remaining = [], set(), set(uid_list)
    cyc: list[str] = []
    while remaining:
        ready = sorted([u for u in remaining if before[u] <= done], key=key)
        if not ready:
            cyc = sorted(remaining)
            break
        pick = ready[0]
        for u in ready:           # adjacency preference: a ready unit touching the assembled set
            if not done or any(_bb_overlap(units[u].bbox(), units[d].bbox(), 0.6) for d in done):
                pick = u
                break
        order.append(pick)
        done.add(pick)
        remaining.discard(pick)
    # simulate the order against the real assembled set
    steps, stuck, assembled = [], [], []
    installed: set[str] = set()
    for uid in order:
        dirs = _unit_dirs(units[uid], sites)
        fd = free_directions(units[uid], [units[a] for a in assembled], allowed, dirs) if assembled else dirs
        st = {"step": len(steps) + 1, "part": uid, "link": units[uid].link,
              "move": [round(x, 3) for x in fd[0]] if fd else None, "free_dirs": len(fd), "screws": [], "blocked_screws": []}
        if not fd:
            stuck.append({"part": uid, "why": "no straight insertion path against the assembled set", "assembled_before": list(assembled)})
        assembled.append(uid)
        cur = {a: units[a] for a in assembled}
        for s in sites:
            if s.kind != "screw" or not s.needs_access or s.part not in units or f"{s.part}:{s.id}" in installed:
                continue
            mate = s.mates if s.mates in units else None
            if s.part in cur and (mate is None or mate in cur):
                installed.add(f"{s.part}:{s.id}")
                bl = [b for b in corridor_blockers(s, cur, s.part) if b not in (s.part, mate)]
                (st["blocked_screws"] if bl else st["screws"]).append({"site": s.id, "blocked_by": bl} if bl else s.id)
        steps.append(st)
    return {"order": order, "steps": steps, "stuck": stuck, "cyc": cyc, "unreachable": unreachable, "reasons": reasons,
            "ok": not stuck and not cyc and not unreachable}


def analyse(asm: Assembly, q: dict[str, float] | None = None, *, by_link: bool = True) -> dict:
    """Derive the assembly order and check every screw corridor and every insertion path at pose q.
    Shaft pieces (the servo's rotating output) are integral with the servo and not planned as separate parts."""
    pl = [p for p in asm.placed(q) if not p.part.hardware and not p.part.keepout and p.part.kind != "shaft"]
    units = {p.part.id: Unit(p.part.id, [p.shape], [p.part.id], p.link) for p in pl}
    sites = [s for _, s in asm.world_sites(q) if s.part in units]
    allowed = set(asm.allowed_pairs)
    link_rank = {ln: i for i, ln in enumerate(asm.links)}
    uid_list = list(units)
    res = _plan(units, sites, allowed, link_rank, uid_list)
    order = res["order"]
    # final-state serviceability
    serviceability = []
    for s in sites:
        if s.kind == "screw" and s.needs_access:
            bl = [b for b in corridor_blockers(s, units, s.part) if b != s.part]
            serviceability.append({"site": f"{s.part}:{s.id}", "serviceable_assembled": not bl, "blocked_by": bl})
    # subassembly tree: each link also has to go together on the bench (its own parts only)
    sub = {}
    for ln in asm.links:
        ids = [p.part.id for p in pl if p.link == ln]
        if not ids:
            continue
        bench = {"parts": ids, "order": [u for u in order if u in ids]}
        if by_link:
            loc = {i: units[i] for i in ids}
            r = _plan(loc, [s for s in sites if s.part in loc], allowed, link_rank, ids)
            bench["bench_assemblable"] = r["ok"]
            if not r["ok"]:
                bench["bench_problems"] = {"stuck": [x["part"] for x in r["stuck"]], "cyclic": r["cyc"],
                                           "unreachable": [f"{u['part']}:{u['site']}" for u in r["unreachable"]]}
        sub[ln] = bench
    tree = {ln: {"parent": L.parent, "parts": sub.get(ln, {}).get("order", [])} for ln, L in asm.links.items()}
    return {"ok": res["ok"], "order": res["steps"], "subassemblies": sub, "tree": tree, "stuck_parts": res["stuck"], "cyclic_parts": res["cyc"],
            "unreachable_screws": res["unreachable"], "serviceability": serviceability, "n_parts": len(units),
            "precedence": [{"before": a, "after": b, "why": w} for (a, b), w in res["reasons"].items()],
            "prep": [{"site": f"{s.part}:{s.id}", "kind": s.kind, "thread": s.thread} for s in sites if s.kind in ("insert", "magnet")]}


def summarize(plan: dict) -> str:
    lines = [f"assembly access: {'PASS' if plan['ok'] else 'FAIL'} ({plan['n_parts']} parts)"]
    lines.append("  assembly order (subassembly = link):")
    cur = None
    for s in plan["order"]:
        if s["link"] != cur:
            cur = s["link"]
            b = plan["subassemblies"].get(cur, {})
            lines.append(f"   [{cur}]  bench-assemblable: {b.get('bench_assemblable', '?')}"
                         + (f"  PROBLEMS {b['bench_problems']}" if b.get("bench_problems") else ""))
        mv = s["move"]
        extra = ""
        if s["screws"]:
            extra += f"  screws: {', '.join(s['screws'])}"
        for b in s["blocked_screws"]:
            extra += f"  BLOCKED screw {b['site']} by {b['blocked_by']}"
        lines.append(f"     {s['step']:2d}. {s['part']:34s} move {mv}{extra}")
    for u in plan["unreachable_screws"]:
        lines.append(f"  UNREACHABLE screw {u['site']} on {u['part']}: {u['why']} ({u['blocked_by']})")
    for u in plan["stuck_parts"]:
        lines.append(f"  STUCK {u['part']}: {u['why']}")
    if plan["cyclic_parts"]:
        lines.append(f"  NO VALID ORDER (precedence cycle) among: {', '.join(plan['cyclic_parts'])}")
        for p in plan["precedence"]:
            if p["before"] in plan["cyclic_parts"] and p["after"] in plan["cyclic_parts"]:
                lines.append(f"     {p['before']} before {p['after']}: {p['why']}")
    n_serv = sum(1 for s in plan["serviceability"] if not s["serviceable_assembled"])
    lines.append(f"  serviceability: {n_serv} of {len(plan['serviceability'])} screws are not reachable once fully assembled")
    return "\n".join(lines)
