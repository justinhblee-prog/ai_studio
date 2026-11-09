import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.repositories.job import SQLiteJobRepository

client = TestClient(app)


def auth(token="token-cancel-a"):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cancel_env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "assets.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", tmp_path / "generation.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "c" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {
        "token-cancel-a": "cancel-a", "token-cancel-b": "cancel-b"
    })
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    monkeypatch.setattr(config, "PROVIDER_ROUTING_MODE", "MANUAL")
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "cancel-ws"}).status_code == 201


def create_job():
    response = client.post("/v1/generation-jobs", headers=auth(), json={
        "workspace_id": "cancel-ws",
        "model_image_url": "https://images.example.org/model.png",
        "garment_image_url": "https://images.example.org/garment.png",
    })
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def test_queued_job_can_be_cancelled_before_dispatch(cancel_env):
    job_id = create_job()
    response = client.post(f"/v1/generation-jobs/{job_id}/cancel", headers=auth(), json={"reason": "Customer changed the garment."})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "JOB_CANCELLED"
    repository = SQLiteJobRepository()
    assert repository.get(job_id)["status"] == "failed"
    storage, path, _ = repository._context()
    with storage.transaction(path) as conn:
        outbox = conn.execute("SELECT status FROM generation_outbox WHERE job_id=?", (job_id,)).fetchone()
        execution = conn.execute("SELECT status,error_code FROM generation_executions WHERE job_id=?", (job_id,)).fetchone()
        events = conn.execute("SELECT event_type,actor_id FROM generation_job_events WHERE job_id=? ORDER BY event_id DESC LIMIT 1", (job_id,)).fetchone()
    assert outbox["status"] == "processed"
    assert execution["status"] == "failed" and execution["error_code"] == "JOB_CANCELLED"
    assert events["event_type"] == "JOB_CANCELLED_BEFORE_DISPATCH" and events["actor_id"] == "cancel-a"


def test_cancellation_is_workspace_scoped_and_requires_write_role(cancel_env):
    job_id = create_job()
    assert client.post(f"/v1/generation-jobs/{job_id}/cancel", headers=auth("token-cancel-b")).status_code == 404
    assert client.post("/v1/workspaces/cancel-ws/members", headers=auth(), json={"user_id": "cancel-b", "role": "viewer"}).status_code == 201
    assert client.post(f"/v1/generation-jobs/{job_id}/cancel", headers=auth("token-cancel-b")).status_code == 403


def test_cannot_cancel_after_dispatch_claim_or_terminal_state(cancel_env):
    job_id = create_job()
    repository = SQLiteJobRepository()
    storage, path, _ = repository._context()
    with storage.transaction(path) as conn:
        conn.execute("UPDATE generation_outbox SET status='processing',claimed_by='worker-x' WHERE job_id=?", (job_id,))
    response = client.post(f"/v1/generation-jobs/{job_id}/cancel", headers=auth())
    assert response.status_code == 409
    with storage.transaction(path) as conn:
        conn.execute("UPDATE generation_outbox SET status='pending',claimed_by=NULL WHERE job_id=?", (job_id,))
    assert client.post(f"/v1/generation-jobs/{job_id}/cancel", headers=auth()).status_code == 200
    assert client.post(f"/v1/generation-jobs/{job_id}/cancel", headers=auth()).status_code == 409


def test_cancel_rejects_unknown_fields_and_long_reason(cancel_env):
    job_id = create_job()
    assert client.post(f"/v1/generation-jobs/{job_id}/cancel", headers=auth(), json={"unexpected": True}).status_code == 422
    assert client.post(f"/v1/generation-jobs/{job_id}/cancel", headers=auth(), json={"reason": "x" * 501}).status_code == 422
