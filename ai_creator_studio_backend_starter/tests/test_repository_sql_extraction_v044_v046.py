from datetime import datetime, timezone


def _configure_db(monkeypatch, tmp_path):
    from app import config
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "repository-extraction.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)


def _job(job_id="job-repo-extraction"):
    return {"job_id":job_id,"workspace_id":"ws-repo","owner_id":"owner","status":"queued",
            "provider":"mock","model":"mock-model","payload_hash":"hash-"+job_id,"payload":{"prompt":"test"}}


def test_outbox_adapter_owns_claim_and_submission_sql(monkeypatch, tmp_path):
    from app import job_repository
    from app.repositories.job import build_job_repository
    from app.repositories.outbox import build_outbox_repository
    _configure_db(monkeypatch,tmp_path)
    jobs=build_job_repository(); jobs.initialize(); jobs.create(_job())
    outbox=build_outbox_repository()
    monkeypatch.setattr(job_repository,"claim_next_outbox",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy claim called")))
    monkeypatch.setattr(job_repository,"complete_outbox_submission",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy completion called")))
    claimed=outbox.claim_next_outbox("dispatcher",30)
    assert claimed and claimed["status"]=="processing"
    updated=outbox.complete_outbox_submission(claimed["event_id"],"job-repo-extraction","provider-req",claimed["claimed_by"])
    assert updated["status"]=="running"
    assert updated["provider_request_id"]=="provider-req"


def test_poll_adapter_owns_claim_and_completion_sql(monkeypatch, tmp_path):
    from app import job_repository
    from app.repositories.job import build_job_repository
    from app.repositories.outbox import build_outbox_repository
    from app.repositories.poll import build_poll_repository
    _configure_db(monkeypatch,tmp_path)
    jobs=build_job_repository(); jobs.initialize(); jobs.create(_job("job-poll-repo"))
    outbox=build_outbox_repository(); event=outbox.claim_next_outbox("dispatcher",30)
    outbox.complete_outbox_submission(event["event_id"],"job-poll-repo","provider-poll-req",event["claimed_by"])
    poll=build_poll_repository()
    monkeypatch.setattr(job_repository,"claim_next_poll_task",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy poll claim called")))
    monkeypatch.setattr(job_repository,"complete_poll_task",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy poll completion called")))
    task=poll.claim_next_poll_task("poller",30)
    assert task and task["status"]=="processing"
    assert poll.complete_poll_task(task["task_id"],"poller") is True


def test_poll_admin_adapter_owns_workspace_list_sql(monkeypatch, tmp_path):
    from app import job_repository
    from app.repositories.job import build_job_repository
    from app.repositories.outbox import build_outbox_repository
    from app.repositories.poll_admin import build_poll_task_admin_repository
    _configure_db(monkeypatch,tmp_path)
    jobs=build_job_repository(); jobs.initialize(); jobs.create(_job("job-poll-admin"))
    outbox=build_outbox_repository(); event=outbox.claim_next_outbox("dispatcher",30)
    outbox.complete_outbox_submission(event["event_id"],"job-poll-admin","provider-admin-req",event["claimed_by"])
    admin=build_poll_task_admin_repository()
    monkeypatch.setattr(job_repository,"list_poll_tasks",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy admin list called")))
    rows=admin.list_for_workspace("ws-repo",status="pending")
    assert len(rows)==1 and rows[0]["job_id"]=="job-poll-admin"


def test_legacy_module_no_longer_owns_outbox_and_poll_task_sql():
    from pathlib import Path
    legacy=Path("app/job_repository.py").read_text()
    assert "OUTBOX_SELECT_READY" not in legacy
    assert "POLL_SELECT_READY" not in legacy
    assert "UPDATE generation_poll_tasks SET status='completed'" not in legacy
    assert "def claim_next_outbox" in legacy  # compatibility facade only


def test_poll_provider_success_handoff_rolls_back_when_event_append_fails(isolated_db):
    import sqlite3
    import pytest
    from app import job_repository
    from app.repositories.outbox import build_outbox_repository
    from app.repositories.poll import build_poll_repository
    job_id = "job-poll-handoff-rollback"
    job_repository.create_job({
        "job_id": job_id, "workspace_id": "ws-poll-atomic", "owner_id": "user-poll-atomic",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "sha256-poll-atomic", "payload": {"model_image_url": "https://example.test/model.png"},
    })
    outbox = build_outbox_repository().claim_next_outbox("dispatcher", 60)
    build_outbox_repository().complete_outbox_submission(outbox["event_id"], job_id, "provider-ref-poll", outbox["claimed_by"])
    task = build_poll_repository().claim_next_poll_task("poller", 60)
    assert task is not None
    with job_repository._connect() as conn:
        conn.execute("""CREATE TRIGGER reject_provider_success_event
            BEFORE INSERT ON generation_job_events WHEN NEW.event_type='PROVIDER_SUCCEEDED'
            BEGIN SELECT RAISE(ABORT, 'injected poll audit failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected poll audit failure"):
        build_poll_repository().mark_provider_succeeded_for_poll(
            task["task_id"], "poller", job_id, "https://provider.example/result.png")
    assert job_repository.get_job(job_id)["status"] == "running"
    diagnostics = job_repository.diagnostics(job_id)
    assert diagnostics["execution"]["status"] == "running"
    assert diagnostics["poll_task"]["status"] == "processing"
    assert diagnostics["poll_task"]["phase"] == "status"
    with job_repository._connect() as conn:
        conn.execute("DROP TRIGGER reject_provider_success_event")


import pytest

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    from app import config, job_repository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "poll-atomic.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    job_repository.initialize()


def test_poll_retry_exhaustion_rolls_back_task_and_job_when_event_fails(isolated_db):
    import sqlite3
    import pytest
    from app import job_repository
    from app.repositories.outbox import build_outbox_repository
    from app.repositories.poll import build_poll_repository
    job_id = "job-poll-exhaustion-rollback"
    job_repository.create_job({
        "job_id": job_id, "workspace_id": "ws-poll-atomic", "owner_id": "user-poll-atomic",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "sha256-poll-exhaust", "payload": {"model_image_url": "https://example.test/model.png"},
    })
    outbox = build_outbox_repository().claim_next_outbox("dispatcher", 60)
    build_outbox_repository().complete_outbox_submission(outbox["event_id"], job_id, "provider-ref-poll-exhaust", outbox["claimed_by"])
    task = build_poll_repository().claim_next_poll_task("poller", 60)
    with job_repository._connect() as conn:
        conn.execute("""CREATE TRIGGER reject_poll_exhaustion_event
            BEFORE INSERT ON generation_job_events WHEN NEW.event_type='POLL_RETRY_BUDGET_EXHAUSTED'
            BEGIN SELECT RAISE(ABORT, 'injected poll exhaustion event failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected poll exhaustion event failure"):
        build_poll_repository().exhaust_poll_task(
            task["task_id"], "poller", job_id, phase="status", error="retry budget reached")
    assert job_repository.get_job(job_id)["status"] == "running"
    diagnostics = job_repository.diagnostics(job_id)
    assert diagnostics["poll_task"]["status"] == "processing"
    assert diagnostics["execution"]["status"] == "running"
    with job_repository._connect() as conn:
        conn.execute("DROP TRIGGER reject_poll_exhaustion_event")
