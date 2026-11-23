"""D-2: ten SYNTHETIC full-body photos (rendered own3d mannequins of known measurements) -> estimated measurements table + front/side render sheet of the re-built bodies.

   python scripts/photo_body_sheet.py [out_dir]      prints a markdown table, writes photo_body_sheet.png

A CLOSED LOOP: the answer is built into each picture, so this measures the estimator, not real-world photos (none were available: 미실행).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import photo_body, render3d_scene, render3d_soft  # noqa: E402

PEOPLE = [("female", {"height_cm": 166, "chest_cm": 88, "waist_cm": 70, "hips_cm": 96}), ("female", {"height_cm": 158, "chest_cm": 80, "waist_cm": 64, "hips_cm": 90}),
          ("female", {"height_cm": 175, "chest_cm": 100, "waist_cm": 84, "hips_cm": 108}), ("female", {"height_cm": 162, "chest_cm": 92, "waist_cm": 76, "hips_cm": 102}),
          ("female", {"height_cm": 170, "chest_cm": 84, "waist_cm": 66, "hips_cm": 94}), ("male", {"height_cm": 178, "chest_cm": 98, "waist_cm": 84, "hips_cm": 100}),
          ("male", {"height_cm": 185, "chest_cm": 108, "waist_cm": 96, "hips_cm": 106}), ("male", {"height_cm": 172, "chest_cm": 92, "waist_cm": 80, "hips_cm": 96}),
          ("male", {"height_cm": 190, "chest_cm": 112, "waist_cm": 90, "hips_cm": 104}), ("male", {"height_cm": 168, "chest_cm": 88, "waist_cm": 74, "hips_cm": 92})]
SIZE = (240, 426)


def build(out: Path) -> str:
    out.mkdir(parents=True, exist_ok=True)
    rows, sheet = [], Image.new("RGB", (SIZE[0] * 4, SIZE[1] * len(PEOPLE) // 2 + 20 * 0), (255, 255, 255))
    sheet = Image.new("RGB", (SIZE[0] * 4 * 1, SIZE[1] * 5), (255, 255, 255))
    errs = {"chest_cm": [], "waist_cm": [], "hips_cm": []}
    for i, (sex, m) in enumerate(PEOPLE):
        body, _, _ = render3d_scene.build_layers(sex, m, [])
        h = render3d_soft.height_of(body)
        photo = render3d_soft.render(body, 0, (360, 640), background=(214, 224, 236), height_m=h)
        est = photo_body.estimate(photo, sex=sex, height_cm=m["height_cm"])
        e = est["measurements"]
        for k in errs:
            errs[k].append(abs(e[k] - m[k]))
        rows.append(f"| {i + 1} {sex} | {m['height_cm']} | {m['chest_cm']} / {e['chest_cm']}{'*' if est['chest_from_prior'] else ''} | {m['waist_cm']} / {e['waist_cm']} | {m['hips_cm']} / {e['hips_cm']} |")
        rebuilt, _, _ = render3d_scene.build_layers(sex, e, [])
        hh = render3d_soft.height_of(rebuilt)
        col, row = (i % 2) * 2, i // 2
        for j, angle in enumerate((0, 90)):
            sheet.paste(render3d_soft.render(rebuilt, angle, SIZE, background=(214, 224, 236), height_m=max(h, hh)), ((col + j) * SIZE[0], row * SIZE[1]))
    sheet.save(out / "photo_body_sheet.png")
    summary = {k: (round(sum(v) / len(v), 1), round(max(v), 1)) for k, v in errs.items()}
    head = "| person | height cm | chest truth / est | waist truth / est | hips truth / est |\n|---|---|---|---|---|\n"
    return head + "\n".join(rows) + f"\n\n(* chest taken from the waist with a prior: the arms hang against the chest)\nabs error cm (mean, max): {summary}\n"


if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else "photo_body_out")))
