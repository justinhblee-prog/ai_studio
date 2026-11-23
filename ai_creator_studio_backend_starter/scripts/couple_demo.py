"""D-3: before/after picture of the couple try-on (own3d mock) on a SYNTHETIC couple photo (two rendered mannequins side by side).

   python scripts/couple_demo.py [out.png]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import couple, couple_jobs, render3d_scene, render3d_soft  # noqa: E402


def main(out: Path) -> dict:
    left, _, _ = render3d_scene.build_layers("female", None, [])
    right, _, _ = render3d_scene.build_layers("male", None, [])
    h = max(render3d_soft.height_of(left), render3d_soft.height_of(right))
    a = render3d_soft.render(left, 0, (240, 480), background=(214, 224, 236), height_m=h)
    b = render3d_soft.render(right, 0, (240, 480), background=(214, 224, 236), height_m=h)
    photo = Image.new("RGB", (460, 480), (214, 224, 236))
    photo.paste(a.crop((20, 0, 220, 480)), (0, 0))
    photo.paste(b.crop((20, 0, 220, 480)), (260, 0))
    slots = {"a": ["top", "skirt"], "b": ["jacket", "bottom"]}
    done = couple.run_couple(photo, couple_jobs.mannequin_runner({"a": "female", "b": "male"}, slots, None))
    sheet = Image.new("RGB", (photo.width * 2, photo.height), (255, 255, 255))
    sheet.paste(photo, (0, 0))
    sheet.paste(done["image"], (photo.width, 0))
    sheet.save(out)
    return {"overlap_px": done["overlap_px"], "people": done["people"], "picture": str(out)}


if __name__ == "__main__":
    print(main(Path(sys.argv[1] if len(sys.argv) > 1 else "couple_demo.png")))
