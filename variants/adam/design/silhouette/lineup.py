"""R2a lineup sheet: the silhouette directions side by side for the maintainer (task T-20261019-d955).

Per direction: two-tone 3/4, front and side views (same camera and lights as the studio rig), the front silhouette at
equal height with the references, and the code-measured numbers. Reads the render sets written by render.py.

Run:  .venv/Scripts/python variants/adam/design/silhouette/lineup.py <tag=title> ... --out docs/design-method/R2a/lineup.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from openhumanoid.design import studio  # noqa: E402

ROOT = REPO / "docs" / "design-method" / "R2a"
KEYS = ["P1", "P2a", "P3", "P4", "P5", "P6", "P7", "P8a", "P8b", "P10a", "P10b", "S3a", "S4a", "HP"]


def main(argv=None) -> int:
    from PIL import Image, ImageDraw

    ap = argparse.ArgumentParser()
    ap.add_argument("items", nargs="+", help="tag=title (render set under docs/design-method/R2a/<tag>)")
    ap.add_argument("--out", default=str(ROOT / "lineup.png"))
    a = ap.parse_args(argv)
    W = 330
    cols = []
    for it in a.items:
        tag, _, title = it.partition("=")
        d = ROOT / tag
        ims = [Image.open(d / f"twotone_{v}.png").convert("RGB") for v in ("three_quarter", "front", "side")]
        ims = [im.crop((60, 30, im.width - 60, im.height - 10)) for im in ims]
        ims = [im.resize((W, round(im.height * W / im.width)), Image.LANCZOS) for im in ims]
        sil = Image.open(d / "silhouette_front.png").convert("RGB").crop((250, 60, 950, 1110))
        sil = sil.resize((W, round(sil.height * W / sil.width)), Image.LANCZOS)
        m = json.loads((d / "design_metrics.json").read_text(encoding="utf-8"))["evaluation"]
        cols.append((title, ims, sil, m))
    colw = 3 * W + 16
    h_img = max(im.height for _, ims, _, _ in cols for im in ims)
    h_sil = max(s.height for _, _, s, _ in cols)
    H = 60 + h_img + 10 + h_sil + 30 + 22 * (len(KEYS) + 2) + 20
    sheet = Image.new("RGB", (colw * len(cols) + 16, H), "white")
    d = ImageDraw.Draw(sheet)
    f_t, f_s = studio._font(30), studio._font(19)
    for i, (title, ims, sil, m) in enumerate(cols):
        x0 = 8 + i * colw
        d.text((x0 + 4, 12), title, fill=(0, 0, 0), font=f_t)
        for j, im in enumerate(ims):
            sheet.paste(im, (x0 + j * (W + 4), 60))
        sheet.paste(sil, (x0 + W + 4, 60 + h_img + 10))
        d.text((x0 + 4, 60 + h_img + 14), "front silhouette\n(equal height)", fill=(90, 90, 90), font=f_s)
        y = 60 + h_img + 10 + h_sil + 20
        d.text((x0 + 4, y), f"numeric criteria passed: {m['n_pass']}/{m['n_scored']}", fill=(0, 0, 0), font=f_s)
        y += 26
        for k in KEYS:
            c = m["criteria"].get(k)
            if not c:
                continue
            v = c["value"]
            v = f"{v:.3f}" if isinstance(v, float) else str(v)
            col = (0, 120, 40) if c["verdict"] == "PASS" else ((190, 30, 30) if c["verdict"] == "FAIL" else (90, 90, 90))
            d.text((x0 + 4, y), f"{k:5s} {v:>7s}  {c['verdict']:4s}  band {c['band']}", fill=col, font=f_s)
            y += 22
        if i:
            d.line([(x0 - 6, 0), (x0 - 6, H)], fill=(220, 220, 220), width=2)
    sheet.save(a.out)
    print(f"lineup -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
