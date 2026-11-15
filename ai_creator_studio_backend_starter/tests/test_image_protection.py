"""R-035: image protection. Signed links work only from this application's pages, images are never cached or offered as files, library
pictures are shown downscaled without metadata. (Package download rules: see test_assets_api.py's lookbook export test.)"""
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app import library
from app.main import app

client = TestClient(app)
WEB = "https://studio.example.org"


def auth(t="a"):
    return {"Authorization": f"Bearer token-{t}"}


def png(size=(24, 32), color=(10, 20, 30), secret=None):
    buf = io.BytesIO()
    info = PngInfo()
    if secret:
        info.add_text("Comment", secret)
    Image.new("RGB", size, color).save(buf, format="PNG", pnginfo=info)
    return buf.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "LIBRARY_STORAGE_DIR", tmp_path / "library")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a"})
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "wa"}).status_code == 201
    return config


def library_item(item_id="top-01", content=None):
    library.upsert_item({"item_id": item_id, "category": "top", "name_ko": "셔츠", "source": "ai_generated", "tool_and_date": "t, 2026-11-20",
                         "rights_confirmed": True}, content or png(), f"{item_id}.png")
    return client.get(f"/v1/library/items/{item_id}/preview-url", headers=auth()).json()["url"]


def asset_urls():
    asset = client.post("/v1/assets/images", headers=auth(), data={"workspace_id": "wa", "rights_confirmed": "true"},
                        files={"file": ("a.png", png(), "application/octet-stream")}).json()
    current = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"][0]["version_id"]
    legacy = client.post(f"/v1/assets/{asset['asset_id']}/preview-url", headers=auth()).json()["url"]
    versioned = client.post(f"/v1/assets/{asset['asset_id']}/versions/{current}/preview-url", headers=auth()).json()["url"]
    return legacy, versioned


# ------------------------------------------------------------------------------------------- who may load a signed link
def all_signed_urls():
    return [library_item(), *asset_urls()]


def test_with_allowed_origins_configured_only_this_application_can_load_images(env, monkeypatch):
    urls = all_signed_urls()
    monkeypatch.setattr(env, "PREVIEW_ALLOWED_ORIGINS", (WEB,))
    for url in urls:
        assert client.get(url).status_code == 403, "an address typed into the browser / a script sends neither Origin nor Referer"
        assert client.get(url, headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.get(url, headers={"Referer": "https://evil.example/page"}).status_code == 403
        assert client.get(url, headers={"Referer": "https://studio.example.org.evil.example/"}).status_code == 403, "a look-alike host is not the same origin"
        assert client.get(url, headers={"Origin": WEB}).status_code == 200
        assert client.get(url, headers={"Referer": f"{WEB}/some/page?x=1"}).status_code == 200


def test_the_check_can_be_switched_off_and_does_nothing_when_no_origin_is_configured(env, monkeypatch):
    urls = all_signed_urls()
    assert env.PREVIEW_ALLOWED_ORIGINS == () and all(client.get(u).status_code == 200 for u in urls)
    monkeypatch.setattr(env, "PREVIEW_ALLOWED_ORIGINS", (WEB,))
    monkeypatch.setattr(env, "PREVIEW_REQUIRE_ORIGIN", False)
    assert all(client.get(u).status_code == 200 for u in urls)


def test_a_wrong_origin_does_not_replace_the_signature_check(env, monkeypatch):
    url = library_item()
    monkeypatch.setattr(env, "PREVIEW_ALLOWED_ORIGINS", (WEB,))
    assert client.get(url.replace("signature=", "signature=0"), headers={"Origin": WEB}).status_code == 403
    assert client.get(url.replace("expires=", "expires=1"), headers={"Origin": WEB}).status_code == 403


def test_an_expired_library_link_is_refused_even_with_a_valid_signature(env):
    library_item()
    past = int(time.time()) - 5
    url = f"/v1/library/items/top-01/versions/1/preview?expires={past}&signature={library._signature('top-01', 1, past)}"
    assert client.get(url).status_code == 403


# ------------------------------------------------------------------------------------------- how images are handed out
def test_every_image_response_is_uncached_inline_and_not_sniffed(env):
    for url in all_signed_urls():
        r = client.get(url)
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/"), url
        assert r.headers["cache-control"] == "private, no-store", url
        assert r.headers["content-disposition"].startswith("inline"), url
        assert r.headers["x-content-type-options"] == "nosniff", url


# ------------------------------------------------------------------------------------------- library pictures are screen copies
def test_a_large_library_image_is_shown_downscaled_without_its_metadata_and_a_small_one_is_not_enlarged(env):
    big = library_item("bg-01", png((2400, 1600), secret="photographer: Jane Roe"))
    shown = client.get(big)
    with Image.open(io.BytesIO(shown.content)) as image:
        assert image.size == (1200, 800) and image.format == "PNG"
        assert "Comment" not in image.info and b"Jane Roe" not in shown.content, "embedded metadata is not passed on"
    small = client.get(library_item("top-02", png((24, 32))))
    with Image.open(io.BytesIO(small.content)) as image:
        assert image.size == (24, 32)
    tall = client.get(library_item("top-03", png((1000, 3000))))
    with Image.open(io.BytesIO(tall.content)) as image:
        assert max(image.size) == 1200 and image.size == (400, 1200)


def test_importing_still_copies_the_original_resolution_into_the_workspace(env):
    library_item("bg-02", png((2400, 1600)))
    asset = client.post("/v1/library/items/bg-02/import", headers=auth(), json={"workspace_id": "wa"}).json()
    versions = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"]
    preview = client.post(f"/v1/assets/{asset['asset_id']}/versions/{versions[0]['version_id']}/preview-url", headers=auth()).json()["url"]
    with Image.open(io.BytesIO(client.get(preview).content)) as image:
        assert image.size == (2400, 1600), "the workspace copy is an ordinary asset at full size (existing permission rules)"


def test_the_download_limit_is_off_until_the_owner_sets_a_value(env):
    assert env.DOWNLOAD_MONTHLY_LIMIT == 0
