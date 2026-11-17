"""Lane 3 / E-09b: put a cut-out product (RGBA, e.g. the result of ``bg_removal.remove_background``) on a new background with a soft shadow and an optional reflection.
Pillow only, no network, nothing is read from or written to disk. The product's own pixels are never recoloured; the shadow and the reflection are added UNDER it.

background: "white" | "solid" (``color``) | "gradient" (``color`` at the top to ``color2`` at the bottom) | "scene" (a ``scene`` picture, cover-fitted).
shadow:     "drop" (offset, blurred copy of the product's shape) | "ground" (a flat soft ellipse under the product, like a table contact shadow) | "none".
"""
from __future__ import annotations

from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter

BACKGROUNDS = ("white", "solid", "gradient", "scene")
SHADOWS = ("drop", "ground", "none")
MAX_SIDE = 4096
Color = tuple[int, int, int]


def _check_color(value: Any, name: str) -> Color:
    if not (isinstance(value, (tuple, list)) and len(value) == 3 and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in value)):
        raise ValueError(f"{name} must be three integers from 0 to 255")
    return tuple(value)  # type: ignore[return-value]


def _cover(scene: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    scale = max(w / scene.width, h / scene.height)
    resized = scene.convert("RGB").resize((max(1, round(scene.width * scale)), max(1, round(scene.height * scale))), Image.LANCZOS)
    left, top = (resized.width - w) // 2, (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def make_background(kind: str, size: tuple[int, int], color: Color = (255, 255, 255), color2: Color | None = None, scene: Image.Image | None = None) -> Image.Image:
    if kind not in BACKGROUNDS:
        raise ValueError(f"unknown background {kind!r}")
    if kind == "white":
        return Image.new("RGB", size, (255, 255, 255))
    if kind == "solid":
        return Image.new("RGB", size, _check_color(color, "color"))
    if kind == "gradient":
        top, bottom = _check_color(color, "color"), _check_color(color2 if color2 is not None else (255, 255, 255), "color2")
        strip = Image.new("RGB", (1, 2))
        strip.putdata([top, bottom])
        return strip.resize(size, Image.BILINEAR)
    if scene is None:
        raise ValueError("a scene background needs a scene picture")
    return _cover(scene, size)


def _place(product: Image.Image, size: tuple[int, int], fit: bool) -> Image.Image:
    """The product on a transparent canvas of the output size: unchanged position when the size is the input's, otherwise scaled to fit 90% and centred."""
    if not fit:
        return product
    scale = min(0.9 * size[0] / product.width, 0.9 * size[1] / product.height)
    scaled = product.resize((max(1, round(product.width * scale)), max(1, round(product.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.paste(scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2), scaled)
    return canvas


def _shadow_layer(placed: Image.Image, kind: str, opacity: float, blur: float, offset: tuple[int, int]) -> Image.Image | None:
    alpha = placed.getchannel("A")
    bbox = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
    if kind == "none" or bbox is None:
        return None
    layer = Image.new("L", placed.size, 0)
    if kind == "drop":
        layer.paste(alpha, offset)
    else:                                                # ground: a flat ellipse centred under the product
        x0, y0, x1, y1 = bbox
        width, height = x1 - x0, max(4, (y1 - y0) // 10)
        draw = ImageDraw.Draw(layer)
        cx, cy = (x0 + x1) // 2, y1 + offset[1] // 2
        draw.ellipse((cx - int(width * 0.42), cy - height // 2, cx + int(width * 0.42), cy + height // 2), fill=255)
    layer = layer.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * opacity))
    black = Image.new("RGBA", placed.size, (0, 0, 0, 255))
    black.putalpha(layer)
    return black


def _reflection_layer(placed: Image.Image, strength: float, reach: float) -> Image.Image | None:
    alpha = placed.getchannel("A")
    bbox = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    crop = placed.crop((x0, y0, x1, y1)).transpose(Image.FLIP_TOP_BOTTOM)
    height = max(1, int((y1 - y0) * reach))
    crop = crop.crop((0, 0, crop.width, min(height, crop.height)))
    fade = Image.new("L", (1, 2))
    fade.putdata([int(255 * strength), 0])
    mask = ImageChops.multiply(crop.getchannel("A"), fade.resize(crop.size, Image.BILINEAR))
    crop.putalpha(mask)
    layer = Image.new("RGBA", placed.size, (0, 0, 0, 0))
    layer.paste(crop, (x0, y1), crop)
    return layer


def compose(product: Image.Image, background: str = "white", *, color: Color = (255, 255, 255), color2: Color | None = None, scene: Image.Image | None = None,
            size: tuple[int, int] | None = None, shadow: str = "drop", shadow_opacity: float = 0.35, shadow_blur: float = 6.0, shadow_offset: tuple[int, int] = (6, 10),
            reflection: bool = False, reflection_strength: float = 0.35, reflection_reach: float = 0.35) -> Image.Image:
    if product.mode != "RGBA":
        raise ValueError("the product must be an RGBA cut-out (use bg_removal.remove_background first)")
    if shadow not in SHADOWS:
        raise ValueError(f"unknown shadow {shadow!r}")
    if not 0.0 <= shadow_opacity <= 1.0 or not 0.0 <= reflection_strength <= 1.0:
        raise ValueError("opacity and strength must be between 0 and 1")
    out_size = size or product.size
    if not (1 <= out_size[0] <= MAX_SIDE and 1 <= out_size[1] <= MAX_SIDE):
        raise ValueError(f"the output size must be between 1 and {MAX_SIDE} pixels per side")
    canvas = make_background(background, out_size, color, color2, scene).convert("RGBA")
    placed = _place(product, out_size, fit=out_size != product.size)
    for layer in (_shadow_layer(placed, shadow, shadow_opacity, shadow_blur, shadow_offset), _reflection_layer(placed, reflection_strength, reflection_reach) if reflection else None):
        if layer is not None:
            canvas = Image.alpha_composite(canvas, layer)
    return Image.alpha_composite(canvas, placed).convert("RGB")
