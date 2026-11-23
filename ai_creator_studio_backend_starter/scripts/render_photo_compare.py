"""E-03: before/after PNG of the SAME scene, angles and size: ``render3d_soft`` (the mock) on top, ``render3d_photo`` (E-03) below.

   python scripts/render_photo_compare.py [out.png]      # default: render_photo_compare.png in the current folder (about 30 s)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import render3d_photo, render3d_scene, render3d_soft  # noqa: E402

ANGLES = (0, 45, 90, 180)
SIZE = (270, 480)


def build(out: Path) -> dict:
    body, layers, _ = render3d_scene.build_layers("female", None, ["top", "bottom"])
    every = body + [t for _, tris, _ in layers for t in tris]
    height = render3d_soft.height_of(every)
    sheet = Image.new("RGB", (SIZE[0] * len(ANGLES), SIZE[1] * 2 + 24), (255, 255, 255))
    t_soft = t_photo = 0.0
    for i, angle in enumerate(ANGLES):
        t = time.time()
        a = render3d_soft.render(every, angle, SIZE, background=(226, 228, 234), height_m=height)
        t_soft += time.time() - t
        t = time.time()
        b = render3d_photo.render_photo([(body, "skin")] + [(tris, "cloth") for _, tris, _ in layers], angle, SIZE, height_m=height)
        t_photo += time.time() - t
        sheet.paste(a, (i * SIZE[0], 0))
        sheet.paste(b, (i * SIZE[0], SIZE[1] + 24))
    d = ImageDraw.Draw(sheet)
    d.text((6, SIZE[1] + 6), "above: render3d_soft (before)   below: render3d_photo (E-03, after)   same scene, size, angles", fill=(0, 0, 0))
    sheet.save(out)
    return {"soft_s_per_picture": t_soft / len(ANGLES), "photo_s_per_picture": t_photo / len(ANGLES)}


if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else "render_photo_compare.png")))
