"""R-061 item 1 (reply 41): the GPS position is removed from pictures when they are DOWNLOADED. The stored original is never changed.

Nothing is re-encoded: the picture data and every other metadata value stay byte for byte as they were. Only the GPS part is cut out:
  * EXIF (JPEG APP1, PNG eXIf, WebP EXIF): the GPS pointer entry is removed from the IFD (the entries after it move up, the entry count goes down by one, the table
    keeps its size) and the GPS IFD with its values is overwritten with zeros. Little- and big-endian EXIF are both handled.
  * XMP (JPEG APP1, PNG iTXt, WebP XMP): ``exif:GPS*`` attributes and elements are blanked with spaces of the same length (the packet keeps its size).
Not handled (said openly): XMP that is compressed (PNG zTXt / compressed iTXt), ImageMagick "Raw profile type exif" text chunks, GPS written inside a MakerNote.
"""
from __future__ import annotations

import re
import struct
import zlib

GPS_POINTER = 0x8825
TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4, 16: 8, 17: 8, 18: 8}
XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"
MAX_IFDS = 4
_ATTR = re.compile(r"\s+exif:GPS[A-Za-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*')")
_ELEM = re.compile(r"<exif:GPS[A-Za-z]+(?:\s[^>]*)?(?:/>|>.*?</exif:GPS[A-Za-z]+\s*>)", re.S)


def scrub_xmp(xmp: bytes) -> bytes:
    """The packet with every exif:GPS* attribute / element replaced by spaces of the same length."""
    text = xmp.decode("latin-1")            # one character per byte: lengths and offsets are preserved
    new = _ELEM.sub(lambda m: " " * len(m.group(0)), _ATTR.sub(lambda m: " " * len(m.group(0)), text))
    return new.encode("latin-1") if new != text else xmp


def _zero_gps_ifd(tiff: bytearray, off: int, endian: str) -> None:
    if off + 2 > len(tiff):
        return
    n = struct.unpack(endian + "H", tiff[off:off + 2])[0]
    table_end = off + 2 + 12 * n + 4
    if n > 500 or table_end > len(tiff):
        return
    for i in range(n):
        e = off + 2 + 12 * i
        ftype, count = struct.unpack(endian + "HI", tiff[e + 2:e + 8])
        size = TYPE_SIZE.get(ftype, 1) * count
        if size > 4:
            voff = struct.unpack(endian + "I", tiff[e + 8:e + 12])[0]
            if voff + size <= len(tiff):
                tiff[voff:voff + size] = bytes(size)
    tiff[off:table_end] = bytes(table_end - off)


def _strip_ifd(tiff: bytearray, off: int, endian: str) -> tuple[bool, int]:
    """Remove the GPS pointer from the IFD at ``off``. Returns (changed, offset of the next IFD or 0)."""
    if off + 2 > len(tiff) or off < 8:
        return False, 0
    n = struct.unpack(endian + "H", tiff[off:off + 2])[0]
    end = off + 2 + 12 * n
    if n > 500 or end + 4 > len(tiff):
        return False, 0
    changed = False
    for i in range(n):
        e = off + 2 + 12 * i
        if struct.unpack(endian + "H", tiff[e:e + 2])[0] == GPS_POINTER:
            _zero_gps_ifd(tiff, struct.unpack(endian + "I", tiff[e + 8:e + 12])[0], endian)
            tail = bytes(tiff[e + 12:end + 4])           # the later entries and the next-IFD pointer
            tiff[e:e + len(tail)] = tail
            tiff[e + len(tail):end + 4] = bytes(end + 4 - (e + len(tail)))
            tiff[off:off + 2] = struct.pack(endian + "H", n - 1)
            n -= 1
            end -= 12
            changed = True
            break
    nxt = struct.unpack(endian + "I", tiff[end:end + 4])[0]
    return changed, nxt


def strip_tiff(tiff: bytearray) -> bool:
    """In place. True when a GPS entry was found and removed."""
    if len(tiff) < 8 or tiff[:2] not in (b"II", b"MM"):
        return False
    endian = "<" if tiff[:2] == b"II" else ">"
    if struct.unpack(endian + "H", tiff[2:4])[0] != 42:
        return False
    off, changed = struct.unpack(endian + "I", tiff[4:8])[0], False
    for _ in range(MAX_IFDS):
        if not off:
            break
        did, nxt = _strip_ifd(tiff, off, endian)
        changed = changed or did
        off = nxt
    return changed


def _exif_payload(payload: bytes) -> tuple[bytes, bytes]:
    return (b"Exif\x00\x00", payload[6:]) if payload[:6] == b"Exif\x00\x00" else (b"", payload)


# ----------------------------------------------------------------------------------------------------------------------- formats
def strip_jpeg(data: bytes) -> tuple[bytes, bool]:
    if data[:2] != b"\xff\xd8":
        return data, False
    out, pos, changed = bytearray(data), 2, False
    while pos + 4 <= len(out) and out[pos] == 0xFF:
        marker = out[pos + 1]
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            pos += 2
            continue
        if marker in (0xDA, 0xD9):
            break
        seg_end = pos + 2 + struct.unpack(">H", out[pos + 2:pos + 4])[0]
        if seg_end > len(out):
            break
        start = pos + 4
        if marker == 0xE1:
            if out[start:start + 6] == b"Exif\x00\x00":
                tiff = bytearray(out[start + 6:seg_end])
                if strip_tiff(tiff):
                    out[start + 6:seg_end] = tiff
                    changed = True
            elif out[start:start + len(XMP_NS)] == XMP_NS:
                xmp = bytes(out[start + len(XMP_NS):seg_end])
                new = scrub_xmp(xmp)
                if new != xmp:
                    out[start + len(XMP_NS):seg_end] = new
                    changed = True
        pos = seg_end
    return bytes(out), changed


def strip_png(data: bytes) -> tuple[bytes, bool]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return data, False
    out, pos, changed = bytearray(data), 8, False
    while pos + 12 <= len(out):
        length, ctype = struct.unpack(">I4s", out[pos:pos + 8])
        end = pos + 12 + length
        if end > len(out):
            break
        body = out[pos + 8:pos + 8 + length]
        new = None
        if ctype == b"eXIf":
            prefix, rest = _exif_payload(bytes(body))
            tiff = bytearray(rest)
            if strip_tiff(tiff):
                new = prefix + bytes(tiff)
        elif ctype == b"iTXt" and body[:18] == b"XML:com.adobe.xmp\x00" and len(body) > 20 and body[18] == 0:
            # keyword, compression flag 0 (plain), method, language\0, translated keyword\0, text
            rest = bytes(body[20:])
            head_len = 20
            for _ in range(2):
                z = rest.find(b"\x00")
                if z < 0:
                    break
                head_len += z + 1
                rest = rest[z + 1:]
            scrubbed = scrub_xmp(rest)
            if scrubbed != rest:
                new = bytes(body[:head_len]) + scrubbed
        if new is not None and len(new) == length:
            out[pos + 8:pos + 8 + length] = new
            out[end - 4:end] = struct.pack(">I", zlib.crc32(ctype + new) & 0xFFFFFFFF)
            changed = True
        pos = end
    return bytes(out), changed


def strip_webp(data: bytes) -> tuple[bytes, bool]:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return data, False
    out, pos, changed = bytearray(data), 12, False
    while pos + 8 <= len(out):
        ctype, size = bytes(out[pos:pos + 4]), struct.unpack("<I", out[pos + 4:pos + 8])[0]
        end = pos + 8 + size
        if end > len(out):
            break
        if ctype == b"EXIF":
            prefix, rest = _exif_payload(bytes(out[pos + 8:end]))
            tiff = bytearray(rest)
            if strip_tiff(tiff):
                out[pos + 8:end] = prefix + bytes(tiff)
                changed = True
        elif ctype == b"XMP ":
            xmp = bytes(out[pos + 8:end])
            new = scrub_xmp(xmp)
            if new != xmp:
                out[pos + 8:end] = new
                changed = True
        pos = end + (size & 1)
    return bytes(out), changed


def strip_gps(data: bytes, media_type: str) -> tuple[bytes, bool]:
    """(the picture without its GPS position, whether anything was removed). Unknown or malformed input comes back unchanged."""
    try:
        if media_type == "image/jpeg":
            return strip_jpeg(data)
        if media_type == "image/png":
            return strip_png(data)
        if media_type == "image/webp":
            return strip_webp(data)
    except (struct.error, ValueError, IndexError):
        pass
    return data, False
