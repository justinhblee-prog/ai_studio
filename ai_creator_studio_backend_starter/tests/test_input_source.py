"""Reply 11 A: uploaded photos are not AI; a job's result is AI-edited; library AI inputs make it AI-generated. The wording follows the inputs."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import library
from app.ai_disclosure import input_source_of_job
from app.main import app

client = TestClient(app)


def auth():
    return {"Authorization": "Bearer token-a"}


def png(color):
    buf = io.BytesIO(); Image.new("RGB", (16, 16), color).save(buf, format="PNG"); return buf.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "p")
    monkeypatch.setattr(config, "LIBRARY_STORAGE_DIR", tmp_path / "lib")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "i" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a"})
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "wi"}).status_code == 201


def uploaded():
    r = client.post("/v1/assets/images", headers=auth(), data={"workspace_id": "wi"}, files={"file": ("u.png", png((1, 2, 3)), "application/octet-stream")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def library_copy(source):
    slug = "lib-" + source.replace("_", "-")
    library.upsert_item({"item_id": slug, "category": "top", "name_ko": "x", "source": source, "tool_and_date": "t", "rights_confirmed": True},
                        png((9, 9, 9)), "x.png")
    r = client.post(f"/v1/library/items/{slug}/import", headers=auth(), json={"workspace_id": "wi"})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def job(a, b):
    url = lambda i: f"https://api.example.org/v1/assets/{i}/versions/v1/preview?expires=1&signature=s"
    return {"payload": {"model_image_url": url(a), "garment_image_url": url(b)}}


def test_only_the_customers_own_photos_are_uploaded(env):
    assert input_source_of_job(job(uploaded(), uploaded())) == "uploaded"


def test_a_library_ai_input_makes_it_library_ai_also_when_mixed(env):
    ai, own = library_copy("ai_generated"), uploaded()
    assert input_source_of_job(job(ai, ai)) == "platform_library_ai"
    assert input_source_of_job(job(own, ai)) == "platform_library_ai", "a mix that includes library AI is labelled as generated"


def test_a_licensed_library_photo_is_not_ai_made(env):
    assert input_source_of_job(job(library_copy("licensed"), uploaded())) == "uploaded"


def test_untraceable_inputs_are_unknown_never_assumed_uploaded(env):
    assert input_source_of_job({"payload": {"model_image_url": "https://images.example.org/m.png", "garment_image_url": "https://images.example.org/g.png"}}) == "unknown"
    assert input_source_of_job(job(uploaded(), "ast_does_not_exist")) == "unknown"
    assert input_source_of_job({"payload": {"model_image_url": f"https://x/v1/assets/{uploaded()}/p", "garment_image_url": "https://images.example.org/g.png"}}) == "unknown"
    assert input_source_of_job({}) == "unknown"
