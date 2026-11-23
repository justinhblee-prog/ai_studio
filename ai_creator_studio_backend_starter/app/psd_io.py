"""R-PSD-01: a small PSD / PSB writer and reader in pure Python + Pillow (no new dependency), so the Photo Studio can hand layered files to ANY PSD program (Photoshop, Photopea, PhotoCraft, ...)
and take the edited file back.

WRITE (``write_psd``): RGB, 8 or 16 bits per channel, layers bottom -> top with name (ASCII record name + Unicode ``luni`` block, so Korean names survive), visible/hidden flag, position,
opacity; an embedded sRGB ICC profile (image resource 1039); the MERGED image is always written (RLE with literal runs: the most widely readable form, "maximise compatibility"); layer
channels are ZIP-compressed (smaller) or, with ``compat=True``, RLE too. ``version=2`` writes PSB (8-byte lengths) for pictures larger than PSD allows.
READ (``read_psd``): the same files plus what Photoshop writes: raw / RLE / ZIP / ZIP-with-prediction channels, 8 or 16 bits, RGB only (Grayscale is read as grey; CMYK, Lab, indexed... are
refused with ``PSD_UNSUPPORTED``). A file whose merged image is missing or empty is read through its layers (``to_image`` composites the visible ones). Text layers, smart objects, masks,
adjustment layers and effects are NOT interpreted: their pixels (as stored) come back as ordinary layers, nothing else. Limits: ``MAX_BYTES`` (300 MB), ``MAX_PIXELS``, ``MAX_LAYERS``.
Honest limits: tested against its own writer and hand-built files and with Pillow's PSD reader (merged image), NOT yet with Photoshop / Photopea themselves (미확인); 32-bit float and 1-bit files are refused.
"""
from __future__ import annotations

import io
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageChops

MAX_BYTES = 300 * 1024 * 1024
MAX_PIXELS = 120_000_000
MAX_LAYERS = 500
MAX_SIDE = {1: 30000, 2: 300000}
MAX_PREDICTION_PIXELS = 20_000_000       # ZIP-with-prediction is decoded in Python: refuse very large ones
SRGB_NAME = "sRGB IEC61966-2.1"


class PsdError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Layer:
    name: str
    image: Image.Image                 # RGBA at the layer's own size
    visible: bool = True
    x: int = 0
    y: int = 0
    opacity: int = 255


@dataclass
class Psd:
    width: int
    height: int
    depth: int
    version: int
    layers: list[Layer] = field(default_factory=list)       # bottom -> top, as stored
    merged: Image.Image | None = None
    icc: bytes | None = None


# ---------------------------------------------------------------------------------------------------------------------------------- write
def _pack_literal_rle(row: bytes) -> bytes:
    """PackBits with literal runs only: every 128 bytes get a header 127. Valid RLE, no compression, fast in Python."""
    return b"".join(b"\x7f" + row[i:i + 128] if len(row[i:i + 128]) == 128 else bytes([len(row[i:i + 128]) - 1]) + row[i:i + 128] for i in range(0, len(row), 128))


def _planes(img: Image.Image, depth: int, mode: str) -> list[bytes]:
    out = []
    for band in img.convert(mode).split():
        data = band.tobytes()
        if depth == 16:
            wide = bytearray(len(data) * 2)
            wide[0::2] = data
            wide[1::2] = data                    # v * 257: the 8-bit value spread over 16 bits
            data = bytes(wide)
        out.append(data)
    return out


def _rle_channels(planes: list[bytes], width: int, height: int, depth: int, version: int) -> bytes:
    """Compression field excluded. Row byte counts of ALL channels first, then the rows."""
    stride = width * (2 if depth == 16 else 1)
    counts, rows = bytearray(), []
    count_fmt = ">I" if version == 2 else ">H"
    for plane in planes:
        for y in range(height):
            packed = _pack_literal_rle(plane[y * stride:(y + 1) * stride])
            counts += struct.pack(count_fmt, len(packed))
            rows.append(packed)
    return bytes(counts) + b"".join(rows)


def _channel_data(plane: bytes, width: int, height: int, depth: int, version: int, compat: bool) -> bytes:
    if compat:
        return struct.pack(">H", 1) + _rle_channels([plane], width, height, depth, version)
    return struct.pack(">H", 2) + zlib.compress(plane, 6)


def _pascal(name: str) -> bytes:
    raw = name.encode("ascii", "replace")[:255]
    data = bytes([len(raw)]) + raw
    return data + b"\x00" * ((-len(data)) % 4)


def _unicode_block(name: str) -> bytes:
    payload = struct.pack(">I", len(name)) + name.encode("utf-16-be")
    payload += b"\x00" * ((-len(payload)) % 4)
    return b"8BIM" + b"luni" + struct.pack(">I", len(payload)) + payload


def srgb_icc() -> bytes | None:
    try:
        from PIL import ImageCms
        return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    except Exception:  # noqa: BLE001 - a Pillow without littlecms: write the file without a profile
        return None


def write_psd(layers: list[Layer], size: tuple[int, int], merged: Image.Image, *, depth: int = 8, version: int = 1, compat: bool = False, icc: bytes | None | bool = True) -> bytes:
    """``layers`` bottom -> top. ``merged`` is the flattened picture of the whole canvas. ``icc=True`` embeds sRGB, ``False``/None none, bytes = that profile."""
    width, height = size
    if depth not in (8, 16) or version not in (1, 2):
        raise PsdError("PSD_UNSUPPORTED", "depth must be 8 or 16 and version 1 (PSD) or 2 (PSB)")
    if not (1 <= width <= MAX_SIDE[version] and 1 <= height <= MAX_SIDE[version]) or width * height > MAX_PIXELS:
        raise PsdError("PSD_TOO_LARGE", "the picture is too large for this PSD version")
    if len(layers) > MAX_LAYERS:
        raise PsdError("PSD_TOO_LARGE", f"at most {MAX_LAYERS} layers")
    wide = ">Q" if version == 2 else ">I"
    profile = srgb_icc() if icc is True else (icc or None)
    resources = b""
    if profile:
        resources = b"8BIM" + struct.pack(">H", 1039) + b"\x00\x00" + struct.pack(">I", len(profile)) + profile + (b"\x00" if len(profile) % 2 else b"")
    records, channel_blobs = b"", b""
    for layer in layers:
        img = layer.image.convert("RGBA")
        lw, lh = img.size
        planes = _planes(img, depth, "RGBA")
        blobs = [_channel_data(p, lw, lh, depth, version, compat) for p in planes]
        ids = (0, 1, 2, -1)
        rec = struct.pack(">iiii", layer.y, layer.x, layer.y + lh, layer.x + lw) + struct.pack(">H", 4)
        for cid, blob in zip(ids, blobs):
            rec += struct.pack(">h", cid) + struct.pack(wide, len(blob))
        extra = struct.pack(">I", 0) + struct.pack(">I", 0) + _pascal(layer.name) + _unicode_block(layer.name)
        rec += b"8BIM" + b"norm" + bytes([max(0, min(255, layer.opacity)), 0, 0 if layer.visible else 2, 0]) + struct.pack(">I", len(extra)) + extra
        records += rec
        channel_blobs += b"".join(blobs)
    layer_info = struct.pack(">h", len(layers)) + records + channel_blobs
    if len(layer_info) % 2:
        layer_info += b"\x00"
    layer_and_mask = struct.pack(wide, len(layer_info)) + layer_info + struct.pack(">I", 0)       # then an empty global layer mask
    merged_planes = _planes(merged.resize((width, height)) if merged.size != (width, height) else merged, depth, "RGB")
    image_data = struct.pack(">H", 1) + _rle_channels(merged_planes, width, height, depth, version)
    header = b"8BPS" + struct.pack(">H", version) + b"\x00" * 6 + struct.pack(">HIIHH", 3, height, width, depth, 3)
    return (header + struct.pack(">I", 0) + struct.pack(">I", len(resources)) + resources + struct.pack(wide, len(layer_and_mask)) + layer_and_mask + image_data)


# ---------------------------------------------------------------------------------------------------------------------------------- read
class _Reader:
    def __init__(self, data: bytes) -> None:
        self.d, self.p = data, 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.p + n > len(self.d):
            raise PsdError("PSD_CORRUPT", "the file ends too early")
        out = self.d[self.p:self.p + n]
        self.p += n
        return out

    def u(self, fmt: str) -> Any:
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, self.take(size))[0]


def _unpack_rows(data: bytes, counts: list[int], width_bytes: int, start: int) -> tuple[bytes, int]:
    rows, pos = [], start
    for n in counts:
        chunk = data[pos:pos + n]
        if len(chunk) != n:
            raise PsdError("PSD_CORRUPT", "a compressed row is cut short")
        try:
            row = Image.frombytes("L", (width_bytes, 1), chunk, "packbits", "L").tobytes()
        except Exception as exc:  # noqa: BLE001
            raise PsdError("PSD_CORRUPT", "a compressed row cannot be decoded") from exc
        rows.append(row)
        pos += n
    return b"".join(rows), pos


def _undo_prediction(plane: bytes, width: int, height: int, depth: int) -> bytes:
    if width * height > MAX_PREDICTION_PIXELS:
        raise PsdError("PSD_UNSUPPORTED", "ZIP with prediction is only read for pictures up to 20 megapixels")
    out = bytearray(plane)
    if depth == 8:
        for y in range(height):
            base = y * width
            acc = 0
            for x in range(width):
                acc = (acc + out[base + x]) & 255
                out[base + x] = acc
    else:
        for y in range(height):
            base = y * width * 2
            acc = 0
            for x in range(width):
                acc = (acc + (out[base + 2 * x] << 8) + out[base + 2 * x + 1]) & 0xFFFF
                out[base + 2 * x], out[base + 2 * x + 1] = acc >> 8, acc & 255
    return bytes(out)


def _read_plane(r: _Reader, width: int, height: int, depth: int, version: int, length: int | None, compression: int | None = None) -> bytes:
    """One channel's pixels (compression field first unless given). ``length`` = the bytes the channel owns (None = whole stream, only for compression 0)."""
    stride = width * (2 if depth == 16 else 1)
    comp = compression if compression is not None else r.u(">H")
    if comp == 0:
        return r.take(stride * height)
    if comp == 1:
        fmt = ">I" if version == 2 else ">H"
        counts = [r.u(fmt) for _ in range(height)]
        body = r.take(sum(counts))
        return _unpack_rows(body, counts, stride, 0)[0]
    if comp in (2, 3):
        if length is None:
            raise PsdError("PSD_UNSUPPORTED", "this compression is not read for the merged image of this file")
        raw = r.take(length - (2 if compression is None else 0))
        try:
            plane = zlib.decompress(raw)
        except zlib.error as exc:
            raise PsdError("PSD_CORRUPT", "a ZIP channel cannot be decoded") from exc
        if len(plane) < stride * height:
            raise PsdError("PSD_CORRUPT", "a ZIP channel is too short")
        plane = plane[:stride * height]
        return _undo_prediction(plane, width, height, depth) if comp == 3 else plane
    raise PsdError("PSD_UNSUPPORTED", f"unknown channel compression {comp}")


def _band(plane: bytes, width: int, height: int, depth: int) -> Image.Image:
    data = plane[0::2] if depth == 16 else plane               # 16 bit -> the high byte
    return Image.frombytes("L", (width, height), data)


def _layer_image(channels: dict[int, bytes], width: int, height: int, depth: int) -> Image.Image:
    if width <= 0 or height <= 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    zero = Image.new("L", (width, height), 0)
    bands = [_band(channels[c], width, height, depth) if c in channels else zero for c in (0, 1, 2)]
    alpha = _band(channels[-1], width, height, depth) if -1 in channels else Image.new("L", (width, height), 255)
    return Image.merge("RGBA", (*bands, alpha))


def read_psd(data: bytes) -> Psd:
    try:
        return _read_psd(data)
    except (struct.error, IndexError, ValueError, OverflowError) as exc:
        if isinstance(exc, PsdError):
            raise
        raise PsdError("PSD_CORRUPT", "the file is damaged or not a valid PSD") from exc


def _read_psd(data: bytes) -> Psd:
    if len(data) > MAX_BYTES:
        raise PsdError("PSD_TOO_LARGE", "the file is larger than 300 MB")
    if data[:4] != b"8BPS":
        raise PsdError("PSD_NOT_PSD", "this is not a PSD / PSB file")
    r = _Reader(data)
    r.take(4)
    version = r.u(">H")
    if version not in (1, 2):
        raise PsdError("PSD_NOT_PSD", "unknown PSD version")
    r.take(6)
    channels, height, width, depth, mode = struct.unpack(">HIIHH", r.take(14))
    if depth not in (8, 16):
        raise PsdError("PSD_UNSUPPORTED", f"{depth}-bit files are not read (8 and 16 are)")
    if mode not in (1, 3):
        raise PsdError("PSD_UNSUPPORTED", "only RGB (and grey) files are read; convert CMYK/Lab/indexed pictures to RGB first")
    if not (1 <= width <= MAX_SIDE[version] and 1 <= height <= MAX_SIDE[version]) or width * height > MAX_PIXELS:
        raise PsdError("PSD_TOO_LARGE", "the picture is too large")
    r.take(r.u(">I"))                                                          # colour mode data
    resources, icc = r.take(r.u(">I")), None
    rr = _Reader(resources)
    while rr.p + 12 <= len(resources):
        if rr.take(4) != b"8BIM":
            break
        rid = rr.u(">H")
        name_len = rr.u(">B")
        rr.take(name_len + ((name_len + 1) % 2))
        size = rr.u(">I")
        body = rr.take(size + size % 2)[:size]
        if rid == 1039:
            icc = body
    wide = ">Q" if version == 2 else ">I"
    lm_len = r.u(wide)
    layers: list[Layer] = []
    lm_end = r.p + lm_len
    if lm_len:
        li_len = r.u(wide)
        li_end = r.p + li_len
        if li_len:
            count = abs(r.u(">h"))
            if count > MAX_LAYERS:
                raise PsdError("PSD_TOO_LARGE", f"more than {MAX_LAYERS} layers")
            recs = []
            for _ in range(count):
                top, left, bottom, right = struct.unpack(">iiii", r.take(16))
                nch = r.u(">H")
                chans = [(r.u(">h"), r.u(wide)) for _ in range(nch)]
                r.take(8)                                                         # '8BIM' + blend key
                blend_sig = None
                opacity, _clip, flags, _fill = struct.unpack(">BBBB", r.take(4))
                extra = _Reader(r.take(r.u(">I")))
                extra.take(extra.u(">I"))                                         # layer mask data
                extra.take(extra.u(">I"))                                         # blending ranges
                nl = extra.u(">B")
                raw_name = extra.take(nl)
                extra.take((-(nl + 1)) % 4)
                name = raw_name.decode("latin-1")
                while extra.p + 12 <= len(extra.d):
                    sig = extra.take(4)
                    if sig not in (b"8BIM", b"8B64"):
                        break
                    key = extra.take(4)
                    ln = extra.u(">I")
                    block = extra.take(ln)
                    if key == b"luni" and len(block) >= 4:
                        n = struct.unpack(">I", block[:4])[0]
                        name = block[4:4 + 2 * n].decode("utf-16-be", "replace")
                recs.append((top, left, bottom, right, chans, opacity, bool(flags & 2), name))
                del blend_sig
            for top, left, bottom, right, chans, opacity, hidden, name in recs:
                lw, lh = right - left, bottom - top
                planes = {}
                for cid, ln in chans:
                    if lw <= 0 or lh <= 0:
                        r.take(ln)
                        continue
                    start = r.p
                    comp = r.u(">H")
                    planes[cid] = _read_plane(r, lw, lh, depth, version, ln - 2, comp) if comp in (2, 3) else _read_plane(r, lw, lh, depth, version, None, comp)
                    r.p = start + ln
                layers.append(Layer(name, _layer_image(planes, lw, lh, depth), not hidden, left, top, opacity))
        r.p = max(r.p, min(li_end, len(data)))
    r.p = lm_end if lm_len else r.p
    merged = None
    if r.p + 2 <= len(data):
        try:
            comp = r.u(">H")
            planes = []
            if comp == 1:
                fmt = ">I" if version == 2 else ">H"
                stride = width * (2 if depth == 16 else 1)
                all_counts = [r.u(fmt) for _ in range(channels * height)]
                body = r.take(sum(all_counts))
                pos = 0
                for c in range(channels):
                    plane, pos = _unpack_rows(body, all_counts[c * height:(c + 1) * height], stride, pos)
                    planes.append(plane)
            elif comp == 0:
                stride = width * (2 if depth == 16 else 1)
                planes = [r.take(stride * height) for _ in range(channels)]
            elif comp in (2, 3):
                stride = width * (2 if depth == 16 else 1)
                whole = zlib.decompress(r.take(len(data) - r.p))
                planes = [whole[i * stride * height:(i + 1) * stride * height] for i in range(channels)]
                if comp == 3:
                    planes = [_undo_prediction(p, width, height, depth) for p in planes]
            if planes and all(len(p) == (width * (2 if depth == 16 else 1)) * height for p in planes[:3 if mode == 3 else 1]):
                bands = [_band(p, width, height, depth) for p in planes]
                merged = Image.merge("RGB", bands[:3]) if mode == 3 and len(bands) >= 3 else Image.merge("RGB", (bands[0],) * 3)
        except (PsdError, zlib.error, struct.error):
            merged = None                                                           # no usable merged image: the layers are used instead
    return Psd(width, height, depth, version, layers, merged, icc)


def composite_layers(psd: Psd, background: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """The visible layers laid over a plain background, bottom to top (opacity applied)."""
    canvas = Image.new("RGBA", (psd.width, psd.height), (*background, 255))
    for layer in psd.layers:
        if not layer.visible or layer.image.size == (1, 1) and layer.image.getpixel((0, 0))[3] == 0:
            continue
        img = layer.image
        if layer.opacity < 255:
            a = img.getchannel("A").point(lambda v, o=layer.opacity: v * o // 255)
            img = img.copy()
            img.putalpha(a)
        canvas.alpha_composite(img, (max(0, layer.x), max(0, layer.y))) if layer.x >= 0 and layer.y >= 0 else canvas.paste(img, (layer.x, layer.y), img)
    return canvas.convert("RGB")


def to_image(psd: Psd) -> tuple[Image.Image, str]:
    """(the picture to use, "merged" | "layers"): the merged image when the file has one that is not blank, else the layers composited."""
    if psd.merged is not None and psd.merged.getbbox() is not None and ImageChops.invert(psd.merged).getbbox() is not None:
        return psd.merged, "merged"
    if psd.layers:
        return composite_layers(psd), "layers"
    return (psd.merged if psd.merged is not None else Image.new("RGB", (psd.width, psd.height), (255, 255, 255))), "merged"


def describe(psd: Psd) -> dict[str, Any]:
    return {"width": psd.width, "height": psd.height, "depth": psd.depth, "version": psd.version, "format": "psb" if psd.version == 2 else "psd", "layers": len(psd.layers),
            "layer_names": [l.name for l in psd.layers], "has_merged": psd.merged is not None, "icc": bool(psd.icc)}


__all__ = ["Layer", "Psd", "PsdError", "write_psd", "read_psd", "to_image", "composite_layers", "describe"]
