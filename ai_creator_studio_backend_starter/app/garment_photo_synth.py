"""R-ENGINE-15 evaluation set: SYNTHETIC flat-lay garment photos with KNOWN dimensions (Pillow only; nothing here is used by the server's request path).

A photo is drawn at 3x resolution from a polygon given in cm (so the truth is exact), a reference object is placed beside it, then the "camera" is applied:
noise, vignette, a soft shadow, a tilt of the garment and the card, a small perspective, a low-contrast background, a stripe pattern.
It tests the image-processing chain (cut-out -> reference scale -> row widths -> colour) under those conditions. It does NOT show how real garments or real phones behave:
the garment shapes are simple, the "truth" follows this module's own width definitions, and no real photo is involved.
"""
from __future__ import annotations

import io
import math
import random
import zlib
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from app import garment_photo

PX_PER_CM = 9.5
SIZE = (1400, 1100)
SS = 3                                  # supersampling for anti-aliased edges
CONDITIONS = ("clean", "noise_vignette", "shadow", "tilt", "perspective", "stripes", "stripes_light", "low_contrast")


def _rounded_rect(cx: float, cy: float, hw: float, hh: float, c: float, s: float, r: float) -> list[tuple[float, float]]:
    """Outline of a (rotated) rectangle with corner radius ``r`` (an ISO bank card has 3.18 mm corners)."""
    pts: list[tuple[float, float]] = []
    for sx, sy in ((1, -1), (1, 1), (-1, 1), (-1, -1)):
        centre = (sx * (hw - r), sy * (hh - r))
        start = {(1, -1): -90, (1, 1): 0, (-1, 1): 90, (-1, -1): 180}[(sx, sy)]
        steps = 8 if r > 0 else 1
        for i in range(steps + 1):
            a = math.radians(start + 90 * i / steps)
            pts.append((centre[0] + (r * math.cos(a) if r > 0 else sx * 0), centre[1] + (r * math.sin(a) if r > 0 else sy * 0)))
    if r == 0:
        pts = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


def _lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * min(1.0, max(0.0, u))


def _profile(points: list[tuple[float, float]], t: float) -> float:
    """Piecewise-linear width (cm) at share ``t`` of the garment's height; ``points`` = [(t, width)] ascending."""
    for (t0, w0), (t1, w1) in zip(points, points[1:]):
        if t0 <= t <= t1:
            return _lerp(w0, w1, (t - t0) / (t1 - t0) if t1 > t0 else 0.0)
    return points[-1][1] if t > points[-1][0] else points[0][1]


def _symmetric(points: list[tuple[float, float]], length: float, steps: int = 200) -> list[tuple[float, float]]:
    """Outline (cm, x centred, y down) of a body whose half-width follows ``points``."""
    left = [(-_profile(points, i / steps) / 2, length * i / steps) for i in range(steps + 1)]
    right = [(-x, y) for x, y in reversed(left)]
    return left + right


SHAPES = {
    "top": lambda d: _top(d),
    "jacket": lambda d: _top(d),
    "bottom": lambda d: _bottom(d),
    "skirt": lambda d: _skirt(d),
    "dress": lambda d: _dress(d),
}


def _top(d: dict[str, float]) -> tuple[list[tuple[float, float]], dict[str, float]]:
    wb, ww, length, sleeve = d["chest_flat"], d["waist_flat"], d["length_cm"], d["sleeve_cm"]
    prof = [(0.0, wb), (0.6, wb), (1.0, ww)]
    body = _profile
    n = wb * 0.22
    drop = min(0.25 * length, 0.55 * sleeve)
    y_a = 0.07 * length + drop
    out_x = wb / 2 + sleeve
    left = [(-n, 0.0), (-out_x, 0.07 * length), (-out_x, y_a), (-wb / 2, y_a)]
    left += [(-_profile(prof, t) / 2, length * t) for t in [y_a / length + (1 - y_a / length) * i / 120 for i in range(121)]]
    poly = left + [(-x, y) for x, y in reversed(left)]
    truth = {"chest_cm": 2 * body(prof, 0.525), "waist_cm": 2 * body(prof, 0.84), "length_cm": length, "sleeve_cm": sleeve}
    return poly, truth


def _bottom(d: dict[str, float]):
    ww, wh, length = d["waist_flat"], d["hips_flat"], d["length_cm"]
    prof = [(0.0, ww), (0.06, ww), (0.15, wh), (0.45, wh)]
    crotch = 0.45
    outer = [(-_profile(prof, i / 200 * crotch) / 2, length * i / 200 * crotch) for i in range(201)]
    hem_out = wh * 0.58 / 2
    legs = [(-_lerp(wh / 2, hem_out, i / 100), length * _lerp(crotch, 1.0, i / 100)) for i in range(1, 101)]
    inner_hem = wh * 0.08 / 2
    inner = [(-_lerp(0.0, inner_hem, i / 100), length * _lerp(crotch, 1.0, i / 100)) for i in range(0, 101)]
    left_side = outer + legs                                      # waist ... hem (outer edge of the left leg)
    left_inner = list(reversed(inner))                            # hem ... crotch (inner edge of the left leg)
    mirror = lambda pts: [(-x, y) for x, y in pts]
    poly = left_side + left_inner[:-1] + mirror(inner)[:-1] + mirror(list(reversed(legs))) + mirror(list(reversed(outer)))
    truth = {"waist_cm": 2 * ww, "hips_cm": 2 * wh, "length_cm": length}
    return poly, truth


def _skirt(d: dict[str, float]):
    ww, wh, wm, length = d["waist_flat"], d["hips_flat"], d["hem_flat"], d["length_cm"]
    prof = [(0.0, ww), (0.06, ww), (0.30, wh), (1.0, wm)]
    truth = {"waist_cm": 2 * ww, "hips_cm": 2 * wh, "length_cm": length}
    return _symmetric(prof, length), truth


def _dress(d: dict[str, float]):
    wc, ww, wh, wm, length = d["chest_flat"], d["waist_flat"], d["hips_flat"], d["hem_flat"], d["length_cm"]
    prof = [(0.0, wc * 0.9), (0.15, wc), (0.28, wc), (0.44, ww), (0.50, ww), (0.62, wh), (0.68, wh), (1.0, wm)]
    truth = {"chest_cm": 2 * wc, "waist_cm": 2 * ww, "hips_cm": 2 * wh, "length_cm": length}
    return _symmetric(prof, length), truth


DEFAULTS = {
    "top": {"chest_flat": 51.0, "waist_flat": 47.0, "length_cm": 68.0, "sleeve_cm": 15.0},
    "jacket": {"chest_flat": 55.0, "waist_flat": 52.0, "length_cm": 72.0, "sleeve_cm": 20.0},
    "bottom": {"waist_flat": 38.0, "hips_flat": 50.0, "length_cm": 100.0},
    "skirt": {"waist_flat": 34.0, "hips_flat": 46.0, "hem_flat": 62.0, "length_cm": 62.0},
    "dress": {"chest_flat": 45.0, "waist_flat": 38.0, "hips_flat": 50.0, "hem_flat": 66.0, "length_cm": 105.0},
}


def synthetic_photo(kind: str, *, scale: float = 1.0, condition: str = "clean", reference: str = "card", seed: int = 0, colour: tuple[int, int, int] = (190, 52, 60)) -> tuple[bytes, dict[str, Any]]:
    """(PNG bytes, truth). ``scale`` multiplies every flat width (a bigger or smaller size of the same shape); the length stays."""
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}")
    rng = random.Random(seed * 7919 + zlib.crc32(f"{kind}|{condition}".encode()) % 997)
    dims = {k: (v * scale if k.endswith("_flat") or k == "sleeve_cm" else v) for k, v in DEFAULTS[kind].items()}
    poly, truth = SHAPES[kind](dims)
    truth = {k: round(v, 2) for k, v in truth.items()}
    truth.update({"kind": kind, "colour": list(colour), "condition": condition, "reference": reference, "scale": scale})
    w, h = SIZE
    px = PX_PER_CM * SS
    bg = (236, 233, 226) if condition != "low_contrast" else (205, 98, 108)           # low contrast: a background close to the garment colour
    big = Image.new("RGB", (w * SS, h * SS), bg)
    d = ImageDraw.Draw(big)
    width_cm = max(x for x, _ in poly) - min(x for x, _ in poly)
    length = dims["length_cm"]
    gx, gy = max(w * SS * 0.36, (width_cm / 2 + 6) * px), (h * SS - length * px) / 2
    tilt = rng.uniform(-3.0, 3.0) if condition == "tilt" else 0.0
    pts = [(x * px, y * px) for x, y in poly]
    c, s = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    cy = length * px / 2
    pts = [(gx + (x * c - (y - cy) * s), gy + cy + (x * s + (y - cy) * c)) for x, y in pts]
    ref_w, ref_h = (garment_photo.REFERENCES[reference][0], garment_photo.REFERENCES[reference][1])
    rx, ry = w * SS * (0.86 if reference == "card" else 0.84), h * SS * (0.30 if reference == "card" else 0.50)
    rot = rng.uniform(-8, 8) if condition == "tilt" else rng.uniform(-2, 2)
    hw, hh = ref_w * px / 2, ref_h * px / 2
    rc, rs = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    corners = _rounded_rect(rx, ry, hw, hh, rc, rs, 0.318 * px if reference == "card" else 0.0)
    card_colour = (60, 90, 150) if reference == "card" else (250, 250, 250)
    if reference == "a4":                                           # an A4 sheet is big: lay it lower right, in portrait
        corners = _rounded_rect(rx, ry, hw, hh, rs, rc, 0.0)
    if condition == "shadow":
        shadow = Image.new("L", big.size, 0)
        sd = ImageDraw.Draw(shadow)
        sd.polygon([(x + 18 * SS, y + 22 * SS) for x, y in pts], fill=110)
        sd.polygon([(x + 10 * SS, y + 12 * SS) for x, y in corners], fill=110)
        shadow = shadow.filter(ImageFilter.GaussianBlur(9 * SS))
        big = Image.composite(Image.new("RGB", big.size, (60, 56, 52)), big, shadow)
        d = ImageDraw.Draw(big)
    if condition in ("stripes", "stripes_light"):
        layer = Image.new("RGB", big.size, colour)
        ld = ImageDraw.Draw(layer)
        stripe = (30, 45, 100) if condition == "stripes" else (245, 245, 240)        # stripes_light: white stripes, almost the background colour (a known failure)
        for y in range(0, big.height, int(7 * px)):
            ld.rectangle([0, y, big.width, y + int(2.6 * px)], fill=stripe)
        mask = Image.new("L", big.size, 0)
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        big.paste(layer, (0, 0), mask)
    else:
        d.polygon(pts, fill=colour)
    d.polygon(corners, fill=card_colour)
    img = big.resize((w, h), Image.LANCZOS)
    if condition == "perspective":
        img = img.transform(img.size, Image.PERSPECTIVE, (1, 0, 0, 0.010, 1, 0, 0.00005, 0.0, 1), Image.BICUBIC, fillcolor=bg)
    if condition in ("noise_vignette", "shadow", "stripes", "stripes_light", "tilt", "perspective"):
        vig = Image.radial_gradient("L").resize(img.size)                                # 0 centre -> 255 corner
        vig = vig.point(lambda v: 255 - int(v * 0.22))
        img = ImageChops.multiply(img, Image.merge("RGB", (vig, vig, vig)))
    if condition in ("noise_vignette", "stripes", "stripes_light", "tilt", "perspective"):
        noise = Image.frombytes("L", img.size, rng.randbytes(img.width * img.height)).point(lambda v: int(128 + (v - 127.5) * 31 / 255))      # seeded uniform noise, sigma about 9 levels
        img = ImageChops.add(img, Image.merge("RGB", (noise, noise, noise)), 1.0, -128)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), truth


__all__ = ["synthetic_photo", "CONDITIONS", "DEFAULTS", "PX_PER_CM"]
