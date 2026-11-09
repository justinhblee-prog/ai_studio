def test_operations_alert_read_adapter_owns_list_query(monkeypatch,tmp_path):
    from app import config, job_repository
    from app.repositories.operations import build_operations_alert_read_repository
    from app.schema_sqlite import initialize_schema
    from app.storage import get_storage
    from pathlib import Path
    monkeypatch.setattr(config,"ASSET_DATABASE_PATH",tmp_path/"ops-alert-read.sqlite3")
    monkeypatch.setattr(config,"GENERATION_DATABASE_PATH",None)
    path=Path(config.ASSET_DATABASE_PATH).resolve()
    with get_storage().transaction(path) as conn:
        initialize_schema(conn)
        now="2026-11-02T00:00:00+00:00"
        conn.execute("INSERT INTO generation_ops_alerts(alert_id,fingerprint,alert_type,severity,status,title,details_json,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?)",("alert-read-1","worker:test","worker_stale","critical","active","Test alert",'{"worker":"outbox"}',now,now))
    repo=build_operations_alert_read_repository()
    monkeypatch.setattr(job_repository,"list_operational_alerts",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy alert read called")))
    rows=repo.list_alerts(status="active")
    assert rows[0]["alert_id"]=="alert-read-1"
    assert rows[0]["details"]=={"worker":"outbox"}


def test_legacy_module_no_longer_owns_alert_list_query():
    from pathlib import Path
    legacy=Path("app/job_repository.py").read_text()
    assert "ops_sql.LIST_ALERTS" not in legacy
