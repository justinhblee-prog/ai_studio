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

from fastapi.responses import StreamingResponse


class PrivateFileError(Exception):
    """A private file failed its descriptor-level validation."""


def open_private_file_response(
    path: str | Path, *, media_type: str, filename: str | None = None,
    expected_size: int | None = None, expected_sha256: str | None = None,
    headers: Mapping[str, str] | None = None, chunk_size: int = 1024 * 1024, inline: bool = False,
) -> StreamingResponse:
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
        os.lseek(fd, 0, os.SEEK_SET)
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
    response_headers["Content-Length"] = str(info.st_size)
    if filename:
        # Avoid injecting untrusted header control characters.
        safe_name = Path(filename).name.replace("\r", "").replace("\n", "").replace('"', "")
        response_headers["Content-Disposition"] = f'{"inline" if inline else "attachment"}; filename="{safe_name}"'
    elif inline:
        response_headers["Content-Disposition"] = "inline"
    if headers:
        response_headers.update(dict(headers))

    async def body():
        try:
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            stream.close()

    return StreamingResponse(body(), media_type=media_type, headers=response_headers)
