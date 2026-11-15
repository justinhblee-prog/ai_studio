"""Make SAMPLE images and a manifest for developing and testing the default library (R-034).

  python scripts/library_make_samples.py OUT_DIR [--per-category 6]

Writes OUT_DIR/images/*.png and OUT_DIR/manifest.csv. Every image is a plain colour block with "SAMPLE" in large letters and the
item id, so it can never be mistaken for a real photo. Every row has is_placeholder=yes, so the import tool refuses the set in a
production environment (--production or ACS_ENVIRONMENT=production). Model rows cover every allowed attribute value several times.
No network access; nothing outside OUT_DIR is touched.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# category -> (image size, Korean name, how many extra "kinds" of colour to cycle)
SPEC = {
    "model": ((384, 512), "샘플 모델"), "top": ((300, 400), "샘플 상의"), "bottom": ((300, 400), "샘플 하의"), "dress": ((300, 400), "샘플 원피스"),
    "outer": ((300, 400), "샘플 아우터"), "bag": ((300, 300), "샘플 가방"), "hat": ((300, 300), "샘플 모자"), "eyewear": ((300, 300), "샘플 안경"),
    "shoes": ((300, 300), "샘플 신발"), "jewelry": ((300, 300), "샘플 주얼리"), "headwear": ((300, 300), "샘플 머리 덮개"),
    "belt_scarf": ((300, 300), "샘플 벨트·스카프"), "background": ((600, 400), "샘플 배경"),
}
PALETTE = [(231, 111, 81), (244, 162, 97), (233, 196, 106), (42, 157, 143), (38, 70, 83), (131, 197, 190), (168, 126, 190), (200, 200, 200)]


def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow: the fixed small default font
        return ImageFont.load_default()


def make_image(path: Path, size, color, line1: str, line2: str):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.text((size[0] // 2, size[1] // 2 - 20), "SAMPLE", fill=(255, 255, 255), font=_font(max(24, size[0] // 6)), anchor="mm")
    draw.text((size[0] // 2, size[1] // 2 + size[0] // 8), line1, fill=(255, 255, 255), font=_font(max(12, size[0] // 18)), anchor="mm")
    draw.text((size[0] // 2, size[1] - 16), line2, fill=(255, 255, 255), font=_font(11), anchor="mm")
    image.save(path, format="PNG")


def build(out: Path, per_category: int = 6) -> dict:
    from app import library
    images = out / "images"
    images.mkdir(parents=True, exist_ok=True)
    attr_names = list(library.MODEL_ATTRIBUTES)
    columns = ["id", "category", "subcategory", "name_ko", "name_en", "tags", "file", "source", "tool_and_date", "rights_ok",
               "likeness_check", "note", "status", "is_placeholder", *attr_names]
    rows = []
    for category, (size, label) in SPEC.items():
        count = max(per_category, 2 * max(len(v) for v in library.MODEL_ATTRIBUTES.values())) if category == "model" else per_category
        for n in range(1, count + 1):
            item_id = f"sample-{category.replace('_', '-')}-{n:02d}"
            color = PALETTE[(n + len(category)) % len(PALETTE)]
            make_image(images / f"{item_id}.png", size, color, f"{category} {n:02d}", "표시용 샘플 이미지 - 실제 사진이 아님")
            row = {c: "" for c in columns}
            row.update({"id": item_id, "category": category, "name_ko": f"{label} {n}", "tags": f"샘플,{label}", "file": f"{item_id}.png",
                        "source": "ai_generated" if category == "model" else ("licensed" if n % 2 else "self_made"),
                        "tool_and_date": "library_make_samples.py (표시용 SAMPLE)", "rights_ok": "yes", "likeness_check": "yes",
                        "note": "개발·시험용 표시 이미지", "status": "published", "is_placeholder": "yes"})
            if category == "model":  # every value of every attribute appears: index n walks through each list in turn
                for name in attr_names:
                    values = library.MODEL_ATTRIBUTES[name]
                    row[name] = values[(n - 1) % len(values)]
            rows.append(row)
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": len(rows), "manifest": str(out / "manifest.csv"), "images": str(images)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--per-category", type=int, default=6)
    args = parser.parse_args(argv)
    if args.per_category < 1 or args.per_category > 50:
        parser.error("--per-category must be 1..50")
    result = build(args.out, args.per_category)
    print(f"wrote {result['rows']} SAMPLE items: {result['manifest']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
