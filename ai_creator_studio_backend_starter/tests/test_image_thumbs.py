"""R-061: 480/960 px WebP display pictures made locally: upright by EXIF orientation, no metadata (GPS gone), original untouched, signed access,
bad files refused (disguised, huge, broken), removed together with the asset."""
import io
import re
import struct

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)


def jpeg_with_exif(size=(400, 200), orientation=6, gps=True, color=(200, 50, 50)):
    im = Image.new("RGB", size, color)
    ex = Image.Exif()
    ex[0x0112] = orientation
    ex[0x010F] = "SecretCamera"
    if gps:
        gps_ifd = ex.get_ifd(0x8825)
        gps_ifd[1] = "N"; gps_ifd[2] = (37.0, 33.0, 59.0); gps_ifd[3] = "E"; gps_ifd[4] = (126.0, 58.0, 41.0)
        ex[0x8825] = gps_ifd
    buf = io.BytesIO(); im.save(buf, format="JPEG", exif=ex.tobytes()); return buf.getvalue()


def png(size=(1200, 800), color=(10, 120, 200), alpha=False):
    buf = io.BytesIO(); Image.new("RGBA" if alpha else "RGB", size, color + ((128,) if alpha else ())).save(buf, format="PNG"); return buf.getvalue()


def upload(content, name="p.jpg", kind="model", ws="wa", who="a"):
    return client.post(f"/v1/workspaces/{ws}/library", headers=auth(who), data={"kind": kind, "name": "x", "rights_confirmed": "true"},
                       files={"file": (name, content, "image/jpeg" if name.endswith(("jpg", "jpeg")) else "image/png")})


def get_url(url):
    return client.get(url)


def stored(env_, asset_id):
    return next((env_["tmp"] / "private").glob(f"{asset_id}.*"))


def test_both_sizes_are_made_as_webp_and_fit_inside_the_box(env):
    r = upload(png((1200, 800)), "big.png")
    assert r.status_code == 201, r.text
    thumbs = r.json()["thumbs"]
    assert set(thumbs) == {"480", "960"}
    for size, url in thumbs.items():
        resp = get_url(url)
        assert resp.status_code == 200 and resp.headers["content-type"] == "image/webp"
        with Image.open(io.BytesIO(resp.content)) as im:
            assert im.format == "WEBP" and max(im.size) == int(size) and im.size == (int(size), int(size) * 2 // 3), "keeps the proportions, longest edge = size"
    small = upload(png((200, 100), (1, 2, 3)), "small.png").json()
    with Image.open(io.BytesIO(get_url(small["thumbs"]["960"]).content)) as im:
        assert im.size == (200, 100), "never enlarged"


def test_exif_orientation_is_applied_and_gps_and_camera_data_are_gone_from_the_display_picture(env):
    original = jpeg_with_exif((400, 200), orientation=6, gps=True)
    with Image.open(io.BytesIO(original)) as im:
        assert im.getexif().get_ifd(0x8825), "the test picture really carries a GPS position"
    r = upload(original, "phone.jpg")
    assert r.status_code == 201, r.text
    data = get_url(r.json()["thumbs"]["480"]).content
    with Image.open(io.BytesIO(data)) as im:
        assert im.size == (200, 400), "orientation 6 turns the 400x200 picture upright"
        assert not im.getexif() and "exif" not in im.info and "icc_profile" not in im.info
    assert b"SecretCamera" not in data and b"Exif" not in data and b"GPS" not in data


def test_the_original_is_stored_unchanged(env):
    original = jpeg_with_exif((300, 300), orientation=3, gps=True)
    r = upload(original, "keep.jpg")
    assert r.status_code == 201
    assert stored(env, r.json()["asset_id"]).read_bytes() == original, "byte-for-byte the uploaded file (its checksum is the provenance)"


def test_transparency_is_kept_in_the_display_picture(env):
    r = upload(png((100, 100), (5, 5, 5), alpha=True), "t.png")
    with Image.open(io.BytesIO(get_url(r.json()["thumbs"]["480"]).content)) as im:
        assert im.mode == "RGBA" and im.getpixel((5, 5))[3] in range(120, 136)


@pytest.mark.parametrize("name,content,why", [
    ("fake.png", jpeg_with_exif(gps=False), "a JPEG named .png"),
    ("fake.jpg", png((50, 50)), "a PNG named .jpg"),
    ("text.png", b"this is not a picture at all" * 20, "text named .png"),
    ("empty.png", b"", "empty"),
    ("evil.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 200, "a PNG signature and nothing else"),
    ("script.png", b"<script>alert(1)</script>", "markup named .png"),
])
def test_disguised_or_broken_files_are_refused_and_nothing_is_stored(env, name, content, why):
    before = client.get("/v1/workspaces/wa/library", headers=auth("a")).json()["total"]
    r = upload(content, name)
    assert r.status_code in (413, 422), (why, r.status_code, r.text)
    assert client.get("/v1/workspaces/wa/library", headers=auth("a")).json()["total"] == before


def test_a_picture_bigger_than_the_ceiling_is_refused(env, monkeypatch):
    monkeypatch.setattr(config, "IMAGE_MAX_UPLOAD_BYTES", 2000)
    ok = upload(png((20, 20)), "tiny.png")
    assert ok.status_code == 201
    r = upload(jpeg_with_exif((600, 600), gps=False), "large.jpg")
    assert r.status_code in (413, 422), r.text
    assert config.IMAGE_MAX_UPLOAD_BYTES == 2000


def test_the_real_default_ceiling_is_25_mb():
    import subprocess, sys, os
    from pathlib import Path
    clean = {k: v for k, v in os.environ.items() if k != "IMAGE_MAX_UPLOAD_BYTES"}
    out = subprocess.run([sys.executable, "-c", "import app.config as c; print(c.IMAGE_MAX_UPLOAD_BYTES, c.THUMB_SIZES)"], cwd=Path(__file__).resolve().parents[1],
                         env=clean, capture_output=True, text=True, check=True).stdout.strip()
    assert out == f"{25 * 1024 * 1024} (480, 960)"


def test_a_huge_picture_in_pixels_is_refused(env):
    # 17000 x 17000 single-colour PNG is a few hundred KB but over the dimension limit
    buf = io.BytesIO(); Image.new("L", (17000, 17000), 7).save(buf, format="PNG", optimize=False, compress_level=9)
    assert len(buf.getvalue()) < config.IMAGE_MAX_UPLOAD_BYTES
    r = upload(buf.getvalue(), "huge.png")
    assert r.status_code == 422, r.status_code


def test_signed_addresses_expire_are_bound_to_the_asset_and_size_and_do_not_open_the_full_picture(env):
    r = upload(png((900, 600)), "s.png").json()
    url480, url960 = r["thumbs"]["480"], r["thumbs"]["960"]
    assert get_url(url480).status_code == 200
    asset_id = r["asset_id"]
    m = re.search(r"expires=(\d+)&signature=([0-9a-f]+)", url480)
    expires, sig = m.group(1), m.group(2)
    assert client.get(f"/v1/assets/{asset_id}/thumb/960?expires={expires}&signature={sig}").status_code == 403, "a 480 signature is not valid for 960"
    assert client.get(f"/v1/assets/{asset_id}/thumb/480?expires={expires}&signature={'0' * 64}").status_code == 403
    assert client.get(f"/v1/assets/{asset_id}/thumb/480?expires=1&signature={sig}").status_code == 403, "expired"
    assert client.get(f"/v1/assets/{asset_id}/preview?expires={expires}&signature={sig}").status_code == 403, "a picture address never opens the full-size preview"
    other = upload(png((900, 600), (9, 9, 9)), "o.png").json()["asset_id"]
    assert client.get(f"/v1/assets/{other}/thumb/480?expires={expires}&signature={sig}").status_code == 403, "bound to the asset"
    assert client.get(f"/v1/assets/{asset_id}/thumb/300?expires={expires}&signature={sig}").status_code == 404, "only the two sizes"
    assert get_url(url960).status_code == 200


def test_signing_not_configured_gives_no_addresses(env, monkeypatch):
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "short")
    r = upload(png((100, 100), (3, 3, 3)), "n.png")
    assert r.status_code == 201 and r.json()["thumbs"] is None


def test_the_list_carries_the_addresses_and_3d_items_have_none(env):
    upload(png((100, 100)), "l.png")
    items = client.get("/v1/workspaces/wa/library", headers=auth("c")).json()["items"]    # a viewer reads too
    assert items and all(set(i["thumbs"]) == {"480", "960"} for i in items)
    from tests.test_workspace_library import glb
    g = client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "3d", "name": "chair"}, files={"file": ("c.glb", glb(), "model/gltf-binary")})
    assert g.status_code == 201 and g.json()["thumbs"] is None


def test_the_display_pictures_are_removed_with_the_asset_and_the_address_stops_working(env):
    r = upload(png((900, 600)), "gone.png").json()
    files = list((config.ASSET_STORAGE_DIR / "thumbs").glob(f"{r['asset_id']}.*.webp"))
    assert len(files) == 2, "both sizes were made when the picture was filed"
    url = r["thumbs"]["480"]
    assert client.delete(f"/v1/workspaces/wa/library/{r['item_id']}", headers=auth("a"), params={"delete_asset": "true"}).status_code == 204
    assert list((config.ASSET_STORAGE_DIR / "thumbs").glob(f"{r['asset_id']}.*.webp")) == []
    assert client.get(url).status_code == 404


def test_a_missing_cache_file_is_rebuilt_on_request(env):
    r = upload(png((900, 600), (77, 7, 7)), "rb.png").json()
    for f in (config.ASSET_STORAGE_DIR / "thumbs").glob(f"{r['asset_id']}.*.webp"):
        f.unlink()
    resp = get_url(r["thumbs"]["480"])
    assert resp.status_code == 200 and Image.open(io.BytesIO(resp.content)).size == (480, 320)
