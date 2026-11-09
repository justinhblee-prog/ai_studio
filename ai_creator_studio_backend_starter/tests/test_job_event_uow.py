import pytest
from app.repositories.job_event_uow import (
    JobEventUnitOfWork, SQLiteJobEventUnitOfWork, build_job_event_uow,
)
from app.services.job_lifecycle import JobLifecycleService


class FakeImplementation:
    def __init__(self):
        self.calls = []
    def transition_job(self, job_id, target, **kwargs):
        self.calls.append(("transition", job_id, target, kwargs))
        return {"job_id": job_id, "status": target}
    def update_job(self, job_id, updates, **kwargs):
        self.calls.append(("update", job_id, updates, kwargs))
        return {"job_id": job_id, **updates}
    def list_events(self, job_id):
        self.calls.append(("events", job_id))
        return [{"job_id": job_id, "event_type": "STATE_CHANGED"}]
    def reconcile_unknown_submission(self, job_id, **kwargs):
        self.calls.append(("reconcile", job_id, kwargs))
        return {"job_id": job_id, "status": "running"}


def test_sqlite_job_event_uow_satisfies_port_and_service_uses_it():
    implementation = FakeImplementation()
    uow = SQLiteJobEventUnitOfWork(implementation)
    assert isinstance(uow, JobEventUnitOfWork)
    service = JobLifecycleService(uow)
    assert service.transition("job-1", "running", event_type="PROVIDER_STARTED")["status"] == "running"
    assert service.update("job-1", {"message": "retry"})["message"] == "retry"
    assert service.events("job-1")[0]["event_type"] == "STATE_CHANGED"
    assert service.reconcile_unknown_submission("job-1", action="attach_request_id")["status"] == "running"
    assert [call[0] for call in implementation.calls] == ["transition", "update", "events", "reconcile"]


def test_job_event_uow_fails_closed_for_postgresql():
    with pytest.raises(RuntimeError, match="PostgreSQL Job/Event Unit of Work is not implemented"):
        build_job_event_uow("postgresql")


def test_poll_repository_routes_lifecycle_writes_through_job_event_uow():
    from app.worker_repositories import SQLitePollRepository
    implementation = FakeImplementation()
    repository = SQLitePollRepository(implementation)
    repository.transition_job("job-2", "failed", event_type="PROVIDER_FAILED")
    repository.update_job("job-2", {"message": "reason"}, event_type="JOB_UPDATED")
    assert [call[0] for call in implementation.calls] == ["transition", "update"]
    assert repository._job_event_uow._implementation is implementation


def test_sqlite_job_event_transition_and_event_insert_share_rollback(tmp_path, monkeypatch):
    from app import config, job_repository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "job-event-uow.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    uow = SQLiteJobEventUnitOfWork(job_repository)
    job_repository.initialize()
    job_repository.create_job({
        "job_id": "job-uow-atomic", "workspace_id": "ws-uow", "owner_id": "user-uow",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "sha256-uow", "payload": {"model_image_url": "https://example.test/model.png"},
    })
    changed = uow.transition_job("job-uow-atomic", "running", event_type="UOW_RUNNING")
    assert changed["status"] == "running"
    assert uow.list_events("job-uow-atomic")[-1]["event_type"] == "UOW_RUNNING"
    with job_repository._connect() as conn:
        conn.execute("""CREATE TRIGGER reject_uow_event BEFORE INSERT ON generation_job_events
            WHEN NEW.event_type='REJECT_UOW' BEGIN SELECT RAISE(ABORT, 'injected event failure'); END""")
    with pytest.raises(Exception, match="injected event failure"):
        uow.transition_job("job-uow-atomic", "post_processing", event_type="REJECT_UOW")
    assert job_repository.get_job("job-uow-atomic")["status"] == "running"
    assert all(event["event_type"] != "REJECT_UOW" for event in uow.list_events("job-uow-atomic"))


def test_lifecycle_service_dependency_reuses_cached_uow():
    from app.dependencies import get_job_event_uow, get_job_lifecycle_service
    get_job_event_uow.cache_clear()
    first = get_job_lifecycle_service()
    second = get_job_lifecycle_service()
    assert first._uow is second._uow
    assert first._uow is get_job_event_uow()


def test_event_sql_is_owned_by_event_repository_not_legacy_job_module():
    from pathlib import Path
    legacy = Path("app/job_repository.py").read_text()
    output = Path("app/repositories/sqlite_output.py").read_text()
    event_adapter = Path("app/repositories/event.py").read_text()
    assert "generation_job_events" not in legacy
    assert "generation_job_events" not in output
    assert "INSERT INTO generation_job_events" in event_adapter
    assert "SELECT * FROM generation_job_events" in event_adapter


def test_default_job_event_uow_reconciliation_uses_outbox_admin_not_legacy(monkeypatch):
    from app import job_repository
    from app.repositories.job_event_uow import build_job_event_uow
    monkeypatch.setattr(job_repository, "reconcile_unknown_submission",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("legacy reconciliation called")))
    uow = build_job_event_uow()
    assert uow._implementation is None
    assert uow._outbox_admin is not None


def _uow_test_job(job_id):
    return {
        "job_id": job_id, "workspace_id": "ws-atomic", "owner_id": "owner-atomic",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "hash-" + job_id, "payload": {"prompt": "atomic"},
    }


def test_dedicated_job_create_rolls_back_job_execution_event_outbox_and_idempotency_on_event_failure(
    monkeypatch, tmp_path,
):
    import pytest
    from app import config
    from app.repositories.job import build_job_repository

    database = tmp_path / "uow-create-rollback.sqlite3"
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", database)
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    repository = build_job_repository("sqlite")
    repository.initialize()
    from app.storage import get_storage
    from pathlib import Path
    with get_storage().transaction(Path(database)) as conn:
        conn.execute("""CREATE TRIGGER reject_create_event BEFORE INSERT ON generation_job_events
            WHEN NEW.event_type='JOB_CREATED' BEGIN SELECT RAISE(ABORT, 'injected create event failure'); END""")

    with pytest.raises(Exception, match="injected create event failure"):
        repository.create(_uow_test_job("job-create-rollback"), "idem-create-rollback")

    with get_storage().transaction(Path(database)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM generation_jobs WHERE job_id=?", ("job-create-rollback",)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM generation_executions WHERE job_id=?", ("job-create-rollback",)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM generation_job_events WHERE job_id=?", ("job-create-rollback",)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM generation_outbox WHERE job_id=?", ("job-create-rollback",)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM generation_idempotency WHERE idempotency_key=?", ("idem-create-rollback",)).fetchone()[0] == 0


def test_job_event_uow_metadata_update_rolls_back_when_audit_event_fails(monkeypatch, tmp_path):
    import pytest
    from pathlib import Path
    from app import config
    from app.repositories.job import build_job_repository
    from app.repositories.job_event_uow import build_job_event_uow
    from app.storage import get_storage

    database = tmp_path / "uow-update-rollback.sqlite3"
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", database)
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    repository = build_job_repository("sqlite")
    created, _ = repository.create(_uow_test_job("job-update-rollback"))
    assert created["message"] is None
    with get_storage().transaction(Path(database)) as conn:
        conn.execute("""CREATE TRIGGER reject_update_event BEFORE INSERT ON generation_job_events
            WHEN NEW.event_type='REJECT_METADATA' BEGIN SELECT RAISE(ABORT, 'injected metadata event failure'); END""")

    uow = build_job_event_uow()
    with pytest.raises(Exception, match="injected metadata event failure"):
        uow.update_job("job-update-rollback", {"message": "must rollback"}, event_type="REJECT_METADATA")

    persisted = repository.get("job-update-rollback")
    assert persisted["message"] is None
    assert persisted["version"] == created["version"]
    assert all(event["event_type"] != "REJECT_METADATA" for event in uow.list_events("job-update-rollback"))
