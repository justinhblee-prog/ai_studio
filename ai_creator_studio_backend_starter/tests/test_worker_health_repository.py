def test_worker_health_adapter_owns_queue_counts_and_heartbeat_reads(monkeypatch,tmp_path):
    from app import config, job_repository
    from app.repositories.operations import build_worker_health_repository
    from app.repositories.operations import build_worker_heartbeat_repository
    monkeypatch.setattr(config,"ASSET_DATABASE_PATH",tmp_path/"worker-health.sqlite3")
    monkeypatch.setattr(config,"GENERATION_DATABASE_PATH",None)
    build_worker_heartbeat_repository().heartbeat("health-worker","running",{"worker_type":"outbox"})
    repo=build_worker_health_repository()
    monkeypatch.setattr(job_repository,"worker_health",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy worker health called")))
    monkeypatch.setattr(job_repository,"outbox_counts",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy outbox counts called")))
    snapshot=repo.worker_health(30)
    assert snapshot["workers"][0]["worker_id"]=="health-worker"
    assert snapshot["workers"][0]["healthy"] is True
    assert snapshot["outbox_counts"]=={}
    assert snapshot["poll_task_counts"]=={}


def test_legacy_module_no_longer_owns_worker_health_sql():
    from pathlib import Path
    legacy=Path("app/job_repository.py").read_text()
    section=legacy.split("def worker_health(",1)[1].split("# ---- Operational metrics",1)[0]
    assert "ops_sql.HEARTBEATS" not in section
    assert "SELECT status,COUNT(*) AS n FROM generation_outbox" not in legacy
    assert "SELECT status,COUNT(*) AS n FROM generation_poll_tasks" not in legacy
