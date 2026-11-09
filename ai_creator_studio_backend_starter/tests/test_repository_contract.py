from __future__ import annotations

import pytest

from app.repository_contract import GenerationJobRepository, SQLiteRepository, build_repository


def test_sqlite_adapter_satisfies_generation_repository_protocol():
    repository = build_repository("sqlite")
    assert isinstance(repository, GenerationJobRepository)
    assert isinstance(repository, SQLiteRepository)
    assert repository.backend == "sqlite"
    assert callable(repository.create_job)
    assert callable(repository.claim_next_outbox)


def test_postgresql_selection_fails_closed_instead_of_falling_back():
    with pytest.raises(RuntimeError, match="live transaction"):
        build_repository("postgresql")


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError, match="Unsupported DATABASE_BACKEND"):
        build_repository("mysql")


def test_compatibility_composition_adapter_bypasses_legacy_facades(monkeypatch):
    from app import job_repository
    repository = build_repository("sqlite")
    def fail(*args, **kwargs):
        raise AssertionError("legacy repository facade must not be called")
    for name in ("create_job", "get_job", "get_idempotent_job", "transition_job",
                 "claim_next_outbox", "complete_outbox_submission", "claim_next_poll_task",
                 "claim_alert_delivery", "heartbeat_worker", "worker_health",
                 "diagnostics", "operational_snapshot"):
        monkeypatch.setattr(job_repository, name, fail)
    assert repository.backend == "sqlite"
    assert callable(repository.create_job)
    assert callable(repository.claim_next_outbox)


def test_compatibility_protocol_signatures_match_adapter_return_contracts():
    import inspect
    from app.repository_contract import GenerationJobRepository
    assert "tuple[dict[str, Any], str]" in str(inspect.signature(GenerationJobRepository.get_idempotent_job))
    assert "dict[str, Any]" in str(inspect.signature(GenerationJobRepository.complete_outbox_submission))
