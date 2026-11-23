"""M5: one picture with the five poses (front and side) of the own3d mannequin wearing a top and trousers, plus the measured penetration per pose.

   python scripts/pose_sheet.py [out.png]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import pose_rig, render3d_photo, render3d_soft  # noqa: E402

SIZE = (216, 384)


def build(out: Path, sex: str = "female", kinds: tuple[str, ...] = ("top", "bottom")) -> list[dict]:
    sheet = Image.new("RGB", (SIZE[0] * len(pose_rig.POSES), SIZE[1] * 2 + 20), (255, 255, 255))
    results = []
    d = ImageDraw.Draw(sheet)
    for i, pose in enumerate(pose_rig.POSES):
        _, body, layers, _ = pose_rig.posed_scene(sex, None, list(kinds), pose)
        height = 1.05 * max(c[1] for t in body + [t for _, g, _ in layers for t in g] for c in t[0])
        for row, angle in enumerate((0, 90)):
            img = render3d_photo.render_photo([(body, "skin")] + [(g, "cloth") for _, g, _ in layers], angle, SIZE, height_m=height, ss=1, floor=True)
            sheet.paste(img, (i * SIZE[0], row * SIZE[1] + 20))
        d.text((i * SIZE[0] + 6, 4), pose, fill=(0, 0, 0))
        results.append(pose_rig.measure_pose(sex, None, list(kinds), pose))
    sheet.save(out)
    return results


if __name__ == "__main__":
    for r in build(Path(sys.argv[1] if len(sys.argv) > 1 else "pose_sheet.png")):
        print(r["pose"], [(g["kind"], g["visible_share_min"]) for g in r["garments"]])
