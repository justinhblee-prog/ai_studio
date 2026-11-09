"""SQLite single-host concurrency regression tests; not PostgreSQL evidence."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from app import config, job_repository


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "concurrency.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    job_repository.initialize()


def _job(job_id: str) -> dict:
    return {
        "job_id": job_id, "workspace_id": "ws-concurrency", "owner_id": "user-concurrency",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "sha256-test", "payload": {"model_image_url": "https://example.com/model.png"},
    }


def _race(call, workers: int = 12):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda index: call(f"worker-{index}"), range(workers)))


def test_concurrent_outbox_claim_has_single_winner(isolated_db):
    job_repository.create_job(_job("job-outbox-race"))
    results = _race(lambda worker: job_repository.claim_next_outbox(worker, 60))
    winners = [item for item in results if item is not None]
    assert len(winners) == 1
    assert winners[0]["claimed_by"].startswith("worker-")


def test_concurrent_poll_claim_has_single_winner(isolated_db):
    job_repository.create_job(_job("job-poll-race"))
    claimed = job_repository.claim_next_outbox("dispatcher", 60)
    assert claimed is not None
    job_repository.complete_outbox_submission(claimed["event_id"], "job-poll-race", "provider-request-1", claimed["claimed_by"])
    results = _race(lambda worker: job_repository.claim_next_poll_task(worker, 60))
    winners = [item for item in results if item is not None]
    assert len(winners) == 1
    assert winners[0]["job_id"] == "job-poll-race"


def test_concurrent_alert_delivery_claim_has_single_winner(isolated_db):
    now = datetime.now(timezone.utc).isoformat()
    with job_repository._connect() as conn:
        conn.execute("""INSERT INTO generation_ops_alerts
            (alert_id,fingerprint,alert_type,severity,status,title,details_json,first_seen_at,last_seen_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            ("alert-race", "fingerprint-race", "queue_age", "warning", "active", "Queue delayed", "{}", now, now))
        conn.execute("""INSERT INTO generation_ops_alert_deliveries
            (delivery_id,alert_id,destination,status,available_at,created_at)
            VALUES(?,?,?,?,?,?)""",
            ("delivery-race", "alert-race", "https://example.com/hook", "pending", now, now))
    results = _race(lambda worker: job_repository.claim_alert_delivery(f"ops-worker-{worker}"))
    winners = [item for item in results if item is not None]
    assert len(winners) == 1
    assert winners[0]["delivery_id"] == "delivery-race"


def test_idempotency_key_is_workspace_scoped_and_replay_is_stable(isolated_db):
    first, created = job_repository.create_job(_job("job-idem-a"), "same-key")
    replay, replay_created = job_repository.create_job(_job("job-idem-b"), "same-key")
    other_workspace_job = _job("job-idem-c")
    other_workspace_job["workspace_id"] = "ws-other"
    other, other_created = job_repository.create_job(other_workspace_job, "same-key")
    assert created is True
    assert replay_created is False
    assert replay["job_id"] == first["job_id"]
    assert other_created is True
    assert other["job_id"] != first["job_id"]


def test_create_job_rolls_back_all_records_when_outbox_insert_fails(isolated_db, monkeypatch):
    from contextlib import contextmanager
    from app import storage as storage_module
    original_get_storage = storage_module.get_storage
    base_storage = original_get_storage()

    class FailingConnection:
        def __init__(self, conn): self.conn = conn
        def execute(self, sql, params=()):
            if "INSERT INTO generation_outbox" in sql:
                raise RuntimeError("simulated outbox write failure")
            return self.conn.execute(sql, params)
        def __getattr__(self, name): return getattr(self.conn, name)

    class FailingStorage:
        def begin_write(self, connection): return base_storage.begin_write(connection.conn)
        @contextmanager
        def transaction(self, database_path):
            with base_storage.transaction(database_path) as conn:
                yield FailingConnection(conn)

    monkeypatch.setattr(storage_module, "get_storage", lambda: FailingStorage())
    with pytest.raises(RuntimeError, match="simulated outbox"):
        job_repository.create_job(_job("job-rollback"), "rollback-key")
    monkeypatch.setattr(storage_module, "get_storage", original_get_storage)
    assert job_repository.get_job("job-rollback") is None
    assert job_repository.get_idempotent_job("ws-concurrency", "rollback-key") is None


def _claimed_output_task(job_id: str):
    job_repository.create_job(_job(job_id))
    outbox = job_repository.claim_next_outbox("dispatcher", 60)
    assert outbox is not None
    job_repository.complete_outbox_submission(outbox["event_id"], job_id, "provider-request-atomic", outbox["claimed_by"])
    with job_repository._connect() as conn:
        task = conn.execute(
            "SELECT task_id FROM generation_poll_tasks WHERE job_id=?", (job_id,)
        ).fetchone()
    assert task is not None
    first_claim = job_repository.claim_next_poll_task("poller", 60)
    assert first_claim is not None and first_claim["task_id"] == task["task_id"]
    assert job_repository.mark_provider_succeeded_for_poll(
        task["task_id"], "poller", job_id, "https://provider.example/output.png"
    ) is True
    claimed = job_repository.claim_next_poll_task("poller", 60)
    assert claimed is not None and claimed["task_id"] == task["task_id"]
    return task["task_id"]


def test_output_success_finalization_is_one_atomic_unit(isolated_db):
    task_id = _claimed_output_task("job-output-atomic")
    assert job_repository.get_job("job-output-atomic")["status"] == "post_processing"
    assert job_repository.finalize_output_success(
        task_id, "poller", "job-output-atomic", storage_key="job-output-atomic.png",
        media_type="image/png", size_bytes=128, output_url="/v1/generation-jobs/job-output-atomic/output",
    ) is True
    assert job_repository.get_job("job-output-atomic")["status"] == "succeeded"
    assert job_repository.get_output("job-output-atomic")["size_bytes"] == 128
    with job_repository._connect() as conn:
        task = conn.execute("SELECT status,claimed_by FROM generation_poll_tasks WHERE task_id=?", (task_id,)).fetchone()
        execution = conn.execute("SELECT status,finished_at FROM generation_executions WHERE job_id=?", ("job-output-atomic",)).fetchone()
    assert task["status"] == "completed" and task["claimed_by"] is None
    assert execution["status"] == "succeeded" and execution["finished_at"] is not None
    assert job_repository.list_events("job-output-atomic")[-1]["event_type"] == "OUTPUT_PERSISTED"


def test_output_success_failure_rolls_back_output_and_job_together(isolated_db):
    task_id = _claimed_output_task("job-output-rollback")
    with job_repository._connect() as conn:
        conn.execute("""CREATE TRIGGER fail_job_success BEFORE UPDATE OF status ON generation_jobs
            WHEN NEW.status='succeeded' BEGIN SELECT RAISE(ABORT,'simulated job status write failure'); END""")
    with pytest.raises(Exception, match="simulated job status write failure"):
        job_repository.finalize_output_success(
            task_id, "poller", "job-output-rollback", storage_key="job-output-rollback.png",
            media_type="image/png", size_bytes=128, output_url="/v1/generation-jobs/job-output-rollback/output",
        )
    assert job_repository.get_job("job-output-rollback")["status"] == "post_processing"
    assert job_repository.get_output("job-output-rollback") is None
    with job_repository._connect() as conn:
        task = conn.execute("SELECT status,claimed_by FROM generation_poll_tasks WHERE task_id=?", (task_id,)).fetchone()
        conn.execute("DROP TRIGGER fail_job_success")
    assert task["status"] == "processing" and task["claimed_by"] == "poller"


def test_concurrent_idempotent_job_creation_has_one_canonical_job(isolated_db):
    def create(index):
        return job_repository.create_job(_job(f"job-idem-race-{index}"), "same-concurrent-key")

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(create, range(12)))

    jobs = [item[0] for item in results]
    created_flags = [item[1] for item in results]
    canonical_ids = {item["job_id"] for item in jobs}
    assert len(canonical_ids) == 1
    assert sum(created_flags) == 1
    with job_repository._connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM generation_jobs WHERE workspace_id=?",
            ("ws-concurrency",),
        ).fetchone()["n"]
        idem_count = conn.execute(
            "SELECT COUNT(*) AS n FROM generation_idempotency WHERE workspace_id=? AND idempotency_key=?",
            ("ws-concurrency", "same-concurrent-key"),
        ).fetchone()["n"]
    assert count == 1
    assert idem_count == 1


def _force_poll_lease_expired(task_id: str) -> None:
    with job_repository._connect() as conn:
        conn.execute(
            "UPDATE generation_poll_tasks SET lease_expires_at=? WHERE task_id=?",
            ("2000-01-01T00:00:00+00:00", task_id),
        )


def _claimed_status_task(job_id: str) -> str:
    job_repository.create_job(_job(job_id))
    outbox = job_repository.claim_next_outbox("dispatcher", 60)
    assert outbox is not None
    job_repository.complete_outbox_submission(outbox["event_id"], job_id, "provider-lease-fence", outbox["claimed_by"])
    task = job_repository.claim_next_poll_task("poller-old", 60)
    assert task is not None
    return task["task_id"]


def test_expired_poll_lease_cannot_complete_task(isolated_db):
    task_id = _claimed_status_task("job-expired-complete")
    _force_poll_lease_expired(task_id)
    assert job_repository.complete_poll_task(task_id, "poller-old") is False
    with job_repository._connect() as conn:
        task = conn.execute("SELECT status,claimed_by FROM generation_poll_tasks WHERE task_id=?", (task_id,)).fetchone()
    assert task["status"] == "processing" and task["claimed_by"] == "poller-old"


def test_expired_poll_lease_cannot_handoff_provider_success(isolated_db):
    task_id = _claimed_status_task("job-expired-provider-handoff")
    _force_poll_lease_expired(task_id)
    assert job_repository.mark_provider_succeeded_for_poll(
        task_id, "poller-old", "job-expired-provider-handoff", "https://provider.example/output.png"
    ) is False
    assert job_repository.get_job("job-expired-provider-handoff")["status"] == "running"


@pytest.mark.parametrize("output_url", [
    "", "http://provider.example/output.png", "https://user:secret@provider.example/output.png",
    "https://provider.example/output with space.png", "https://provider.example/" + ("x" * 4100),
])
def test_provider_success_rejects_malformed_output_reference_without_state_change(isolated_db, output_url):
    task_id = _claimed_status_task("job-invalid-provider-reference")
    with pytest.raises(ValueError):
        job_repository.mark_provider_succeeded_for_poll(
            task_id, "poller", "job-invalid-provider-reference", output_url
        )
    assert job_repository.get_job("job-invalid-provider-reference")["status"] == "running"


@pytest.mark.parametrize("overrides", [
    {"storage_key": "../escape.png"},
    {"storage_key": "output.jpg", "media_type": "image/png"},
    {"media_type": "image/gif"},
    {"size_bytes": 0},
    {"size_bytes": config.MAX_OUTPUT_BYTES + 1},
    {"output_url": "https://public.example/output.png"},
    {"output_url": "/v1/generation-jobs/another-job/output"},
])
def test_output_finalization_rejects_invalid_private_output_contract(isolated_db, overrides):
    task_id = _claimed_output_task("job-invalid-final-output")
    arguments = {
        "storage_key": "job-invalid-final-output.png", "media_type": "image/png",
        "size_bytes": 128, "output_url": "/v1/generation-jobs/job-invalid-final-output/output",
    }
    arguments.update(overrides)
    with pytest.raises(ValueError):
        job_repository.finalize_output_success(
            task_id, "poller", "job-invalid-final-output", **arguments
        )
    assert job_repository.get_job("job-invalid-final-output")["status"] == "post_processing"
    assert job_repository.get_output("job-invalid-final-output") is None


def test_expired_poll_lease_cannot_reschedule_or_exhaust(isolated_db):
    task_id = _claimed_status_task("job-expired-reschedule")
    _force_poll_lease_expired(task_id)
    assert job_repository.reschedule_poll_task(
        task_id, "poller-old", delay_seconds=0, error="late retry"
    ) is False
    assert job_repository.exhaust_poll_task(
        task_id, "poller-old", "job-expired-reschedule", phase="status", error="late failure"
    ) is False
    with job_repository._connect() as conn:
        task = conn.execute("SELECT status,claimed_by FROM generation_poll_tasks WHERE task_id=?", (task_id,)).fetchone()
    assert task["status"] == "processing" and task["claimed_by"] == "poller-old"


def test_expired_output_lease_cannot_finalize_job_success(isolated_db):
    task_id = _claimed_output_task("job-expired-output-finalize")
    _force_poll_lease_expired(task_id)
    assert job_repository.finalize_output_success(
        task_id, "poller", "job-expired-output-finalize", storage_key="expired.png",
        media_type="image/png", size_bytes=128,
        output_url="/v1/generation-jobs/job-expired-output-finalize/output",
    ) is False
    assert job_repository.get_job("job-expired-output-finalize")["status"] == "post_processing"
    assert job_repository.get_output("job-expired-output-finalize") is None


def test_expired_poll_task_recovery_has_single_concurrent_winner(isolated_db):
    """Only one replacement worker may reclaim an expired safe-poll task."""
    task_id = _claimed_status_task("job-poll-recovery-race")
    _force_poll_lease_expired(task_id)

    results = _race(lambda worker: job_repository.claim_next_poll_task(worker, 60))
    winners = [item for item in results if item is not None]

    assert len(winners) == 1
    assert winners[0]["task_id"] == task_id
    assert winners[0]["claimed_by"].startswith("worker-")
    assert winners[0]["status"] == "processing"


def test_reclaimed_poll_task_fences_previous_worker(isolated_db):
    """After recovery, the former lease owner cannot mutate the new claim."""
    task_id = _claimed_status_task("job-poll-recovery-fence")
    _force_poll_lease_expired(task_id)

    reclaimed = job_repository.claim_next_poll_task("poller-new", 60)
    assert reclaimed is not None and reclaimed["task_id"] == task_id

    assert job_repository.complete_poll_task(task_id, "poller-old") is False
    assert job_repository.reschedule_poll_task(
        task_id, "poller-old", delay_seconds=0, error="stale worker retry"
    ) is False
    assert job_repository.exhaust_poll_task(
        task_id, "poller-old", "job-poll-recovery-fence", phase="status", error="stale worker failure"
    ) is False

    with job_repository._connect() as conn:
        task = conn.execute(
            "SELECT status,claimed_by FROM generation_poll_tasks WHERE task_id=?", (task_id,)
        ).fetchone()
    assert task["status"] == "processing"
    assert task["claimed_by"] == "poller-new"
    assert job_repository.complete_poll_task(task_id, "poller-new") is True


def test_expired_poll_lease_cannot_fail_job_from_provider_terminal_result(isolated_db):
    from app.repositories.poll import SQLitePollRepository

    task_id = _claimed_status_task("job-expired-provider-failure")
    _force_poll_lease_expired(task_id)
    repository = SQLitePollRepository()

    assert repository.fail_provider_poll_task(
        task_id, "poller-old", "job-expired-provider-failure",
        error_code="PROVIDER_GENERATION_FAILED", message="late provider failure",
        event_type="PROVIDER_FAILED",
    ) is False
    assert job_repository.get_job("job-expired-provider-failure")["status"] == "running"


def test_provider_terminal_failure_and_task_completion_are_atomic(isolated_db):
    from app.repositories.poll import SQLitePollRepository

    task_id = _claimed_status_task("job-provider-terminal-failure")
    repository = SQLitePollRepository()

    assert repository.fail_provider_poll_task(
        task_id, "poller-old", "job-provider-terminal-failure",
        error_code="PROVIDER_GENERATION_FAILED", message="provider rejected generation",
        event_type="PROVIDER_FAILED",
    ) is True
    job = job_repository.get_job("job-provider-terminal-failure")
    assert job["status"] == "failed"
    assert job["error_code"] == "PROVIDER_GENERATION_FAILED"
    with job_repository._connect() as conn:
        task = conn.execute(
            "SELECT status,claimed_by,lease_expires_at FROM generation_poll_tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        events = conn.execute(
            "SELECT COUNT(*) AS n FROM generation_job_events WHERE job_id=? AND event_type='PROVIDER_FAILED'",
            ("job-provider-terminal-failure",),
        ).fetchone()["n"]
    assert task["status"] == "completed"
    assert task["claimed_by"] is None
    assert task["lease_expires_at"] is None
    assert events == 1
