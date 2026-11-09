def test_operations_monitoring_adapter_owns_snapshot_and_alert_evaluation(monkeypatch,tmp_path):
    from app import config, job_repository
    from app.repositories.operations import build_operations_monitoring_repository, build_worker_heartbeat_repository
    monkeypatch.setattr(config,"ASSET_DATABASE_PATH",tmp_path/"ops-monitoring.sqlite3")
    monkeypatch.setattr(config,"GENERATION_DATABASE_PATH",None)
    build_worker_heartbeat_repository().heartbeat("monitor-worker","running",{"worker_type":"outbox"})
    repo=build_operations_monitoring_repository()
    monkeypatch.setattr(job_repository,"operational_snapshot",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy snapshot called")))
    monkeypatch.setattr(job_repository,"evaluate_operational_alerts",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy alert evaluation called")))
    snapshot=repo.snapshot(30)
    assert snapshot["workers"][0]["worker_type"]=="outbox"
    active=repo.evaluate_alerts(required_worker_types=("provider_poll",))
    assert len(active)==1
    assert active[0]["fingerprint"]=="worker:provider_poll:stale"
    # A second evaluation updates the same fingerprint instead of duplicating it.
    repo.evaluate_alerts(required_worker_types=("provider_poll",))
    from app.repositories.operations import SQLiteOperationsAlertReadRepository
    alerts=SQLiteOperationsAlertReadRepository().list_alerts(status="active")
    assert len([a for a in alerts if a["fingerprint"]=="worker:provider_poll:stale"])==1


def test_legacy_module_no_longer_owns_monitoring_aggregate_sql():
    from pathlib import Path
    legacy=Path("app/job_repository.py").read_text()
    assert "ops_sql.HEARTBEATS" not in legacy
    assert "ops_sql.OUTBOX_AGGREGATES" not in legacy
    assert "ops_sql.POLL_AGGREGATES" not in legacy
    assert "ops_sql.ACTIVE_FINGERPRINTS" not in legacy
    assert "ops_sql.UPDATE_ALERT" not in legacy


def test_worker_operations_repository_uses_monitoring_adapter_not_legacy(monkeypatch, tmp_path):
    from app import config, job_repository
    from app.worker_repositories import SQLiteOperationsRepository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "worker-ops.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(job_repository, "evaluate_operational_alerts",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("legacy path called")))
    repo = SQLiteOperationsRepository()
    result = repo.evaluate_operational_alerts(required_worker_types=())
    assert isinstance(result, list)


def test_alert_and_delivery_creation_roll_back_together_on_delivery_failure(monkeypatch, tmp_path):
    import sqlite3
    import pytest
    from pathlib import Path
    from app import config
    from app.repositories.operations import build_operations_monitoring_repository
    from app.storage import get_storage

    database = tmp_path / "ops-atomic.sqlite3"
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", database)
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    repository = build_operations_monitoring_repository()
    storage = get_storage()
    with storage.transaction(Path(database).resolve()) as conn:
        from app.schema_sqlite import initialize_schema
        initialize_schema(conn)
        conn.execute("""CREATE TRIGGER reject_alert_delivery BEFORE INSERT ON generation_ops_alert_deliveries
            BEGIN SELECT RAISE(ABORT, 'injected delivery failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected delivery failure"):
        repository.evaluate_alerts(required_worker_types=("missing_worker",), webhook_destination="https://example.test/hook")
    with storage.transaction(Path(database).resolve()) as conn:
        alerts = conn.execute("SELECT COUNT(*) AS n FROM generation_ops_alerts").fetchone()["n"]
        deliveries = conn.execute("SELECT COUNT(*) AS n FROM generation_ops_alert_deliveries").fetchone()["n"]
    assert alerts == 0
    assert deliveries == 0
