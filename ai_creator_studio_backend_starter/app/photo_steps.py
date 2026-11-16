"""Photo Studio step pipeline, local part (R-044 bundle A): small, deterministic image steps run one after another on one image.

A run is a LIST of steps (not one ``operation``): e.g. auto_crop -> solid_background -> fit_canvas. Every step is local: no network, no provider,
no AI. The input image is never modified (each step returns a new image); every step leaves a record (name, parameters, local mode, size in/out).
Parameters are validated against a whitelist with bounds before anything runs, so a bad request fails as a whole and changes nothing.
Channel size presets are NOT defined here: their values must come from each channel's own published rules (not yet checked).
"""
from __future__ import annotations

import time
from typing import Any

from PIL import Image

MAX_STEPS = 12
MAX_SIDE = 8192
OPS = {
    "auto_crop": {"tolerance": (int, 0, 128, 24), "margin_pct": (int, 0, 40, 5)},
    "solid_background": {"color": (str, None, None, "#ffffff")},
    "fit_canvas": {"width": (int, 16, MAX_SIDE, 1200), "height": (int, 16, MAX_SIDE, 1200), "color": (str, None, None, "#ffffff")},
}


class StepError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def parse_color(value: str) -> tuple[int, int, int]:
    text = str(value).strip().lstrip("#")
    if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
        raise StepError("STEP_COLOR_INVALID", "color must look like #rrggbb")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def validate_steps(steps: Any) -> list[dict[str, Any]]:
    """Normalised steps (defaults filled in) or StepError. Unknown operations, unknown parameters and out-of-range values are all refused."""
    if not isinstance(steps, list) or not steps:
        raise StepError("STEPS_REQUIRED", "give at least one step")
    if len(steps) > MAX_STEPS:
        raise StepError("STEPS_TOO_MANY", f"at most {MAX_STEPS} steps")
    out = []
    for i, step in enumerate(steps, start=1):
        if not isinstance(step, dict) or step.get("op") not in OPS:
            raise StepError("STEP_UNKNOWN", f"step {i}: unknown operation")
        spec = OPS[step["op"]]
        extra = set(step) - {"op"} - set(spec)
        if extra:
            raise StepError("STEP_PARAMETER_UNKNOWN", f"step {i}: unknown parameter {sorted(extra)[0]}")
        clean: dict[str, Any] = {"op": step["op"]}
        for name, (kind, lo, hi, default) in spec.items():
            value = step.get(name, default)
            if kind is int:
                if isinstance(value, bool) or not isinstance(value, int) or not (lo <= value <= hi):
                    raise StepError("STEP_PARAMETER_INVALID", f"step {i}: {name} must be an integer {lo}..{hi}")
            else:
                parse_color(value)
            clean[name] = value
        out.append(clean)
    return out


def _flatten(image: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    rgba = image.convert("RGBA")
    base = Image.new("RGBA", rgba.size, color + (255,))
    base.alpha_composite(rgba)
    return base.convert("RGB")


def _content_box(image: Image.Image, tolerance: int):
    """Bounding box of what is not background: the transparent pixels if the image has an alpha channel with transparency, else everything that
    differs from the corner colour by more than `tolerance` in any channel."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] < 255:
        return alpha.point(lambda v: 255 if v > 0 else 0).getbbox()
    rgb = rgba.convert("RGB")
    w, h = rgb.size
    corners = [rgb.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    bg = tuple(sorted(c[i] for c in corners)[1] for i in range(3))   # the middle value of the corners: one odd corner does not fool it
    from PIL import ImageChops
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg)).convert("L").point(lambda v: 255 if v > tolerance else 0)
    return diff.getbbox()


def auto_crop(image: Image.Image, tolerance: int = 24, margin_pct: int = 5) -> Image.Image:
    box = _content_box(image, tolerance)
    if box is None:   # nothing but background: leave the picture as it is
        return image.copy()
    left, top, right, bottom = box
    pad_x, pad_y = round((right - left) * margin_pct / 100), round((bottom - top) * margin_pct / 100)
    box = (max(0, left - pad_x), max(0, top - pad_y), min(image.width, right + pad_x), min(image.height, bottom + pad_y))
    return image.crop(box)


def fit_canvas(image: Image.Image, width: int, height: int, color: tuple[int, int, int]) -> Image.Image:
    """The whole picture, scaled to fit (never cropped), centred on a width x height canvas of one colour."""
    scale = min(width / image.width, height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.convert("RGBA").resize(size, Image.LANCZOS)
    canvas = Image.new("RGBA", (width, height), color + (255,))
    canvas.alpha_composite(resized, ((width - size[0]) // 2, (height - size[1]) // 2))
    return canvas.convert("RGB")


def run_steps(image: Image.Image, steps: Any) -> tuple[Image.Image, list[dict[str, Any]]]:
    """Validate, then run. Returns the result and one record per step. The input image is not changed."""
    plan = validate_steps(steps)
    current, records = image.copy(), []
    for step in plan:
        started, before = time.perf_counter(), current.size
        if step["op"] == "auto_crop":
            current = auto_crop(current, step["tolerance"], step["margin_pct"])
        elif step["op"] == "solid_background":
            current = _flatten(current, parse_color(step["color"]))
        elif step["op"] == "fit_canvas":
            current = fit_canvas(current, step["width"], step["height"], parse_color(step["color"]))
        records.append({**step, "mode": "local", "size_in": list(before), "size_out": list(current.size),
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2)})
    return current, records
