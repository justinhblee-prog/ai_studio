import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def listing_env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "assets.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", tmp_path / "generation.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {
        "token-user-a": "user-a", "token-user-b": "user-b"
    })
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    monkeypatch.setattr(config, "PROVIDER_ROUTING_MODE", "MANUAL")
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "list-ws"}).status_code == 201
    return tmp_path


def test_generation_job_list_is_workspace_scoped_and_paginated(listing_env):
    created = client.post("/v1/generation-jobs", headers=auth(), json={
        "workspace_id": "list-ws",
        "model_image_url": "https://images.example.org/model.png",
        "garment_image_url": "https://images.example.org/garment.png",
    })
    assert created.status_code == 202, created.text
    first = client.get("/v1/generation-jobs?workspace_id=list-ws&limit=1&offset=0", headers=auth())
    assert first.status_code == 200 and len(first.json()) == 1
    assert first.json()[0]["job_id"] == created.json()["job_id"]
    assert client.get("/v1/generation-jobs?workspace_id=list-ws&limit=1&offset=1", headers=auth()).json() == []
    assert client.get("/v1/generation-jobs?workspace_id=unknown-ws", headers=auth()).status_code == 404
    assert client.get("/v1/generation-jobs?workspace_id=list-ws", headers=auth("token-user-b")).status_code == 404


def test_workspace_viewer_can_list_jobs_but_cannot_create(listing_env):
    assert client.post("/v1/workspaces/list-ws/members", headers=auth(), json={
        "user_id": "user-b", "role": "viewer"
    }).status_code == 201
    assert client.get("/v1/generation-jobs?workspace_id=list-ws", headers=auth("token-user-b")).status_code == 200
    denied = client.post("/v1/generation-jobs", headers=auth("token-user-b"), json={
        "workspace_id": "list-ws",
        "model_image_url": "https://images.example.org/model.png",
        "garment_image_url": "https://images.example.org/garment.png",
    })
    assert denied.status_code == 403


def test_generation_job_list_rejects_invalid_pagination(listing_env):
    assert client.get("/v1/generation-jobs?workspace_id=list-ws&limit=101", headers=auth()).status_code == 422
    assert client.get("/v1/generation-jobs?workspace_id=list-ws&offset=-1", headers=auth()).status_code == 422
