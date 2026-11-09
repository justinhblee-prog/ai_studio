from app.repositories.outbox import OutboxRepository, SQLiteOutboxRepository, build_outbox_repository

class FakeImplementation:
    def initialize(self): return "init"
    def claim_next_outbox(self, worker_id, lease_seconds): return {"worker":worker_id,"lease":lease_seconds}
    def get_job(self, job_id): return {"job_id":job_id}
    def mark_outbox_unknown(self, event_id, job_id, error, worker_id): return (event_id,job_id,error,worker_id)
    def complete_outbox_submission(self, event_id, job_id, provider_request_id, worker_id): return {"id":event_id,"request":provider_request_id,"worker":worker_id}
    def heartbeat_worker(self, worker_id, state, metadata=None): return (worker_id,state,metadata)

def test_sqlite_outbox_adapter_implements_dedicated_port():
    adapter=SQLiteOutboxRepository(FakeImplementation())
    assert isinstance(adapter, OutboxRepository)
    assert adapter.claim_next_outbox("worker", 15)=={"worker":"worker","lease":15}
    assert adapter.get_job("job-1")=={"job_id":"job-1"}
    assert adapter.mark_outbox_unknown("evt","job","unknown","worker")==("evt","job","unknown","worker")
    assert adapter.complete_outbox_submission("evt","job","req","worker")=={"id":"evt","request":"req","worker":"worker"}

def test_outbox_builder_fails_closed_for_unimplemented_backend():
    import pytest
    with pytest.raises(RuntimeError, match="not implemented"):
        build_outbox_repository("postgresql")


def _make_queued_job(job_id):
    from app import job_repository
    job_repository.create_job({
        "job_id": job_id, "workspace_id": "ws-outbox-atomic", "owner_id": "user-outbox-atomic",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "sha256-outbox-atomic", "payload": {"model_image_url": "https://example.test/model.png"},
    })
    return job_repository.claim_next_outbox("dispatcher", 60)


def test_outbox_submission_finalization_rolls_back_job_execution_poll_and_event(isolated_db):
    import pytest
    import sqlite3
    from app import job_repository
    from app.repositories.outbox import build_outbox_repository
    outbox = _make_queued_job("job-outbox-finalize-rollback")
    assert outbox is not None
    with job_repository._connect() as conn:
        conn.execute("""CREATE TRIGGER reject_provider_submitted_event
            BEFORE INSERT ON generation_job_events WHEN NEW.event_type='PROVIDER_SUBMITTED'
            BEGIN SELECT RAISE(ABORT, 'injected event write failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected event write failure"):
        build_outbox_repository().complete_outbox_submission(
            outbox["event_id"], "job-outbox-finalize-rollback", "provider-ref-rollback", outbox["claimed_by"])
    assert job_repository.get_job("job-outbox-finalize-rollback")["status"] == "queued"
    diagnostics = job_repository.diagnostics("job-outbox-finalize-rollback")
    assert diagnostics["execution"]["status"] == "queued"
    assert diagnostics["outbox"]["status"] == "processing"
    with job_repository._connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM generation_poll_tasks WHERE job_id=?",
                             ("job-outbox-finalize-rollback",)).fetchone()[0]
        conn.execute("DROP TRIGGER reject_provider_submitted_event")
    assert count == 0


def test_outbox_unknown_quarantine_rolls_back_when_audit_event_fails(isolated_db):
    import pytest
    import sqlite3
    from app import job_repository
    from app.repositories.outbox import build_outbox_repository
    outbox = _make_queued_job("job-outbox-unknown-rollback")
    assert outbox is not None
    with job_repository._connect() as conn:
        conn.execute("""CREATE TRIGGER reject_unknown_event
            BEFORE INSERT ON generation_job_events WHEN NEW.event_type='PROVIDER_START_UNKNOWN'
            BEGIN SELECT RAISE(ABORT, 'injected audit failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected audit failure"):
        build_outbox_repository().mark_outbox_unknown(
            outbox["event_id"], "job-outbox-unknown-rollback", "network timeout", outbox["claimed_by"])
    assert job_repository.get_job("job-outbox-unknown-rollback")["status"] == "queued"
    diagnostics = job_repository.diagnostics("job-outbox-unknown-rollback")
    assert diagnostics["execution"]["status"] == "queued"
    assert diagnostics["outbox"]["status"] == "processing"
    with job_repository._connect() as conn:
        conn.execute("DROP TRIGGER reject_unknown_event")

import pytest

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    from app import config, job_repository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "outbox-atomic.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    job_repository.initialize()

@pytest.mark.parametrize("worker_id,lease_seconds", [
    ("", 30), ("   ", 30), (None, 30), ("worker", 0), ("worker", -1),
    ("worker", True), ("worker", 1.5), ("worker", "30"),
    ("w" * 129, 30),
])
def test_outbox_claim_rejects_invalid_worker_lease_before_storage(worker_id, lease_seconds):
    import pytest
    adapter = SQLiteOutboxRepository(FakeImplementation())
    with pytest.raises(ValueError):
        adapter.claim_next_outbox(worker_id, lease_seconds)
