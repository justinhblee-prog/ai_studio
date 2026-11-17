"""Lane 3 / E-10: a quality check for a FINISHED product picture (what would be exported or sent to review). Pillow only, deterministic, no network.

Each check returns ``pass`` / ``warn`` / ``fail`` with a plain reason. ``fail`` = do not deliver as is (blank, product cut off by the edge, wrong size); ``warn`` = a person should look
(off-centre, tiny, blurry, background not clean, blown highlights). THE THRESHOLDS BELOW ARE PROVISIONAL starting values chosen on synthetic pictures; they have never been tuned on real
product photos, so a ``pass`` means "none of these simple rules fired", not "this is a good photo". The product is found with ``bg_removal.foreground_mask`` and so inherits its limits
(plain or smoothly shaded backgrounds only).
"""
from __future__ import annotations

from typing import Any

from PIL import Image, ImageChops, ImageFilter, ImageStat

from app import bg_removal

THRESHOLDS = {
    "min_side_warn": 800,            # px: below this the picture is small for most channels
    "blank_stddev": 3.0,            # luminance spread below this = a flat picture
    "edge_touch_share": 0.02,       # share of an edge row/column that is "product" before we call it cut off
    "centre_offset_warn": 0.08,     # product centre further than this share of width/height from the picture centre
    "coverage_small": 0.05,         # product area share
    "coverage_large": 0.95,
    "sharpness_warn": 40.0,         # variance of the edge response inside the product box; lower = softer
    "white_bg_dirty_share": 0.02,   # share of background pixels that are not near-white on a "white" background
    "blown_share": 0.35,            # share of product pixels at 253+ in every channel
}


def _check(name: str, status: str, value: Any, message: str) -> dict[str, Any]:
    return {"name": name, "status": status, "value": value, "message": message}


def check_image(img: Image.Image, *, target_size: tuple[int, int] | None = None, background: str | None = None) -> dict[str, Any]:
    rgb = img.convert("RGB")
    t = THRESHOLDS
    checks: list[dict[str, Any]] = []
    w, h = rgb.size
    if target_size is not None:
        ok = (w, h) == tuple(target_size)
        checks.append(_check("size", "pass" if ok else "fail", [w, h], "size matches the channel" if ok else f"size is {w}x{h}, the channel needs {target_size[0]}x{target_size[1]}"))
    else:
        small = min(w, h) < t["min_side_warn"]
        checks.append(_check("size", "warn" if small else "pass", [w, h], f"the short side is under {t['min_side_warn']} px" if small else "size is fine"))
    lum = rgb.convert("L")
    spread = ImageStat.Stat(lum).stddev[0]
    if spread < t["blank_stddev"]:
        checks.append(_check("blank", "fail", round(spread, 2), "the picture is blank or one flat colour"))
        return _finish(checks)
    checks.append(_check("blank", "pass", round(spread, 2), "the picture has content"))
    mask = bg_removal.foreground_mask(rgb, "auto")
    bbox = mask.getbbox()
    area = sum(mask.histogram()[128:]) / (w * h)
    if bbox is None or area < 0.002:
        checks.append(_check("product_found", "fail", round(area, 4), "no product could be told apart from the background"))
        return _finish(checks)
    checks.append(_check("product_found", "pass", round(area, 4), "a product was found"))
    touching = []
    for side, strip in (("left", mask.crop((0, 0, 1, h))), ("right", mask.crop((w - 1, 0, w, h))), ("top", mask.crop((0, 0, w, 1))), ("bottom", mask.crop((0, h - 1, w, h)))):
        share = sum(strip.histogram()[128:]) / (strip.width * strip.height)
        if share > t["edge_touch_share"]:
            touching.append(side)
    checks.append(_check("edges", "fail" if touching else "pass", touching, f"the product touches the {', '.join(touching)} edge (cut off)" if touching else "the product is inside the picture"))
    x0, y0, x1, y1 = bbox
    off_x, off_y = abs((x0 + x1) / 2 - w / 2) / w, abs((y0 + y1) / 2 - h / 2) / h
    off = max(off_x, off_y)
    checks.append(_check("centred", "warn" if off > t["centre_offset_warn"] else "pass", round(off, 3), "the product is off-centre" if off > t["centre_offset_warn"] else "the product is centred"))
    if area < t["coverage_small"] or area > t["coverage_large"]:
        checks.append(_check("coverage", "warn", round(area, 3), "the product is very small in the picture" if area < t["coverage_small"] else "the product fills almost the whole picture"))
    else:
        checks.append(_check("coverage", "pass", round(area, 3), "the product has a sensible size"))
    box = lum.crop(bbox)
    sharp = ImageStat.Stat(box.filter(ImageFilter.FIND_EDGES)).var[0]
    checks.append(_check("sharpness", "warn" if sharp < t["sharpness_warn"] else "pass", round(sharp, 1), "the product looks soft or blurry" if sharp < t["sharpness_warn"] else "the product is sharp enough"))
    product_pixels = ImageChops.multiply(rgb, Image.merge("RGB", (mask, mask, mask)))
    hot = rgb.point(lambda v: 255 if v >= 253 else 0)
    r, g, b = hot.split()
    blown = ImageChops.multiply(ImageChops.multiply(r, g), ImageChops.multiply(b, mask))
    blown_share = sum(blown.histogram()[128:]) / max(1, sum(mask.histogram()[128:]))
    del product_pixels
    checks.append(_check("highlights", "warn" if blown_share > t["blown_share"] else "pass", round(blown_share, 3), "much of the product is pure white (blown highlights)" if blown_share > t["blown_share"] else "highlights are fine"))
    if background == "white":
        outside = ImageChops.invert(mask)
        near_white = rgb.point(lambda v: 255 if v >= 245 else 0)
        pr, pg, pb = near_white.split()
        white = ImageChops.multiply(ImageChops.multiply(pr, pg), pb)
        dirty = ImageChops.subtract(outside, ImageChops.multiply(outside, white))
        share = sum(dirty.histogram()[128:]) / max(1, sum(outside.histogram()[128:]))
        checks.append(_check("background", "warn" if share > t["white_bg_dirty_share"] else "pass", round(share, 3), "the white background is not clean" if share > t["white_bg_dirty_share"] else "the background is clean white"))
    return _finish(checks)


def _finish(checks: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = {c["status"] for c in checks}
    status = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {"status": status, "checks": checks, "failed": [c["name"] for c in checks if c["status"] == "fail"], "warnings": [c["name"] for c in checks if c["status"] == "warn"],
            "provisional_thresholds": True, "note": "pass = none of these simple rules fired; it is not a judgement that the photo is good"}


def check_files(files: list[dict[str, Any]], channels: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """For the dicts channel_export.export_set returns: decode each file and check it against its channel size (and white background where the channel asks for one)."""
    import io
    out = []
    for f in files:
        spec = channels[f["channel"]]
        report = check_image(Image.open(io.BytesIO(f["bytes"])), target_size=spec["size"], background="white" if spec["background"] == "white" else None)
        out.append({"filename": f["filename"], **report})
    return out
