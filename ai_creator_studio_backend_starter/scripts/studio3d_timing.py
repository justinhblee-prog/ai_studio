"""D-1: time the server render job the 3D studio's "5-angle shoot" uses (photo renderer, 2 garments, a pose) and write the before/after pictures.

   python scripts/studio3d_timing.py [out_dir]

Runs the job in-process (no HTTP). 'before' = the mock renderer in the standing pose, 'after' = the lit renderer in the walking pose, same model, garments, size.
Numbers are for THIS machine; the 8 GB-class PC figure has not been measured.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import pose_rig, render3d_photo, render3d_scene, render3d_soft  # noqa: E402

ANGLES = (0, 45, 90, 180, 270)
SIZE = (360, 640)


def run(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    body, layers, _ = render3d_scene.build_layers("female", None, ["top", "bottom"])
    flat = body + [t for _, g, _ in layers for t in g]
    h = render3d_soft.height_of(flat)
    t0 = time.time()
    before = [render3d_soft.render(flat, a, SIZE, background=render3d_soft.BACKGROUNDS["studio"], height_m=h) for a in ANGLES]
    soft_s = time.time() - t0
    t0 = time.time()
    moved, _ = pose_rig.skin_triangles(pose_rig.Skeleton("female"), [body] + [g for _, g, _ in layers], "walking")
    skin_s = time.time() - t0
    t0 = time.time()
    after = [render3d_photo.render_photo([(moved[0], "skin")] + [(g, "cloth") for g in moved[1:]], a, SIZE, background=render3d_soft.BACKGROUNDS["studio"], height_m=h, ss=2) for a in ANGLES]
    photo_s = time.time() - t0
    sheet = Image.new("RGB", (SIZE[0] * len(ANGLES), SIZE[1] * 2), (255, 255, 255))
    for i, (b, a) in enumerate(zip(before, after)):
        sheet.paste(b, (i * SIZE[0], 0))
        sheet.paste(a, (i * SIZE[0], SIZE[1]))
    sheet.save(out / "d1_before_after.png")
    return {"soft_standing_5_angles_s": round(soft_s, 2), "pose_skinning_s": round(skin_s, 2), "photo_walking_5_angles_s": round(photo_s, 2), "pictures": str(out / "d1_before_after.png")}


if __name__ == "__main__":
    print(run(Path(sys.argv[1] if len(sys.argv) > 1 else "studio3d_out")))
