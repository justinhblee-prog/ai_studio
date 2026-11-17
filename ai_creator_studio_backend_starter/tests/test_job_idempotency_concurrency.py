"""B-08: duplicate and racing job creation. The same Idempotency-Key sent many times at once makes exactly one job (everyone gets that job back),
the same key with different bodies lets one body win and refuses the rest, and calls without a key are all real jobs."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
URL = "/v1/generation-jobs"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    import app.config as config
    import app.main as main
    from app.assets.store import create_workspace
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "assets.sqlite3")
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "assets")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a"})
    create_workspace("ws-test", "user-a")
    main.jobs.clear()
    main.idempotency.clear()
    yield
    main.jobs.clear()
    main.idempotency.clear()


H = {"Authorization": "Bearer token-user-a"}


def body(**kw):
    return {"workspace_id": "ws-test", "model_image_url": "https://example.com/model.jpg", "garment_image_url": "https://example.com/garment.jpg", **kw}


def job_count():
    r = client.get(URL, headers=H, params={"workspace_id": "ws-test", "limit": 100})
    assert r.status_code == 200
    return len(r.json())


def test_the_same_key_sent_at_once_makes_exactly_one_job():
    headers = {**H, "Idempotency-Key": "race-key-0001"}
    with ThreadPoolExecutor(8) as pool:
        got = list(pool.map(lambda _: client.post(URL, headers=headers, json=body()), range(8)))
    assert all(r.status_code in (200, 201, 202) for r in got), [r.status_code for r in got]
    assert len({r.json()["job_id"] for r in got}) == 1
    assert job_count() == 1


def test_the_same_key_with_different_bodies_has_one_winner_and_the_rest_are_refused():
    headers = {**H, "Idempotency-Key": "race-key-0002"}
    bodies = [body(), body(category="bottoms")] * 3
    with ThreadPoolExecutor(6) as pool:
        got = list(pool.map(lambda b: client.post(URL, headers=headers, json=b), bodies))
    ok = [r for r in got if r.status_code < 300]
    refused = [r for r in got if r.status_code == 409]
    assert len(ok) + len(refused) == 6 and ok and refused, [r.status_code for r in got]
    assert len({r.json()["job_id"] for r in ok}) == 1
    assert job_count() == 1


def test_calls_without_a_key_are_all_real_jobs():
    with ThreadPoolExecutor(4) as pool:
        got = list(pool.map(lambda _: client.post(URL, headers=H, json=body()), range(4)))
    assert all(r.status_code < 300 for r in got) and len({r.json()["job_id"] for r in got}) == 4
    assert job_count() == 4
