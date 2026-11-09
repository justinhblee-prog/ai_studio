def test_worker_heartbeat_adapter_owns_upsert_sql(monkeypatch,tmp_path):
    from app import config, job_repository
    from app.repositories.operations import build_worker_heartbeat_repository
    monkeypatch.setattr(config,"ASSET_DATABASE_PATH",tmp_path/"heartbeat.sqlite3")
    monkeypatch.setattr(config,"GENERATION_DATABASE_PATH",None)
    repository=build_worker_heartbeat_repository()
    monkeypatch.setattr(job_repository,"heartbeat_worker",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy heartbeat called")))
    repository.heartbeat("worker-test","running",{"worker_type":"outbox"})
    from app.storage import get_storage
    from pathlib import Path
    with get_storage().transaction(Path(config.ASSET_DATABASE_PATH).resolve()) as conn:
        row=conn.execute("SELECT state,metadata_json FROM generation_worker_heartbeats WHERE worker_id=?",("worker-test",)).fetchone()
    assert row["state"]=="running"
    assert '"worker_type": "outbox"' in row["metadata_json"]


def test_legacy_module_no_longer_owns_worker_heartbeat_upsert():
    from pathlib import Path
    legacy=Path("app/job_repository.py").read_text()
    assert "INSERT INTO generation_worker_heartbeats" not in legacy
