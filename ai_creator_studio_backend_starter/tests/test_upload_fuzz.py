"""B-06: hostile uploads. Every kind of bad file is refused with a clean 4xx (never 5xx), nothing is stored for it, and odd file names cannot write outside the storage folder.
Covers the library upload and the two asset upload routes. Valid pictures still go through (so the checks are not just refusing everything)."""
import io
import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from tests.test_image_thumbs import png, upload as library_upload
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a, wb: owner b)

client = TestClient(app)


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png_claiming(width: int, height: int) -> bytes:
    """A few dozen bytes that CLAIM a huge picture (decompression-bomb shape)."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(b"\x00" * 64)) + _chunk(b"IEND", b"")


def zip_bytes() -> bytes:
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("a.bin", b"\x00" * 5_000_000)
    return buf.getvalue()


BAD = {
    "empty": (b"", "x.png"),
    "svg-with-script-as-png": (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "x.png"),
    "svg-file": (b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>', "x.svg"),
    "html-as-png": (b"<html><script>alert(1)</script></html>", "x.png"),
    "truncated-png": (png()[:60], "x.png"),
    "png-claiming-100000x100000": (png_claiming(100000, 100000), "x.png"),
    "png-claiming-65535x65535": (png_claiming(65535, 65535), "x.png"),
    "zip-as-glb": (zip_bytes(), "x.glb"),
    "random-bytes": (bytes(range(256)) * 40, "x.png"),
    "exe-header": (b"MZ" + b"\x90" * 500, "x.png"),
}


def stored_files():
    root = config.ASSET_STORAGE_DIR
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


@pytest.mark.parametrize("name", sorted(BAD))
def test_library_upload_refuses_bad_files_cleanly_and_stores_nothing(env, name):
    content, filename = BAD[name]
    before = len(stored_files())
    r = library_upload(content, filename)
    assert 400 <= r.status_code < 500, (name, r.status_code, r.text[:200])
    assert len(stored_files()) == before, "a refused file must leave nothing behind"


@pytest.mark.parametrize("name", sorted(BAD))
def test_image_asset_upload_refuses_bad_files_cleanly(env, name):
    content, filename = BAD[name]
    r = client.post("/v1/assets/images", headers=auth("a"), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": (filename, content, "image/png")})
    assert 400 <= r.status_code < 500, (name, r.status_code, r.text[:200])


@pytest.mark.parametrize("name", ["empty", "zip-as-glb", "random-bytes", "exe-header", "html-as-png"])
def test_model_asset_upload_refuses_non_models(env, name):
    content, _ = BAD[name]
    r = client.post("/v1/assets", headers=auth("a"), data={"workspace_id": "wa"}, files={"file": ("m.glb", content, "application/octet-stream")})
    assert 400 <= r.status_code < 500, (name, r.status_code, r.text[:200])


@pytest.mark.parametrize("filename", ["../../escape.png", "..\..\escape.png", "a\x00b.png", "x" * 400 + ".png", "/etc/passwd.png", "con.png", " .png", "ä‮txt.png"])
def test_odd_file_names_never_write_outside_storage(env, filename):
    tmp = env["tmp"]
    r = library_upload(png((300, 200)), filename)
    assert r.status_code < 500, (filename, r.status_code, r.text[:200])
    for escaped in (tmp / "escape.png", tmp.parent / "escape.png", tmp.parent.parent / "escape.png"):
        assert not escaped.exists(), escaped
    root = config.ASSET_STORAGE_DIR.resolve()
    assert all(root in p.resolve().parents or p.resolve() == root for p in stored_files())


def test_a_valid_picture_still_goes_through(env):
    r = library_upload(png((300, 200)), "fine.png")
    assert r.status_code == 201, r.text[:200]
