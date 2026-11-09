"""Cost control: per-workspace daily cap on generation jobs (PROVIDER_MODE=mock, no provider is called)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}


def body(workspace="ws-cap", n=0):
    return {"workspace_id": workspace, "model_image_url": "https://example.com/model.jpg",
            "garment_image_url": f"https://example.com/garment-{n}.jpg"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    from app.assets.store import create_workspace
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "cap.sqlite3")
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "assets")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a", "token-user-b": "user-b"})
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    create_workspace("ws-cap", "user-a")
    create_workspace("ws-other", "user-a")
    return config


def create(workspace="ws-cap", n=0, key=None, token="token-user-a"):
    headers = auth(token) | ({"Idempotency-Key": key} if key else {})
    return client.post("/v1/generation-jobs", headers=headers, json=body(workspace, n))


def test_default_is_unlimited(env):
    assert env.GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE == 0
    assert [create(n=i).status_code for i in range(6)] == [202] * 6


def test_jobs_over_the_daily_limit_are_blocked_with_429_and_a_retry_hint(env, monkeypatch):
    monkeypatch.setattr(env, "GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE", 3)
    assert [create(n=i).status_code for i in range(3)] == [202, 202, 202]
    blocked = create(n=3)
    assert blocked.status_code == 429, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "DAILY_JOB_LIMIT_EXCEEDED" and detail["limit"] == 3 and detail["used"] == 3
    assert 1 <= int(blocked.headers["Retry-After"]) <= 86401
    listed = client.get("/v1/generation-jobs?workspace_id=ws-cap", headers=auth()).json()
    assert len(listed) == 3, "a blocked request must not create a job"


def test_the_limit_is_per_workspace(env, monkeypatch):
    monkeypatch.setattr(env, "GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE", 2)
    assert [create("ws-cap", i).status_code for i in range(2)] == [202, 202]
    assert create("ws-cap", 9).status_code == 429
    assert [create("ws-other", i).status_code for i in range(2)] == [202, 202]
    assert create("ws-other", 9).status_code == 429


def test_idempotent_replays_are_not_counted_and_not_blocked_at_the_limit(env, monkeypatch):
    monkeypatch.setattr(env, "GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE", 2)
    first = create(n=0, key="same-key")
    assert first.status_code == 202
    assert create(n=1).status_code == 202  # limit reached (2/2)
    replay = create(n=0, key="same-key")
    assert replay.status_code == 202 and replay.json()["job_id"] == first.json()["job_id"]
    assert create(n=2, key="new-key").status_code == 429
    assert len(client.get("/v1/generation-jobs?workspace_id=ws-cap", headers=auth()).json()) == 2


def test_jobs_created_before_today_do_not_count(env, monkeypatch):
    import sqlite3
    monkeypatch.setattr(env, "GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE", 2)
    assert create(n=0).status_code == 202 and create(n=1).status_code == 202
    assert create(n=2).status_code == 429
    yesterday = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)).isoformat()
    db = sqlite3.connect(env.ASSET_DATABASE_PATH)
    db.execute("UPDATE generation_jobs SET created_at=? WHERE workspace_id='ws-cap'", (yesterday,))
    db.commit(); db.close()
    assert create(n=3).status_code == 202, "yesterday's jobs must not count against today's limit"


def test_a_viewer_cannot_create_jobs_and_a_refused_request_is_not_counted(env, monkeypatch):
    monkeypatch.setattr(env, "GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE", 1)
    assert create(token="token-user-b").status_code in (403, 404)
    assert create(n=0).status_code == 202


def test_limit_setting_rejects_garbage_instead_of_silently_allowing_everything():
    import os
    import subprocess
    import sys

    def run(value):
        env = {k: v for k, v in os.environ.items() if k != "GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE"}
        if value is not None:
            env["GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE"] = value
        return subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, '.'); import app.config as c; print(c.GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE)"],
                              capture_output=True, text=True, env=env)
    assert run(None).stdout.strip() == "0" and run("25").stdout.strip() == "25"
    assert run("").stdout.strip() == "0", "an empty value means 'not set'"
    for bad in ("abc", "-1", "2.5"):
        result = run(bad)
        assert result.returncode != 0 and "GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE" in result.stderr, (bad, result.stdout, result.stderr[-200:])
