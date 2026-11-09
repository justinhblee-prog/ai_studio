from app.repositories.outbox_admin import OutboxAdminRepository, SQLiteOutboxAdminRepository, build_outbox_admin_repository

class FakeUow:
    def reconcile_unknown_submission(self, job_id, **kwargs): return {"job_id":job_id, **kwargs}

def test_outbox_admin_adapter_delegates_explicit_resolution_fields():
    adapter=SQLiteOutboxAdminRepository(FakeUow())
    assert isinstance(adapter, OutboxAdminRepository)
    result=adapter.reconcile_unknown_submission("job-1",action="attach_request_id",actor_id="admin-1",reason="provider confirmed",provider_request_id="req-1")
    assert result["provider_request_id"]=="req-1"
    assert result["actor_id"]=="admin-1"

def test_outbox_admin_builder_fails_closed_for_postgresql():
    import pytest
    with pytest.raises(RuntimeError,match="PostgreSQL storage driver is not implemented"):
        build_outbox_admin_repository("postgresql")


def _unknown_submission(job_id):
    from app import job_repository
    job_repository.create_job({
        "job_id": job_id, "workspace_id": "ws-reconcile-atomic", "owner_id": "user-reconcile-atomic",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "sha256-reconcile", "payload": {"model_image_url": "https://example.test/model.png"},
    })
    claimed = job_repository.claim_next_outbox("dispatcher", 60)
    job_repository.mark_outbox_unknown(claimed["event_id"], job_id, "network timeout", claimed["claimed_by"])
    return claimed


def test_attach_request_reconciliation_rolls_back_when_event_append_fails(isolated_db):
    import sqlite3
    import pytest
    from app import job_repository
    from app.repositories.outbox_admin import build_outbox_admin_repository
    job_id = "job-reconcile-attach-rollback"
    _unknown_submission(job_id)
    with job_repository._connect() as conn:
        conn.execute("""CREATE TRIGGER reject_attach_reconciliation
            BEFORE INSERT ON generation_job_events WHEN NEW.event_type='MANUAL_RECONCILIATION_REQUEST_ATTACHED'
            BEGIN SELECT RAISE(ABORT, 'injected reconcile event failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected reconcile event failure"):
        build_outbox_admin_repository().reconcile_unknown_submission(
            job_id, action="attach_request_id", actor_id="ops-admin", reason="verified", provider_request_id="provider-ref")
    assert job_repository.get_job(job_id)["status"] == "queued"
    diagnostics = job_repository.diagnostics(job_id)
    assert diagnostics["execution"]["status"] == "unknown"
    assert diagnostics["outbox"]["status"] == "needs_reconciliation"
    assert diagnostics["poll_task"] is None
    with job_repository._connect() as conn:
        conn.execute("DROP TRIGGER reject_attach_reconciliation")


def test_confirm_not_submitted_reconciliation_rolls_back_new_attempt_and_outbox(isolated_db):
    import sqlite3
    import pytest
    from app import job_repository
    from app.repositories.outbox_admin import build_outbox_admin_repository
    job_id = "job-reconcile-confirm-rollback"
    _unknown_submission(job_id)
    with job_repository._connect() as conn:
        conn.execute("""CREATE TRIGGER reject_confirm_reconciliation
            BEFORE INSERT ON generation_job_events WHEN NEW.event_type='MANUAL_RECONCILIATION_CONFIRMED_NOT_SUBMITTED'
            BEGIN SELECT RAISE(ABORT, 'injected confirm event failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected confirm event failure"):
        build_outbox_admin_repository().reconcile_unknown_submission(
            job_id, action="confirm_not_submitted", actor_id="ops-admin", reason="provider confirms absent")
    assert job_repository.get_job(job_id)["status"] == "queued"
    diagnostics = job_repository.diagnostics(job_id)
    assert diagnostics["execution"]["status"] == "unknown"
    assert diagnostics["outbox"]["status"] == "needs_reconciliation"
    with job_repository._connect() as conn:
        attempts = conn.execute("SELECT COUNT(*) FROM generation_executions WHERE job_id=?", (job_id,)).fetchone()[0]
        outbox_rows = conn.execute("SELECT COUNT(*) FROM generation_outbox WHERE job_id=?", (job_id,)).fetchone()[0]
        conn.execute("DROP TRIGGER reject_confirm_reconciliation")
    assert attempts == 1
    assert outbox_rows == 1


import pytest

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    from app import config, job_repository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "reconcile-atomic.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    job_repository.initialize()
