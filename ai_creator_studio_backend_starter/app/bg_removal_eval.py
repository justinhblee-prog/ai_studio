"""Lane 3 / E-09a: the evaluation set and the scorer for the background removal candidates (app/bg_removal.py).

Every case is a DRAWN picture (no photograph, no downloaded file) with an exact truth mask, so the numbers are reproducible on any machine:
`python -m app.bg_removal_eval` prints the table that docs/ENGINE_QUALITY.md records. Drawn pictures are easier than real photos (no lens
blur, no JPEG noise, no texture): the scores are an upper bound for real photos, not a promise.

Scores per case and method: IoU of the kept area against the truth (1.0 = identical), `detail_kept` = share of a marked detail (a logo in the
background's colour, thin straps) that survived, and the run time in milliseconds.
"""
from __future__ import annotations

import random
import time
from typing import Any, Callable

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from app.bg_removal import METHODS, remove_background

BG = (250, 250, 250)
SIDE = 1000
DETAIL_FLOOR = 0.95      # a method that loses more than 5% of a marked detail in any case cannot be selected


def _blank(size: tuple[int, int], colour: tuple[int, int, int] = BG) -> tuple[Image.Image, Image.Image]:
    return Image.new("RGB", size, colour), Image.new("L", size, 0)


def _both(img: Image.Image, truth: Image.Image, draw: Callable[[ImageDraw.ImageDraw, Any], None], colour) -> None:
    """Draw the same shape on the picture (in `colour`) and on the truth mask (in 255)."""
    draw(ImageDraw.Draw(img), colour)
    draw(ImageDraw.Draw(truth), 255)


def case_plain():
    img, truth = _blank((SIDE, SIDE))
    _both(img, truth, lambda d, c: d.rounded_rectangle((200, 250, 800, 750), radius=60, fill=c), (30, 70, 170))
    return img, truth, None


def case_small_exact():
    img, truth = _blank((300, 300))
    _both(img, truth, lambda d, c: d.ellipse((60, 80, 240, 220), fill=c), (170, 40, 40))
    return img, truth, None


def case_gradient_background():
    size = (SIDE, SIDE)
    shade = Image.linear_gradient("L").resize(size).point(lambda v: 255 - round(v * 30 / 255))    # 255 at the top, 225 at the bottom
    img, truth = Image.merge("RGB", (shade, shade, shade)), Image.new("L", size, 0)
    _both(img, truth, lambda d, c: d.rounded_rectangle((250, 200, 750, 800), radius=40, fill=c), (180, 30, 40))
    return img, truth, None


def case_white_product_with_outline():
    img, truth = _blank((SIDE, SIDE))
    ImageDraw.Draw(img).rounded_rectangle((200, 200, 800, 800), radius=80, fill=(236, 236, 236), outline=(40, 40, 40), width=5)
    ImageDraw.Draw(truth).rounded_rectangle((200, 200, 800, 800), radius=80, fill=255)
    return img, truth, None


def case_logo_in_background_colour():
    img, truth = _blank((SIDE, SIDE))
    _both(img, truth, lambda d, c: d.rounded_rectangle((150, 250, 850, 750), radius=50, fill=c), (25, 25, 30))
    detail = Image.new("L", img.size, 0)
    for box in ((300, 430, 380, 570), (420, 430, 500, 570), (540, 430, 700, 470), (540, 530, 700, 570)):
        ImageDraw.Draw(img).rectangle(box, fill=BG)
        ImageDraw.Draw(detail).rectangle(box, fill=255)
    return img, truth, detail


def case_ring_with_hole():
    img, truth = _blank((SIDE, SIDE))
    _both(img, truth, lambda d, c: d.ellipse((200, 200, 800, 800), fill=c), (60, 50, 40))
    ImageDraw.Draw(img).ellipse((380, 380, 620, 620), fill=BG)       # the background shows through the hole
    ImageDraw.Draw(truth).ellipse((380, 380, 620, 620), fill=0)
    return img, truth, None


def case_cast_shadow():
    img, truth = _blank((SIDE, SIDE))
    shadow = Image.new("L", img.size, 0)
    ImageDraw.Draw(shadow).ellipse((220, 700, 780, 820), fill=70)
    shadow = shadow.filter(ImageFilter.GaussianBlur(25))
    img = ImageChops.subtract(img, Image.merge("RGB", (shadow, shadow, shadow)))
    _both(img, truth, lambda d, c: d.rounded_rectangle((300, 250, 700, 760), radius=30, fill=c), (40, 110, 70))
    return img, truth, None


def case_noisy_background():
    size = (600, 600)
    rnd = random.Random(7)
    noise = Image.frombytes("L", size, bytes(rnd.choices(range(238, 251), k=size[0] * size[1])))
    img, truth = Image.merge("RGB", (noise, noise, noise)), Image.new("L", size, 0)
    _both(img, truth, lambda d, c: d.ellipse((150, 120, 450, 480), fill=c), (200, 120, 20))
    return img, truth, None


def case_coloured_background():
    img, truth = _blank((SIDE, SIDE), (200, 180, 150))
    _both(img, truth, lambda d, c: d.ellipse((220, 300, 780, 700), fill=c), (20, 90, 60))
    return img, truth, None


def case_large_with_thin_straps():
    img, truth = _blank((1600, 1200))
    _both(img, truth, lambda d, c: d.rounded_rectangle((450, 400, 1150, 1050), radius=40, fill=c), (120, 20, 30))
    detail = Image.new("L", img.size, 0)
    for line in (((500, 400), (440, 150)), ((1100, 400), (1160, 150))):          # open straps, 3 pixels wide
        _both(img, truth, lambda d, c: d.line(line, fill=c, width=3), (120, 20, 30))
        ImageDraw.Draw(detail).line(line, fill=255, width=3)
    return img, truth, detail


def case_low_contrast():
    img, truth = _blank((SIDE, SIDE))
    _both(img, truth, lambda d, c: d.rounded_rectangle((250, 250, 750, 750), radius=40, fill=c), (240, 240, 240))
    return img, truth, None


CASES: dict[str, tuple[Callable, str]] = {
    "plain": (case_plain, "dark product on a plain light background"),
    "small_exact": (case_small_exact, "300 px picture: no reduction step"),
    "gradient_background": (case_gradient_background, "background 255 -> 225 from top to bottom"),
    "white_product_with_outline": (case_white_product_with_outline, "near-white product with a dark outline"),
    "logo_in_background_colour": (case_logo_in_background_colour, "logo inside the product has the background's colour"),
    "ring_with_hole": (case_ring_with_hole, "KNOWN LIMIT: background visible through a hole"),
    "cast_shadow": (case_cast_shadow, "KNOWN LIMIT: soft shadow under the product"),
    "noisy_background": (case_noisy_background, "background noise of +-6 levels"),
    "coloured_background": (case_coloured_background, "beige background"),
    "large_with_thin_straps": (case_large_with_thin_straps, "1600x1200, straps 3 px wide"),
    "low_contrast": (case_low_contrast, "KNOWN LIMIT: product 10 levels from the background, no outline"),
}


def _binary(alpha: Image.Image) -> Image.Image:
    return alpha.point(lambda v: 255 if v > 127 else 0)


def iou(alpha: Image.Image, truth: Image.Image) -> float:
    kept = _binary(alpha)
    union = ImageChops.lighter(kept, truth).histogram()[255]
    return 1.0 if union == 0 else ImageChops.darker(kept, truth).histogram()[255] / union


def detail_kept(alpha: Image.Image, detail: Image.Image) -> float:
    total = detail.histogram()[255]
    return 1.0 if total == 0 else ImageChops.darker(_binary(alpha), detail).histogram()[255] / total


def evaluate(remover: Callable[..., tuple[Image.Image, dict]] = remove_background, methods: tuple[str, ...] = METHODS) -> dict[str, Any]:
    """Run every method on every case. `selected` = best mean IoU among the methods that keep every marked detail (>= DETAIL_FLOOR)."""
    cases = []
    for name, (build, note) in CASES.items():
        img, truth, detail = build()
        results = {}
        for method in methods:
            started = time.perf_counter()
            out, info = remover(img, method=method)
            elapsed = (time.perf_counter() - started) * 1000
            alpha = out.getchannel("A")
            results[method] = {"iou": round(iou(alpha, truth), 4), "detail_kept": None if detail is None else round(detail_kept(alpha, detail), 4),
                               "ms": round(elapsed, 1), "warnings": info["warnings"]}
        cases.append({"name": name, "size": list(img.size), "note": note, "results": results})
    summary = {}
    for method in methods:
        rows = [c["results"][method] for c in cases]
        details = [r["detail_kept"] for r in rows if r["detail_kept"] is not None]
        summary[method] = {"mean_iou": round(sum(r["iou"] for r in rows) / len(rows), 4), "min_iou": min(r["iou"] for r in rows),
                           "cases_iou_99": sum(1 for r in rows if r["iou"] >= 0.99), "min_detail_kept": min(details) if details else None,
                           "max_ms": max(r["ms"] for r in rows)}
    eligible = [m for m in methods if summary[m]["min_detail_kept"] is None or summary[m]["min_detail_kept"] >= DETAIL_FLOOR]
    selected = max(eligible, key=lambda m: summary[m]["mean_iou"]) if eligible else None
    return {"cases": cases, "summary": summary, "selected": selected, "case_count": len(cases)}


def to_markdown(report: dict[str, Any]) -> str:
    methods = list(report["summary"])
    lines = ["| case | size | " + " | ".join(f"{m} IoU / detail / ms" for m in methods) + " |", "|---|---|" + "---|" * len(methods)]
    for case in report["cases"]:
        cells = []
        for m in methods:
            r = case["results"][m]
            cells.append(f"{r['iou']:.4f} / {'-' if r['detail_kept'] is None else format(r['detail_kept'], '.4f')} / {r['ms']:.0f}")
        lines.append(f"| {case['name']} | {case['size'][0]}x{case['size'][1]} | " + " | ".join(cells) + " |")
    lines += ["", "| method | mean IoU | min IoU | cases with IoU >= 0.99 | min detail kept | slowest case ms |", "|---|---|---|---|---|---|"]
    for m in methods:
        s = report["summary"][m]
        lines.append(f"| {m} | {s['mean_iou']:.4f} | {s['min_iou']:.4f} | {s['cases_iou_99']}/{report['case_count']} | "
                     f"{'-' if s['min_detail_kept'] is None else format(s['min_detail_kept'], '.4f')} | {s['max_ms']:.0f} |")
    lines += ["", f"selected: {report['selected']}"]
    return "\n".join(lines)


if __name__ == "__main__":
    print(to_markdown(evaluate()))
