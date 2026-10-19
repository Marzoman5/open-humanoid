"""Stress picture of an FEA result: failure index (stress / weakest-direction allowable) on the outer surface, clipped colour scale 0..2."""
from __future__ import annotations

from pathlib import Path

import numpy as np


def plot_fea(part, res, path: Path, title: str, size=(900, 650), clim=2.0) -> None:
    import pyvista as pv

    mesh = res.data["mesh"]
    el = res.data["el_max"]
    nodes = np.zeros(mesh.p.shape[1])
    cnt = np.zeros(mesh.p.shape[1])
    for k in range(4):
        np.add.at(nodes, mesh.t[k], el)
        np.add.at(cnt, mesh.t[k], 1)
    nodes /= np.maximum(cnt, 1)
    cells = np.hstack([np.full((mesh.t.shape[1], 1), 4), mesh.t.T]).ravel()
    grid = pv.UnstructuredGrid(cells, np.full(mesh.t.shape[1], pv.CellType.TETRA), mesh.p.T)
    grid.point_data["failure index"] = nodes
    surf = grid.extract_surface()
    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=list(size))
    pl.set_background("white")
    pl.add_mesh(surf, scalars="failure index", cmap="turbo", clim=[0, clim], smooth_shading=False, show_edges=False,
                scalar_bar_args={"title": "failure index (1 = at allowable)", "color": "black", "title_font_size": 12, "label_font_size": 11})
    pl.add_text(title, font_size=9, color="black")
    pl.camera_position = "iso"
    pl.camera.zoom(1.15)
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.screenshot(str(path))
    pl.close()
    _shrink(path)


def _shrink(path: Path, max_kb: int = 280) -> None:
    from PIL import Image

    im = Image.open(path).convert("RGB")
    q = 85
    while True:
        im.save(path, optimize=True) if path.suffix == ".png" else im.save(path, quality=q)
        if path.stat().st_size / 1024 <= max_kb or im.width < 400:
            break
        im = im.resize((int(im.width * 0.85), int(im.height * 0.85)), Image.LANCZOS)
        im = im.quantize(colors=128).convert("RGB") if path.suffix == ".png" else im
