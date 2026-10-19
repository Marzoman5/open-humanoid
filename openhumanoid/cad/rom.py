"""Range-of-motion sweep: step every joint through its range, and the coupled poses (squat, wave, pickup), and report which parts
collide with which and at what joint angle. Replaces eyeballing renders for "does it move without hitting itself".

Only part pairs that change relative position are tested: for a joint, parts in the moved subtree against everything else.
Contacts that exist by design (`Assembly.allowed_pairs`) and hardware are ignored. A collision is an overlap above CLASH_MM3;
the onset angle is refined by bisection (default 0.25 deg). Clearance is optional (`gap_check=True`): the first angle at which
the minimum distance drops below dfm `moving_gap_min_mm`.

Result per joint: {"limit_pos": deg or None, "limit_neg": deg or None, "within_spec": bool, "collisions": [{...}]}.
`limit_*` is the last collision-free angle in that direction (None = free over the whole spec range). `within_spec` is False when a
collision happens inside the range the spec requires (the design must be fixed, not the spec).
"""
from __future__ import annotations

import math

from . import dfm
from .assembly import Assembly, Placed
from .core import bboxes_overlap, min_distance, overlap_volume
from .geometry_gate import CLASH_MM3

# fraction of the joint range in each named coupled pose (by base joint name); "match_foot" levels the foot.
DEFAULT_POSES = {
    "squat": {"hip_pitch": ("min", 0.8), "knee": ("max", 0.9), "ankle_pitch": "level"},
    "deep_squat": {"hip_pitch": ("min", 1.0), "knee": ("max", 1.0), "ankle_pitch": "level"},
    "step_forward": {"hip_pitch": ("min", 0.4), "knee": ("max", 0.5), "ankle_pitch": "level"},
    "wave": {"shoulder_pitch": ("min", 0.8), "shoulder_roll": ("max", 0.6), "elbow": ("min", 0.5)},
    "pickup": {"hip_pitch": ("min", 0.6), "knee": ("max", 0.7), "ankle_pitch": "level", "shoulder_pitch": ("min", 0.5), "elbow": ("min", 0.6)},
    "split_stance": {"hip_roll": ("max", 0.7), "ankle_roll": ("min", 0.5)},
    "twist": {"hip_yaw": ("max", 0.8), "neck_yaw": ("max", 0.8)},
}


def _base(name: str) -> str:
    return name[:-2] if name.endswith(("_l", "_r")) else name


def pose_angles(asm: Assembly, pose: dict | str, side: str | None = None) -> dict[str, float]:
    """Joint angles (rad) of a named pose for every joint the assembly has (`side` = "l"/"r"/None = both)."""
    spec = DEFAULT_POSES[pose] if isinstance(pose, str) else pose
    joints = asm.joints()
    q: dict[str, float] = {}
    for name, j in joints.items():
        b = _base(name)
        if side and not name.endswith("_" + side):
            continue
        if b not in spec or spec[b] == "level":
            continue
        which, frac = spec[b]
        lo, hi = j["range"]
        deg = (hi if which == "max" else lo) * frac
        q[name] = math.radians(deg)
    # levelling joints: cancel the pitch sum of the chain so the foot stays flat
    for name, j in joints.items():
        b = _base(name)
        if side and not name.endswith("_" + side):
            continue
        if spec.get(b) == "level":
            sfx = name[-2:] if name.endswith(("_l", "_r")) else ""
            tot = sum(v for k, v in q.items() if _base(k) in ("hip_pitch", "knee") and k.endswith(sfx))
            lo, hi = (math.radians(x) for x in j["range"])
            q[name] = min(max(-tot, lo), hi)
    return q


def _moving_sets(asm: Assembly, joint: str) -> tuple[set[str], set[str]]:
    """(links that move with the joint, all others)."""
    ln = asm.joints()[joint]["link"]
    moved = asm.subtree(ln)
    return moved, set(asm.links) - moved


def _collisions(asm: Assembly, q: dict, moved: set[str] | None, min_mm3: float, gap_check: bool, gap: float) -> list[dict]:
    pl = [p for p in asm.placed(q) if not p.part.hardware]
    out = []
    n = len(pl)
    for i in range(n):
        for k in range(i + 1, n):
            a, b = pl[i], pl[k]
            if moved is not None and not ((a.link in moved) != (b.link in moved)):
                continue
            if a.link == b.link:
                continue
            if frozenset((a.part.id, b.part.id)) in asm.allowed_pairs:
                continue
            if not bboxes_overlap(a.shape, b.shape, gap if gap_check else 0.0):
                continue
            v = overlap_volume(a.shape, b.shape)
            if v > min_mm3:
                out.append({"a": a.part.id, "b": b.part.id, "mm3": round(v, 1), "kind": "clash"})
            elif gap_check and v >= 0 and min_distance(a.shape, b.shape) < gap:
                out.append({"a": a.part.id, "b": b.part.id, "mm3": 0.0, "kind": "tight"})
    return out


def sweep_joint(asm: Assembly, joint: str, *, step_deg: float = 5.0, base_pose: dict | None = None, min_mm3: float = CLASH_MM3,
                refine_deg: float = 0.25, gap_check: bool = False) -> dict:
    j = asm.joints()[joint]
    lo, hi = j["range"]
    moved, _ = _moving_sets(asm, joint)
    gap = float(dfm.load_dfm()["moving_gap_min_mm"]["v"])
    base = dict(base_pose or {})
    out = {"joint": joint, "range_deg": [lo, hi], "limit_pos": None, "limit_neg": None, "collisions": [], "within_spec": True}

    def hits(angle_deg: float) -> list[dict]:
        q = {**base, joint: math.radians(angle_deg)}
        return _collisions(asm, q, moved, min_mm3, gap_check, gap)

    if hits(0.0):
        out["collisions"].append({"angle_deg": 0.0, "pairs": hits(0.0), "note": "collides at the zero pose"})
        out["limit_pos"] = out["limit_neg"] = 0.0
        out["within_spec"] = False
        return out
    for direction, end, key in ((1, hi, "limit_pos"), (-1, lo, "limit_neg")):
        if (direction == 1 and end <= 0) or (direction == -1 and end >= 0):
            continue
        last_free, a = 0.0, 0.0
        n = int(math.ceil(abs(end) / step_deg))
        for s in range(1, n + 1):
            a = direction * min(s * step_deg, abs(end))
            h = hits(a)
            if h:
                # bisect between last_free and a
                f, c = last_free, a
                while abs(c - f) > refine_deg:
                    mid = (f + c) / 2
                    if hits(mid):
                        c = mid
                    else:
                        f = mid
                out[key] = round(f, 2)
                out["collisions"].append({"angle_deg": round(c, 2), "direction": "+" if direction > 0 else "-", "pairs": hits(c)})
                if abs(f) < abs(end) - 1e-6:
                    out["within_spec"] = False
                break
            last_free = a
    return out


def sweep_all(asm: Assembly, joints: list[str] | None = None, **kw) -> dict:
    names = joints or list(asm.joints())
    res = {n: sweep_joint(asm, n, **kw) for n in names}
    return {"assembly": asm.name, "joints": res, "ok": all(r["within_spec"] for r in res.values()),
            "failing": [n for n, r in res.items() if not r["within_spec"]]}


def check_pose(asm: Assembly, pose: dict | str, side: str | None = None, min_mm3: float = CLASH_MM3, gap_check: bool = False) -> dict:
    q = pose_angles(asm, pose, side)
    gap = float(dfm.load_dfm()["moving_gap_min_mm"]["v"])
    h = _collisions(asm, q, None, min_mm3, gap_check, gap)
    return {"pose": pose if isinstance(pose, str) else "custom", "q_deg": {k: round(math.degrees(v), 1) for k, v in q.items()}, "collisions": h,
            "ok": not [c for c in h if c["kind"] == "clash"]}


def summarize(sweep: dict, poses: list[dict] | None = None) -> str:
    lines = [f"ROM sweep: {sweep['assembly']}  ->  {'PASS' if sweep['ok'] else 'FAIL'}"]
    for n, r in sweep["joints"].items():
        lo, hi = r["range_deg"]
        stat = "free over the spec range" if r["within_spec"] else "COLLIDES inside the spec range"
        lim = f"limits [{r['limit_neg']}, {r['limit_pos']}] of spec [{lo}, {hi}]"
        lines.append(f"  {n:16s} {stat}; {lim}")
        for c in r["collisions"]:
            for p in c["pairs"][:6]:
                lines.append(f"      at {c['angle_deg']:+.2f} deg: {p['a']} x {p['b']} ({p['kind']}, {p['mm3']} mm3)")
    for p in poses or []:
        lines.append(f"  pose {p['pose']}: {'ok' if p['ok'] else 'COLLIDES'} {p['q_deg']}")
        for c in p["collisions"][:8]:
            lines.append(f"      {c['a']} x {c['b']} ({c['kind']}, {c['mm3']} mm3)")
    return "\n".join(lines)
