import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import job_repository

client = TestClient(app)

@pytest.fixture(autouse=True)
def isolated_generation_env(tmp_path, monkeypatch):
    import app.config as config
    import app.main as main
    from app.assets.store import create_workspace
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "assets.sqlite3")
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "assets")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a", "token-user-b": "user-b"})
    create_workspace("ws-test", "user-a")
    main.jobs.clear()
    main.idempotency.clear()
    yield
    main.jobs.clear()
    main.idempotency.clear()

def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}

def body(**overrides):
    value = {"workspace_id": "ws-test", "model_image_url": "https://example.com/model.jpg", "garment_image_url": "https://example.com/garment.jpg"}
    value.update(overrides)
    return value

def create(**overrides):
    response = client.post("/v1/generation-jobs", headers=auth(), json=body(**overrides))
    if response.status_code == 202:
        import asyncio
        from app.worker import process_one
        from app.poll_worker import process_one as process_poll
        asyncio.run(process_one())
        # Provider polling/output work is handled by its own durable worker, not GET.
        for _ in range(3):
            if not asyncio.run(process_poll()):
                break
        latest = client.get(f"/v1/generation-jobs/{response.json()['job_id']}", headers=auth())
        latest.status_code = 202
        return latest
    return response

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["version"] == "0.7.0"

def test_models_expose_both_fashn_models():
    response = client.get("/v1/engines/models")
    assert response.status_code == 200
    models = {(item["provider"], item["model"]) for item in response.json()}
    assert {("mock", "mock-tryon"), ("fashn", "tryon-v1.6"), ("fashn", "tryon-max")} <= models

def test_generation_requires_authentication():
    assert client.post("/v1/generation-jobs", json=body()).status_code == 401

def test_generation_requires_workspace_membership():
    response = client.post("/v1/generation-jobs", headers=auth("token-user-b"), json=body())
    assert response.status_code == 404

def test_viewer_cannot_create_generation_job(monkeypatch):
    import app.main as main
    from app.assets.store import add_workspace_member
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    add_workspace_member("ws-test", "user-b", "viewer")
    response = client.post("/v1/generation-jobs", headers=auth("token-user-b"), json=body())
    assert response.status_code == 403

def test_create_job_mock_mode(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    response = create(category="tops")
    assert response.status_code == 202
    assert response.json()["provider"] == "mock"
    assert response.json()["status"] == "running"
    assert response.json()["output_url"] is None

def test_idempotency_replays_same_body(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    headers = {**auth(), "Idempotency-Key": "repeat-key-001"}
    a = client.post("/v1/generation-jobs", headers=headers, json=body()).json()
    b = client.post("/v1/generation-jobs", headers=headers, json=body()).json()
    assert a["job_id"] == b["job_id"]

def test_idempotency_rejects_different_body(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    headers = {**auth(), "Idempotency-Key": "repeat-key-002"}
    client.post("/v1/generation-jobs", headers=headers, json=body())
    response = client.post("/v1/generation-jobs", headers=headers, json=body(category="bottoms"))
    assert response.status_code == 409

def test_idempotency_is_workspace_scoped(monkeypatch):
    import app.main as main
    from app.assets.store import create_workspace
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    create_workspace("ws-other", "user-a")
    headers = {**auth(), "Idempotency-Key": "same-key"}
    first = client.post("/v1/generation-jobs", headers=headers, json=body()).json()
    second_body = body(workspace_id="ws-other")
    second = client.post("/v1/generation-jobs", headers=headers, json=second_body).json()
    assert first["job_id"] != second["job_id"]

def test_public_outputs_mount_is_removed():
    assert client.get("/outputs/not-a-real-output.png").status_code == 404

def test_job_read_requires_authentication(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    job_id = create().json()["job_id"]
    assert client.get(f"/v1/generation-jobs/{job_id}").status_code == 401

def test_job_read_is_workspace_scoped(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    job_id = create().json()["job_id"]
    assert client.get(f"/v1/generation-jobs/{job_id}", headers=auth("token-user-b")).status_code == 404

def test_http_images_rejected():
    response = create(model_image_url="http://example.com/model.jpg")
    assert response.status_code == 422

def test_fashn_v16_payload(monkeypatch):
    import app.config as config
    from app.providers.fashn import FashnProvider
    monkeypatch.setattr(config, "FASHN_API_KEY", "test-only")
    monkeypatch.setattr(config, "FASHN_MODEL", "tryon-v1.6")
    payload = FashnProvider().build_request(body(category="outerwear", mode="quality", resolution="4k"))
    assert payload["model_name"] == "tryon-v1.6"
    assert payload["inputs"]["category"] == "auto"
    assert "resolution" not in payload["inputs"]
    assert payload["inputs"]["mode"] == "quality"

def test_fashn_max_payload(monkeypatch):
    import app.config as config
    from app.providers.fashn import FashnProvider
    monkeypatch.setattr(config, "FASHN_API_KEY", "test-only")
    monkeypatch.setattr(config, "FASHN_MODEL", "tryon-max")
    payload = FashnProvider().build_request(body(category="outerwear", resolution="4k", prompt="keep the buttons"))
    assert payload["model_name"] == "tryon-max"
    assert payload["inputs"]["product_image"] == "https://example.com/garment.jpg"
    assert payload["inputs"]["resolution"] == "4k"
    assert payload["inputs"]["prompt"] == "keep the buttons"

def test_successful_provider_result_is_post_processed_and_output_is_private(monkeypatch, tmp_path):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "fashn")
    class FakeProvider:
        name = "fashn"
        model = "tryon-v1.6"
        async def start(self, payload):
            return {"request_id": "fake-provider-request"}
        async def status(self, request_id):
            return {"status": "succeeded", "output_url": "https://cdn.fashn.ai/test.png", "message": None}
    monkeypatch.setattr(main, "get_provider", lambda: FakeProvider())
    from app import poll_worker
    async def fake_save(url, job_id, attempt_id):
        assert url == "https://cdn.fashn.ai/test.png"
        output_dir = main.config.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        key = f"{job_id}.attempt-{attempt_id}.test.png"
        (output_dir / key).write_bytes(b"\x89PNG\r\n\x1a\nprivate")
        return f"/v1/generation-jobs/{job_id}/output", key
    monkeypatch.setattr(poll_worker, "save_provider_output_artifact", fake_save)
    created = create()
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    result = client.get(f"/v1/generation-jobs/{job_id}", headers=auth())
    assert result.status_code == 200
    assert result.json()["status"] == "succeeded"
    assert result.json()["output_url"] == f"/v1/generation-jobs/{job_id}/output"
    assert "/outputs/" not in result.text
    assert client.get(f"/v1/generation-jobs/{job_id}/output").status_code == 401
    assert client.get(f"/v1/generation-jobs/{job_id}/output", headers=auth("token-user-b")).status_code == 404
    download = client.get(f"/v1/generation-jobs/{job_id}/output", headers=auth())
    assert download.status_code == 200
    assert download.headers["cache-control"] == "private, no-store"
    assert download.content.startswith(b"\x89PNG")
    diagnostics = client.get(f"/v1/generation-jobs/{job_id}/events", headers=auth()).json()
    assert diagnostics["execution"]["status"] == "succeeded"
    assert diagnostics["output"]["media_type"] == "image/png"
    assert diagnostics["output"]["size_bytes"] > 0
    assert diagnostics["events"][-1]["event_type"] == "OUTPUT_PERSISTED"

def test_output_store_rejects_unapproved_host():
    from app.output_store import _validate_output_url, OutputStoreError
    with pytest.raises(OutputStoreError):
        _validate_output_url("https://example.com/output.png")

def test_fashn_max_maps_performance_to_fast(monkeypatch):
    import app.config as config
    from app.providers.fashn import FashnProvider
    monkeypatch.setattr(config, "FASHN_API_KEY", "test-only")
    monkeypatch.setattr(config, "FASHN_MODEL", "tryon-max")
    payload = FashnProvider().build_request(body(mode="performance"))
    assert payload["inputs"]["generation_mode"] == "fast"


def test_job_survives_in_memory_cache_clear_and_has_event_history(monkeypatch):
    import app.main as main
    from app import job_repository
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    created = create()
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    # Clearing legacy compatibility caches must not affect durable reads.
    main.jobs.clear(); main.idempotency.clear()
    fetched = client.get(f"/v1/generation-jobs/{job_id}", headers=auth())
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "running"
    diagnostics = client.get(f"/v1/generation-jobs/{job_id}/events", headers=auth())
    assert diagnostics.status_code == 200
    assert [e["event_type"] for e in diagnostics.json()["events"]] == ["JOB_CREATED", "PROVIDER_SUBMITTED"]
    assert diagnostics.json()["execution"]["status"] == "running"


def test_idempotency_persists_in_sqlite_after_cache_clear(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    headers = {**auth(), "Idempotency-Key": "durable-key-001"}
    first = client.post("/v1/generation-jobs", headers=headers, json=body()).json()
    main.jobs.clear(); main.idempotency.clear()
    second = client.post("/v1/generation-jobs", headers=headers, json=body()).json()
    assert second["job_id"] == first["job_id"]


def test_job_events_endpoint_is_workspace_scoped(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    job_id = create().json()["job_id"]
    assert client.get(f"/v1/generation-jobs/{job_id}/events", headers=auth("token-user-b")).status_code == 404


def test_generation_create_commits_pending_outbox_before_worker(monkeypatch):
    import app.main as main
    from app import job_repository
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    response = client.post("/v1/generation-jobs", headers=auth(), json=body())
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    counts = job_repository.outbox_counts()
    assert counts.get("pending", 0) == 1


def test_worker_dispatch_completes_outbox_and_job(monkeypatch):
    import asyncio
    import app.main as main
    from app import job_repository
    from app.worker import process_one
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    response = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = response.json()["job_id"]
    assert asyncio.run(process_one()) is True
    job = job_repository.get_job(job_id)
    assert job["status"] == "running"
    assert job["provider_request_id"]
    assert job_repository.outbox_counts().get("processed", 0) == 1


def test_worker_dispatch_failure_is_not_automatically_retried(monkeypatch):
    import asyncio
    import app.main as main
    from app import job_repository
    from app.worker import process_one
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    class UncertainProvider:
        name = "mock"
        model = "mock-tryon"
        async def start(self, payload):
            raise TimeoutError("simulated uncertain timeout")
    monkeypatch.setattr(main, "get_provider", lambda: UncertainProvider())
    response = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = response.json()["job_id"]
    assert asyncio.run(process_one()) is True
    job = job_repository.get_job(job_id)
    assert job["status"] == "queued"
    assert job["error_code"] == "PROVIDER_START_UNKNOWN"
    assert job_repository.outbox_counts().get("needs_reconciliation", 0) == 1
    assert asyncio.run(process_one()) is False


def test_expired_worker_lease_is_quarantined_not_replayed(monkeypatch):
    import app.main as main
    from app import job_repository
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    response = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = response.json()["job_id"]
    claimed = job_repository.claim_next_outbox("worker-a", lease_seconds=90)
    assert claimed is not None
    with job_repository._connect() as conn:
        conn.execute("UPDATE generation_outbox SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE event_id=?", (claimed["event_id"],))
    assert job_repository.claim_next_outbox("worker-b", lease_seconds=90) is None
    job = job_repository.get_job(job_id)
    assert job["error_code"] == "PROVIDER_START_UNKNOWN"
    diagnostics = job_repository.diagnostics(job_id)
    assert diagnostics["outbox"]["status"] == "needs_reconciliation"
    assert diagnostics["execution"]["status"] == "unknown"


def test_t13_job_and_outbox_insert_rollback_together(monkeypatch):
    import app.main as main
    from app import job_repository
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    job_repository.initialize()
    with job_repository._connect() as conn:
        conn.execute("""CREATE TRIGGER force_outbox_insert_failure
            BEFORE INSERT ON generation_outbox
            BEGIN SELECT RAISE(ABORT, 'simulated outbox write failure'); END;""")
    response = client.post("/v1/generation-jobs", headers=auth(), json=body())
    assert response.status_code == 503
    with job_repository._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM generation_jobs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM generation_idempotency").fetchone()[0] == 0
    with job_repository._connect() as conn:
        conn.execute("DROP TRIGGER force_outbox_insert_failure")


def test_t14_output_persistence_failure_keeps_job_pending_then_recovers(monkeypatch, tmp_path):
    import app.main as main
    from app.output_store import OutputStoreError
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "fashn")

    class FakeProvider:
        name = "fashn"
        model = "tryon-v1.6"
        async def start(self, payload):
            return {"request_id": "t14-provider-request"}
        async def status(self, request_id):
            return {"status": "succeeded", "output_url": "https://cdn.fashn.ai/t14.png", "message": None}

    monkeypatch.setattr(main, "get_provider", lambda: FakeProvider())
    attempts = {"count": 0}
    from app import poll_worker
    async def flaky_save(url, job_id, attempt_id):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OutputStoreError("simulated output storage interruption")
        main.config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        key = f"{job_id}.attempt-{attempt_id}.t14.png"
        (main.config.OUTPUT_DIR / key).write_bytes(b"\x89PNG\r\n\x1a\nT14")
        return f"/v1/generation-jobs/{job_id}/output", key

    monkeypatch.setattr(poll_worker, "save_provider_output_artifact", flaky_save)
    created = create()
    job_id = created.json()["job_id"]
    assert created.json()["status"] == "post_processing"
    assert created.json()["error_code"] == "OUTPUT_SAVE_PENDING"
    from app import job_repository
    assert job_repository.get_output(job_id) is None

    # GET is now read-only; advance the durable retry schedule and let the poll worker recover.
    with job_repository._connect() as conn:
        conn.execute("UPDATE generation_poll_tasks SET available_at=? WHERE job_id=?", (job_repository._now(), job_id))
    from app.poll_worker import process_one as process_poll
    import asyncio
    assert asyncio.run(process_poll()) is True
    recovered = client.get(f"/v1/generation-jobs/{job_id}", headers=auth())
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "succeeded"
    assert job_repository.get_output(job_id)["size_bytes"] > 0
    assert attempts["count"] == 2


def test_job_get_is_read_only_and_poll_task_is_durable(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = created.json()["job_id"]
    from app.worker import process_one
    import asyncio
    assert asyncio.run(process_one()) is True
    before = job_repository.diagnostics(job_id)["poll_task"]
    assert before["status"] == "pending"
    # Repeated GET requests must not invoke Provider.status or mutate polling attempts.
    for _ in range(3):
        assert client.get(f"/v1/generation-jobs/{job_id}", headers=auth()).status_code == 200
    after = job_repository.diagnostics(job_id)["poll_task"]
    assert after["attempts"] == before["attempts"]
    assert after["status"] == before["status"]


def test_poll_worker_transitions_to_post_processing_and_succeeds(monkeypatch, tmp_path):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "fashn")
    class FakeProvider:
        name = "fashn"; model = "tryon-v1.6"
        async def start(self, payload): return {"request_id": "poll-success-1"}
        async def status(self, request_id):
            return {"status": "succeeded", "output_url": "https://cdn.fashn.ai/poll.png"}
    monkeypatch.setattr(main, "get_provider", lambda: FakeProvider())
    from app import poll_worker
    async def fake_save(url, job_id, attempt_id):
        main.config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        key = f"{job_id}.attempt-{attempt_id}.poll.png"
        (main.config.OUTPUT_DIR / key).write_bytes(b"\x89PNG\r\n\x1a\nPOLL")
        return f"/v1/generation-jobs/{job_id}/output", key
    monkeypatch.setattr(poll_worker, "save_provider_output_artifact", fake_save)
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    from app.worker import process_one
    from app.poll_worker import process_one as process_poll
    import asyncio
    assert asyncio.run(process_one()) is True
    assert asyncio.run(process_poll()) is True
    job_id = created.json()["job_id"]
    assert job_repository.get_job(job_id)["status"] == "post_processing"
    assert asyncio.run(process_poll()) is True
    assert job_repository.get_job(job_id)["status"] == "succeeded"
    assert job_repository.diagnostics(job_id)["poll_task"]["status"] == "completed"


def test_poll_task_lease_expiry_requeues_safe_status_get(monkeypatch):
    import app.main as main
    from app import job_repository
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = created.json()["job_id"]
    from app.worker import process_one
    import asyncio
    asyncio.run(process_one())
    claimed = job_repository.claim_next_poll_task("poll-worker-a", lease_seconds=60)
    assert claimed and claimed["job_id"] == job_id
    with job_repository._connect() as conn:
        conn.execute("UPDATE generation_poll_tasks SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE task_id=?", (claimed["task_id"],))
    reclaimed = job_repository.claim_next_poll_task("poll-worker-b", lease_seconds=60)
    assert reclaimed and reclaimed["task_id"] == claimed["task_id"]
    assert reclaimed["claimed_by"] == "poll-worker-b"


def _unknown_job(monkeypatch):
    import app.main as main
    from app import job_repository
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    response = client.post("/v1/generation-jobs", headers=auth(), json=body())
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    claimed = job_repository.claim_next_outbox("test-worker", 90)
    assert claimed and claimed["job_id"] == job_id
    job_repository.mark_outbox_unknown(claimed["event_id"], job_id, "simulated timeout", claimed["claimed_by"])
    return job_id


def test_manual_reconciliation_attaches_provider_request_id(monkeypatch):
    from app import job_repository
    job_id = _unknown_job(monkeypatch)
    response = client.post(f"/v1/generation-jobs/{job_id}/reconciliation", headers=auth(), json={
        "action": "attach_request_id", "provider_request_id": "fashn-prediction-123",
        "reason": "Located the accepted prediction in provider request history."
    })
    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["provider_request_id"] == "fashn-prediction-123"
    diag = job_repository.diagnostics(job_id)
    assert diag["execution"]["status"] == "running"
    assert diag["outbox"]["status"] == "processed"
    assert diag["events"][-1]["event_type"] == "MANUAL_RECONCILIATION_REQUEST_ATTACHED"


def test_manual_reconciliation_confirm_not_submitted_creates_new_attempt(monkeypatch):
    from app import job_repository
    job_id = _unknown_job(monkeypatch)
    response = client.post(f"/v1/generation-jobs/{job_id}/reconciliation", headers=auth(), json={
        "action": "confirm_not_submitted",
        "reason": "Verified provider history; no accepted request exists for this job."
    })
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    diag = job_repository.diagnostics(job_id)
    assert diag["execution"]["attempt_no"] == 2
    assert diag["execution"]["status"] == "queued"
    assert diag["outbox"]["status"] == "pending"
    assert diag["events"][-1]["event_type"] == "MANUAL_RECONCILIATION_CONFIRMED_NOT_SUBMITTED"


def test_manual_reconciliation_is_admin_only(monkeypatch):
    from app.assets.store import add_workspace_member
    job_id = _unknown_job(monkeypatch)
    add_workspace_member("ws-test", "user-b", "viewer")
    response = client.post(f"/v1/generation-jobs/{job_id}/reconciliation", headers=auth("token-user-b"), json={
        "action": "confirm_not_submitted",
        "reason": "Verified provider history; no accepted request exists for this job."
    })
    assert response.status_code == 403


def test_manual_reconciliation_rejects_invalid_action_payload(monkeypatch):
    job_id = _unknown_job(monkeypatch)
    response = client.post(f"/v1/generation-jobs/{job_id}/reconciliation", headers=auth(), json={
        "action": "attach_request_id", "reason": "Provider history was checked carefully."
    })
    assert response.status_code == 422


def test_worker_heartbeat_and_ops_health(monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", ("user-a",))
    from app import job_repository
    job_repository.heartbeat_worker("worker-test", "running", {"poll_seconds": 1})
    response = client.get("/internal/ops/workers", headers=auth())
    assert response.status_code == 200
    data = response.json()
    assert any(item["worker_id"] == "worker-test" and item["healthy"] for item in data["workers"])
    assert client.get("/internal/ops/workers", headers=auth("token-user-b")).status_code == 403


def test_public_health_does_not_expose_operational_topology_or_queue_counts():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "version": "0.7.0"}


def test_fashn_official_media_output_host_is_allowed(monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "FASHN_OUTPUT_HOSTS", ("cdn.fashn.ai", "media.fashn.ai"))
    from app.output_store import _validate_output_url
    assert _validate_output_url("https://media.fashn.ai/example/output.png") is None


def test_provider_capability_registry_exposes_verification_and_evidence():
    response = client.get("/v1/engines/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert data["registry_version"] == "2026-11-02.1"
    fashn = [item for item in data["items"] if item["provider_id"] == "fashn"]
    assert len(fashn) == 2
    assert all(item["verification_status"] == "DOCUMENTED" for item in fashn)
    assert all(item["production_eligible"] is False for item in fashn)
    assert all(item["idempotency_support"] == "NOT_DOCUMENTED" for item in fashn)


def test_fashn_production_dispatch_blocked_until_verification(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "fashn")
    monkeypatch.setattr(main.config, "FASHN_MODEL", "tryon-v1.6")
    response = client.post("/v1/generation-jobs", headers=auth(), json=body())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "PROVIDER_NOT_PRODUCTION_READY"


def test_auto_routing_is_disabled_until_po_approval(monkeypatch):
    from app.provider_registry import resolve_routing, ProviderPolicyError
    with pytest.raises(ProviderPolicyError) as exc:
        resolve_routing("AUTO", "fashn", "tryon-v1.6")
    assert exc.value.code == "AUTO_ROUTING_NOT_APPROVED"


def test_provider_registry_ops_is_owner_admin_only(monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", ("user-a",))
    response = client.get("/internal/ops/provider-registry", headers=auth())
    assert response.status_code == 200
    assert response.json()["selected_provider"] == "mock"
    assert client.get("/internal/ops/provider-registry", headers=auth("token-user-b")).status_code == 403


def test_provider_adapter_validation_happens_before_job_creation(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    class InvalidAdapter:
        name = "mock"; model = "mock-tryon"
        def validate_request(self, payload):
            raise ValueError("Both input images are required.")
    monkeypatch.setattr(main, "get_provider", lambda: InvalidAdapter())
    response = client.post("/v1/generation-jobs", headers=auth(), json=body())
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_auto_mode_blocks_job_creation_until_policy_approval(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    monkeypatch.setattr(main.config, "PROVIDER_ROUTING_MODE", "AUTO")
    response = client.post("/v1/generation-jobs", headers=auth(), json=body())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTO_ROUTING_NOT_APPROVED"


def test_poll_retry_backoff_is_exponential_and_bounded(monkeypatch):
    import app.config as config
    from app import poll_worker
    monkeypatch.setattr(config, "POLL_RETRY_BASE_SECONDS", 3.0)
    monkeypatch.setattr(config, "POLL_RETRY_MAX_SECONDS", 10.0)
    monkeypatch.setattr(config, "POLL_RETRY_AFTER_MAX_SECONDS", 20.0)
    assert poll_worker._retry_delay(1) == 3.0
    assert poll_worker._retry_delay(2) == 6.0
    assert poll_worker._retry_delay(3) == 10.0
    assert poll_worker._retry_delay(8) == 10.0
    assert poll_worker._retry_delay(1, 17) == 17.0
    assert poll_worker._retry_delay(1, 1000) == 20.0


def test_fashn_retry_after_header_parser_accepts_seconds_and_rejects_invalid():
    from app.providers.fashn import _retry_after_seconds
    assert _retry_after_seconds("12") == 12.0
    assert _retry_after_seconds("not-a-date") is None
    assert _retry_after_seconds(None) is None


def test_poll_retry_budget_exhaustion_requires_operator_review(monkeypatch):
    import app.main as main
    from app import job_repository, poll_worker
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    monkeypatch.setattr(poll_worker, "MAX_ATTEMPTS", 1)
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = created.json()["job_id"]
    from app.worker import process_one as dispatch_one
    import asyncio
    assert asyncio.run(dispatch_one()) is True
    # First safe status GET returns running; max attempts forces an explicit review state.
    assert asyncio.run(poll_worker.process_one()) is True
    diag = job_repository.diagnostics(job_id)
    assert diag["poll_task"]["status"] == "needs_reconciliation"
    assert job_repository.get_job(job_id)["error_code"] == "PROVIDER_POLL_REQUIRES_REVIEW"


def test_worker_refuses_to_silently_reroute_persisted_job(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    with pytest.raises(RuntimeError, match="does not match"):
        main.get_provider_for_job({"provider": "fashn", "model": "tryon-v1.6"})


def test_manual_attach_request_id_schedules_poll_task(monkeypatch):
    from app import job_repository
    job_id = _unknown_job(monkeypatch)
    response = client.post(f"/v1/generation-jobs/{job_id}/reconciliation", headers=auth(), json={
        "action": "attach_request_id", "provider_request_id": "provider-request-for-poll",
        "reason": "Located this accepted request in the Provider request history."
    })
    assert response.status_code == 200
    assert job_repository.diagnostics(job_id)["poll_task"]["status"] == "pending"


def test_fashn_429_retry_after_header_becomes_bounded_retry_metadata():
    import httpx
    from app.providers.fashn import _raise_poll_http_error
    from app.providers.base import ProviderAdapterError
    request = httpx.Request("GET", "https://api.fashn.ai/v1/status/prediction-id")
    response = httpx.Response(429, headers={"Retry-After": "15"}, request=request)
    error = httpx.HTTPStatusError("rate limited", request=request, response=response)
    with pytest.raises(ProviderAdapterError) as caught:
        _raise_poll_http_error(error)
    assert caught.value.retryable is True
    assert caught.value.retry_after_seconds == 15.0


def test_fashn_non_retryable_poll_http_error_does_not_claim_retry_after():
    import httpx
    from app.providers.fashn import _raise_poll_http_error
    from app.providers.base import ProviderAdapterError
    request = httpx.Request("GET", "https://api.fashn.ai/v1/status/prediction-id")
    response = httpx.Response(404, headers={"Retry-After": "30"}, request=request)
    error = httpx.HTTPStatusError("not found", request=request, response=response)
    with pytest.raises(ProviderAdapterError) as caught:
        _raise_poll_http_error(error)
    assert caught.value.retryable is False
    assert caught.value.retry_after_seconds == 30.0


def test_submission_worker_refuses_provider_config_drift(monkeypatch):
    import app.main as main
    from app import job_repository
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = created.json()["job_id"]
    # Simulate deployment config drift between Job creation and worker pickup.
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "fashn")
    from app.worker import process_one
    import asyncio
    assert asyncio.run(process_one()) is True
    job = job_repository.get_job(job_id)
    assert job["provider"] == "mock"
    assert job["status"] == "queued"
    assert job["error_code"] == "PROVIDER_START_UNKNOWN"
    assert job_repository.diagnostics(job_id)["outbox"]["status"] == "needs_reconciliation"


def test_fashn_status_adapter_uses_retry_after_response_header(monkeypatch):
    import asyncio
    import httpx
    import app.config as config
    import app.providers.fashn as fashn_module
    monkeypatch.setattr(config, "FASHN_API_KEY", "unit-test-key")
    monkeypatch.setattr(config, "FASHN_MODEL", "tryon-v1.6")
    async def handler(request):
        assert request.url.path == "/v1/status/prediction-123"
        return httpx.Response(200, headers={"Retry-After": "11"}, json={"status": "processing"})
    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)
    monkeypatch.setattr(fashn_module.httpx, "AsyncClient", client_factory)
    result = asyncio.run(fashn_module.FashnProvider().status("prediction-123"))
    assert result["status"] == "running"
    assert result["retry_after_seconds"] == 11.0


def test_output_store_writes_complete_file_with_atomic_replace(monkeypatch, tmp_path):
    import asyncio
    import httpx
    import app.output_store as output_store
    import app.config as config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "FASHN_OUTPUT_HOSTS", ("cdn.fashn.ai",))
    image_bytes = b"\x89PNG\r\n\x1a\natomic-image-data"
    class FakeResponse:
        headers = {"content-type": "image/png", "content-length": str(len(image_bytes))}
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        def raise_for_status(self): return None
        async def aiter_bytes(self):
            yield image_bytes
    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        def stream(self, *args, **kwargs): return FakeResponse()
    monkeypatch.setattr(output_store.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(output_store.save_provider_output("https://cdn.fashn.ai/output.png", "job-atomic"))
    assert result == "/v1/generation-jobs/job-atomic/output"
    artifacts = list(tmp_path.glob("job-atomic.attempt-*.png"))
    assert len(artifacts) == 1
    assert artifacts[0].read_bytes() == image_bytes
    assert list(tmp_path.glob("*.tmp")) == []


def test_poll_task_ops_list_is_workspace_owner_admin_only(monkeypatch):
    import app.main as main
    from app import poll_worker, job_repository
    from app.assets.store import add_workspace_member
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    monkeypatch.setattr(poll_worker, "MAX_ATTEMPTS", 1)
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = created.json()["job_id"]
    from app.worker import process_one as dispatch_one
    import asyncio
    asyncio.run(dispatch_one())
    asyncio.run(poll_worker.process_one())
    add_workspace_member("ws-test", "user-b", "viewer")
    response = client.get("/internal/ops/poll-tasks?workspace_id=ws-test&status=needs_reconciliation", headers=auth())
    assert response.status_code == 200
    assert response.json()["items"][0]["job_id"] == job_id
    assert client.get("/internal/ops/poll-tasks?workspace_id=ws-test", headers=auth("token-user-b")).status_code == 403
    assert client.get("/internal/ops/poll-tasks?workspace_id=ws-not-owned", headers=auth()).status_code == 404


def test_admin_can_retry_poll_task_without_resubmitting_provider_post(monkeypatch):
    import app.main as main
    from app import poll_worker, job_repository
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    monkeypatch.setattr(poll_worker, "MAX_ATTEMPTS", 1)
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = created.json()["job_id"]
    from app.worker import process_one as dispatch_one
    import asyncio
    asyncio.run(dispatch_one())
    asyncio.run(poll_worker.process_one())
    diag_before = job_repository.diagnostics(job_id)
    outbox_event_id = diag_before["outbox"]["event_id"]
    outbox_attempts = diag_before["outbox"]["attempts"]
    task_id = diag_before["poll_task"]["task_id"]
    response = client.post(f"/internal/ops/poll-tasks/{task_id}/retry", headers=auth(), json={
        "workspace_id": "ws-test", "reason": "Operator reviewed the provider status and authorizes another safe GET poll."
    })
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["attempts"] == 0
    diag_after = job_repository.diagnostics(job_id)
    assert diag_after["outbox"]["event_id"] == outbox_event_id
    assert diag_after["outbox"]["attempts"] == outbox_attempts
    assert diag_after["events"][-1]["event_type"] == "POLL_TASK_MANUALLY_REQUEUED"


def test_poll_task_retry_rejects_tasks_not_awaiting_review(monkeypatch):
    import app.main as main
    from app import job_repository
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = created.json()["job_id"]
    from app.worker import process_one as dispatch_one
    import asyncio
    asyncio.run(dispatch_one())
    task_id = job_repository.diagnostics(job_id)["poll_task"]["task_id"]
    response = client.post(f"/internal/ops/poll-tasks/{task_id}/retry", headers=auth(), json={
        "workspace_id": "ws-test", "reason": "This retry request should be rejected because the task is pending."
    })
    assert response.status_code == 409


def test_admin_can_resume_output_persistence_phase(monkeypatch):
    import asyncio
    import app.main as main
    from app import job_repository, poll_worker
    from app.output_store import OutputStoreError
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "fashn")
    monkeypatch.setattr(poll_worker, "MAX_ATTEMPTS", 1)
    class FakeProvider:
        name = "fashn"; model = "tryon-v1.6"
        async def start(self, payload): return {"request_id": "persist-review-request"}
        async def status(self, request_id):
            return {"status": "succeeded", "output_url": "https://cdn.fashn.ai/persist-review.png"}
    monkeypatch.setattr(main, "get_provider", lambda: FakeProvider())
    async def fail_save(url, job_id):
        raise OutputStoreError("simulated output persistence failure")
    monkeypatch.setattr(main, "save_provider_output", fail_save)
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = created.json()["job_id"]
    from app.worker import process_one as dispatch_one
    assert asyncio.run(dispatch_one()) is True
    assert asyncio.run(poll_worker.process_one()) is True  # status -> persist_output
    assert asyncio.run(poll_worker.process_one()) is True  # exhaust output retry budget
    before = job_repository.diagnostics(job_id)
    assert before["poll_task"]["status"] == "needs_reconciliation"
    assert before["poll_task"]["phase"] == "persist_output"
    task_id = before["poll_task"]["task_id"]
    response = client.post(f"/internal/ops/poll-tasks/{task_id}/retry", headers=auth(), json={
        "workspace_id": "ws-test", "reason": "Output storage has recovered; resume only the safe output download phase."
    })
    assert response.status_code == 200
    assert response.json()["phase"] == "persist_output"
    assert response.json()["status"] == "pending"
    assert job_repository.get_job(job_id)["status"] == "post_processing"



def test_ops_metrics_and_alerts_are_owner_admin_only(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "OPS_ADMIN_USER_IDS", ("user-a",))
    from app import job_repository
    metrics = client.get("/internal/ops/metrics", headers=auth())
    assert metrics.status_code == 200
    assert "acs_outbox_tasks" in metrics.text
    assert client.get("/internal/ops/metrics", headers=auth("token-user-b")).status_code == 403
    alerts = client.get("/internal/ops/alerts", headers=auth())
    assert alerts.status_code == 200
    assert "snapshot" in alerts.json()


def test_monitor_creates_and_resolves_worker_alerts():
    from app import job_repository
    from app.config import REQUIRED_WORKER_TYPES
    job_repository.evaluate_operational_alerts(required_worker_types=("outbox", "provider_poll"),
                                               worker_stale_seconds=30, queue_age_seconds=120)
    active = job_repository.list_operational_alerts(status="active")
    assert {a["fingerprint"] for a in active} >= {"worker:outbox:stale", "worker:provider_poll:stale"}
    job_repository.heartbeat_worker("outbox-test", "running", {"worker_type": "outbox"})
    job_repository.heartbeat_worker("poll-test", "running", {"worker_type": "provider_poll"})
    job_repository.evaluate_operational_alerts(required_worker_types=("outbox", "provider_poll"),
                                               worker_stale_seconds=30, queue_age_seconds=120)
    active = job_repository.list_operational_alerts(status="active")
    assert not {"worker:outbox:stale", "worker:provider_poll:stale"} & {a["fingerprint"] for a in active}
    resolved = job_repository.list_operational_alerts(status="resolved")
    assert {a["fingerprint"] for a in resolved} >= {"worker:outbox:stale", "worker:provider_poll:stale"}


def test_monitor_detects_queue_age_and_reconciliation_backlog(monkeypatch):
    import app.main as main
    from app import job_repository
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    response = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = response.json()["job_id"]
    response2 = client.post("/v1/generation-jobs", headers=auth(), json=body(category="bottoms"))
    pending_job_id = response2.json()["job_id"]
    with job_repository._connect() as conn:
        old = "2000-01-01T00:00:00+00:00"
        conn.execute("UPDATE generation_outbox SET created_at=?,status='needs_reconciliation' WHERE job_id=?", (old, job_id))
        conn.execute("UPDATE generation_outbox SET created_at=?,available_at=? WHERE job_id=?", (old, old, pending_job_id))
    job_repository.evaluate_operational_alerts(required_worker_types=(), worker_stale_seconds=30, queue_age_seconds=10)
    active = {a["fingerprint"] for a in job_repository.list_operational_alerts(status="active")}
    assert "queue:outbox:age" in active
    assert "outbox:needs_reconciliation" in active


def test_monitor_webhook_delivery_uses_https_and_sanitized_payload(monkeypatch):
    import asyncio
    import app.monitor_worker as monitor
    from app import job_repository, config
    monkeypatch.setattr(config, "OPS_ALERT_WEBHOOK_URL", "https://alerts.example.test/hook")
    monkeypatch.setattr(config, "OPS_ALERT_WEBHOOK_TOKEN", "secret-token")
    monkeypatch.setattr(config, "REQUIRED_WORKER_TYPES", ("outbox",))
    monitor.evaluate_once()
    captured = {}
    class FakeResponse:
        status_code = 204
    class FakeClient:
        def __init__(self, **kwargs):
            captured["timeout"] = kwargs["timeout"]
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, url, json, headers):
            captured.update({"url": url, "payload": json, "headers": headers})
            return FakeResponse()
    monkeypatch.setattr(monitor.httpx, "AsyncClient", FakeClient)
    assert asyncio.run(monitor.dispatch_one()) is True
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert captured["payload"]["event"] == "ai_creator_studio.operational_alert"
    assert "user_id" not in str(captured["payload"])
    assert "payload" not in str(captured["payload"])
    with job_repository._connect() as conn:
        row = conn.execute("SELECT status FROM generation_ops_alert_deliveries ORDER BY created_at LIMIT 1").fetchone()
    assert row["status"] == "delivered"


def test_monitor_rejects_non_https_webhook(monkeypatch):
    import app.monitor_worker as monitor
    from app import config
    monkeypatch.setattr(config, "OPS_ALERT_WEBHOOK_URL", "http://alerts.example.test/hook")
    with pytest.raises(RuntimeError):
        monitor.evaluate_once()


def test_monitor_uses_newest_heartbeat_per_worker_type():
    from app import job_repository
    job_repository.heartbeat_worker("old-outbox", "running", {"worker_type": "outbox"})
    with job_repository._connect() as conn:
        conn.execute("UPDATE generation_worker_heartbeats SET last_seen_at='2000-01-01T00:00:00+00:00' WHERE worker_id='old-outbox'")
    job_repository.heartbeat_worker("new-outbox", "running", {"worker_type": "outbox"})
    job_repository.heartbeat_worker("new-poll", "running", {"worker_type": "provider_poll"})
    job_repository.evaluate_operational_alerts(required_worker_types=("outbox", "provider_poll"),
                                               worker_stale_seconds=30, queue_age_seconds=120)
    active = {a["fingerprint"] for a in job_repository.list_operational_alerts(status="active")}
    assert "worker:outbox:stale" not in active
    assert "worker:provider_poll:stale" not in active


def test_alert_webhook_failure_is_retried_then_bounded(monkeypatch):
    from app import job_repository, config
    monkeypatch.setattr(config, "OPS_ALERT_WEBHOOK_URL", "https://alerts.example.test/hook")
    job_repository.evaluate_operational_alerts(required_worker_types=("outbox",), webhook_destination=config.OPS_ALERT_WEBHOOK_URL)
    delivery = job_repository.claim_alert_delivery("ops-test-worker")
    assert delivery is not None
    job_repository.finish_alert_delivery(delivery["delivery_id"], worker_id="ops-test-worker", delivered=False, error="timeout",
                                         retry_delay_seconds=1, max_attempts=8)
    with job_repository._connect() as conn:
        row = conn.execute("SELECT status,attempts FROM generation_ops_alert_deliveries WHERE delivery_id=?", (delivery["delivery_id"],)).fetchone()
        conn.execute("UPDATE generation_ops_alert_deliveries SET available_at='2000-01-01T00:00:00+00:00' WHERE delivery_id=?", (delivery["delivery_id"],))
    assert row["status"] == "pending"
    assert row["attempts"] == 1
    for _ in range(7):
        claimed = job_repository.claim_alert_delivery("ops-test-worker")
        assert claimed is not None
        job_repository.finish_alert_delivery(claimed["delivery_id"], worker_id="ops-test-worker", delivered=False, error="timeout",
                                             retry_delay_seconds=1, max_attempts=8)
        with job_repository._connect() as conn:
            conn.execute("UPDATE generation_ops_alert_deliveries SET available_at='2000-01-01T00:00:00+00:00' WHERE delivery_id=?", (delivery["delivery_id"],))
    with job_repository._connect() as conn:
        row = conn.execute("SELECT status,attempts FROM generation_ops_alert_deliveries WHERE delivery_id=?", (delivery["delivery_id"],)).fetchone()
    assert row["status"] == "failed"
    assert row["attempts"] == 8



def test_poll_output_lease_renewal_is_fenced_and_never_resurrects_expired_lease(monkeypatch):
    import app.main as main
    from app import job_repository
    from app.repositories.poll import SQLitePollRepository
    import asyncio

    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    job_id = created.json()["job_id"]
    from app.worker import process_one
    assert asyncio.run(process_one()) is True

    repository = SQLitePollRepository()
    task = repository.claim_next_poll_task("lease-owner", lease_seconds=60)
    assert task and task["job_id"] == job_id
    assert repository.mark_provider_succeeded_for_poll(
        task["task_id"], "lease-owner", job_id, "https://cdn.fashn.ai/lease.png"
    ) is True
    output_task = repository.claim_next_poll_task("lease-owner", lease_seconds=60)
    assert output_task and output_task["task_id"] == task["task_id"]
    assert output_task["phase"] == "persist_output"

    assert repository.renew_poll_task_lease(output_task["task_id"], "wrong-owner", 120) is False
    assert repository.renew_poll_task_lease(output_task["task_id"], "lease-owner", 120) is True
    with job_repository._connect() as conn:
        row = conn.execute(
            "SELECT lease_expires_at FROM generation_poll_tasks WHERE task_id=?",
            (task["task_id"],),
        ).fetchone()
        assert row["lease_expires_at"]
        conn.execute(
            "UPDATE generation_poll_tasks SET lease_expires_at=? WHERE task_id=?",
            ("2000-01-01T00:00:00+00:00", output_task["task_id"]),
        )
    assert repository.renew_poll_task_lease(output_task["task_id"], "lease-owner", 120) is False


def test_output_download_renews_lease_until_download_completes(monkeypatch):
    import asyncio
    from app import poll_worker

    monkeypatch.setattr(poll_worker, "LEASE_SECONDS", 1)
    renewals = {"count": 0}

    class LiveLeaseRepository:
        def renew_poll_task_lease(self, task_id, worker_id, lease_seconds):
            renewals["count"] += 1
            assert (task_id, worker_id, lease_seconds) == ("task-live", "worker-live", 1)
            return True

    async def slow_download(url, job_id, attempt_id):
        await asyncio.sleep(0.4)
        return "/v1/generation-jobs/job-live/output", "job-live.attempt-task-live-1.artifact.png"

    monkeypatch.setattr(poll_worker, "save_provider_output_artifact", slow_download)

    async def scenario():
        result = await poll_worker._save_output_with_live_lease(
            "https://cdn.fashn.ai/slow.png", "job-live", "task-live-1",
            "task-live", "worker-live", LiveLeaseRepository(),
        )
        assert result[1].endswith("artifact.png")

    asyncio.run(scenario())
    assert renewals["count"] >= 1


def test_output_download_is_cancelled_when_lease_renewal_is_rejected(monkeypatch):
    import asyncio
    from app import poll_worker
    from app.job_state import InvalidJobTransition

    monkeypatch.setattr(poll_worker, "LEASE_SECONDS", 1)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class LostLeaseRepository:
        def renew_poll_task_lease(self, task_id, worker_id, lease_seconds):
            return False

    async def blocked_download(url, job_id, attempt_id):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(poll_worker, "save_provider_output_artifact", blocked_download)

    async def scenario():
        operation = asyncio.create_task(poll_worker._save_output_with_live_lease(
            "https://cdn.fashn.ai/slow.png", "job-lease", "attempt-1",
            "task-1", "worker-1", LostLeaseRepository(),
        ))
        await started.wait()
        with pytest.raises(InvalidJobTransition, match="lease was lost"):
            await operation
        assert cancelled.is_set()

    asyncio.run(scenario())

def test_attempt_scoped_outputs_never_replace_each_other_and_cleanup_protects_committed(monkeypatch, tmp_path):
    import asyncio
    import os
    import time
    import app.output_store as output_store
    import app.config as config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "FASHN_OUTPUT_HOSTS", ("cdn.fashn.ai",))

    payloads = [b"\x89PNG\r\n\x1a\nworker-a", b"\x89PNG\r\n\x1a\nworker-b"]
    calls = {"count": 0}
    class FakeResponse:
        headers = {"content-type": "image/png"}
        def __init__(self, data): self.data = data
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        def raise_for_status(self): return None
        async def aiter_bytes(self): yield self.data
    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        def stream(self, *args, **kwargs):
            data = payloads[calls["count"]]
            calls["count"] += 1
            return FakeResponse(data)
    monkeypatch.setattr(output_store.httpx, "AsyncClient", FakeClient)

    first_route, first_key = asyncio.run(output_store.save_provider_output_artifact(
        "https://cdn.fashn.ai/out.png", "job-race", "task-1-1"))
    second_route, second_key = asyncio.run(output_store.save_provider_output_artifact(
        "https://cdn.fashn.ai/out.png", "job-race", "task-1-2"))
    assert first_route == second_route == "/v1/generation-jobs/job-race/output"
    assert first_key != second_key
    assert output_store.get_stored_output("job-race", first_key).read_bytes() == payloads[0]
    assert output_store.get_stored_output("job-race", second_key).read_bytes() == payloads[1]

    stale_key = "job-race.attempt-old.stale.png"
    stale_path = tmp_path / stale_key
    stale_path.write_bytes(b"orphan")
    old = time.time() - 7200
    os.utime(stale_path, (old, old))
    os.utime(tmp_path / first_key, (old, old))  # simulate a crash after file write, before DB commit
    # Committed artifacts are retained; only unreferenced, old attempt files are candidates.
    candidates = output_store.cleanup_orphaned_attempt_outputs(
        {second_key}, older_than_seconds=3600, now=time.time(), apply=False)
    assert stale_key in candidates and first_key in candidates
    assert second_key not in candidates
    assert stale_path.exists()  # dry-run does not mutate
    deleted = output_store.cleanup_orphaned_attempt_outputs(
        {second_key}, older_than_seconds=3600, now=time.time(), apply=True)
    assert stale_key in deleted and first_key in deleted
    assert not stale_path.exists()
    assert (tmp_path / second_key).exists()


def test_stored_output_resolver_requires_job_scoped_plain_attempt_key(monkeypatch, tmp_path):
    import app.config as config
    from app.output_store import get_stored_output
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    valid = "job-safe.attempt-task-2-1.artifact.png"
    (tmp_path / valid).write_bytes(b"image")
    assert get_stored_output("job-safe", valid) == tmp_path / valid
    assert get_stored_output("job-safe", "../" + valid) is None
    assert get_stored_output("other-job", valid) is None
    assert get_stored_output("job-safe", "job-safe.png") is None


def test_job_execution_and_output_history_endpoints_are_workspace_scoped(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    created = client.post("/v1/generation-jobs", headers=auth(), json=body())
    assert created.status_code == 202, created.text
    job_id = created.json()["job_id"]
    empty_outputs = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=auth())
    assert empty_outputs.status_code == 200 and empty_outputs.json()["data"] == []
    with job_repository._connect() as db:
        db.execute("UPDATE generation_jobs SET status='succeeded' WHERE job_id=?", (job_id,))
        db.execute("INSERT INTO generation_executions(execution_id,job_id,attempt_no,status,provider,started_at,metadata_json) VALUES(?,?,?,?,?,?,?)",
                   ("exec_retry_test", job_id, 2, "failed", "mock", "2026-01-01T00:00:00+00:00", '{"internal":"not exposed"}'))
        db.execute("INSERT INTO generation_outputs(output_id,job_id,storage_key,media_type,size_bytes,created_at) VALUES(?,?,?,?,?,?)",
                   ("out_test", job_id, "private-output.png", "image/png", 123, "2026-01-01T00:00:00+00:00"))
    executions = client.get(f"/v1/generation-jobs/{job_id}/executions?limit=1", headers=auth())
    assert executions.status_code == 200
    assert len(executions.json()["data"]) == 1 and executions.json()["meta"]["has_more"] is True
    assert executions.json()["data"][0]["attempt_number"] == 2
    cursor = executions.json()["meta"]["next_cursor"]
    next_page = client.get(f"/v1/generation-jobs/{job_id}/executions?limit=1&cursor={cursor}", headers=auth())
    assert next_page.status_code == 200 and next_page.json()["data"][0]["attempt_number"] == 1
    assert next_page.json()["meta"]["has_more"] is False
    invalid_cursor = client.get(f"/v1/generation-jobs/{job_id}/executions?cursor=invalid", headers=auth())
    assert invalid_cursor.status_code == 422
    outputs = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=auth())
    assert outputs.status_code == 200
    assert len(outputs.json()["data"]) == 1
    assert outputs.json()["data"][0]["mime_type"] == "image/png"
    assert "storage_key" not in outputs.json()["data"][0]
    assert client.get(f"/v1/generation-jobs/{job_id}/executions", headers=auth("token-user-b")).status_code == 404
