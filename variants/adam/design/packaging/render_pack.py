"""Packaging-for-look study (T-20261019-c1aa): studio sheet + two-tone + hard-point overlay for one profiles.yaml, with the R2a render
code (variants/adam/design/silhouette/render.py, same rig, refs optimus_like + atlas_like), written to docs/design-method/R2a-packaging/<tag>/
and COMPACTED: sheet / two-tone / overlay as JPEG <= 300 KB, the per-view PNGs deleted (the repo grew 29 MB last round).

Run:  .venv/Scripts/python variants/adam/design/packaging/render_pack.py <profiles.yaml> <tag> [--label design-1]
      .venv/Scripts/python variants/adam/design/packaging/render_pack.py --compact-only <src_dir> <tag>   (e.g. the R2a B4 sheet, for the critic)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "silhouette"))
sys.path.insert(0, str(REPO))
OUT = REPO / "docs" / "design-method" / "R2a-packaging"
LIMIT = 300_000


def compact(src: Path, dst: Path, width: int) -> Path:
    from PIL import Image
    im = Image.open(src).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    q = 88
    while True:
        im.save(dst, "JPEG", quality=q, optimize=True)
        if dst.stat().st_size <= LIMIT or q <= 50:
            break
        q -= 6
    return dst


def compact_dir(d: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, w in (("sheet", 1400), ("twotone", 1600), ("hardpoints", 1100)):
        p = d / f"{name}.png"
        if p.exists():
            compact(p, out / f"{name}.jpg", w)
    if (d / "design_metrics.json").exists() and d != out:
        shutil.copy(d / "design_metrics.json", out / "design_metrics.json")


def render(profiles: Path, tag: str, label: str) -> dict:
    import render as R2R
    R2R.OUT_ROOT = OUT
    rep = R2R.run(profiles, tag, label, True)
    d = OUT / tag
    compact_dir(d, d)
    for p in d.glob("*.png"):
        p.unlink()
    for p in ("studio.json",):
        (d / p).unlink(missing_ok=True)
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("tag")
    ap.add_argument("--label", default="design")
    ap.add_argument("--compact-only", action="store_true")
    a = ap.parse_args(argv)
    if a.compact_only:
        compact_dir(Path(a.src), OUT / a.tag)
    else:
        render(Path(a.src), a.tag, a.label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
