"""Studio render rig (ADR 0010, A4): pyvista clay + SSAO + 3-point light, orthographic silhouettes on the fixed rig,
head-unit grid, equal-height reference overlays, optional zebra pass, and a review sheet.

`oh render <id> --studio` -> variants/<id>/generated/renders/studio/. MuJoCo renders (render.py) stay for sim.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import yaml

from . import silhouette as sil
from .meshio import Subject, load_subject

RIG_PATH = Path(__file__).with_name("rig.yaml")


def load_rig() -> dict:
    return yaml.safe_load(RIG_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------------------------- clay
def _to_pv(mesh):
    import pyvista as pv

    faces = np.hstack([np.full((len(mesh.faces), 1), 3), mesh.faces]).astype(np.int64).ravel()
    poly = pv.PolyData(np.asarray(mesh.vertices, float), faces)
    if "sdf_normals" in mesh.metadata:
        poly.point_data["Normals"] = np.asarray(mesh.metadata["sdf_normals"], float)
    return poly


def _camera(rig: dict, H: float, az_deg: float, centre_xy: tuple):
    c = rig["clay"]
    fov = 2 * math.degrees(math.atan((c["sensor_mm"] / 2) / c["lens_mm"]))
    dist = (H * c["fit"] / 2) / math.tan(math.radians(fov / 2))
    az = math.radians(az_deg)
    tgt = (centre_xy[0], centre_xy[1], H * c["target_z_frac"])
    pos = (tgt[0] + dist * math.cos(az), tgt[1] + dist * math.sin(az), H * c["camera_z_frac"])
    return pos, tgt, fov


def _lights(rig: dict, H: float, centre_xy: tuple):
    import pyvista as pv

    out = []
    tgt = (centre_xy[0], centre_xy[1], H * 0.5)
    for L in rig["clay"]["lights"].values():
        az, el, r = math.radians(L["az"]), math.radians(L["el"]), L["dist"] * H
        pos = (tgt[0] + r * math.cos(el) * math.cos(az), tgt[1] + r * math.cos(el) * math.sin(az), tgt[2] + r * math.sin(el))
        out.append(pv.Light(position=pos, focal_point=tgt, color="white", intensity=L["intensity"], light_type="scene light"))
    return out


def render_clay(subject: Subject, view: str, out: Path, rig: dict | None = None, zebra: bool = False,
                size: tuple | None = None, color_by_class: bool = False) -> Path:
    import pyvista as pv

    rig = rig or load_rig()
    c = rig["clay"]
    H = subject.height_m
    allm = subject.mesh
    centre = ((allm.bounds[0][0] + allm.bounds[1][0]) / 2, (allm.bounds[0][1] + allm.bounds[1][1]) / 2)
    pos, tgt, fov = _camera(rig, H, c["views"][view], centre)
    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=list(size or c["window"]))
    pl.set_background(c["background"][0], top=c["background"][1])
    pl.remove_all_lights()
    for L in _lights(rig, H, centre):
        pl.add_light(L)
    for name, m in subject.render_meshes.items():
        poly = _to_pv(m)
        smooth = "Normals" in poly.point_data
        if zebra:
            if not smooth:
                poly = poly.compute_normals(point_normals=True, cell_normals=False, split_vertices=True, feature_angle=40, inplace=False)
            n = poly.point_data["Normals"]
            v = np.array(pos) - poly.points
            v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-12
            r = 2 * np.sum(n * v, axis=1, keepdims=True) * n - v
            k = rig["zebra"]["stripes"]
            poly.point_data["zebra"] = np.tanh(3.0 * np.sin(math.pi * k * r[:, 2]))
            pl.add_mesh(poly, scalars="zebra", cmap=["#101010", "#f2f2f2"], lighting=False, show_scalar_bar=False, smooth_shading=True)
        else:
            col = "#4a4a4f" if (color_by_class and subject.classes.get(name) == "hardware") else c["color"]
            kw = {} if smooth else {"split_sharp_edges": True, "feature_angle": 35}
            pl.add_mesh(poly, color=col, smooth_shading=True, specular=c["specular"], specular_power=c["specular_power"],
                        ambient=0.12, diffuse=0.85, **kw)
    if not zebra:
        try:
            pl.enable_ssao(radius=H * c["ssao"]["radius_frac"] * 4, bias=H * c["ssao"]["bias_frac"], kernel_size=128, blur=True)
        except Exception:  # SSAO needs a capable GL context; fall back to plain lighting
            pass
    pl.camera.position, pl.camera.focal_point, pl.camera.up = pos, tgt, (0, 0, 1)
    pl.camera.view_angle = fov
    pl.camera.clipping_range = (0.05 * H, 20 * H)
    pl.enable_anti_aliasing("ssaa") if hasattr(pl, "enable_anti_aliasing") else None
    out.parent.mkdir(parents=True, exist_ok=True)
    pl.screenshot(str(out))
    pl.close()
    return out


# -------------------------------------------------------------------------------------------------------- silhouettes
def _font(size: int):
    from PIL import ImageFont

    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def _outline(mask: np.ndarray, width: int = 3) -> np.ndarray:
    from scipy.ndimage import binary_dilation

    return binary_dilation(mask, iterations=width) & ~mask


def silhouette_image(s: sil.Silhouette, head_unit_m: float | None, rig: dict, ref_masks: dict | None = None,
                     title: str = "") -> "Image":  # noqa: F821
    """Candidate silhouette (grey fill) with the head-unit grid and reference outlines at equal height."""
    from PIL import Image, ImageDraw

    ov = rig["overlay"]
    img = np.full((sil.CANVAS, sil.CANVAS, 3), 255, np.uint8)
    img[s.mask] = ov["candidate_fill"] if ref_masks else (30, 30, 30)
    colours = [tuple(ov["reference_outline"]), (30, 90, 220), (20, 150, 70), (200, 120, 0)]
    for i, (name, m) in enumerate((ref_masks or {}).items()):
        img[_outline(m)] = colours[i % len(colours)]
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    f = _font(22)
    top_row = sil.GROUND_ROW - sil.H_PX
    d.line([(0, sil.GROUND_ROW), (sil.CANVAS, sil.GROUND_ROW)], fill=(120, 120, 120), width=2)
    d.line([(sil.CENTER_COL, top_row - 20), (sil.CENTER_COL, sil.GROUND_ROW + 10)], fill=(200, 200, 200), width=1)
    if head_unit_m and rig["grid"]["head_units"]:
        hu_px = head_unit_m * s.px_per_m
        k = 0
        while top_row + k * hu_px <= sil.GROUND_ROW + 1:
            y = top_row + k * hu_px
            d.line([(0, y), (sil.CANVAS, y)], fill=tuple(rig["grid"]["line_color"]) , width=1)
            d.text((6, y - 26), f"{k} hu", fill=(60, 60, 60), font=f)
            k += 1
    d.text((10, 10), title, fill=(0, 0, 0), font=_font(28))
    y0 = 44
    for i, name in enumerate((ref_masks or {})):
        d.text((10, y0 + 26 * i), f"outline: {name}", fill=colours[i % len(colours)], font=f)
    return im


def lineup_image(masks: dict, rig: dict, title: str = "equal-height lineup") -> "Image":  # noqa: F821
    """Candidate and references side by side at equal height."""
    from PIL import Image, ImageDraw

    n = len(masks)
    crop_w = 520
    out = Image.new("RGB", (crop_w * n, 1160), "white")
    d = ImageDraw.Draw(out)
    for i, (name, m) in enumerate(masks.items()):
        ys, xs = np.where(m)
        cx = (xs.min() + xs.max()) // 2 if len(xs) else sil.CENTER_COL
        c0 = int(cx - crop_w // 2)
        tile = np.zeros((1160, crop_w), bool)
        a0, a1 = max(c0, 0), min(c0 + crop_w, sil.CANVAS)
        tile[:, a0 - c0:a1 - c0] = m[:1160, a0:a1]
        rgb = np.full((1160, crop_w, 3), 255, np.uint8)
        rgb[tile] = (30, 30, 30)
        out.paste(Image.fromarray(rgb), (i * crop_w, 0))
        d.text((i * crop_w + 10, 8), name, fill=(0, 0, 0), font=_font(28))
        d.line([(i * crop_w, 0), (i * crop_w, 1160)], fill=(210, 210, 210))
    d.text((10, 1125), title, fill=(90, 90, 90), font=_font(22))
    return out


def reference_mask(ref: str | Path, view: str = "front") -> tuple[str, np.ndarray]:
    """name=path (profile yaml, mesh/dir, or silhouette image) -> (name, normalised mask for `view`)."""
    ref = str(ref)
    name, _, path = ref.partition("=") if "=" in ref else (Path(ref).stem, "", ref)
    p = Path(path)
    if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return name, sil.from_image(p)
    subj = load_subject(p, name)
    return name, sil.normalise_mask(sil.rasterise(list(subj.parts.values()), view, subj.height_m).mask)


# ---------------------------------------------------------------------------------------------------------- the sheet
def render_studio(subject: Subject, out_dir: str | Path, refs: list[str] | None = None, zebra: bool = False,
                  clay: bool = True, color_by_class: bool = False) -> dict:
    """Write the full studio set. Returns {"files": {...}, "sheet": Path, ...}."""
    from PIL import Image, ImageDraw

    rig = load_rig()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}
    hu = (subject.profiles or {}).get("head_unit_m") or subject.height_m * 0.14
    meshes = list(subject.render_meshes.values())
    masks = {v: sil.rasterise(meshes, v, subject.height_m) for v in rig["silhouette"]["views"]}
    ref_front = dict(reference_mask(r, "front") for r in (refs or []))
    ref_side = dict(reference_mask(r, "side") for r in (refs or []))
    for v, s in masks.items():
        f = out / f"silhouette_{v}.png"
        silhouette_image(s, hu, rig, None, f"{subject.name} {v} (1 head unit = {hu * 1000:.0f} mm)").save(f)
        files[f"silhouette_{v}"] = f
        if refs:
            f = out / f"overlay_{v}.png"
            silhouette_image(s, hu, rig, ref_front if v == "front" else ref_side, f"{subject.name} {v} vs references").save(f)
            files[f"overlay_{v}"] = f
    cand_n = {v: sil.normalise_mask(masks[v].mask) for v in masks}
    for v, rm in (("front", ref_front), ("side", ref_side)):
        lm = {subject.name: cand_n[v], **rm}
        f = out / f"lineup_{v}.png"
        lineup_image(lm, rig, f"{v} view, all normalised to equal height").save(f)
        files[f"lineup_{v}"] = f
    if clay:
        for v in rig["clay"]["views"]:
            files[f"clay_{v}"] = render_clay(subject, v, out / f"clay_{v}.png", rig, color_by_class=color_by_class)
        if zebra:
            for v in rig["zebra"]["view"]:
                files[f"zebra_{v}"] = render_clay(subject, v, out / f"zebra_{v}.png", rig, zebra=True)
    sheet = _compose_sheet(subject, files, rig, bool(refs))
    sheet_path = out / "sheet.png"
    sheet.save(sheet_path)
    files["sheet"] = sheet_path
    meta = {"subject": subject.name, "source": subject.source, "height_m": subject.height_m, "head_unit_m": hu,
            "rig_version": rig["version"], "refs": list(ref_front), "zebra": zebra,
            "files": {k: str(v.name) for k, v in files.items()}}
    (out / "studio.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"files": files, "sheet": sheet_path, "meta": meta}


def _compose_sheet(subject: Subject, files: dict, rig: dict, has_refs: bool):
    from PIL import Image, ImageDraw

    def load(k, w=None):
        if k not in files:
            return None
        im = Image.open(files[k]).convert("RGB")
        if w:
            im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        return im

    W = 560
    clay_keys = [k for k in ("clay_three_quarter", "clay_front", "clay_side", "clay_back") if k in files]
    row1 = [load(k, W) for k in clay_keys]
    row2_keys = ["overlay_front" if has_refs else "silhouette_front", "overlay_side" if has_refs else "silhouette_side"]
    row2 = [load(k, 2 * W) for k in row2_keys]
    row3 = [load("lineup_front", 4 * W)]
    pad = 8
    rows = [r for r in (row1, row2, row3) if r and all(x is not None for x in r)]
    height = sum(max(x.height for x in r) for r in rows) + pad * (len(rows) + 2) + 40
    width = max(sum(x.width for x in r) + pad * (len(r) + 1) for r in rows)
    sheet = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(sheet)
    d.text((pad, 6), f"{subject.name}  |  studio rig v{rig['version']}  |  H = {subject.height_m * 1000:.0f} mm", fill=(0, 0, 0), font=_font(26))
    y = 40
    for r in rows:
        x = pad
        for im in r:
            sheet.paste(im, (x, y))
            x += im.width + pad
        y += max(im.height for im in r) + pad
    return sheet
