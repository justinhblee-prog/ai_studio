def test_dedicated_job_repository_owns_create_read_and_idempotency(monkeypatch, tmp_path):
    from app import config, job_repository
    from app.repositories.job import build_job_repository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "job-create-extract.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    repository = build_job_repository("sqlite")
    repository.initialize()
    job = {
        "job_id": "job-create-extracted", "workspace_id": "ws-create", "owner_id": "owner",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "payload-hash", "payload": {"prompt": "catalog"},
    }
    # Prove the adapter no longer calls the legacy create/read/idempotency functions.
    monkeypatch.setattr(job_repository, "create_job", lambda *a, **k: (_ for _ in ()).throw(AssertionError("legacy create called")))
    monkeypatch.setattr(job_repository, "get_job", lambda *a, **k: (_ for _ in ()).throw(AssertionError("legacy get called")))
    created, was_created = repository.create(job, "idem-1")
    assert was_created is True
    assert created["payload"] == {"prompt": "catalog"}
    assert repository.get("job-create-extracted")["job_id"] == "job-create-extracted"
    existing = repository.get_idempotent("ws-create", "idem-1")
    assert existing[0]["job_id"] == "job-create-extracted"
    assert existing[1] == "payload-hash"
    duplicate, was_created = repository.create({**job, "job_id": "job-duplicate"}, "idem-1")
    assert was_created is False
    assert duplicate["job_id"] == "job-create-extracted"


def test_job_create_sql_is_removed_from_legacy_module():
    from pathlib import Path
    legacy = Path("app/job_repository.py").read_text()
    dedicated = Path("app/repositories/job.py").read_text()
    assert "INSERT INTO generation_jobs" not in legacy
    assert "generation_idempotency" not in legacy
    assert "INSERT INTO generation_jobs" in dedicated
    assert "generation_idempotency" in dedicated
