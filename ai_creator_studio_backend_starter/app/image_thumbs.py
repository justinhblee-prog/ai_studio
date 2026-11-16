"""R-061: display-size pictures (480 / 960 px WebP) made on this machine (no provider, no cost).

The original file is never touched (its checksum is part of the provenance). A display picture is a NEW file decoded from the original, turned upright
by its EXIF orientation, scaled to fit the size and written as WebP WITHOUT any metadata: no EXIF, no GPS position, no camera data, no ICC profile text.
Files are cached next to the private assets and are rebuilt when missing. Access is by a short-lived signed address (the same idea as the asset preview).
"""
from __future__ import annotations

import hashlib
import hmac
import io
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app import config, takedown
from app.assets import store
from app.image_guard import check_embed_origin

router = APIRouter(tags=["image-thumbs"])
MAX_PIXELS = 100_000_000
QUALITY = 80


def render(content: bytes, size: int) -> bytes:
    """WebP bytes of the picture fitted into size x size, upright, with no metadata. Raises ValueError for anything that is not a plain picture."""
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(content)) as im:
            if im.format not in ("PNG", "JPEG", "WEBP"):
                raise ValueError("not a PNG, JPEG or WebP picture")
            im.seek(0)
            upright = ImageOps.exif_transpose(im)      # a new image with the orientation applied (and the orientation tag gone)
            upright.load()
            mode = "RGBA" if (upright.mode in ("RGBA", "LA") or "transparency" in upright.info) else "RGB"
            flat = upright.convert(mode)
            flat.thumbnail((size, size), Image.LANCZOS)   # fits inside size x size, never enlarges
            out = io.BytesIO()
            flat.save(out, format="WEBP", quality=QUALITY, method=4)     # no exif=, no icc_profile=: nothing is carried over
            return out.getvalue()
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001  (decode errors, bombs)
        raise ValueError("the picture cannot be decoded") from exc


def _cache_dir() -> Path:
    path = config.ASSET_STORAGE_DIR / "thumbs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_file(source: Path, size: int) -> Path:
    stat = source.stat()
    key = hashlib.sha256(f"{source.name}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()[:24]
    return _cache_dir() / f"{source.stem}.{size}.{key}.webp"


def thumb_bytes(asset_id: str, size: int) -> bytes | None:
    """The display picture of a stored image asset (built and cached on first use); None when there is no readable picture."""
    from app.ports.asset_bytes import get_asset_bytes_port
    source = get_asset_bytes_port().current_file(asset_id)
    if not source or source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        return None
    try:
        cached = _cache_file(source, size)
        if cached.exists():
            return cached.read_bytes()
        data = render(source.read_bytes(), size)
        tmp = cached.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(cached)
        return data
    except (OSError, ValueError):
        return None


def prepare(asset_id: str) -> None:
    """Make every display size now (called when a picture is filed). Never raises: a failure only means the pictures are built on first request."""
    try:
        for size in config.THUMB_SIZES:
            thumb_bytes(asset_id, size)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------------------------------------------- signed addresses
def _signature(asset_id: str, size: int, expires: int) -> str | None:
    secret = config.ASSET_SIGNING_SECRET.encode("utf-8")
    if len(secret) < 32:
        return None
    # the "thumb" label keeps this signature from ever being valid for the full-size preview address
    return hmac.new(secret, f"thumb:{asset_id}:{size}:{expires}".encode(), hashlib.sha256).hexdigest()


def urls_for(asset_id: str, media_type: str | None) -> dict[str, str] | None:
    """{"480": signed address, "960": ...} for an image asset, or None (not an image, or signing is not configured)."""
    if not media_type or not media_type.startswith("image/"):
        return None
    expires = int(time.time()) + max(30, min(config.ASSET_PREVIEW_TTL_SECONDS, 900))
    out = {}
    for size in config.THUMB_SIZES:
        sig = _signature(asset_id, size, expires)
        if sig is None:
            return None
        out[str(size)] = f"/v1/assets/{asset_id}/thumb/{size}?expires={expires}&signature={sig}"
    return out


@router.get("/v1/assets/{asset_id}/thumb/{size}", operation_id="getAssetDisplayPicture", responses={200: {"content": {"image/webp": {}}}})
async def get_thumb(request: Request, asset_id: str, size: int, expires: int, signature: str):
    check_embed_origin(request)
    now = int(time.time())
    if size not in config.THUMB_SIZES:
        raise HTTPException(status_code=404, detail="Unknown size")
    expected = _signature(asset_id, size, expires)
    if expected is None:
        raise HTTPException(status_code=503, detail="Picture signing is not configured")
    if expires < now or expires > now + 901 or not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Picture URL expired or invalid")
    store.initialize()
    with store._connect() as db:
        live = db.execute("SELECT 1 FROM assets WHERE asset_id=? AND deleted_at IS NULL", (asset_id,)).fetchone()
    if not live or takedown.state_of(asset_id) is not None:
        raise HTTPException(status_code=404, detail="Asset not found")
    data = thumb_bytes(asset_id, size)
    if data is None:
        raise HTTPException(status_code=404, detail="No display picture for this asset")
    return Response(content=data, media_type="image/webp", headers={"Cache-Control": "private, max-age=60", "X-Content-Type-Options": "nosniff"})
