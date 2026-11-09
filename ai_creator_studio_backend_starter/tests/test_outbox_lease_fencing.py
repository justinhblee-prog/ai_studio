from datetime import datetime, timedelta, timezone

import pytest

from app import job_repository
from app.repositories.outbox import build_outbox_repository


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "outbox-lease-fence.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    job_repository.initialize()


def _claimed(job_id: str, worker_id: str = "worker-old"):
    job_repository.create_job({
        "job_id": job_id, "workspace_id": "ws-outbox-fence", "owner_id": "owner",
        "status": "queued", "provider": "mock", "model": "mock-model",
        "payload_hash": "hash-" + job_id, "payload": {"prompt": "fence"},
    })
    claimed = job_repository.claim_next_outbox(worker_id, 60)
    assert claimed is not None
    return claimed


def _expire(event_id: str):
    expired = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    with job_repository._connect() as conn:
        conn.execute("UPDATE generation_outbox SET lease_expires_at=? WHERE event_id=?", (expired, event_id))


def test_stale_outbox_owner_cannot_finalize_after_ownership_changes(isolated_db):
    outbox = _claimed("job-outbox-stale-finalize")
    future = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    with job_repository._connect() as conn:
        conn.execute("UPDATE generation_outbox SET claimed_by='worker-new',lease_expires_at=? WHERE event_id=?", (future, outbox["event_id"]))

    with pytest.raises(RuntimeError, match="not owned by this worker"):
        job_repository.complete_outbox_submission(
            outbox["event_id"], "job-outbox-stale-finalize", "stale-provider-id", "worker-old")

    current = job_repository.diagnostics("job-outbox-stale-finalize")
    assert current["outbox"]["status"] == "processing"
    assert current["outbox"]["claimed_by"] == "worker-new"
    assert job_repository.get_job("job-outbox-stale-finalize")["status"] == "queued"

    completed = job_repository.complete_outbox_submission(
        outbox["event_id"], "job-outbox-stale-finalize", "current-provider-id", "worker-new")
    assert completed["status"] == "running"


def test_expired_outbox_owner_cannot_complete_or_quarantine_after_lease_expiry(isolated_db):
    outbox = _claimed("job-outbox-stale-unknown")
    _expire(outbox["event_id"])
    with pytest.raises(RuntimeError, match="not owned by this worker"):
        job_repository.complete_outbox_submission(
            outbox["event_id"], "job-outbox-stale-unknown", "stale-provider-id", "worker-old")
    assert job_repository.mark_outbox_unknown(
        outbox["event_id"], "job-outbox-stale-unknown", "stale timeout", "worker-old") is False

    # The next claimant detects an expired in-flight POST and quarantines it;
    # it must not replay the submission because provider acceptance is unknown.
    assert job_repository.claim_next_outbox("worker-new", 60) is None
    current = job_repository.diagnostics("job-outbox-stale-unknown")
    assert current["outbox"]["status"] == "needs_reconciliation"
    assert current["outbox"]["claimed_by"] is None
    assert job_repository.get_job("job-outbox-stale-unknown")["status"] == "queued"


def test_outbox_finalizers_reject_missing_or_invalid_worker_identity(isolated_db):
    outbox = _claimed("job-outbox-invalid-worker")
    with pytest.raises(ValueError, match="worker_id"):
        job_repository.complete_outbox_submission(
            outbox["event_id"], "job-outbox-invalid-worker", "provider-id", " ")
    with pytest.raises(ValueError, match="worker_id"):
        job_repository.mark_outbox_unknown(
            outbox["event_id"], "job-outbox-invalid-worker", "timeout", " ")
    assert job_repository.diagnostics("job-outbox-invalid-worker")["outbox"]["status"] == "processing"
