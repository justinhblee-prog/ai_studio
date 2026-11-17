"""Lane 3 / E-09a: background removal CANDIDATES (Pillow only, classical image processing) and a small synthetic evaluation set.

Why classical: an AI cut-out model (U2-Net, rembg, a paid API) needs a new dependency / model file / external service, which is not approved. These two candidates only
work when the product sits on a roughly plain or smoothly shaded background; ``removal_confidence`` says so instead of pretending.

Candidates
  ``flood``     edge-seeded flood fill: grow the background from many border points while the colour stays within a tolerance of the seed.
  ``gradient``  model the background as a bilinear blend of the four corner colours, keep pixels that differ from it, close holes, soften the edge.

Both return an RGBA image (alpha 0 = background) and never touch the network.
"""
from __future__ import annotations

import random
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter

METHODS = ("flood", "gradient")
MARK = (255, 0, 254)


def _patch_median(img: Image.Image, x: int, y: int, r: int = 3) -> tuple[int, int, int]:
    box = img.crop((max(0, x - r), max(0, y - r), min(img.width, x + r + 1), min(img.height, y + r + 1))).convert("RGB")
    chans = []
    for band in box.split():
        values = sorted(band.getdata())
        chans.append(values[len(values) // 2])
    return tuple(chans)  # type: ignore[return-value]


def _corner_background(img: Image.Image) -> Image.Image:
    w, h = img.size
    m = 4
    corners = [_patch_median(img, m, m), _patch_median(img, w - 1 - m, m), _patch_median(img, m, h - 1 - m), _patch_median(img, w - 1 - m, h - 1 - m)]
    small = Image.new("RGB", (2, 2))
    small.putdata(corners)
    return small.resize((w, h), Image.BILINEAR)


def _mask_flood(rgb: Image.Image, tolerance: int) -> Image.Image:
    work = rgb.copy()
    w, h = work.size
    seeds = [(i * (w - 1) // 8, 0) for i in range(9)] + [(i * (w - 1) // 8, h - 1) for i in range(9)] + [(0, j * (h - 1) // 8) for j in range(9)] + [(w - 1, j * (h - 1) // 8) for j in range(9)]
    for seed in seeds:
        if work.getpixel(seed) != MARK:
            ImageDraw.floodfill(work, seed, MARK, thresh=tolerance)
    marker = Image.new("RGB", work.size, MARK)
    background = ImageChops.difference(work, marker).convert("L").point(lambda v: 255 if v == 0 else 0)
    return ImageChops.invert(background)                      # 255 = foreground


def _mask_gradient(rgb: Image.Image, tolerance: int) -> Image.Image:
    diff = ImageChops.difference(rgb, _corner_background(rgb))
    r, g, b = diff.split()
    strength = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mask = strength.point(lambda v: 255 if v > tolerance else 0).filter(ImageFilter.MedianFilter(5))
    # close holes: whatever the border can reach in the inverted mask is background, everything else is product
    inverse = ImageChops.invert(mask).convert("RGB")
    for seed in ((0, 0), (inverse.width - 1, 0), (0, inverse.height - 1), (inverse.width - 1, inverse.height - 1)):
        if inverse.getpixel(seed) == (255, 255, 255):
            ImageDraw.floodfill(inverse, seed, MARK)
    reached = ImageChops.difference(inverse, Image.new("RGB", inverse.size, MARK)).convert("L").point(lambda v: 255 if v == 0 else 0)
    return ImageChops.invert(reached)


def foreground_mask(img: Image.Image, method: str = "gradient", tolerance: int | None = None) -> Image.Image:
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    rgb = img.convert("RGB")
    if method == "flood":
        return _mask_flood(rgb, 40 if tolerance is None else tolerance)
    return _mask_gradient(rgb, 28 if tolerance is None else tolerance)


def remove_background(img: Image.Image, method: str = "gradient", tolerance: int | None = None, feather: float = 0.8) -> Image.Image:
    mask = foreground_mask(img, method, tolerance)
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def removal_confidence(img: Image.Image, method: str = "gradient") -> dict[str, Any]:
    """A cheap honesty check: how much of the picture became product, and how different the product is from the background it was cut from."""
    mask = foreground_mask(img, method)
    hist = mask.histogram()
    fg = sum(hist[128:]) / (mask.width * mask.height)
    rgb = img.convert("RGB")
    bg_model = _corner_background(rgb)
    fg_mean = ImageChops.multiply(rgb, Image.merge("RGB", (mask, mask, mask))).resize((1, 1), Image.BOX).getpixel((0, 0))
    scale = 255 * max(fg, 1e-6)
    fg_colour = tuple(min(255, int(c * 255 / scale)) for c in fg_mean) if fg > 0 else (0, 0, 0)
    bg_colour = bg_model.resize((1, 1), Image.BOX).getpixel((0, 0))
    contrast = sum(abs(a - b) for a, b in zip(fg_colour, bg_colour)) / 3
    warnings = []
    if fg < 0.02:
        warnings.append("almost nothing was kept: the product may look like the background")
    if fg > 0.97:
        warnings.append("almost everything was kept: the background may be busy or textured")
    if contrast < 25 and fg >= 0.02:
        warnings.append("the product is close to the background colour: the cut-out is uncertain")
    return {"foreground_share": round(fg, 3), "colour_contrast": round(contrast, 1), "reliable": not warnings, "warnings": warnings}


# --- evaluation set -------------------------------------------------------------------------------------------------------------------
SIZE = (160, 160)


def _background(kind: str, rng: random.Random) -> Image.Image:
    w, h = SIZE
    if kind == "white":
        return Image.new("RGB", SIZE, (252, 252, 252))
    if kind == "gray":
        return Image.new("RGB", SIZE, (205, 207, 210))
    if kind == "gradient":
        small = Image.new("RGB", (2, 2))
        small.putdata([(235, 238, 245), (215, 225, 240), (190, 200, 215), (170, 180, 200)])
        return small.resize(SIZE, Image.BILINEAR)
    if kind == "noisy":
        base = Image.new("RGB", SIZE, (228, 226, 220))
        noise = Image.effect_noise(SIZE, 10).convert("RGB")
        return ImageChops.blend(base, noise, 0.12)
    raise ValueError(kind)


def _product(shape: str, colour: tuple[int, int, int]) -> tuple[Image.Image, Image.Image]:
    """(picture of the product on transparent black, its exact mask)."""
    w, h = SIZE
    mask = Image.new("L", SIZE, 0)
    d = ImageDraw.Draw(mask)
    if shape == "ellipse":
        d.ellipse((34, 28, 126, 134), fill=255)
    elif shape == "rect":
        d.rounded_rectangle((38, 30, 122, 132), radius=14, fill=255)
    elif shape == "donut":
        d.ellipse((30, 30, 130, 130), fill=255)
        d.ellipse((62, 62, 98, 98), fill=0)                  # a real hole the cut-out must keep as background
    else:
        raise ValueError(shape)
    body = Image.new("RGB", SIZE, colour)
    shade = Image.new("RGB", SIZE, (0, 0, 0))
    shade.paste((255, 255, 255), (0, 0, w, h // 2))
    body = ImageChops.blend(body, ImageChops.multiply(body, shade.filter(ImageFilter.GaussianBlur(30))), 0.25)
    return body, mask


def evaluation_set() -> list[dict[str, Any]]:
    rng = random.Random(11)
    cases = []
    spec = [("white", "ellipse", (200, 40, 40)), ("white", "rect", (30, 60, 170)), ("gray", "ellipse", (40, 120, 60)), ("gradient", "rect", (150, 60, 160)),
            ("noisy", "ellipse", (60, 60, 60)), ("white", "donut", (220, 150, 30)), ("gradient", "donut", (30, 30, 30)),
            ("white", "ellipse", (246, 246, 246))]                # the hard case: a white product on a white background
    for background, shape, colour in spec:
        body, mask = _product(shape, colour)
        picture = _background(background, rng)
        picture.paste(body, (0, 0), mask)
        cases.append({"name": f"{background}-{shape}-{'x'.join(map(str, colour))}", "image": picture, "truth": mask, "hard": colour == (246, 246, 246)})
    return cases


def iou(predicted: Image.Image, truth: Image.Image) -> float:
    p, t = predicted.point(lambda v: 255 if v >= 128 else 0), truth.point(lambda v: 255 if v >= 128 else 0)
    inter = sum(ImageChops.multiply(p, t).point(lambda v: 255 if v > 0 else 0).histogram()[255:])
    union = sum(ImageChops.lighter(p, t).histogram()[255:])
    return inter / union if union else 1.0


def evaluate(methods: tuple[str, ...] = METHODS) -> dict[str, Any]:
    cases = evaluation_set()
    table: dict[str, dict[str, float]] = {m: {} for m in methods}
    for case in cases:
        for method in methods:
            table[method][case["name"]] = round(iou(foreground_mask(case["image"], method), case["truth"]), 4)
    easy = [c["name"] for c in cases if not c["hard"]]
    summary = {m: {"mean_iou_easy": round(sum(table[m][n] for n in easy) / len(easy), 4), "min_iou_easy": min(table[m][n] for n in easy)} for m in methods}
    best = max(methods, key=lambda m: summary[m]["mean_iou_easy"])
    return {"cases": [c["name"] for c in cases], "iou": table, "summary": summary, "selected": best}
