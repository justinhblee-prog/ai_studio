"""Lane 3 / E-09c: auto-crop, centre and size a cut-out product for a SALES CHANNEL, name the files by a fixed rule, mark them as AI-made when they are, and bundle them.
Pillow only. The channel table below is a set of PROVISIONAL, common-practice values (sizes, margins, formats): they are NOT verified against any marketplace's current rules
and must be checked (and made configurable) before anyone relies on them. The licence label is NOT written into the files yet: the licence tiers are still a provisional design (reply 55).
"""
from __future__ import annotations

import io
import re
import zipfile
from typing import Any

from PIL import Image

from app import ai_marking, bg_compose

# name -> output size (px), empty margin around the product (share of each side), file format, quality, default background. PROVISIONAL values.
CHANNELS: dict[str, dict[str, Any]] = {
    "marketplace_square": {"size": (1000, 1000), "margin": 0.06, "format": "jpeg", "quality": 90, "background": "white", "label": "마켓 정사각 1:1"},
    "feed_4_5": {"size": (1080, 1350), "margin": 0.08, "format": "jpeg", "quality": 90, "background": "white", "label": "피드 4:5"},
    "story_9_16": {"size": (1080, 1920), "margin": 0.12, "format": "jpeg", "quality": 88, "background": "white", "label": "스토리·릴스 9:16"},
    "banner_16_9": {"size": (1920, 1080), "margin": 0.10, "format": "jpeg", "quality": 88, "background": "white", "label": "배너 16:9"},
    "thumbnail": {"size": (600, 600), "margin": 0.05, "format": "webp", "quality": 85, "background": "white", "label": "썸네일"},
    "transparent_png": {"size": (1200, 1200), "margin": 0.04, "format": "png", "quality": 100, "background": "transparent", "label": "투명 PNG(합성용)"},
}
MEDIA = {"jpeg": ("image/jpeg", "jpg"), "png": ("image/png", "png"), "webp": ("image/webp", "webp")}
SKU_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


def crop_to_product(rgba: Image.Image, pad_ratio: float = 0.0) -> Image.Image:
    """Cut away the empty transparent border; ``pad_ratio`` keeps a little of it. Raises when nothing is left."""
    if rgba.mode != "RGBA":
        raise ValueError("the product must be an RGBA cut-out")
    bbox = rgba.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox is None:
        raise ValueError("the picture has no visible product (fully transparent)")
    x0, y0, x1, y1 = bbox
    pad = int(max(x1 - x0, y1 - y0) * pad_ratio)
    return rgba.crop((max(0, x0 - pad), max(0, y0 - pad), min(rgba.width, x1 + pad), min(rgba.height, y1 + pad)))


def render(rgba: Image.Image, channel: str, *, background: str | None = None, shadow: str = "drop", **compose_args: Any) -> Image.Image:
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}")
    spec = CHANNELS[channel]
    cropped = crop_to_product(rgba)
    kind = background or spec["background"]
    fit = 1.0 - 2 * spec["margin"]
    if kind == "transparent":
        scale = min(fit * spec["size"][0] / cropped.width, fit * spec["size"][1] / cropped.height)
        scaled = cropped.resize((max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))), Image.LANCZOS)
        canvas = Image.new("RGBA", spec["size"], (0, 0, 0, 0))
        canvas.paste(scaled, ((spec["size"][0] - scaled.width) // 2, (spec["size"][1] - scaled.height) // 2), scaled)
        return canvas
    return bg_compose.compose(cropped, kind, size=spec["size"], fit_ratio=fit, shadow=shadow, **compose_args)


def filename(sku: str, channel: str, index: int, extension: str) -> str:
    if not isinstance(sku, str) or not SKU_RE.match(sku):
        raise ValueError("the product code may use letters, digits, '-' and '_' (1-40 characters, not starting with - or _)")
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}")
    if not isinstance(index, int) or isinstance(index, bool) or not 1 <= index <= 99:
        raise ValueError("the picture number must be 1-99")
    return f"{sku}_{channel}_{index:02d}.{extension}"


def encode(image: Image.Image, fmt: str, quality: int, ai_kind: str | None = None) -> tuple[bytes, str]:
    if fmt not in MEDIA:
        raise ValueError(f"unknown format {fmt!r}")
    media, _ = MEDIA[fmt]
    buffer = io.BytesIO()
    if fmt == "jpeg":
        image.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True)
    elif fmt == "png":
        image.save(buffer, "PNG", optimize=True)
    else:
        image.save(buffer, "WEBP", quality=quality, method=4)
    data = buffer.getvalue()
    if ai_kind is not None:
        data = ai_marking.mark(data, media, ai_kind)
    return data, media


def export_set(rgba: Image.Image, channels: list[str], sku: str, *, index: int = 1, ai_kind: str | None = None, **render_args: Any) -> list[dict[str, Any]]:
    if not channels or len(set(channels)) != len(channels):
        raise ValueError("choose at least one channel, each once")
    out = []
    for channel in channels:
        spec = CHANNELS[channel] if channel in CHANNELS else (_ for _ in ()).throw(ValueError(f"unknown channel {channel!r}"))
        picture = render(rgba, channel, **render_args)
        data, media = encode(picture, spec["format"], spec["quality"], ai_kind)
        out.append({"channel": channel, "filename": filename(sku, channel, index, MEDIA[spec["format"]][1]), "media_type": media, "width": picture.width, "height": picture.height,
                    "bytes": data, "ai_marked": ai_kind is not None})
    return out


def zip_bytes(files: list[dict[str, Any]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for f in files:
            archive.writestr(f["filename"], f["bytes"])
    return buffer.getvalue()
