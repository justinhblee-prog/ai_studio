"""Strict, dependency-free validation for single-file glTF 2.0 assets.

This validates the container/document only; it is not a complete security sandbox
for arbitrary 3D parsers. Keep assets private and enforce upload quotas upstream.
"""
from __future__ import annotations

import json
import struct
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath

GLB_MAGIC = b"glTF"
GLB_JSON_CHUNK = 0x4E4F534A
GLB_BIN_CHUNK = 0x004E4942
MAX_ASSET_BYTES = 100 * 1024 * 1024
MAX_JSON_BYTES = 8 * 1024 * 1024


class AssetValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ValidatedAsset:
    media_type: str
    size_bytes: int
    gltf_version: str | None
    embedded_binary: bool


def _validate_gltf_document(raw: bytes) -> tuple[dict, bool]:
    if len(raw) > MAX_JSON_BYTES:
        raise AssetValidationError("ASSET_JSON_TOO_LARGE", "glTF JSON document exceeds the allowed size.")
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssetValidationError("ASSET_PARSE_FAILED", "glTF JSON is invalid UTF-8 or malformed JSON.") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("asset"), dict):
        raise AssetValidationError("ASSET_FORMAT_UNSUPPORTED", "A glTF 2.0 asset object is required.")
    version = str(doc["asset"].get("version", ""))
    if not version.startswith("2."):
        raise AssetValidationError("ASSET_FORMAT_UNSUPPORTED", "Only glTF 2.0 assets are supported.")

    # Single-file uploads cannot safely resolve external resources. Embedded data
    # URIs are permitted; path/URL references are rejected to prevent SSRF/path reads.
    for collection in ("buffers", "images"):
        values = doc.get(collection, [])
        if not isinstance(values, list):
            raise AssetValidationError("ASSET_PARSE_FAILED", f"glTF {collection} must be an array.")
        for item in values:
            if not isinstance(item, dict):
                raise AssetValidationError("ASSET_PARSE_FAILED", f"glTF {collection} entries must be objects.")
            uri = item.get("uri")
            if uri is None:
                continue
            if not isinstance(uri, str) or not uri.startswith("data:") or ";base64," not in uri:
                raise AssetValidationError("ASSET_EXTERNAL_URI_BLOCKED", "External glTF resource URIs are not allowed.")
            if len(uri) > MAX_ASSET_BYTES * 2:
                raise AssetValidationError("ASSET_DATA_URI_TOO_LARGE", "Embedded glTF resource is too large.")
    return doc, bool(doc.get("buffers") or doc.get("images"))


def validate_gltf_upload(filename: str, content: bytes, *, max_bytes: int = MAX_ASSET_BYTES) -> ValidatedAsset:
    """Validate GLB or JSON glTF bytes and return server-determined media metadata."""
    if not isinstance(content, bytes) or not content:
        raise AssetValidationError("ASSET_EMPTY", "The uploaded asset is empty.")
    if len(content) > max_bytes:
        raise AssetValidationError("ASSET_TOO_LARGE", "The uploaded asset exceeds the configured size limit.")
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if suffix == ".glb":
        if len(content) < 20 or content[:4] != GLB_MAGIC:
            raise AssetValidationError("ASSET_SIGNATURE_INVALID", "GLB magic signature is invalid.")
        version, declared_length = struct.unpack_from("<II", content, 4)
        if version != 2 or declared_length != len(content):
            raise AssetValidationError("ASSET_SIGNATURE_INVALID", "GLB version or declared length is invalid.")
        offset = 12
        json_chunk = None
        seen_bin = False
        while offset < len(content):
            if offset + 8 > len(content):
                raise AssetValidationError("ASSET_SIGNATURE_INVALID", "GLB chunk header is truncated.")
            chunk_length, chunk_type = struct.unpack_from("<II", content, offset)
            offset += 8
            if chunk_length % 4 or offset + chunk_length > len(content):
                raise AssetValidationError("ASSET_SIGNATURE_INVALID", "GLB chunk length is invalid.")
            chunk = content[offset:offset + chunk_length]
            offset += chunk_length
            if chunk_type == GLB_JSON_CHUNK:
                if json_chunk is not None:
                    raise AssetValidationError("ASSET_SIGNATURE_INVALID", "GLB contains multiple JSON chunks.")
                json_chunk = chunk
            elif chunk_type == GLB_BIN_CHUNK:
                if seen_bin:
                    raise AssetValidationError("ASSET_SIGNATURE_INVALID", "GLB contains multiple BIN chunks.")
                seen_bin = True
        if offset != len(content) or json_chunk is None:
            raise AssetValidationError("ASSET_SIGNATURE_INVALID", "GLB must contain one valid JSON chunk.")
        _validate_gltf_document(json_chunk.rstrip(b" \t\r\n\x00"))
        return ValidatedAsset("model/gltf-binary", len(content), "2.0", seen_bin)

    if suffix == ".gltf":
        _, embedded = _validate_gltf_document(content)
        return ValidatedAsset("model/gltf+json", len(content), "2.0", embedded)
    raise AssetValidationError("ASSET_FORMAT_UNSUPPORTED", "Only .glb and self-contained .gltf files are supported.")


IMAGE_FORMATS = {
    "PNG": ("image/png", {".png"}),
    "JPEG": ("image/jpeg", {".jpg", ".jpeg"}),
    "WEBP": ("image/webp", {".webp"}),
}


def validate_image_upload(filename: str, content: bytes, *, max_bytes: int = MAX_ASSET_BYTES,
                          max_pixels: int = 100_000_000, max_dimension: int = 16_384) -> ValidatedAsset:
    """Decode and verify a single-frame PNG/JPEG/WebP image with bounded dimensions."""
    if not isinstance(content, bytes) or not content:
        raise AssetValidationError("ASSET_EMPTY", "The uploaded image is empty.")
    from app import config as _config
    if len(content) > min(max_bytes, _config.IMAGE_MAX_UPLOAD_BYTES):   # R-061: pictures have their own (smaller) ceiling
        raise AssetValidationError("ASSET_TOO_LARGE", "The uploaded image exceeds the configured size limit.")
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    try:
        from PIL import Image, UnidentifiedImageError
        Image.MAX_IMAGE_PIXELS = max_pixels
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                image_format = image.format
                width, height = image.size
                frames = getattr(image, "n_frames", 1)
                if image_format not in IMAGE_FORMATS:
                    raise AssetValidationError("IMAGE_FORMAT_UNSUPPORTED", "Only PNG, JPEG, and WebP images are supported.")
                media_type, allowed_suffixes = IMAGE_FORMATS[image_format]
                if suffix not in allowed_suffixes:
                    raise AssetValidationError("IMAGE_EXTENSION_MISMATCH", "Image extension does not match its detected format.")
                if frames != 1:
                    raise AssetValidationError("IMAGE_ANIMATION_UNSUPPORTED", "Animated images are not supported.")
                if width < 1 or height < 1 or width > max_dimension or height > max_dimension or width * height > max_pixels:
                    raise AssetValidationError("IMAGE_DIMENSIONS_UNSUPPORTED", "Image dimensions exceed the supported limit.")
                image.verify()
            # verify() checks container integrity; a second open + load forces pixel decoding.
            with Image.open(BytesIO(content)) as decoded:
                decoded.load()
    except AssetValidationError:
        raise
    except Exception as exc:
        raise AssetValidationError("IMAGE_DECODE_FAILED", "Image data is malformed, truncated, or unsafe to decode.") from exc
    return ValidatedAsset(media_type, len(content), None, False)


def validate_asset_upload(filename: str, content: bytes, *, max_bytes: int = MAX_ASSET_BYTES) -> ValidatedAsset:
    """Dispatch upload validation by filename extension without trusting client MIME."""
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return validate_image_upload(filename, content, max_bytes=max_bytes)
    return validate_gltf_upload(filename, content, max_bytes=max_bytes)


def validate_video_asset(filename: str, content: bytes, *, max_bytes: int = MAX_ASSET_BYTES) -> ValidatedAsset:
    """Re-check a SERVER-MADE MP4 (for example when a stored version is restored). Deliberately NOT part of ``validate_asset_upload``:
    people cannot upload videos. Reads the file structure only (pure Python, no ffmpeg): the file must be a complete H.264 MP4."""
    if len(content) > max_bytes:
        raise AssetValidationError("ASSET_TOO_LARGE", "Asset exceeds the allowed size.")
    from app import video_mp4
    try:
        probe = video_mp4.probe_mp4(content)
    except video_mp4.VideoEncodeError as exc:
        raise AssetValidationError("ASSET_VIDEO_INVALID", "The video file is not a complete MP4.") from exc
    if probe["codec"] != "avc1" or probe["frames"] < 1:
        raise AssetValidationError("ASSET_VIDEO_INVALID", "The video file is not an H.264 MP4 with frames.")
    return ValidatedAsset(media_type="video/mp4", size_bytes=len(content), gltf_version=None, embedded_binary=False)


def asset_kind_of(media_type: str) -> str:
    """'image', 'video' or 'model' (a 3D file): the one rule every listing, upload check and library filing uses."""
    media_type = str(media_type)
    return "image" if media_type.startswith("image/") else "video" if media_type.startswith("video/") else "model"


def storage_suffix(media_type: str) -> str:
    mapping = {
        "model/gltf-binary": ".glb",
        "model/gltf+json": ".gltf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "video/mp4": ".mp4",      # server-made only (app/video_mp4.py): an upload of .mp4 is still refused by validate_asset_upload
    }
    try:
        return mapping[media_type]
    except KeyError as exc:
        raise AssetValidationError("ASSET_MEDIA_TYPE_UNSUPPORTED", "Unsupported asset media type.") from exc
