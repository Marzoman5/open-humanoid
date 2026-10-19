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
PATH_LEN = 120.0
PATH_STEP = 3.0
AXES = [(0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)]


@dataclass
class Unit:
    id: str
    shapes: list[bd.Shape]
    parts: list[str]
    link: str | None = None

    def bbox(self):
        bbs = [bbox_tuple(s) for s in self.shapes]
        lo = tuple(min(b[0][i] for b in bbs) for i in range(3))
        hi = tuple(max(b[1][i] for b in bbs) for i in range(3))
        return lo, hi


def _bb_overlap(a, b, pad=0.0) -> bool:
    return all(a[0][i] - pad <= b[1][i] and b[0][i] - pad <= a[1][i] for i in range(3))


def _swept_bbox(bb, d, length):
    lo, hi = bb
    lo2 = tuple(lo[i] + d[i] * length for i in range(3))
    hi2 = tuple(hi[i] + d[i] * length for i in range(3))
    return tuple(min(lo[i], lo2[i]) for i in range(3)), tuple(max(hi[i], hi2[i]) for i in range(3))


def path_blocked_by(mover: Unit, d, static: Unit, mate_overlap: bool, length: float = PATH_LEN, step: float = PATH_STEP) -> bool:
    """Does moving `mover` from its final pose by t*d (t in (0, length]) hit `static`? Final-pose overlap (a designed press fit) only
    counts as blocking if it grows."""
    bbm, bbs = mover.bbox(), static.bbox()
    if not _bb_overlap(_swept_bbox(bbm, d, length), bbs, 0.0):
        return False
    base = 0.0
    if mate_overlap:
        base = sum(overlap_volume(a, b) for a in mover.shapes for b in static.shapes if bboxes_overlap(a, b))
    t = step
    while t <= length + 1e-9:
        loc = bd.Location((d[0] * t, d[1] * t, d[2] * t))
        for m in mover.shapes:
            mm = None
            for s in static.shapes:
                bm = bbox_tuple(m)
                moved_bb = ((bm[0][0] + d[0] * t, bm[0][1] + d[1] * t, bm[0][2] + d[2] * t),
                            (bm[1][0] + d[0] * t, bm[1][1] + d[1] * t, bm[1][2] + d[2] * t))
                if not _bb_overlap(moved_bb, bbox_tuple(s)):
                    continue
                mm = mm or (loc * m)
                v = overlap_volume(mm, s)
                if v > max(CLASH, base + CLASH):
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
    out = []
    for uid, u in units.items():
        for s in u.shapes:
            if not bboxes_overlap(cor, s):
                continue
            if overlap_volume(cor, s) > CLASH * 0.5:
                out.append(uid)
                break
    return out


def analyse(asm: Assembly, q: dict[str, float] | None = None, *, by_link: bool = True) -> dict:
    """Derive the assembly order and check every screw corridor and every insertion path at pose q."""
    pl = [p for p in asm.placed(q) if not p.part.hardware and not p.part.keepout]
    part_link = {p.part.id: p.link for p in pl}
    # units: one per part (the order is part level; the subassembly tree is derived afterwards)
    units = {p.part.id: Unit(p.part.id, [p.shape], [p.part.id], p.link) for p in pl}
    sites = [s for _, s in asm.world_sites(q) if s.part in units]
    allowed = set(asm.allowed_pairs)

    # ---- precedence graph:  before[a] = set of units that must come BEFORE a
    before: dict[str, set[str]] = {u: set() for u in units}
    reasons: dict[tuple[str, str], str] = {}
    problems: list[dict] = []

    def add(a_before: str, b_after: str, why: str):
        if a_before == b_after:
            return
        before[b_after].add(a_before)
        reasons.setdefault((a_before, b_after), why)

    uid_list = list(units)
    # path-based precedence: v needs a free direction; if a lone neighbour u kills them all, v must come before u
    for v in uid_list:
        dirs = _unit_dirs(units[v], sites)
        near = [u for u in uid_list if u != v and _bb_overlap(_swept_bbox(units[v].bbox(), (0, 0, 0), 0), units[u].bbox(), PATH_LEN)]
        for u in near:
            if not free_directions(units[v], [units[u]], allowed, dirs):
                add(v, u, f"{u} would block every insertion path of {v}")
    # fastener corridors: whatever blocks a corridor must come after the screw is installed (after both parts)
    unreachable = []
    for s in sites:
        if s.kind != "screw" or not s.needs_access:
            continue
        owner = s.part
        mate = s.mates if s.mates in units else None
        blockers = [b for b in corridor_blockers(s, units, owner)]
        for b in blockers:
            if b == owner or b == mate:
                unreachable.append({"site": s.id, "part": owner, "mate": mate, "blocked_by": b,
                                    "why": "the part itself / its mate covers the tool corridor"})
                continue
            add(owner, b, f"{b} blocks the tool corridor of screw {s.id} on {owner}")
            if mate:
                add(mate, b, f"{b} blocks the tool corridor of screw {s.id} (mate {mate})")

    # ---- topological order (soft preference: keep each link's parts together, parents first)
    link_rank = {ln: i for i, ln in enumerate(asm.links)}
    key = lambda u: (link_rank.get(units[u].link, 99), uid_list.index(u))  # noqa: E731
    order, done, remaining = [], set(), set(uid_list)
    cyc = []
    while remaining:
        ready = sorted([u for u in remaining if before[u] <= done], key=key)
        if not ready:
            cyc = sorted(remaining)
            break
        # adjacency preference: pick a ready unit touching the assembled set if any
        pick = ready[0]
        for u in ready:
            if not done or any(_bb_overlap(units[u].bbox(), units[d].bbox(), 0.6) for d in done):
                pick = u
                break
        order.append(pick)
        done.add(pick)
        remaining.discard(pick)

    # ---- simulate the order against the real assembled set
    steps, stuck = [], []
    assembled: list[str] = []
    site_by_part: dict[str, list[Site]] = {}
    for s in sites:
        site_by_part.setdefault(s.part, []).append(s)
    installed_sites: set[str] = set()
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
            if s.kind != "screw" or not s.needs_access or f"{s.part}:{s.id}" in installed_sites:
                continue
            mate = s.mates if s.mates in units else None
            if s.part in cur and (mate is None or mate in cur):
                installed_sites.add(f"{s.part}:{s.id}")
                bl = [b for b in corridor_blockers(s, cur, s.part) if b not in (s.part, mate)]
                (st["blocked_screws"] if bl else st["screws"]).append(s.id if not bl else {"site": s.id, "blocked_by": bl})
        steps.append(st)
    # screws whose mate never appears (mates not a part id): install at owner time was handled (mate None)
    # ---- final-state serviceability
    final = {a: units[a] for a in units}
    serviceability = []
    for s in sites:
        if s.kind == "screw" and s.needs_access:
            bl = [b for b in corridor_blockers(s, final, s.part) if b != s.part]
            serviceability.append({"site": f"{s.part}:{s.id}", "serviceable_assembled": not bl, "blocked_by": bl})

    # ---- subassembly tree
    sub = {}
    for ln in asm.links:
        ids = [p.part.id for p in pl if p.link == ln]
        if not ids:
            continue
        bench = {"parts": ids, "order": [u for u in order if u in ids]}
        if by_link:
            bench["bench_assemblable"] = _bench_ok(ids, units, sites, allowed)
        sub[ln] = bench
    tree = {ln: {"parent": L.parent, "parts": sub.get(ln, {}).get("order", [])} for ln, L in asm.links.items()}
    ok = not unreachable and not stuck and not cyc
    return {"ok": ok, "order": steps, "subassemblies": sub, "tree": tree, "stuck_parts": stuck, "cyclic_parts": cyc,
            "unreachable_screws": unreachable, "serviceability": serviceability, "n_parts": len(units),
            "precedence": [{"before": a, "after": b, "why": w} for (a, b), w in reasons.items()],
            "prep": [{"site": f"{s.part}:{s.id}", "kind": s.kind, "thread": s.thread} for s in sites if s.kind in ("insert", "magnet")]}


def _bench_ok(ids: list[str], units: dict[str, Unit], sites: list[Site], allowed) -> bool:
    """Can this link's parts be put together on the bench (no other links present) in some order? Greedy with pairwise blocking."""
    local = {i: units[i] for i in ids}
    dirs0 = {i: _unit_dirs(local[i], sites) for i in ids}
    remaining = set(ids)
    placed: list[str] = []
    guard = 0
    while remaining and guard < 200:
        guard += 1
        progress = False
        for u in sorted(remaining):
            fd = free_directions(local[u], [local[a] for a in placed], allowed, dirs0[u]) if placed else dirs0[u]
            # u must also not trap a part that is still to come: require each remaining part to keep a path against placed+u
            if not fd:
                continue
            trap = False
            for v in remaining:
                if v == u:
                    continue
                if not free_directions(local[v], [local[a] for a in placed + [u]], allowed, dirs0[v]) and \
                        free_directions(local[v], [local[a] for a in placed], allowed, dirs0[v]):
                    trap = True
                    break
            if trap:
                continue
            placed.append(u)
            remaining.discard(u)
            progress = True
            break
        if not progress:
            return False
    return not remaining


def summarize(plan: dict) -> str:
    lines = [f"assembly access: {'PASS' if plan['ok'] else 'FAIL'} ({plan['n_parts']} parts)"]
    lines.append("  assembly order (subassembly = link):")
    cur = None
    for s in plan["order"]:
        if s["link"] != cur:
            cur = s["link"]
            b = plan["subassemblies"].get(cur, {})
            lines.append(f"   [{cur}]  bench-assemblable: {b.get('bench_assemblable', '?')}")
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
