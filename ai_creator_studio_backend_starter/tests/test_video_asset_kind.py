"""Lane 4: the ``video`` asset kind (server-made MP4): kind rule, listing, restore re-check, library filing, and that people still cannot upload videos."""
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import video_mp4
from app.assets import store
from app.assets.validation import (AssetValidationError, ValidatedAsset, asset_kind_of, storage_suffix, validate_asset_upload, validate_video_asset)
from app.main import app
from tests.test_photo_steps_api import auth, env, product_png  # noqa: F401
from tests.test_video_mp4 import ffmpeg  # noqa: F401
from tests.test_workspace_library import glb

client = TestClient(app)


def tiny_mp4():
    size = (160, 96)
    return video_mp4.encode_mp4((Image.linear_gradient("L").resize(size).rotate(i * 4).convert("RGB") for i in range(24)), size, comment="test")


def save_video(owner="user-a", ws="wa", content=None):
    content = content or tiny_mp4()
    return store.save_asset(owner_id=owner, workspace_id=ws, filename="clip.mp4", content=content,
                            validated=ValidatedAsset(media_type="video/mp4", size_bytes=len(content), gltf_version=None, embedded_binary=False),
                            provenance_event="asset.video_output", provenance_extra={"mode": "mock"})


def test_the_kind_rule_and_suffix():
    assert [asset_kind_of(m) for m in ("image/png", "image/webp", "video/mp4", "model/gltf-binary", "model/gltf+json")] == ["image", "image", "video", "model", "model"]
    assert storage_suffix("video/mp4") == ".mp4"
    with pytest.raises(AssetValidationError):
        storage_suffix("video/webm")


def test_people_still_cannot_upload_a_video_and_junk_is_not_a_video():
    for name in ("clip.mp4", "clip.MP4"):
        with pytest.raises(AssetValidationError):
            validate_asset_upload(name, b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64)
    for junk in (b"", b"not a video", b"\x00\x00\x00\x10ftypisom\x00\x00\x02\x00"):
        with pytest.raises(AssetValidationError) as err:
            validate_video_asset("x.mp4", junk)
        assert err.value.code == "ASSET_VIDEO_INVALID"
    with pytest.raises(AssetValidationError) as err:
        validate_video_asset("x.mp4", b"x" * 20, max_bytes=10)
    assert err.value.code == "ASSET_TOO_LARGE"


def test_the_upload_routes_refuse_an_mp4_file(env):
    fake = bytes([0, 0, 0, 24]) + b"ftypisom" + bytes(100)
    r = client.post("/v1/assets/images", headers=auth("a"), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": ("clip.mp4", fake, "video/mp4")})
    assert r.status_code == 422, r.text
    r = client.post("/v1/assets", headers=auth("a"), data={"workspace_id": "wa"}, files={"file": ("clip.mp4", fake, "video/mp4")})
    assert r.status_code == 422, r.text


def test_a_saved_mp4_is_a_video_asset_listed_only_under_video(env, ffmpeg):
    saved = save_video()
    assert saved["asset_kind"] == "video" and saved["media_type"] == "video/mp4" and saved["gltf_version"] is None and saved["embedded_binary"] is False
    def ids(kind):
        r = client.get("/v1/assets", headers=auth("a"), params={"workspace_id": "wa", "kind": kind})
        assert r.status_code == 200, r.text
        return {i["asset_id"] for i in r.json()["items"]}
    assert saved["asset_id"] in ids("video") and saved["asset_id"] in ids("all")
    assert saved["asset_id"] not in ids("image") and saved["asset_id"] not in ids("model")
    assert env["asset"] in ids("image") and env["asset"] not in ids("video"), "the uploaded picture is not a video"
    assert client.get("/v1/assets", headers=auth("a"), params={"workspace_id": "wa", "kind": "audio"}).status_code == 422
    assert next((env["tmp"] / "private").glob(saved["asset_id"] + ".mp4")).is_file(), "stored with the .mp4 suffix"


def test_the_file_is_served_with_the_video_media_type_to_members_only(env, ffmpeg):
    saved = save_video()
    url = client.post(f"/v1/assets/{saved['asset_id']}/preview-url", headers=auth("a")).json()["url"]
    r = client.get(url)
    assert r.status_code == 200 and r.headers["content-type"].startswith("video/mp4") and r.content[4:8] == b"ftyp", r.text[:200]
    assert r.headers["cache-control"] == "private, no-store"
    assert client.post(f"/v1/assets/{saved['asset_id']}/preview-url", headers=auth("b")).status_code in (403, 404), "another workspace's user gets no link"


def test_a_new_version_must_keep_the_video_kind(env, ffmpeg):
    saved = save_video()
    r = client.post(f"/v1/assets/{saved['asset_id']}/versions", headers=auth("a"), data={"rights_confirmed": "true"}, files={"file": ("shoe.png", product_png(), "image/png")})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "ASSET_KIND_MISMATCH", r.text
    r = client.post(f"/v1/assets/{saved['asset_id']}/versions", headers=auth("a"), files={"file": ("m.glb", glb(), "model/gltf-binary")})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "ASSET_KIND_MISMATCH", "a 3D file cannot replace a video either: " + r.text


def test_the_library_takes_a_video_only_under_render(env, ffmpeg):
    saved = save_video()
    for kind in ("garment", "model", "bg", "3d"):
        r = client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": saved["asset_id"], "kind": kind})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "LIBRARY_KIND_MISMATCH", (kind, r.text)
    r = client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": saved["asset_id"], "kind": "render", "name": "clip"})
    assert r.status_code == 201, r.text
    assert r.json()["media_type"] == "video/mp4"
    r = client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": env["asset"], "kind": "3d"})
    assert r.status_code == 422, "a picture still cannot be filed as 3D"


def test_restoring_a_stored_video_checks_it_as_a_video(env, ffmpeg):
    saved = save_video()
    first = client.get(f"/v1/assets/{saved['asset_id']}/versions", headers=auth("a")).json()["items"][0]["version_id"]
    r = client.post(f"/v1/assets/{saved['asset_id']}/versions/{first}/restore", headers=auth("a"))
    assert r.status_code == 201, r.text
    assert r.json()["media_type"] == "video/mp4" and r.json()["version_number"] == 2, "restored as a new version of the same video"
