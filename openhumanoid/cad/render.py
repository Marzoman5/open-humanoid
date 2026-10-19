"""Clay-style review renders of an assembly (pyvista, offscreen), in the spirit of `oh render --studio` (docs/design-language.md): matte clay
for printed parts, dark servos, silver horns/bearings, soft 3-point light + SSAO, orthographic front/side and a perspective 3/4 view, a
section view (cut through the joint axis plane) that shows servos sitting in their pockets, and a pose view.

`render_views(asm, out_dir, pose=None)` -> list of PNG paths (individual views plus `sheet.png`).
Colours encode part role only: this is evidence that the geometry exists and fits, not a design-look render (that is the design studio's job).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .assembly import Assembly
from .core import mesh_of

COLORS = {"frame": (0.80, 0.80, 0.78), "servo": (0.10, 0.10, 0.12), "horn": (0.72, 0.74, 0.78), "shaft": (0.72, 0.74, 0.78),
          "purchased": (0.72, 0.74, 0.78), "cover": (0.62, 0.64, 0.66), "idler": (0.86, 0.80, 0.70), "sole": (0.2, 0.2, 0.2)}


def _color(p) -> tuple:
    if p.kind == "frame":
        if p.id.startswith("cover_"):
            return COLORS["cover"]
        if "idler" in p.id or "cradle" in p.id:
            return COLORS["idler"]
    return COLORS.get(p.kind, COLORS["frame"])


def _poly(shape):
    import pyvista as pv

    m = mesh_of(shape, tol=0.08)
    faces = np.hstack([np.full((len(m.faces), 1), 3), m.faces]).astype(np.int64).ravel()
    return pv.PolyData(np.asarray(m.vertices, float), faces)


def render_views(asm: Assembly, out_dir: Path, pose: str | None = None, side: str = "l", size: tuple[int, int] = (900, 1100),
                 hide: tuple[str, ...] = ()) -> list[Path]:
    import pyvista as pv

    from . import rom

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    q = rom.pose_angles(asm, pose, side) if pose else None
    pl = [p for p in asm.placed(q) if not p.part.keepout and not p.part.hardware and p.part.id not in hide]
    polys = [(p, _poly(p.shape)) for p in pl]
    allpts = np.vstack([pp.points for _, pp in polys])
    lo, hi = allpts.min(axis=0), allpts.max(axis=0)
    centre = (lo + hi) / 2
    span = float(np.linalg.norm(hi - lo))
    files: list[Path] = []

    def shot(name: str, direction: tuple, up=(0, 0, 1), ortho: bool = True, clip_y: float | None = None, zoom: float = 1.0) -> Path:
        pv.OFF_SCREEN = True
        pt = pv.Plotter(off_screen=True, window_size=list(size))
        pt.set_background("white")
        for p, pp in polys:
            mesh = pp
            if clip_y is not None:
                mesh = pp.clip(normal=(0, 1, 0), origin=(0, clip_y, 0), invert=True, crinkle=False)
                if mesh.n_points == 0:
                    continue
            pt.add_mesh(mesh, color=_color(p.part), smooth_shading=False, specular=0.15, ambient=0.25, diffuse=0.85,
                        show_edges=False, pbr=False)
        d = np.array(direction, float)
        d /= np.linalg.norm(d)
        pt.camera_position = [tuple(centre + d * span * 1.6), tuple(centre), up]
        if ortho:
            pt.camera.parallel_projection = True
            pt.camera.parallel_scale = span * 0.5 / zoom
        else:
            pt.camera.view_angle = 30
        try:
            pt.enable_ssao(radius=span * 0.04, bias=span * 0.002)
        except Exception:  # noqa: BLE001
            pass
        try:
            pt.enable_anti_aliasing("ssaa")
        except Exception:  # noqa: BLE001
            pass
        path = out_dir / f"{name}.png"
        pt.screenshot(str(path))
        pt.close()
        files.append(path)
        return path

    tag = f"_{pose}" if pose else ""
    shot(f"front{tag}", (1, 0, 0))                       # robot faces +x: look at it from the front
    shot(f"side{tag}", (0, -1, 0))
    shot(f"three_quarter{tag}", (1, -0.8, 0.45), ortho=False)
    shot(f"back{tag}", (-1, -0.5, 0.35), ortho=False)
    hip_y = float(np.median([pp.center[1] for p, pp in polys if p.part.kind == "servo"]))
    shot(f"section{tag}", (0, 1, 0), clip_y=hip_y, zoom=1.0)    # cut through the servo mid-plane, looking from +y (outboard) inward
    _sheet(files, out_dir / f"sheet{tag}.png")
    files.append(out_dir / f"sheet{tag}.png")
    return files


def _autocrop(path: Path, margin: int = 24) -> None:
    from PIL import Image, ImageChops

    im = Image.open(path).convert("RGB")
    bg = Image.new("RGB", im.size, "white")
    box = ImageChops.difference(im, bg).getbbox()
    if box:
        l, u, r, d = box
        im = im.crop((max(l - margin, 0), max(u - margin, 0), min(r + margin, im.width), min(d + margin, im.height)))
        im.save(path)


def _sheet(files: list[Path], out: Path, cols: int = 5) -> None:
    from PIL import Image

    for f in files:
        _autocrop(f)
    ims = [Image.open(f).convert("RGB") for f in files]
    H = 700
    ims = [im.resize((max(int(im.width * H / im.height), 1), H)) for im in ims]
    W = sum(im.width for im in ims) + 20 * (len(ims) + 1)
    sheet = Image.new("RGB", (W, H + 40), "white")
    x = 20
    for im in ims:
        sheet.paste(im, (x, 20))
        x += im.width + 20
    sheet.save(out)
