"""Bake-off renders on the committed studio rig (openhumanoid/design/rig.yaml): clay + SSAO + 3-point light, zebra, the
orthographic silhouettes with the TARGET outline overlaid, knee-flexion poses, and one review sheet per design.

The rig's whole-body bits (head-unit grid, equal-height lineup) are not used: the subject here is one leg segment.
Units in: mm (knee-axis frame). Units out: PNG.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..meshio import Subject
from ..studio import _font, load_rig, render_clay
from .spec import LegSpec


def rotate_shank(mesh, theta_deg: float):
    """Rotate a shank mesh about the knee axis (y through the origin) by `theta` flexion (foot swings backwards)."""
    t = np.radians(theta_deg)
    c, s = np.cos(t), np.sin(t)
    R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    m = mesh.copy()
    m.vertices = np.asarray(m.vertices) @ R.T
    return m


def posed(parts: dict, theta_deg: float) -> dict:
    return {k: (rotate_shank(m, theta_deg) if k.startswith("shank") else m) for k, m in parts.items()}


def to_subject(parts_mm: dict, name: str, ref_parts_mm: dict | None = None) -> Subject:
    """Metres, centred on x=y=0 and standing on z=0 using the straight pose of `ref_parts_mm` (default: the parts)."""
    ref = ref_parts_mm or parts_mm
    lo = np.min([m.bounds[0] for m in ref.values()], axis=0)
    hi = np.max([m.bounds[1] for m in ref.values()], axis=0)
    shift = np.array([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    out = {}
    for k, m in parts_mm.items():
        m = m.copy()
        m.apply_translation(shift)
        m.apply_scale(0.001)
        out[k] = m
    return Subject(name, out, float((hi[2] - lo[2]) * 0.001), None, {}, [], "bakeoff", {k: "shell" for k in out})


def smooth_vertex_normals(mesh, iters: int = 12, angle_deg: float = 35.0) -> np.ndarray:
    """Vertex normals averaged over neighbours whose normals are within `angle_deg` (sharp creases stay sharp). Used for
    the zebra pass so tessellation noise (B-rep triangulation, marching cubes) does not read as bad surface quality."""
    N = np.asarray(mesh.vertex_normals, float).copy()
    e = mesh.edges_unique
    a, b = e[:, 0], e[:, 1]
    c = np.cos(np.radians(angle_deg))
    for _ in range(iters):
        ok = (N[a] * N[b]).sum(1) > c
        acc = N.copy()
        np.add.at(acc, a[ok], N[b[ok]])
        np.add.at(acc, b[ok], N[a[ok]])
        N = acc / (np.linalg.norm(acc, axis=1, keepdims=True) + 1e-12)
    return N


def clay(parts_mm: dict, out: Path, view: str, name: str, zebra: bool = False, theta: float = 0.0, ref_parts_mm=None, size=None) -> Path:
    subj = to_subject(posed(parts_mm, theta), name, ref_parts_mm or parts_mm)
    if zebra:
        for m in subj.parts.values():
            m.metadata["sdf_normals"] = smooth_vertex_normals(m)
    return render_clay(subj, view, out, load_rig(), zebra=zebra, size=size)


def target_masks(spec: LegSpec, px_per_mm: float = 2.0, margin: float = 6.0):
    """Analytic target silhouettes (front = y-z, side = x-z) on a common canvas, plus the canvas origin. Cached per spec."""
    from .evaluate import target_silhouettes
    return target_silhouettes(spec, px_per_mm, margin)


def _overlay(mask_c: np.ndarray, mask_t: np.ndarray, title: str, px_per_mm: float):  # noqa: ARG001
    from PIL import Image, ImageDraw
    from scipy.ndimage import binary_dilation

    h, w = mask_c.shape
    img = np.full((h, w, 3), 255, np.uint8)
    img[mask_c] = (150, 150, 155)
    edge = binary_dilation(mask_t, iterations=1) & ~mask_t
    img[edge] = (220, 30, 30)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    d.text((8, 28), "red = target outline", fill=(220, 30, 30), font=_font(20))
    # 10 mm scale bar
    d.line([(8, h - 14), (8 + 10 * px_per_mm * 5, h - 14)], fill=(0, 0, 0), width=3)
    d.text((8, h - 40), "50 mm", fill=(0, 0, 0), font=_font(18))
    return im


def render_set(parts_mm: dict, spec: LegSpec, out_dir: str | Path, name: str) -> dict:
    """All images for one design. `name` is printed on the sheet (use a neutral one for blind critic runs)."""
    from PIL import Image, ImageDraw

    from .evaluate import candidate_masks

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}
    for v in ("three_quarter", "front", "side", "back"):
        files[f"clay_{v}"] = clay(parts_mm, out / f"clay_{v}.png", v, name)
    for th in (65, 130):
        files[f"knee_{th}"] = clay(parts_mm, out / f"knee_{th}.png", "side", name, theta=th)
    files["zebra_three_quarter"] = clay(parts_mm, out / "zebra_three_quarter.png", "three_quarter", name, zebra=True)
    files["zebra_side"] = clay(parts_mm, out / "zebra_side.png", "side", name, zebra=True)
    ppm = 2.0
    tm = target_masks(spec, ppm)
    cm = candidate_masks(parts_mm, spec, ppm)
    for v in ("front", "side"):
        im = _overlay(cm[v], tm[v], f"{name}: {v} silhouette", ppm)
        f = out / f"silhouette_{v}.png"
        im.save(f)
        files[f"silhouette_{v}"] = f
    files["sheet"] = compose_sheet(files, out / "sheet.png", name)
    return files


def compose_sheet(files: dict, path: Path, name: str) -> Path:
    from PIL import Image, ImageDraw

    def load(k, h):
        im = Image.open(files[k]).convert("RGB")
        return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)

    rows = [
        [load(k, 640) for k in ("clay_three_quarter", "clay_front", "clay_side", "clay_back")],
        [load(k, 640) for k in ("knee_65", "knee_130", "zebra_three_quarter", "zebra_side")],
        [load(k, 600) for k in ("silhouette_front", "silhouette_side")],
    ]
    labels = [["3/4 view", "front", "side", "back"], ["side, knee flexed 65 deg", "side, knee flexed 130 deg", "zebra 3/4", "zebra side"],
              ["front silhouette (grey) vs target (red)", "side silhouette (grey) vs target (red)"]]
    pad = 8
    W = max(sum(i.width for i in r) + pad * (len(r) + 1) for r in rows)
    Hh = sum(max(i.height for i in r) for r in rows) + pad * (len(rows) + 1) + 44
    sheet = Image.new("RGB", (W, Hh), "white")
    d = ImageDraw.Draw(sheet)
    d.text((pad, 6), f"{name}  |  leg segment (thigh + knee + shank), 0.5 m humanoid  |  studio rig v1 clay + SSAO", fill=(0, 0, 0), font=_font(26))
    y = 44
    for r, lab in zip(rows, labels):
        x = pad
        for im, l in zip(r, lab):
            sheet.paste(im, (x, y))
            d.text((x + 6, y + 4), l, fill=(70, 70, 70), font=_font(20))
            x += im.width + pad
        y += max(i.height for i in r) + pad
    sheet.thumbnail((2600, 2600))
    sheet.save(path)
    return path
