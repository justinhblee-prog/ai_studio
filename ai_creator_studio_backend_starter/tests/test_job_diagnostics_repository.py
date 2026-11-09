import pytest
from app.repositories.diagnostics import (
    JobDiagnosticsRepository, SQLiteJobDiagnosticsRepository, build_job_diagnostics_repository,
)


def test_diagnostics_repository_composes_event_execution_output_and_worker_state(monkeypatch, tmp_path):
    from app import config, job_repository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "diagnostics.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    job_repository.initialize()
    job_repository.create_job({
        "job_id": "job-diagnostics", "workspace_id": "ws-diagnostics", "owner_id": "owner",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "diag-hash", "payload": {"prompt": "test"},
    })
    repository = build_job_diagnostics_repository("sqlite")
    assert isinstance(repository, JobDiagnosticsRepository)
    result = repository.get("job-diagnostics")
    assert result["execution"]["status"] == "queued"
    assert result["events"][-1]["event_type"] == "JOB_CREATED"
    assert result["output"] is None
    assert result["outbox"]["event_type"] == "SUBMIT_GENERATION"
    assert result["poll_task"] is None


def test_diagnostics_repository_fails_closed_for_postgresql():
    with pytest.raises(RuntimeError, match="PostgreSQL Job Diagnostics Repository is not implemented"):
        build_job_diagnostics_repository("postgresql")


def test_diagnostics_sql_is_removed_from_legacy_job_module():
    from pathlib import Path
    legacy = Path("app/job_repository.py").read_text()
    dedicated = Path("app/repositories/diagnostics.py").read_text()
    facade = legacy.split("def diagnostics(", 1)[1].split("# ---- Transactional outbox", 1)[0]
    assert "SELECT" not in facade
    assert "build_job_diagnostics_repository" in facade
    assert "SELECT * FROM generation_executions" in dedicated
