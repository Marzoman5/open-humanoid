"""Orthographic silhouettes on the fixed framing used by the studio rig, the metrics and the reference comparison.

Framing (see rig.yaml): the canvas is CANVAS x CANVAS pixels, the subject height H maps to H_PX pixels with the ground at
row GROUND_ROW, and the subject's bounding box is centred horizontally. So every silhouette is height-normalised and
two silhouettes can be compared pixel by pixel (equal-height overlay, IoU).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

CANVAS = 1200
H_PX = 1000
GROUND_ROW = 1100
CENTER_COL = CANVAS // 2


@dataclass
class Silhouette:
    mask: np.ndarray      # (CANVAS, CANVAS) bool; row 0 = top
    px_per_m: float
    height_m: float
    view: str

    def row_of_z(self, z_m: float) -> float:
        return GROUND_ROW - z_m * self.px_per_m

    def z_of_row(self, row) -> np.ndarray | float:
        return (GROUND_ROW - np.asarray(row)) / self.px_per_m


def _project(verts: np.ndarray, view: str, s: float, cx: float) -> np.ndarray:
    """(N,3) design-frame points -> (N,2) pixel (col,row). front looks along -x (robot's left on image right);
    side is seen from the robot's right with forward (+x) to the image right."""
    h = verts[:, 1] if view == "front" else verts[:, 0]
    col = CENTER_COL + (h - cx) * s
    row = GROUND_ROW - verts[:, 2] * s
    return np.stack([col, row], axis=1)


def rasterise(meshes, view: str, height_m: float | None = None, bbox_center: tuple | None = None) -> Silhouette:
    """Rasterise one mesh or a list of meshes (filled triangles, no shading)."""
    from PIL import Image, ImageDraw

    meshes = meshes if isinstance(meshes, (list, tuple)) else [meshes]
    lo = np.min([m.bounds[0] for m in meshes], axis=0)
    hi = np.max([m.bounds[1] for m in meshes], axis=0)
    H = height_m or float(hi[2] - 0.0)
    s = H_PX / H
    k = 1 if view == "front" else 0
    cx = bbox_center[k] if bbox_center else (lo[k] + hi[k]) / 2
    img = Image.new("L", (CANVAS, CANVAS), 0)
    d = ImageDraw.Draw(img)
    for m in meshes:
        px = _project(np.asarray(m.vertices), view, s, cx)
        tris = px[np.asarray(m.faces)]
        # skip degenerate triangles cheaply
        for t in tris:
            d.polygon([tuple(t[0]), tuple(t[1]), tuple(t[2])], fill=255)
    return Silhouette(np.asarray(img) > 0, s, H, view)


def normalise_mask(mask: np.ndarray) -> np.ndarray:
    """Crop a binary silhouette to its bbox, scale to H_PX tall, place on the canvas (ground row, bbox-centred)."""
    from PIL import Image

    ys, xs = np.where(mask)
    if len(ys) == 0:
        return np.zeros((CANVAS, CANVAS), bool)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    s = H_PX / h
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize((max(1, round(w * s)), H_PX), Image.BILINEAR)
    a = np.asarray(im) > 127
    out = np.zeros((CANVAS, CANVAS), bool)
    r0 = GROUND_ROW - H_PX
    c0 = CENTER_COL - a.shape[1] // 2
    c0c = max(c0, 0)
    a = a[:, c0c - c0:CANVAS - c0] if c0 < 0 else a
    out[r0:r0 + H_PX, c0c:c0c + a.shape[1]] = a[:, :CANVAS - c0c]
    return out


def from_image(path: str | Path, thresh: int = 128, invert: bool | None = None) -> np.ndarray:
    """Silhouette mask from a reference image (PNG/JPG). A background of mostly light pixels means the subject is dark
    (silhouette = dark), otherwise the subject is the light region. For photos, pre-remove the background first."""
    from PIL import Image

    im = Image.open(path)
    if im.mode == "RGBA":
        alpha = np.asarray(im)[:, :, 3]
        if alpha.min() < 250:
            return normalise_mask(alpha > 127)
    g = np.asarray(im.convert("L"))
    dark = g < thresh
    if invert is None:
        invert = dark.mean() > 0.5
    return normalise_mask(~dark if invert else dark)


def iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def save_mask(mask: np.ndarray, path: str | Path) -> None:
    from PIL import Image
    Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).save(path)
