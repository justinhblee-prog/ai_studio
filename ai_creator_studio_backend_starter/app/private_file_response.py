"""Descriptor-pinned responses for private local files.

The file is opened once with O_NOFOLLOW where supported, validated and optionally
hashed through that descriptor, then streamed from the same descriptor. Replacing
the pathname after response construction cannot swap the bytes being delivered.
"""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Mapping

from fastapi.responses import Response, StreamingResponse


class PrivateFileError(Exception):
    """A private file failed its descriptor-level validation."""


def parse_byte_range(header: str | None, size: int) -> tuple[str, int, int]:
    """One HTTP byte range of a file of ``size`` bytes: ("full", 0, size-1) when there is nothing to do (no header, another unit, several ranges, garbage: the
    whole file is sent), ("partial", first, last) for a satisfiable range (last is clamped to the end), ("invalid", 0, 0) for one that cannot be satisfied (416)."""
    if not header:
        return "full", 0, max(0, size - 1)
    text = header.strip()
    if not text.lower().startswith("bytes=") or "," in text:
        return "full", 0, max(0, size - 1)
    spec = text[6:].strip()
    first, dash, last = spec.partition("-")
    if not dash or not (first.isdigit() or first == "") or not (last.isdigit() or last == "") or (first == "" and last == ""):
        return "full", 0, max(0, size - 1)
    if size <= 0:
        return "invalid", 0, 0
    if first == "":                                   # the last N bytes
        count = int(last)
        return ("invalid", 0, 0) if count == 0 else ("partial", max(0, size - count), size - 1)
    start = int(first)
    end = size - 1 if last == "" else min(int(last), size - 1)
    return ("invalid", 0, 0) if start >= size or end < start else ("partial", start, end)


def open_private_file_response(
    path: str | Path, *, media_type: str, filename: str | None = None,
    expected_size: int | None = None, expected_sha256: str | None = None,
    headers: Mapping[str, str] | None = None, chunk_size: int = 1024 * 1024, inline: bool = False, range_header: str | None = None,
    ranges: bool = False,
) -> Response:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(os.fspath(path), flags)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PrivateFileError("Private file is not a regular file")
        if expected_size is not None and info.st_size != int(expected_size):
            raise PrivateFileError("Private file size does not match its recorded value")
        digest = hashlib.sha256() if expected_sha256 else None
        if digest is not None:
            with os.fdopen(os.dup(fd), "rb") as verifier:
                for chunk in iter(lambda: verifier.read(chunk_size), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected_sha256:
                raise PrivateFileError("Private file checksum does not match its recorded value")
        kind, first, last = parse_byte_range(range_header, info.st_size) if ranges else ("full", 0, max(0, info.st_size - 1))
        if kind == "invalid":
            os.close(fd)
            return Response(status_code=416, headers={"Content-Range": f"bytes */{info.st_size}", "Cache-Control": "private, no-store"})
        os.lseek(fd, first if kind == "partial" else 0, os.SEEK_SET)
    except PrivateFileError:
        try:
            os.close(fd)
        except (OSError, UnboundLocalError):
            pass
        raise
    except OSError as exc:
        try:
            os.close(fd)
        except (OSError, UnboundLocalError):
            pass
        raise PrivateFileError("Private file cannot be opened safely") from exc

    stream = os.fdopen(fd, "rb", closefd=True)
    response_headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    remaining = (last - first + 1) if kind == "partial" else info.st_size
    response_headers["Content-Length"] = str(remaining)
    if ranges:                       # only where the caller serves pieces (video, 3D models): a zip download does not promise it
        response_headers["Accept-Ranges"] = "bytes"
    if kind == "partial":
        response_headers["Content-Range"] = f"bytes {first}-{last}/{info.st_size}"
    if filename:
        # Avoid injecting untrusted header control characters.
        safe_name = Path(filename).name.replace("\r", "").replace("\n", "").replace('"', "")
        response_headers["Content-Disposition"] = f'{"inline" if inline else "attachment"}; filename="{safe_name}"'
    elif inline:
        response_headers["Content-Disposition"] = "inline"
    if headers:
        response_headers.update(dict(headers))

    async def body():
        left = remaining
        try:
            while left > 0:
                chunk = stream.read(min(chunk_size, left))
                if not chunk:
                    break
                left -= len(chunk)
                yield chunk
        finally:
            stream.close()

    return StreamingResponse(body(), status_code=206 if kind == "partial" else 200, media_type=media_type, headers=response_headers)
