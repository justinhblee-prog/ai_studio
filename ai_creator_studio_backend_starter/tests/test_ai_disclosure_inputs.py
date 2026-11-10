"""L-07: the disclosure fields are decided by the server; a request cannot switch them off."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth():
    return {"Authorization": "Bearer token-user-a"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "d.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", tmp_path / "g.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a"})
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "disc-ws"}).status_code == 201


def test_the_server_overrides_a_flag_already_on_an_output_item():
    """The job's provider decides; whatever an item carries (even a stored false) is replaced."""
    from app.ai_disclosure import disclose_job_outputs
    listing = {"data": [{"output_id": "o1", "is_ai_generated": False}, {"output_id": "o2"}]}
    out = disclose_job_outputs(listing, {"provider": "fashn", "model": "m"})
    assert [i["is_ai_generated"] for i in out["data"]] == [True, True]
    listing = {"data": [{"output_id": "o1", "is_ai_generated": True}]}
    assert disclose_job_outputs(listing, {"provider": "mock", "model": "m"})["data"][0]["is_ai_generated"] is False


def test_an_extra_disclosure_field_in_a_job_request_is_ignored_not_stored(env):
    body = {"workspace_id": "disc-ws", "model_image_url": "https://example.com/m.jpg", "garment_image_url": "https://example.com/g.jpg",
            "is_ai_generated": False}
    res = client.post("/v1/generation-jobs", headers=auth(), json=body)
    assert res.status_code == 202, res.text
    job = client.get(f"/v1/generation-jobs/{res.json()['job_id']}", headers=auth()).json()
    assert "is_ai_generated" not in job.get("payload", {})
    assert job.get("is_ai_generated") is None   # not the client's False: a queued job has no disclosure yet


def test_the_disclosure_is_not_a_field_of_any_writable_model():
    """No request body model of the API has a disclosure field to set (the response models only report it)."""
    from app import main as m
    from app.photo_engine import PhotoDraftInput
    from app.lookbook import LookbookDraftInput
    for model in (m.CreateTryOnJob, PhotoDraftInput, LookbookDraftInput):
        assert not [f for f in model.model_fields if "ai_generated" in f or "disclosure" in f], model
