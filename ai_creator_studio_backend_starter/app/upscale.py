"""Lane 3 / E-09d: UPSCALING by classical interpolation (Pillow only: no AI model, no network, no new dependency), a candidate comparison, and a size guard.

What it is: resize an image larger with a resampling filter and, optionally, a mild unsharp mask so the edges do not look soft. What it is NOT: it adds no detail that is not in the picture (that
needs a super-resolution model, which is not approved here): a blurry photo stays blurry, only bigger. The comparison below is measured by a ROUND TRIP (shrink a sharp picture, enlarge it back
with each candidate, compare with the original), the one honest way to rank interpolation without a model.
Alpha is kept (the resize premultiplies, so a transparent edge does not grow a dark halo); the sharpening touches colour only.
"""
from __future__ import annotations

import math
import random
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

MAX_SIDE = 8192
MAX_PIXELS = 40_000_000           # a result above this is refused before anything is allocated
FILTERS = {"nearest": Image.NEAREST, "bilinear": Image.BILINEAR, "bicubic": Image.BICUBIC, "lanczos": Image.LANCZOS}
DEFAULT_METHOD = "lanczos"
PSNR_CAP = 60.0                   # an exact copy would be infinite; capped so one lucky case cannot decide a ranking


class UpscaleError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def target_size(size: tuple[int, int], factor_pct: int) -> tuple[int, int]:
    w, h = size
    out = (max(1, round(w * factor_pct / 100)), max(1, round(h * factor_pct / 100)))
    if max(out) > MAX_SIDE or out[0] * out[1] > MAX_PIXELS:
        raise UpscaleError("STEP_RESULT_TOO_LARGE", f"the result would be {out[0]}x{out[1]} px; the limit is {MAX_SIDE} px per side and {MAX_PIXELS // 1_000_000} megapixels")
    return out


def upscale(image: Image.Image, factor_pct: int = 200, sharpen_pct: int = 30, method: str = DEFAULT_METHOD) -> Image.Image:
    """``factor_pct`` 100 = unchanged size, 200 = twice as wide and tall. ``sharpen_pct`` 0..100 scales an unsharp mask (0 = none)."""
    if method not in FILTERS:
        raise UpscaleError("UPSCALE_METHOD_UNKNOWN", f"method must be one of {sorted(FILTERS)}")
    size = target_size(image.size, factor_pct)
    has_alpha = "A" in image.getbands()
    base = image.convert("RGBA" if has_alpha else "RGB")
    bigger = base.resize(size, FILTERS[method]) if size != base.size else base.copy()
    if sharpen_pct and method != "nearest":
        radius, percent = 1.4, int(round(120 * sharpen_pct / 100))
        if has_alpha:
            # sharpen only well inside the opaque part: next to a transparent area the (black) colour of the transparent pixels would be sharpened INTO the edge as a dark fringe
            plain = bigger.convert("RGB")
            sharp = plain.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=2))
            inside = bigger.getchannel("A").filter(ImageFilter.MinFilter(2 * math.ceil(radius) + 1))
            out = Image.composite(sharp, plain, inside)
            out.putalpha(bigger.getchannel("A"))
            return out
        return bigger.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=2))
    return bigger


# ------------------------------------------------------------------------------------------------------------------ evaluation
def evaluation_set(size: int = 128) -> list[tuple[str, Image.Image]]:
    """Sharp synthetic pictures with the kinds of detail photos have: thin lines, a checker, text-like strokes, round shapes, noise."""
    rng = random.Random(5)
    cases: list[tuple[str, Image.Image]] = []
    img = Image.new("RGB", (size, size), (250, 250, 250))
    d = ImageDraw.Draw(img)
    for x in range(0, size, 6):
        d.line((x, 0, x, size), fill=(30, 30, 30), width=1)
    cases.append(("thin vertical lines", img))
    img = Image.new("RGB", (size, size), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, size, 7):                     # 7 px cells: NOT aligned with a 2x shrink, so no candidate can win by landing on the pixel grid
        for x in range(0, size, 7):
            if (x // 7 + y // 7) % 2 == 0:
                d.rectangle((x, y, x + 6, y + 6), fill=(20, 20, 20))
    cases.append(("checker 7 px", img))
    img = Image.new("RGB", (size, size), (240, 240, 235))
    d = ImageDraw.Draw(img)
    for i in range(10):
        y = 10 + i * 11
        for j in range(0, size - 12, 14):
            d.line((j + 2, y, j + 2 + rng.randint(3, 9), y + rng.randint(-2, 2)), fill=(10, 10, 10), width=2)
    cases.append(("text-like strokes", img))
    img = Image.new("RGB", (size, size), (235, 235, 235))
    d = ImageDraw.Draw(img)
    d.ellipse((20, 20, size - 20, size - 20), fill=(200, 40, 40), outline=(40, 0, 0), width=3)
    d.ellipse((50, 50, size - 50, size - 50), fill=(250, 220, 40))
    cases.append(("round shapes", img))
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            v = 128 + int(60 * math.sin(x / 7.0) * math.cos(y / 9.0)) + rng.randint(-12, 12)
            px[x, y] = (max(0, min(255, v)),) * 3
    cases.append(("smooth waves + noise", img))
    return cases


def psnr(a: Image.Image, b: Image.Image) -> float:
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    rms = math.sqrt(sum(ch * ch for ch in ImageStat.Stat(diff).rms) / 3)
    return PSNR_CAP if rms == 0 else min(PSNR_CAP, round(20 * math.log10(255.0 / rms), 2))


def round_trip_table(factor_pct: int = 200) -> dict[str, Any]:
    """For each candidate (and each with the default sharpening): shrink the original to 100/factor with a box filter (like a camera's area average), enlarge back, PSNR against the original."""
    rows, candidates = [], [(m, 0) for m in FILTERS] + [(m, 30) for m in ("bicubic", "lanczos")]
    for name, original in evaluation_set():
        small = original.resize((original.width * 100 // factor_pct, original.height * 100 // factor_pct), Image.BOX)
        row = {"case": name}
        for method, sharpen in candidates:
            row[f"{method}{'+sharpen' + str(sharpen) if sharpen else ''}"] = psnr(upscale(small, factor_pct, sharpen, method), original)
        rows.append(row)
    keys = [k for k in rows[0] if k != "case"]
    mean = {k: round(sum(r[k] for r in rows) / len(rows), 2) for k in keys}
    return {"factor_pct": factor_pct, "rows": rows, "mean_psnr_db": mean, "best": max(mean, key=mean.get),
            "note": "round trip on synthetic pictures: higher is closer to the original; no model, no new detail is created"}
