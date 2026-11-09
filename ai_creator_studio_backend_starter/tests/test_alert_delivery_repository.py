def test_alert_delivery_repository_claim_and_finish_are_dedicated(monkeypatch,tmp_path):
    from app import config, job_repository
    from app.repositories.operations import build_alert_delivery_repository
    from app.storage import get_storage
    from pathlib import Path
    monkeypatch.setattr(config,"ASSET_DATABASE_PATH",tmp_path/"alert-delivery.sqlite3")
    monkeypatch.setattr(config,"GENERATION_DATABASE_PATH",None)
    repo=build_alert_delivery_repository()
    from app.schema_sqlite import initialize_schema
    path=Path(config.ASSET_DATABASE_PATH).resolve()
    with get_storage().transaction(path) as conn:
        initialize_schema(conn)
        now="2026-11-02T00:00:00+00:00"
        conn.execute("INSERT INTO generation_ops_alerts(alert_id,fingerprint,alert_type,severity,status,title,details_json,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?)",("alert-1","worker:test","worker_stale","critical","active","Test alert","{}",now,now))
        conn.execute("INSERT INTO generation_ops_alert_deliveries(delivery_id,alert_id,destination,status,available_at,created_at) VALUES(?,?,?,?,?,?)",("delivery-1","alert-1","https://example.invalid/hook","pending",now,now))
    monkeypatch.setattr(job_repository,"claim_alert_delivery",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy claim called")))
    monkeypatch.setattr(job_repository,"finish_alert_delivery",lambda *a,**k: (_ for _ in ()).throw(AssertionError("legacy finish called")))
    item=repo.claim("delivery-worker")
    assert item and item["delivery_id"]=="delivery-1"
    assert repo.finish("delivery-1",worker_id="delivery-worker",delivered=True) is True
    with get_storage().transaction(path) as conn:
        row=conn.execute("SELECT status FROM generation_ops_alert_deliveries WHERE delivery_id='delivery-1'").fetchone()
    assert row["status"]=="delivered"


def test_legacy_module_no_longer_owns_alert_delivery_mutation_sql():
    from pathlib import Path
    legacy=Path("app/job_repository.py").read_text()
    assert "CLAIM_DELIVERY" not in legacy
    assert "DELIVERY_MARK_SENT" not in legacy


def test_alert_delivery_finish_is_fenced_by_owner_and_live_lease(monkeypatch,tmp_path):
    from app import config
    from app.repositories.operations import build_alert_delivery_repository
    from app.storage import get_storage
    from pathlib import Path
    from app.schema_sqlite import initialize_schema
    monkeypatch.setattr(config,"ASSET_DATABASE_PATH",tmp_path/"alert-fence.sqlite3")
    monkeypatch.setattr(config,"GENERATION_DATABASE_PATH",None)
    repo=build_alert_delivery_repository(); path=Path(config.ASSET_DATABASE_PATH).resolve()
    with get_storage().transaction(path) as conn:
        initialize_schema(conn); now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        conn.execute("INSERT INTO generation_ops_alerts(alert_id,fingerprint,alert_type,severity,status,title,details_json,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?)",("a","f","worker_stale","critical","active","A","{}",now,now))
        conn.execute("INSERT INTO generation_ops_alert_deliveries(delivery_id,alert_id,destination,status,available_at,created_at) VALUES(?,?,?,?,?,?)",("d","a","https://example.invalid","pending",now,now))
    claimed=repo.claim("worker-a",lease_seconds=30)
    assert claimed and claimed["claimed_by"]=="worker-a"
    assert repo.finish("d",worker_id="worker-b",delivered=True) is False
    with get_storage().transaction(path) as conn:
        row=conn.execute("SELECT status,claimed_by FROM generation_ops_alert_deliveries WHERE delivery_id='d'").fetchone()
        conn.execute("UPDATE generation_ops_alert_deliveries SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE delivery_id='d'")
    assert row["status"]=="processing" and row["claimed_by"]=="worker-a"
    assert repo.finish("d",worker_id="worker-a",delivered=True) is False
    with get_storage().transaction(path) as conn:
        row=conn.execute("SELECT status FROM generation_ops_alert_deliveries WHERE delivery_id='d'").fetchone()
    assert row["status"]=="processing"


def test_alert_delivery_expired_lease_is_reclaimed_and_old_owner_cannot_finish(monkeypatch,tmp_path):
    from app import config
    from app.repositories.operations import build_alert_delivery_repository
    from app.storage import get_storage
    from pathlib import Path
    from app.schema_sqlite import initialize_schema
    monkeypatch.setattr(config,"ASSET_DATABASE_PATH",tmp_path/"alert-reclaim.sqlite3")
    monkeypatch.setattr(config,"GENERATION_DATABASE_PATH",None)
    repo=build_alert_delivery_repository(); path=Path(config.ASSET_DATABASE_PATH).resolve()
    with get_storage().transaction(path) as conn:
        initialize_schema(conn); now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        conn.execute("INSERT INTO generation_ops_alerts(alert_id,fingerprint,alert_type,severity,status,title,details_json,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?)",("a","f","worker_stale","critical","active","A","{}",now,now))
        conn.execute("INSERT INTO generation_ops_alert_deliveries(delivery_id,alert_id,destination,status,available_at,created_at) VALUES(?,?,?,?,?,?)",("d","a","https://example.invalid","pending",now,now))
    first=repo.claim("worker-a",lease_seconds=1)
    assert first
    with get_storage().transaction(path) as conn:
        conn.execute("UPDATE generation_ops_alert_deliveries SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE delivery_id='d'")
    second=repo.claim("worker-b",lease_seconds=60)
    assert second and second["claimed_by"]=="worker-b"
    assert repo.finish("d",worker_id="worker-a",delivered=True) is False
    assert repo.finish("d",worker_id="worker-b",delivered=True) is True


def test_alert_delivery_rejects_invalid_claim_identity_before_storage():
    from app.repositories.operations import SQLiteAlertDeliveryRepository
    import pytest
    repo=SQLiteAlertDeliveryRepository()
    for worker_id,lease in [("",30),("worker",0),("worker",True),("x"*129,30)]:
        with pytest.raises(ValueError): repo.claim(worker_id,lease)
