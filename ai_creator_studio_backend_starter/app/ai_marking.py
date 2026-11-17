"""R-062: an "AI-made" mark inside the picture files that leave the service.

When a downloaded / previewed picture is the result of an AI provider, the file is served with the mark written into its metadata:
  * PNG  - tEXt chunks (AIGenerated, AIDisclosure, DigitalSourceType) and an XMP packet (iTXt "XML:com.adobe.xmp")
  * JPEG - an XMP APP1 segment and a JPEG comment
  * WebP - an XMP chunk (the container is upgraded to VP8X when needed)
The XMP packet carries the IPTC ``Iptc4xmpExt:DigitalSourceType``: ``trainedAlgorithmicMedia`` (made by AI) or ``compositeWithTrainedAlgorithmicMedia`` (the customer's own
photo was edited by AI). The wording (``dc:description`` and the text chunks) comes from settings (AI_MARK_TEXT_*): the final legal wording is pending.
The pictures' PIXELS and every metadata block already in the file are left exactly as they were: the chunks / segments are INSERTED, nothing is re-encoded.
Never marked: a picture the customer uploaded (served as uploaded), and results of the built-in mock or of local processing (not made by AI).
The stored file never changes (its checksum stays valid): the mark is added to the copy that is sent.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import struct
import zlib
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from fastapi.responses import Response

from app import config
from app.privacy_strip import strip_gps
from app.private_file_response import PrivateFileError, open_private_file_response

DST = "http://cv.iptc.org/newscodes/digitalsourcetype/"
SOURCE_TYPE = {"generated": "trainedAlgorithmicMedia", "edited": "compositeWithTrainedAlgorithmicMedia", "unknown": "trainedAlgorithmicMedia"}
XMP_KEY = "XML:com.adobe.xmp"
MAX_BYTES = 64 * 1024 * 1024


def text_for(kind: str) -> str:
    return {"generated": config.AI_MARK_TEXT_GENERATED, "edited": config.AI_MARK_TEXT_EDITED}.get(kind, config.AI_MARK_TEXT_UNKNOWN)


def xmp_packet(kind: str) -> bytes:
    text = escape(text_for(kind))
    return ('<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
            '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            '<rdf:Description rdf:about="" xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xmp="http://ns.adobe.com/xap/1.0/">'
            f'<Iptc4xmpExt:DigitalSourceType>{DST}{SOURCE_TYPE[kind]}</Iptc4xmpExt:DigitalSourceType>'
            f'<dc:description><rdf:Alt><rdf:li xml:lang="x-default">{text}</rdf:li></rdf:Alt></dc:description>'
            '<xmp:CreatorTool>AI Creator Studio</xmp:CreatorTool>'
            '</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>').encode("utf-8")


def already_marked(data: bytes) -> bool:
    return b"trainedAlgorithmicMedia" in data or b"TrainedAlgorithmicMedia" in data


# ---------------------------------------------------------------------------------------------------------------------- PNG
def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def _latin1(text: str) -> bytes:
    return text.encode("latin-1", "replace")


def mark_png(data: bytes, kind: str) -> bytes:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, chunks, has_xmp = 8, [], False
    while pos + 8 <= len(data):
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        end = pos + 12 + length
        if end > len(data):
            raise ValueError("truncated PNG")
        if ctype == b"iTXt" and data[pos + 8:pos + 8 + len(XMP_KEY) + 1] == XMP_KEY.encode() + b"\x00":
            has_xmp = True
        chunks.append((pos, end, ctype))
        pos = end
    if not chunks or chunks[0][2] != b"IHDR":
        raise ValueError("PNG without IHDR")
    add = _png_chunk(b"tEXt", b"AIGenerated\x00true") + _png_chunk(b"tEXt", b"AIDisclosure\x00" + _latin1(text_for(kind))) \
        + _png_chunk(b"tEXt", b"DigitalSourceType\x00" + (DST + SOURCE_TYPE[kind]).encode())
    if not has_xmp:
        add += _png_chunk(b"iTXt", XMP_KEY.encode() + b"\x00\x00\x00\x00\x00" + xmp_packet(kind))
    first_end = chunks[0][1]
    return data[:first_end] + add + data[first_end:]


# --------------------------------------------------------------------------------------------------------------------- JPEG
XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"


def _jpeg_segment(marker: int, payload: bytes) -> bytes:
    if len(payload) + 2 > 0xFFFF:
        raise ValueError("segment too long")
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def mark_jpeg(data: bytes, kind: str) -> bytes:
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    pos, has_xmp = 2, False
    while pos + 4 <= len(data) and data[pos] == 0xFF and data[pos + 1] in (0xE0, 0xE1):       # leading JFIF / Exif / XMP segments stay where they are
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if data[pos + 4:pos + 4 + len(XMP_NS)] == XMP_NS:
            has_xmp = True
        pos += 2 + length
    if pos > len(data):
        raise ValueError("truncated JPEG")
    add = b"" if has_xmp else _jpeg_segment(0xE1, XMP_NS + xmp_packet(kind))
    add += _jpeg_segment(0xFE, ("AI: " + text_for(kind) + " | " + SOURCE_TYPE[kind]).encode("utf-8")[:2000])
    return data[:pos] + add + data[pos:]


# --------------------------------------------------------------------------------------------------------------------- WebP
def mark_webp(data: bytes, kind: str) -> bytes:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP")
    body = data[12:]
    pos, chunks = 0, []
    while pos + 8 <= len(body):
        ctype, size = body[pos:pos + 4], struct.unpack("<I", body[pos + 4:pos + 8])[0]
        end = pos + 8 + size + (size & 1)
        if end > len(body):
            raise ValueError("truncated WebP")
        chunks.append((ctype, pos, end))
        pos = end
    if not chunks:
        raise ValueError("empty WebP")
    if any(c[0] == b"XMP " for c in chunks):
        return data                                    # it already has XMP: left as it is (the text chunks of other formats do not exist here)
    packet = xmp_packet(kind)
    xmp_chunk = b"XMP " + struct.pack("<I", len(packet)) + packet + (b"\x00" if len(packet) & 1 else b"")
    if chunks[0][0] == b"VP8X":
        head = bytearray(body[chunks[0][1]:chunks[0][2]])
        head[8] |= 0x04                                # the XMP flag
        new_body = bytes(head) + body[chunks[0][2]:] + xmp_chunk
    else:
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(data)) as im:
            width, height = im.size
            alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
        vp8x = b"VP8X" + struct.pack("<I", 10) + bytes([0x04 | (0x10 if alpha else 0)]) + b"\x00\x00\x00" + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
        new_body = vp8x + body + xmp_chunk
    return b"RIFF" + struct.pack("<I", 4 + len(new_body)) + b"WEBP" + new_body


def mark(data: bytes, media_type: str, kind: str) -> bytes:
    """The file with the mark inserted. Raises ValueError for an unknown or malformed picture (the caller then serves the file as it is)."""
    if kind not in SOURCE_TYPE:
        raise ValueError("unknown kind")
    if already_marked(data):
        return data
    if media_type == "image/png":
        return mark_png(data, kind)
    if media_type == "image/jpeg":
        return mark_jpeg(data, kind)
    if media_type == "image/webp":
        return mark_webp(data, kind)
    raise ValueError("unsupported media type")


# ------------------------------------------------------------------------------------------------------ which files, and serving
def kind_for_asset(asset_id: str) -> str | None:
    """'generated' | 'edited' | 'unknown' when the asset is the result of an AI provider's job, else None (uploads, local processing, mock)."""
    if not config.AI_MARKING_ENABLED:
        return None
    try:
        from app.ai_disclosure import input_source_of_job, is_ai_generated_provider
        from app.assets import store
        from app.dependencies import get_job_repository
        store.initialize()
        with store._connect() as db:
            row = db.execute("SELECT details_json FROM asset_provenance WHERE asset_id=? AND event_type='asset.generated_output_imported' ORDER BY created_at LIMIT 1",
                             (asset_id,)).fetchone()
        if row is None:
            return None
        job_id = (json.loads(row["details_json"] or "{}")).get("job_id")
        job = get_job_repository().get(job_id) if job_id else None
        if job is None:
            return "unknown"          # an AI-output asset whose job cannot be found: when in doubt, disclose
        return kind_for_job(job)
    except Exception:  # noqa: BLE001 - the decision must never break a download; an unreadable record means "disclose"
        return "unknown"


def kind_for_job(job: dict[str, Any]) -> str | None:
    from app.ai_disclosure import input_source_of_job, is_ai_generated_provider
    if not config.AI_MARKING_ENABLED or not is_ai_generated_provider(job.get("provider")):
        return None
    return {"uploaded": "edited", "platform_library_ai": "generated"}.get(input_source_of_job(job), "unknown")


def serve(path: str | Path, *, media_type: str, kind: str | None, filename: str | None = None, expected_size: int | None = None,
          expected_sha256: str | None = None, inline: bool = True, range_header: str | None = None):
    """The same response as ``open_private_file_response`` (same integrity checks and headers) but with the mark inserted when ``kind`` is set."""
    if not media_type.startswith("image/"):
        return open_private_file_response(path, media_type=media_type, filename=filename, expected_size=expected_size, expected_sha256=expected_sha256, inline=inline,
                                          range_header=range_header, ranges=True)     # a video is played in pieces (Safari will not play one without Range)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(os.fspath(path), flags)
    except OSError as exc:
        raise PrivateFileError("Private file cannot be opened safely") from exc
    with os.fdopen(fd, "rb") as handle:      # the same checks as open_private_file_response: a regular file of the recorded size and checksum
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise PrivateFileError("Private file is not a regular file")
        if expected_size is not None and info.st_size != int(expected_size):
            raise PrivateFileError("Private file size does not match its recorded value")
        data = handle.read(MAX_BYTES + 1)
    if expected_sha256 and hashlib.sha256(data).hexdigest() != expected_sha256:
        raise PrivateFileError("Private file checksum does not match its recorded value")
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    if filename:
        headers["Content-Disposition"] = f'{"inline" if inline else "attachment"}; filename="{Path(filename).name.replace(chr(13), "").replace(chr(10), "").replace(chr(34), "")}"'
    elif inline:
        headers["Content-Disposition"] = "inline"
    if len(data) > MAX_BYTES:
        headers["X-AI-Marked"] = "skipped-too-large"
        return Response(content=data, media_type=media_type, headers=headers)
    if config.STRIP_GPS_ON_DOWNLOAD:            # reply 41: the position leaves nowhere; the stored original is not touched
        data, removed = strip_gps(data, media_type)
        if removed:
            headers["X-GPS-Stripped"] = "1"
    if kind is not None:
        try:
            data, state = mark(data, media_type, kind), kind
        except ValueError:
            state = "failed"                    # a malformed picture is served as it is (and says so)
        headers["X-AI-Marked"] = state
    return Response(content=data, media_type=media_type, headers=headers)
