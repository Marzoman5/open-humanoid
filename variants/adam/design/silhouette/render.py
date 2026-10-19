"""R2a render set for one silhouette direction (task T-20261019-d955).

For a profiles.yaml it writes, into docs/design-method/R2a/<tag>/:
  studio rig set + sheet.png      (openhumanoid.design.studio.render_studio, refs optimus_like + atlas_like)  <- the critic's sheet
  design_metrics.json             (openhumanoid.design.metrics, the code-measured numbers)
  twotone_*.png + twotone.png     same camera/lights as the rig, faces coloured by segment role: shell = matte warm white,
                                  dark = graphite, visor = glossy black. The clay rig is one colour, so this is the only view of G3.
  hardpoints.png                  front + side silhouettes with every hard point box and the P3 band limits
The sheet title carries only the neutral --label, so the blind critic does not learn which design is whose.

Run:  .venv/Scripts/python variants/adam/design/silhouette/render.py <profiles.yaml> <tag> [--label design-1] [--no-clay]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from openhumanoid.design import metrics, silhouette as sil, studio  # noqa: E402
from openhumanoid.design.massing import build_massing, split_by_label  # noqa: E402
from openhumanoid.design.meshio import Subject  # noqa: E402
from openhumanoid.design.profiles import load_profiles  # noqa: E402

OUT_ROOT = REPO / "docs" / "design-method" / "R2a"
REFS = [f"optimus_like={REPO / 'openhumanoid/design/references/optimus_like.yaml'}",
        f"atlas_like={REPO / 'openhumanoid/design/references/atlas_like.yaml'}"]
SHELL, DARK, VISOR = (0.90, 0.885, 0.85), (0.17, 0.17, 0.18), (0.06, 0.06, 0.07)


def subject_with_labels(path: Path, name: str):
    prof = load_profiles(path)
    mesh, labels = build_massing(prof)
    parts = split_by_label(mesh, labels)
    joints = {j["id"]: tuple(j["pos"]) for j in prof.get("joints", [])}
    subj = Subject(name, parts, prof["height_m"], prof, joints, prof.get("hard_points", []), f"profiles:{path}",
                   {k: "shell" for k in parts}, mesh)
    return subj, prof, mesh, labels


def face_colours(prof, labels):
    role = {s["id"]: s["role"] for s in prof["segments"]}
    out = np.empty((len(labels), 3))
    for i, lab in enumerate(labels):
        if lab == "visor":
            out[i] = VISOR
        elif role.get(lab) == "dark":
            out[i] = DARK
        else:
            out[i] = SHELL
    return out


def render_twotone(subj, prof, mesh, labels, out_dir: Path) -> dict:
    import pyvista as pv

    rig = studio.load_rig()
    c = rig["clay"]
    H = subj.height_m
    centre = ((mesh.bounds[0][0] + mesh.bounds[1][0]) / 2, (mesh.bounds[0][1] + mesh.bounds[1][1]) / 2)
    poly = studio._to_pv(mesh)
    # vertex colours = mean of the adjacent faces' colours, so the shell/graphite split is anti-aliased at voxel scale
    fc = face_colours(prof, labels)
    vc = np.zeros((len(mesh.vertices), 3))
    cnt = np.zeros(len(mesh.vertices))
    for j in range(3):
        np.add.at(vc, mesh.faces[:, j], fc)
        np.add.at(cnt, mesh.faces[:, j], 1)
    poly.point_data["rgb"] = (vc / np.maximum(cnt, 1)[:, None] * 255).astype(np.uint8)
    files = {}
    for view in ("three_quarter", "front", "side", "back"):
        pos, tgt, fov = studio._camera(rig, H, c["views"][view], centre)
        pv.OFF_SCREEN = True
        pl = pv.Plotter(off_screen=True, window_size=list(c["window"]))
        pl.set_background(c["background"][0], top=c["background"][1])
        pl.remove_all_lights()
        lrig = rig
        if view == "back":       # the rig's key light is in front; for the back view turn the lights with the camera
            import copy
            lrig = copy.deepcopy(rig)
            for L in lrig["clay"]["lights"].values():
                L["az"] += 180
        for L in studio._lights(lrig, H, centre):
            pl.add_light(L)
        pl.add_mesh(poly, scalars="rgb", rgb=True, smooth_shading=True, specular=0.35, specular_power=30, ambient=0.14, diffuse=0.85)
        try:
            pl.enable_ssao(radius=H * c["ssao"]["radius_frac"] * 4, bias=H * c["ssao"]["bias_frac"], kernel_size=128, blur=True)
        except Exception:
            pass
        pl.camera.position, pl.camera.focal_point, pl.camera.up = pos, tgt, (0, 0, 1)
        pl.camera.view_angle = fov
        pl.camera.clipping_range = (0.05 * H, 20 * H)
        if hasattr(pl, "enable_anti_aliasing"):
            pl.enable_anti_aliasing("ssaa")
        f = out_dir / f"twotone_{view}.png"
        pl.screenshot(str(f))
        pl.close()
        files[view] = f
    return files


def compose_row(files: list[Path], title: str, out: Path, w: int = 560):
    from PIL import Image, ImageDraw

    ims = [Image.open(f).convert("RGB") for f in files]
    ims = [im.resize((w, round(im.height * w / im.width)), Image.LANCZOS) for im in ims]
    pad = 8
    sheet = Image.new("RGB", (len(ims) * (w + pad) + pad, max(i.height for i in ims) + 48), "white")
    d = ImageDraw.Draw(sheet)
    d.text((pad, 8), title, fill=(0, 0, 0), font=studio._font(26))
    for i, im in enumerate(ims):
        sheet.paste(im, (pad + i * (w + pad), 44))
    sheet.save(out)
    return out


def hardpoint_overlay(subj, prof, out: Path, label: str):
    """Front + side silhouettes of the massing with every hard-point box (incl. margin dashed) and the P3 0.29 H limits."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    H = subj.height_m
    fig, axs = plt.subplots(1, 2, figsize=(12, 8.6), dpi=110)
    meshes = list(subj.render_meshes.values())
    for ax, view in zip(axs, ("front", "side")):
        s = sil.rasterise(meshes, view, H)
        lo, hi = subj.mesh.bounds
        k = 1 if view == "front" else 0
        cx = (lo[k] + hi[k]) / 2
        ext = (-(sil.CENTER_COL) / s.px_per_m * 1000 + cx * 1000, (sil.CANVAS - sil.CENTER_COL) / s.px_per_m * 1000 + cx * 1000,
               (sil.GROUND_ROW - sil.CANVAS) / s.px_per_m * 1000, sil.GROUND_ROW / s.px_per_m * 1000)
        ax.imshow(np.where(s.mask, 0.78, 1.0), cmap="gray", vmin=0, vmax=1, extent=ext, origin="upper")
        for hp in prof["hard_points"]:
            c = [v * 1000 for v in hp["center"]]
            sz = [v * 1000 for v in hp["size"]]
            u, w = (c[1], sz[1]) if view == "front" else (c[0], sz[0])
            m = hp.get("margin_m", 0) * 1000
            col = "#2471a3" if "servo" in hp["id"] else ("#c0392b" if ("pack" in hp["id"] or "pi5" in hp["id"]) else "#7d3c98")
            ax.add_patch(Rectangle((u - w / 2, c[2] - sz[2] / 2), w, sz[2], fill=True, alpha=0.30, color=col, lw=0))
            ax.add_patch(Rectangle((u - w / 2, c[2] - sz[2] / 2), w, sz[2], fill=False, color=col, lw=0.7))
            ax.add_patch(Rectangle((u - w / 2 - m, c[2] - sz[2] / 2 - m), w + 2 * m, sz[2] + 2 * m, fill=False, color=col, lw=0.4, ls=":"))
        for j in prof.get("joints", []):
            if view == "front":
                for sg in ((1, -1) if j["id"].endswith("_l") else (1,)):
                    ax.plot(sg * j["pos"][1] * 1000, j["pos"][2] * 1000, "k+", ms=7)
            else:
                ax.plot(j["pos"][0] * 1000, j["pos"][2] * 1000, "k+", ms=7)
        if view == "front":
            lim = 0.145 * H * 1000
            for v in (lim, -lim):
                ax.axvline(v, color="#e67e22", lw=1)
            ax.text(lim + 3, H * 1000 * 0.97, "P3 band max\n0.29 H", fontsize=7, color="#e67e22")
            ax.set_xlim(-190, 190)
        else:
            ax.set_xlim(-150, 150)
        ax.set_ylim(-5, H * 1000 + 10)
        ax.set_aspect("equal")
        ax.set_title(f"{view}: silhouette (grey), hard points (boxes incl. housing; dotted = + wall and gap), joints (+)", fontsize=8)
        ax.set_xlabel("y (mm)" if view == "front" else "x (mm, forward +)")
        ax.set_ylabel("z (mm)")
    fig.suptitle(f"{label}: hard-point overlay, H = {H * 1000:.0f} mm", fontsize=11)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def run(profiles: Path, tag: str, label: str, clay: bool = True) -> dict:
    out = OUT_ROOT / tag
    out.mkdir(parents=True, exist_ok=True)
    subj, prof, mesh, labels = subject_with_labels(profiles, label)
    studio.render_studio(subj, out, refs=REFS, clay=clay)
    refs = dict(studio.reference_mask(r, "front") for r in REFS)
    rep = metrics.write_report(subj, out / "design_metrics.json", ref_masks=refs)
    if clay:
        tt = render_twotone(subj, prof, mesh, labels, out)
        compose_row([tt[v] for v in ("three_quarter", "front", "side", "back")],
                    f"{label} | two-tone (shell matte white / graphite structure / gloss visor), same camera + lights as the studio rig",
                    out / "twotone.png")
    hardpoint_overlay(subj, prof, out / "hardpoints.png", label)
    ev = rep["evaluation"]
    summary = {k: (v["value"], v["verdict"]) for k, v in ev["criteria"].items()}
    print(f"{tag}: {ev['n_pass']}/{ev['n_scored']} pass; failed {ev['failed']}")
    print("  " + "  ".join(f"{k}={v[0]}" for k, v in summary.items() if v[0] is not None and not isinstance(v[0], (dict, list, str))))
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("profiles")
    ap.add_argument("tag")
    ap.add_argument("--label", default="design")
    ap.add_argument("--no-clay", action="store_true")
    a = ap.parse_args(argv)
    run(Path(a.profiles), a.tag, a.label, not a.no_clay)
    return 0


if __name__ == "__main__":
    sys.exit(main())
