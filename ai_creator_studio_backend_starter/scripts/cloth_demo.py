"""M3 stage 1 demo: one sleeveless top (XPBD cloth) draping over the own3d torso. Prints timing and numbers; writes before/after PNG.

   python scripts/cloth_demo.py [out.png] [steps]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import base_models, cloth_xpbd, render3d_photo, render3d_scene, render3d_soft  # noqa: E402


def main(out: Path, steps: int = 240) -> dict:
    sex = "female"
    body = render3d_soft.triangles_of(base_models.build_base_model(sex, top_style="tank", bottom_style="shorts", skin=render3d_scene.SKIN, top=render3d_scene.SKIN, bottom=render3d_scene.SKIN))
    cloth = cloth_xpbd.Cloth(sex)
    before = cloth.triangles()
    result = cloth.run(steps)
    after = cloth.triangles()
    h = 1.05 * render3d_soft.height_of(body)
    size = (270, 480)
    sheet = Image.new("RGB", (size[0] * 4, size[1]), (255, 255, 255))
    for i, (tris, ang) in enumerate(((before, 0), (after, 0), (before, 90), (after, 90))):
        sheet.paste(render3d_photo.render_photo([(body, "skin"), (tris, "cloth")], ang, size, height_m=h, ss=1), (i * size[0], 0))
    sheet.save(out)
    return result


if __name__ == "__main__":
    print(main(Path(sys.argv[1] if len(sys.argv) > 1 else "cloth_demo.png"), int(sys.argv[2]) if len(sys.argv) > 2 else 240))
