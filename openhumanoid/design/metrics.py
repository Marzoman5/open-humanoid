"""Code-measured rubric numbers (ADR 0010, A5). Numbers come from here, never from a model looking at a picture.

Everything is measured on the fixed-framing orthographic silhouettes (silhouette.py), so a mesh, a profile massing and a
reference all go through the same algorithm. H = subject height; hu = head height. See docs/design-method.md for the
definition of every metric and openhumanoid/design/rubric.yaml for the bands.

Landmarks are *found* in the silhouette (neck = narrowest row under the head, crotch = where the legs separate, ...),
so they work on any humanoid-ish mesh. If joint positions are known (profiles or an MJCF) they override the estimates.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from . import silhouette as sil
from .meshio import Subject

RUBRIC_PATH = Path(__file__).with_name("rubric.yaml")


def load_rubric() -> dict:
    return yaml.safe_load(RUBRIC_PATH.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ row-run utilities
def _runs(row: np.ndarray) -> list[tuple[int, int]]:
    """Connected True runs in a 1-D bool array as (start, end) inclusive, bridging 1-px gaps."""
    idx = np.flatnonzero(row)
    if idx.size == 0:
        return []
    splits = np.flatnonzero(np.diff(idx) > 2)
    starts = np.r_[idx[0], idx[splits + 1]]
    ends = np.r_[idx[splits], idx[-1]]
    return list(zip(starts.tolist(), ends.tolist()))


class Profile:
    """Per-row measurements of a front silhouette, indexed by integer row, in metres via px_per_m."""

    def __init__(self, s: sil.Silhouette):
        self.s = s
        self.mask = s.mask
        ys = np.flatnonzero(self.mask.any(axis=1))
        self.top, self.bottom = int(ys.min()), int(ys.max())
        self.H_px = self.bottom - self.top + 1
        n = sil.CANVAS
        self.total = np.zeros(n)     # overall width of the row (outer extents)
        self.central = np.zeros(n)   # width of the run containing the centre column (trunk), 0 if none
        self.nruns = np.zeros(n, int)
        self.runs: list[list[tuple[int, int]]] = [[] for _ in range(n)]
        cx = sil.CENTER_COL
        # silhouette is bbox-centred, so use the centre of mass of the bbox as the body axis
        cols = np.flatnonzero(self.mask.any(axis=0))
        cx = (cols.min() + cols.max()) / 2
        self.cx = cx
        for r in range(self.top, self.bottom + 1):
            rr = _runs(self.mask[r])
            self.runs[r] = rr
            self.nruns[r] = len(rr)
            if rr:
                self.total[r] = rr[-1][1] - rr[0][0] + 1
                for a, b in rr:
                    if a <= cx <= b:
                        self.central[r] = b - a + 1

    # z fraction of H (0 ground .. 1 top) <-> row
    def row(self, zf: float) -> int:
        return int(round(self.bottom - zf * (self.H_px - 1)))

    def zf(self, row: int) -> float:
        return (self.bottom - row) / (self.H_px - 1)

    def rows(self, z0: float, z1: float) -> np.ndarray:
        a, b = sorted((self.row(z0), self.row(z1)))
        return np.arange(a, b + 1)

    def px(self, v) -> float:
        """pixels -> fraction of H"""
        return v / (self.H_px - 1)

    def leg_widths(self, rows: np.ndarray, side: int = 0) -> np.ndarray:
        """Width (px) of the leg run nearest the centre on the left(+1)/right(-1) side; side 0 = mean of both. NaN when
        the legs are merged or absent."""
        out = []
        for r in rows:
            rr = [x for x in self.runs[r] if not (x[0] <= self.cx <= x[1])]
            left = [x for x in rr if (x[0] + x[1]) / 2 < self.cx]
            right = [x for x in rr if (x[0] + x[1]) / 2 >= self.cx]
            if not left or not right:
                out.append(np.nan)
                continue
            l = max(left, key=lambda x: x[1])      # nearest to the centre
            rg = min(right, key=lambda x: x[0])
            wl, wr = l[1] - l[0] + 1, rg[1] - rg[0] + 1
            out.append({0: (wl + wr) / 2, 1: wr, -1: wl}[side])
        return np.array(out, float)


def _smooth(a: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return a
    pad = np.pad(a, (k // 2, k // 2), mode="edge")
    return np.convolve(pad, np.ones(k) / k, mode="valid")


# ----------------------------------------------------------------------------------------------------- landmarks
def landmarks(P: Profile) -> dict:
    """Find the body landmarks in the front silhouette. All heights are fractions of H."""
    L: dict = {}
    # head width and neck: head = widest central run in the top 22%
    cw = P.central
    top_band = np.arange(P.top, P.top + int(0.11 * P.H_px))
    head_peak_row = int(top_band[np.argmax(cw[top_band])])
    head_w = cw[head_peak_row]
    r = head_peak_row
    while r < P.bottom and (cw[r] <= 1.25 * head_w or r < head_peak_row + 3):
        r += 1
    neck_search = np.arange(head_peak_row, r)
    neck_row = int(neck_search[np.argmin(_smooth(cw[neck_search], 3))])
    neck_w = cw[neck_row]
    thr = neck_w + 0.30 * (head_w - neck_w)
    r = neck_row
    while r > P.top and cw[r] < thr:
        r -= 1
    head_bottom = r                                   # chin
    r = neck_row
    while r < P.bottom and cw[r] < thr and P.nruns[r] >= 1:
        r += 1
    neck_bottom = r                                   # where the shoulders start
    L.update(head_w=head_w, neck_w=neck_w, neck_row=neck_row, head_bottom_row=head_bottom, neck_bottom_row=neck_bottom)
    L["head_h_f"] = P.px(head_bottom - P.top)
    L["neck_len_f"] = P.px(neck_bottom - head_bottom)
    # crotch: lowest row (going down from the waist) where the legs are still joined, i.e. above the first row with
    # no central run; use the first row (from mid-height downward) at which the central run vanishes
    r = P.row(0.55)
    while r < P.bottom and P.central[r] > 0:
        r += 1
    L["crotch_row"] = r
    L["crotch_f"] = P.zf(r)
    return L


def _measure_front(P: Profile, L: dict, joints: dict | None, H_m: float) -> dict:
    M: dict = {}
    f = P.px
    hu_px = L["head_bottom_row"] - P.top
    M["P1_head_height_f"] = L["head_h_f"]
    M["P2_neck_length_hu"] = (L["neck_bottom_row"] - L["head_bottom_row"]) / max(hu_px, 1)
    M["P2_neck_width_ratio"] = L["neck_w"] / max(L["head_w"], 1)
    # shoulder band: from neck base down 0.14 H, widest total (includes deltoids/arms)
    sh_rows = np.arange(L["neck_bottom_row"], min(L["neck_bottom_row"] + int(0.14 * (P.H_px - 1)), P.bottom))
    M["P3_shoulder_width_f"] = f(P.total[sh_rows].max())
    shoulder_w_px = P.total[sh_rows].max()
    shoulder_row = sh_rows[np.argmax(P.total[sh_rows])]
    # waist: narrowest trunk run between the crotch and the shoulders
    cr = L["crotch_row"]
    wr = np.arange(shoulder_row + int(0.05 * P.H_px), cr - int(0.06 * P.H_px))
    wr = wr[P.central[wr] > 0] if len(wr) else wr
    if len(wr):
        wsm = _smooth(P.central[wr], 5)
        waist_row = wr[int(np.argmin(wsm))]
        M["P4_waist_over_shoulder"] = float(wsm.min() / shoulder_w_px)
        L["waist_row"] = int(waist_row)
    else:
        M["P4_waist_over_shoulder"] = None
    # pelvis: widest trunk run in the 10% band above the crotch
    pr = np.arange(cr - int(0.10 * P.H_px), cr)
    pw = P.central[pr].max() if len(pr) else 0
    M["P5_pelvis_over_shoulder"] = float(pw / shoulder_w_px) if pw else None
    # hip and knee heights
    src = "silhouette"
    jh = joints or {}
    hip = next((jh[k] for k in ("hip_l", "hip_pitch_l") if k in jh), None)
    knee = next((jh[k] for k in ("knee_l",) if k in jh), None)
    ankle = next((jh[k] for k in ("ankle_l", "ankle_pitch_l") if k in jh), None)
    if hip is not None:
        M["P6_hip_height_f"] = float(hip[2] / H_m)
        M["P6_source"] = "joint"
    else:
        M["P6_hip_height_f"] = L["crotch_f"] + 0.03
        M["P6_source"] = "crotch+0.03H (estimate)"
    if knee is not None:
        knee_f = float(knee[2] / H_m)
        M["P7_source"] = "joint"
    else:
        rows = P.rows(0.20, 0.34)
        lw = _smooth(P.leg_widths(rows), 5)
        if np.all(np.isnan(lw)):
            knee_f, M["P7_source"] = 0.275, "default"
        else:
            knee_f = P.zf(int(rows[int(np.nanargmin(np.where(np.isnan(lw), 1e9, lw)))]))
            M["P7_source"] = "min leg width (estimate)"
    M["P7_knee_height_f"] = knee_f
    ank_f = float(ankle[2] / H_m) if ankle is not None else None
    L["knee_f"] = knee_f
    L["hip_f"] = M["P6_hip_height_f"]
    L["ankle_f"] = ank_f
    return M


def _leg_taper(P: Profile, L: dict, side_foot_h: float) -> dict:
    M: dict = {}
    top = L["crotch_f"]
    knee = L["knee_f"]
    ankle = L["ankle_f"] if L["ankle_f"] is not None else side_foot_h
    ankle = max(ankle, side_foot_h)

    def mean_w(z0, z1):
        v = P.leg_widths(P.rows(z0, z1))
        return float(np.nanmean(v)) if np.isfinite(v).any() else np.nan

    span = top - knee
    prox_t = mean_w(top - 0.30 * span, top - 0.05 * span)
    dist_t = mean_w(knee + 0.05 * span, knee + 0.30 * span)
    M["P8_thigh_taper_area"] = float((dist_t / prox_t) ** 2) if prox_t == prox_t and dist_t == dist_t else None
    span2 = knee - ankle
    prox_s = np.nanmax(P.leg_widths(P.rows(knee - 0.60 * span2, knee - 0.05 * span2))) if span2 > 0 else np.nan
    dist_s = mean_w(ankle + 0.05 * span2, ankle + 0.25 * span2) if span2 > 0 else np.nan
    M["P8_shank_taper_area"] = float((dist_s / prox_s) ** 2) if prox_s == prox_s and dist_s == dist_s else None
    rows = P.rows(knee, top)
    w = _smooth(P.leg_widths(rows), 5)
    if np.isfinite(w).any():
        wmax_row = rows[int(np.nanargmax(np.where(np.isnan(w), -1, w)))]
        M["P9_thigh_widest_from_top"] = float((P.zf(wmax_row) - knee) / span) if span else None
        M["P9_thigh_widest_from_top"] = 1.0 - M["P9_thigh_widest_from_top"] if M["P9_thigh_widest_from_top"] is not None else None
    else:
        M["P9_thigh_widest_from_top"] = None
    rows = P.rows(ankle, knee)
    w = _smooth(P.leg_widths(rows), 5)
    if np.isfinite(w).any() and span2 > 0:
        r = rows[int(np.nanargmax(np.where(np.isnan(w), -1, w)))]
        M["P9_calf_widest_from_top"] = float(1.0 - (P.zf(r) - ankle) / span2)
    else:
        M["P9_calf_widest_from_top"] = None
    return M


def _measure_side(S: Profile, H_m: float) -> dict:
    """Foot length and height from the side silhouette (bottom rows)."""
    M: dict = {}
    foot_rows = np.arange(S.bottom - int(0.06 * S.H_px), S.bottom + 1)
    base = S.total[foot_rows].max()
    # foot top = the sharpest narrowing of the side silhouette within the bottom 12% (instep -> shank)
    win = max(2, int(0.012 * S.H_px))
    ks = np.arange(int(0.02 * S.H_px), int(0.12 * S.H_px))
    w = _smooth(S.total[S.bottom - ks], 3)
    drop = np.array([S.total[S.bottom - k - win] if False else 0 for k in ks])
    wk = np.array([S.total[S.bottom - k] for k in ks], float)
    wk_up = np.array([S.total[S.bottom - k - win] for k in ks], float)
    drop = wk - wk_up
    j = int(np.argmax(drop))
    foot_h_rows = int(ks[j]) if drop[j] > 0.15 * base else int(0.12 * S.H_px)
    M["P10_foot_length_f"] = S.px(base)
    M["P10_foot_height_f"] = S.px(foot_h_rows)
    return M


def _edge_steps(P: Profile, z0=0.05, z1=0.96, thr_f=0.006) -> dict:
    """G0 breaks in the outer silhouette: rows where an outer edge jumps sideways by more than thr_f*H between adjacent
    rows (a horizontal ledge). Smooth silhouettes have none; box-on-box silhouettes have many. Consecutive rows merge."""
    rows = P.rows(z0, z1)
    thr = thr_f * P.H_px
    steps = 0
    last_row = -99
    total_px = 0.0
    for r in rows[1:]:
        a, b = P.runs[r], P.runs[r - 1]
        if not a or not b:
            continue
        # compare run edges against the overlapping run in the previous row
        jump = 0.0
        for (x0, x1) in a:
            ov = [(p0, p1) for (p0, p1) in b if p0 <= x1 and p1 >= x0]
            if ov:
                jump = max(jump, abs(x0 - min(o[0] for o in ov)), abs(x1 - max(o[1] for o in ov)))
        if jump > thr:
            total_px += jump
            if r - last_row > 2:
                steps += 1
            last_row = r
    return {"S3_ledge_count": steps, "S3_ledge_total_f": float(total_px / P.H_px)}


def _bumps(P: Profile, z0=0.06, z1=0.60, prom_f=0.012) -> int:
    """Count local extrema pairs in the single-leg width profile deeper than prom_f*H (unintended bumps)."""
    rows = P.rows(z0, z1)
    w = P.leg_widths(rows)
    w = _smooth(np.where(np.isnan(w), np.nanmean(w) if np.isfinite(w).any() else 0, w), 9)
    d = np.diff(w)
    sign = np.sign(np.where(np.abs(d) < 0.02, 0, d))
    sign = sign[sign != 0]
    ext = 0
    if len(sign) > 1:
        flips = np.flatnonzero(np.diff(sign) != 0)
        # prominence filter
        pts = [w[0]] + [w[i + 1] for i in flips] + [w[-1]]
        ext = sum(1 for a, b in zip(pts[:-1], pts[1:]) if abs(a - b) > prom_f * P.H_px)
    return int(ext)


def planar_patches(mesh, tol_cells: int = 8) -> list[float]:
    """Areas (m^2) of connected near-planar patches: faces whose normals fall in the same ~7 degree bin and are adjacent."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    n = np.asarray(mesh.face_normals)
    key = np.round(n * tol_cells).astype(int)
    code = (key[:, 0] + 100) * 40000 + (key[:, 1] + 100) * 200 + (key[:, 2] + 100)
    adj = np.asarray(mesh.face_adjacency)
    same = code[adj[:, 0]] == code[adj[:, 1]]
    a = adj[same]
    nf = len(n)
    g = coo_matrix((np.ones(len(a)), (a[:, 0], a[:, 1])), shape=(nf, nf))
    _, comp = connected_components(g, directed=False)
    areas = np.bincount(comp, weights=np.asarray(mesh.area_faces))
    return areas.tolist()


def _flatness(subject: Subject, H: float) -> dict:
    amin = 0.002 * H * H            # ~22 x 22 mm at H = 0.5 m: a patch worth calling a flat face
    tot_area = flat_area = 0.0
    worst = 0.0
    for name, m in subject.parts.items():
        if len(m.faces) < 8:
            continue
        areas = np.array(planar_patches(m))
        a = float(m.area)
        big = areas[areas >= amin]
        tot_area += a
        flat_area += float(big.sum())
        if a > 0.001 * H * H:
            worst = max(worst, float(big.max() / a) if len(big) else 0.0)
    return {"S4_flat_area_fraction": flat_area / tot_area if tot_area else 0.0, "S4_worst_part_flat_fraction": worst}


def _manifold_ok(meshes: dict) -> str:
    """manifold3d accepts the mesh as a valid 2-manifold (what its booleans need): 'n/m' of the parts, or 'n/a' if missing."""
    try:
        import manifold3d as mf
    except ImportError:
        return "n/a (manifold3d not installed)"
    ok = 0
    for m in meshes.values():
        try:
            mm = mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
            ok += int(mm.status() == mf.Error.NoError)
        except Exception:
            pass
    return f"{ok}/{len(meshes)}"


def _printability(subject: Subject, bed_m=(0.22, 0.22, 0.25)) -> dict:
    M: dict = {}
    meshes = {subject.name: subject.whole} if subject.whole is not None else subject.parts
    M["M1_watertight_parts"] = f"{sum(1 for m in meshes.values() if m.is_watertight)}/{len(meshes)}"
    over = [k for k, m in meshes.items() if sorted(m.extents)[0] > min(bed_m) * 5 or max(m.extents) > 3 * max(bed_m)]
    M["M1_manifold3d_valid"] = _manifold_ok(meshes)
    M["M1_parts_over_bed"] = over if subject.height_m <= 1.0 else "n/a (height > 1 m)"
    M["M1_not_computed"] = ["wall_thickness", "step_roundtrip", "frame_clearance", "rom_sweep"]
    M["M1_not_computed_reason"] = "needs the frame/servo model and the CAD geometry gate (T-0004 / cad check); not derivable from an outer mesh"
    return M


def hardware_visible_fraction(subject: Subject) -> dict | None:
    """S5: fraction of silhouette-interior pixels, in the front and side views, whose frontmost surface belongs to a
    hardware part (servo/frame/horn). Needs a labelled mesh set; None otherwise."""
    classes = subject.classes
    if not any(v == "hardware" for v in classes.values()):
        return None
    res = {}
    for view in ("front", "side"):
        res[view] = _visible_class_fraction(subject, view)
    return {"S5_hardware_visible_fraction_front": res["front"], "S5_hardware_visible_fraction_side": res["side"]}


def _visible_class_fraction(subject: Subject, view: str) -> float:
    """Painter's-algorithm raster of triangles sorted by depth, colour = class. Cheap and exact enough for a fraction."""
    from PIL import Image, ImageDraw

    H = subject.height_m
    s = sil.H_PX / H
    allv = np.vstack([m.bounds for m in subject.parts.values()])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    k = 1 if view == "front" else 0
    cx = (lo[k] + hi[k]) / 2
    tris, depth, cls = [], [], []
    for name, m in subject.parts.items():
        px = sil._project(np.asarray(m.vertices), view, s, cx)
        t = px[np.asarray(m.faces)]
        tris.append(t)
        dax = 0 if view == "front" else 1
        dv = np.asarray(m.vertices)[:, dax][np.asarray(m.faces)].mean(axis=1)
        depth.append(dv if view == "front" else -dv)   # front: nearer = larger x; side from -y: nearer = smaller y
        cls.append(np.full(len(t), 2 if subject.classes.get(name) == "hardware" else 1))
    tris, depth, cls = np.vstack([t for t in tris]), np.concatenate(depth), np.concatenate(cls)
    order = np.argsort(depth)       # far first, near drawn last
    img = Image.new("L", (sil.CANVAS, sil.CANVAS), 0)
    d = ImageDraw.Draw(img)
    for i in order:
        t = tris[i]
        d.polygon([tuple(t[0]), tuple(t[1]), tuple(t[2])], fill=int(cls[i]))
    a = np.asarray(img)
    vis = (a > 0).sum()
    return float((a == 2).sum() / vis) if vis else 0.0


# ------------------------------------------------------------------------------------------------------------- main
def compute(subject: Subject, ref_masks: dict | None = None, approved: Subject | None = None) -> dict:
    """All code-measured metrics for a subject. `ref_masks`: {name: normalised front mask} for S2; `approved`: the
    approved D1 subject for S1."""
    H = subject.height_m
    meshes = list(subject.render_meshes.values())
    front = sil.rasterise(meshes, "front", H)
    side = sil.rasterise(meshes, "side", H)
    P, S = Profile(front), Profile(side)
    L = landmarks(P)
    M = _measure_front(P, L, subject.joints, H)
    side_m = _measure_side(S, H)
    M.update(side_m)
    M.update(_leg_taper(P, L, side_m["P10_foot_height_f"]))
    M.update(_edge_steps(P))
    M["S3_leg_bumps"] = _bumps(P)
    M.update(_flatness(subject, H))
    hw = hardware_visible_fraction(subject)
    if hw:
        M.update(hw)
    M.update(_printability(subject))
    cand_n = sil.normalise_mask(front.mask)
    cand_side_n = sil.normalise_mask(side.mask)
    if ref_masks:
        M["S2_iou_front_vs_refs"] = {k: round(sil.iou(cand_n, v), 4) for k, v in ref_masks.items()}
    if approved is not None:
        am = [sil.normalise_mask(sil.rasterise(list(approved.render_meshes.values()), v, approved.height_m).mask) for v in ("front", "side")]
        M["S1_iou_front"] = sil.iou(cand_n, am[0])
        M["S1_iou_side"] = sil.iou(cand_side_n, am[1])
    if subject.hard_points and subject.profiles:
        from .massing import hard_point_margins
        hp = hard_point_margins(subject.profiles)
        M["HP_hard_points"] = hp
        M["HP_all_enclosed_with_margin"] = all(h["pass"] for h in hp)
    M["height_m"] = H
    M["head_unit_m"] = L["head_h_f"] * H
    M["landmarks_f"] = {"crotch": L["crotch_f"], "knee": L["knee_f"], "hip": L["hip_f"],
                        "neck_bottom": P.zf(L["neck_bottom_row"]), "head_bottom": P.zf(L["head_bottom_row"])}
    return _round(M)


def _round(o):
    if isinstance(o, dict):
        return {k: _round(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if o != o else round(float(o), 4)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


# ------------------------------------------------------------------------------------------------------ verdicts
def evaluate(metrics: dict, rubric: dict | None = None) -> dict:
    """Compare measured numbers with the rubric bands. Returns {id: {value, band, verdict, ...}} + a summary.
    verdict: PASS / FAIL / NA (not measurable here)."""
    rubric = rubric or load_rubric()
    out = {}
    for item in rubric["metrics"]:
        key = item["key"]
        v = metrics.get(key)
        if v is None or isinstance(v, (str, dict, list)):
            out[item["id"]] = {"key": key, "value": v, "band": item["band"], "verdict": "NA", "name": item["name"]}
            continue
        lo, hi = item["band"]
        ok = (lo is None or v >= lo) and (hi is None or v <= hi)
        out[item["id"]] = {"key": key, "value": v, "band": item["band"], "verdict": "PASS" if ok else "FAIL", "name": item["name"]}
    scored = [x for x in out.values() if x["verdict"] != "NA"]
    n_pass = sum(1 for x in scored if x["verdict"] == "PASS")
    return {"criteria": out, "n_pass": n_pass, "n_scored": len(scored),
            "pass_fraction": round(n_pass / len(scored), 3) if scored else None,
            "failed": [k for k, x in out.items() if x["verdict"] == "FAIL"]}


def write_report(subject: Subject, out_path: str | Path, **kw) -> dict:
    m = compute(subject, **kw)
    ev = evaluate(m)
    rep = {"generated_by": "oh design metrics (openhumanoid/design/metrics.py)", "subject": subject.name,
           "source": subject.source, "measured": m, "evaluation": ev,
           "rubric": str(RUBRIC_PATH.name), "note": "bands are calibration-pending starting values; see docs/design-method.md#calibration"}
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    return rep
