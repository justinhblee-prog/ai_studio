import asyncio
import os

import pytest

from app.private_file_response import PrivateFileError, open_private_file_response


def _consume(response):
    async def collect():
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        return b"".join(chunks)
    return asyncio.run(collect())

def test_stream_is_pinned_to_open_descriptor_after_path_replacement(tmp_path):
    target = tmp_path / "private.zip"
    original = b"approved-package-bytes"
    target.write_bytes(original)
    response = open_private_file_response(target, media_type="application/zip",
        expected_size=len(original), expected_sha256=__import__("hashlib").sha256(original).hexdigest())
    moved = tmp_path / "original.bin"
    os.replace(target, moved)
    target.write_bytes(b"attacker-replacement")
    assert _consume(response) == original

def test_symlink_is_rejected_where_no_follow_is_supported(tmp_path):
    if not getattr(os, "O_NOFOLLOW", 0):
        pytest.skip("O_NOFOLLOW is not available on this platform")
    target = tmp_path / "target.bin"; target.write_bytes(b"secret")
    link = tmp_path / "link.bin"; link.symlink_to(target)
    with pytest.raises(PrivateFileError):
        open_private_file_response(link, media_type="application/octet-stream")

def test_descriptor_checksum_mismatch_is_rejected(tmp_path):
    target = tmp_path / "private.bin"; target.write_bytes(b"changed")
    with pytest.raises(PrivateFileError):
        open_private_file_response(target, media_type="application/octet-stream",
            expected_size=7, expected_sha256="0" * 64)

def test_descriptor_rejects_directory(tmp_path):
    with pytest.raises(PrivateFileError):
        open_private_file_response(tmp_path, media_type="application/octet-stream")
