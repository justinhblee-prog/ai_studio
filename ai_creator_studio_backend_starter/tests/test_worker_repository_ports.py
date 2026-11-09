from app.worker_repositories import (
    OutboxRepository, PollRepository, OperationsRepository,
    SQLiteOutboxRepository, SQLitePollRepository, SQLiteOperationsRepository,
    build_outbox_repository, build_poll_repository, build_operations_repository,
)


def test_worker_ports_are_runtime_checkable_and_separated():
    assert isinstance(build_outbox_repository(), OutboxRepository)
    assert isinstance(build_poll_repository(), PollRepository)
    assert isinstance(build_operations_repository(), OperationsRepository)
    assert isinstance(build_outbox_repository(), SQLiteOutboxRepository)
    assert isinstance(build_poll_repository(), SQLitePollRepository)
    assert isinstance(build_operations_repository(), SQLiteOperationsRepository)


def test_outbox_and_poll_repositories_own_task_sql_operations():
    from app import job_repository
    outbox = build_outbox_repository()
    poll = build_poll_repository()
    operations = build_operations_repository()
    assert outbox._impl is None
    assert poll._impl is None
    assert operations._impl is None


def test_worker_ports_fail_closed_for_postgresql(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DATABASE_BACKEND", "postgresql")
    import pytest
    with pytest.raises(RuntimeError, match="PostgreSQL storage driver is not implemented"):
        build_outbox_repository()
    with pytest.raises(RuntimeError, match="PostgreSQL storage driver is not implemented"):
        build_poll_repository()
    with pytest.raises(RuntimeError, match="PostgreSQL storage driver is not implemented"):
        build_operations_repository()


def test_poll_repository_composes_dedicated_output_repository():
    from app.repositories.output import OutputRepository
    from app.repositories.sqlite_output import SQLiteOutputRepository
    repository = build_poll_repository()
    assert isinstance(repository._output, OutputRepository)
    assert isinstance(repository._output, SQLiteOutputRepository)
    assert callable(repository.finalize_output_success)


def test_output_repository_selects_postgresql_adapter_without_fallback():
    from app.repositories.sqlite_output import build_output_repository
    from app.repositories.postgres_output import PostgreSQLOutputRepository
    assert isinstance(build_output_repository("postgresql"), PostgreSQLOutputRepository)


def test_outbox_and_poll_heartbeat_bypass_legacy_facade(monkeypatch, tmp_path):
    from app import config, job_repository
    from app.repositories.outbox import SQLiteOutboxRepository
    from app.repositories.poll import SQLitePollRepository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "worker-heartbeats.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(job_repository, "heartbeat_worker",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("legacy heartbeat called")))
    SQLiteOutboxRepository().heartbeat_worker("outbox-di", "running", {"worker_type": "outbox"})
    SQLitePollRepository().heartbeat_worker("poll-di", "running", {"worker_type": "provider_poll"})
    from app.repositories.operations import SQLiteWorkerHeartbeatRepository
    from pathlib import Path
    from app.storage import get_storage
    with get_storage().transaction(Path(config.ASSET_DATABASE_PATH).resolve()) as conn:
        rows = conn.execute("SELECT worker_id,state FROM generation_worker_heartbeats ORDER BY worker_id").fetchall()
    assert [(row["worker_id"], row["state"]) for row in rows] == [
        ("outbox-di", "running"), ("poll-di", "running")]
