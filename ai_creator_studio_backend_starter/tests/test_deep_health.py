"""Deep health report: every check can pass, warn or fail, and the endpoint is private."""
import json
import shutil
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import deep_health
from app.main import app

client = TestClient(app)
Usage = namedtuple("Usage", "total used free")


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    from app.assets.store import create_workspace
    from app.repositories.operations import build_worker_heartbeat_repository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "health.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", ("ops-user",))
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"tok-ops": "ops-user", "tok-user": "plain-user"})
    (tmp_path / "private").mkdir(); (tmp_path / "outputs").mkdir(); (tmp_path / "backups").mkdir()
    create_workspace("ws-health", "plain-user")  # creates the schema
    # never depend on the real disk of the machine running the tests (a CI runner or sandbox may be nearly full)
    monkeypatch.setattr(deep_health.shutil, "disk_usage", lambda p: Usage(1_000_000, 500_000, 500_000))
    beat = build_worker_heartbeat_repository().heartbeat
    for wid, wtype, state in (("o", "outbox", "running"), ("p", "provider_poll", "running"), ("l", "output_asset_link", "idle")):
        beat(wid, state, {"worker_type": wtype})
    return config


def by_id(report):
    return {c["id"]: c for c in report["checks"]}


def write_backup(directory, created_at, name="backup-x"):
    d = Path(directory) / name; d.mkdir()
    (d / "manifest.json").write_text(json.dumps({"created_at": created_at.isoformat(), "totals": {"file_count": 3, "rows": 42}}))


def test_everything_ok_when_the_pilot_is_healthy(env):
    write_backup(env.BACKUP_DIR, datetime.now(timezone.utc) - timedelta(hours=2))
    report = deep_health.run_deep_health()
    assert report["status"] == "ok", report
    checks = by_id(report)
    assert set(checks) == {"database_assets", "storage_private_assets", "storage_outputs", "disk_space", "workers", "backup"}
    assert checks["database_assets"]["journal_mode"] in {"wal", "delete"} and checks["backup"]["rows"] == 42
    assert "path" not in json.dumps(report).lower().replace("pathology", ""), "the report must not expose file system paths"


def test_a_missing_database_fails(env):
    Path(env.ASSET_DATABASE_PATH).unlink()
    check = by_id(deep_health.run_deep_health())["database_assets"]
    assert check["status"] == "fail" and "missing" in check["detail"], "the operator must be told the file is missing, not just that it cannot be read"
    assert not Path(env.ASSET_DATABASE_PATH).exists(), "the health check must never create a database"


def test_a_corrupted_database_fails_without_a_traceback(env):
    Path(env.ASSET_DATABASE_PATH).write_bytes(b"this is not a sqlite database" * 100)
    check = by_id(deep_health.run_deep_health())["database_assets"]
    assert check["status"] == "fail" and "cannot be read" in check["detail"] or "quick_check" in check["detail"]


def test_a_database_that_fails_the_quick_check_fails(env, monkeypatch):
    real = deep_health.sqlite3.connect

    class Wrapped:
        def __init__(self, conn): self.conn = conn
        def execute(self, sql, *a):
            if sql == "PRAGMA quick_check":
                class R:
                    def fetchone(self_inner): return ("*** in database main *** Page 7: btreeInitPage() returns error code 11",)
                return R()
            return self.conn.execute(sql, *a)
        def close(self): self.conn.close()
    monkeypatch.setattr(deep_health.sqlite3, "connect", lambda *a, **k: Wrapped(real(*a, **k)))
    check = by_id(deep_health.run_deep_health())["database_assets"]
    assert check["status"] == "fail" and "quick_check" in check["detail"]


def test_a_storage_path_that_is_not_a_folder_fails_and_a_missing_one_fails(env, tmp_path):
    (tmp_path / "outputs").rmdir(); (tmp_path / "outputs").write_text("a file, not a folder")
    shutil.rmtree(tmp_path / "private")
    checks = by_id(deep_health.run_deep_health())
    assert checks["storage_outputs"]["status"] == "fail" and checks["storage_private_assets"]["status"] == "fail"
    assert deep_health.run_deep_health()["status"] == "fail"


def test_an_unwritable_storage_folder_fails_and_the_probe_file_is_cleaned_up(env, monkeypatch, tmp_path):
    ok = by_id(deep_health.run_deep_health())["storage_private_assets"]
    assert ok["status"] == "ok" and list((tmp_path / "private").iterdir()) == [], "a healthy check must not leave its probe behind"
    real_write = Path.write_bytes
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: (_ for _ in ()).throw(OSError(28, "No space left on device")) if ".healthcheck-" in self.name else real_write(self, data))
    check = by_id(deep_health.run_deep_health())["storage_private_assets"]
    assert check["status"] == "fail" and "not writable" in check["detail"]


@pytest.mark.parametrize("free_percent,expected", [(50, "ok"), (14.9, "warn"), (15, "ok"), (4.9, "fail"), (5, "warn"), (0, "fail")])
def test_disk_space_thresholds(env, monkeypatch, free_percent, expected):
    total = 1_000_000
    monkeypatch.setattr(deep_health.shutil, "disk_usage", lambda p: Usage(total, total - int(total * free_percent / 100), int(total * free_percent / 100)))
    assert by_id(deep_health.run_deep_health())["disk_space"]["status"] == expected


def test_a_missing_required_worker_fails_and_the_report_names_it(env):
    import sqlite3
    db = sqlite3.connect(env.ASSET_DATABASE_PATH); db.execute("DELETE FROM generation_worker_heartbeats WHERE worker_id='p'"); db.commit(); db.close()
    check = by_id(deep_health.run_deep_health())["workers"]
    assert check["status"] == "fail" and "provider_poll" in check["detail"] and "outbox" not in check["detail"].split(":")[1]


def test_a_stale_worker_heartbeat_fails(env):
    import sqlite3
    old = (datetime.now(timezone.utc) - timedelta(seconds=env.WORKER_STALE_AFTER_SECONDS + 60)).isoformat()
    db = sqlite3.connect(env.ASSET_DATABASE_PATH); db.execute("UPDATE generation_worker_heartbeats SET last_seen_at=? WHERE worker_id='o'", (old,)); db.commit(); db.close()
    check = by_id(deep_health.run_deep_health())["workers"]
    assert check["status"] == "fail" and "outbox" in check["detail"]


def test_submissions_needing_reconciliation_warn(env):
    import sqlite3
    db = sqlite3.connect(env.ASSET_DATABASE_PATH)
    db.execute("INSERT INTO generation_jobs(job_id,workspace_id,owner_id,status,provider,payload_hash,payload_json,created_at,updated_at) VALUES('j1','ws-health','plain-user','queued','mock','h','{}','2026-01-01','2026-01-01')")
    db.execute("INSERT INTO generation_outbox(event_id,job_id,event_type,payload_json,status,available_at,created_at) VALUES('e1','j1','SUBMIT_GENERATION','{}','needs_reconciliation','2026-01-01','2026-01-01')")
    db.commit(); db.close()
    check = by_id(deep_health.run_deep_health())["workers"]
    assert check["status"] == "warn" and "reconciliation" in check["detail"]


@pytest.mark.parametrize("hours_old,expected", [(1, "ok"), (25.9, "ok"), (26.5, "warn"), (500, "warn")])
def test_backup_freshness(env, hours_old, expected):
    write_backup(env.BACKUP_DIR, datetime.now(timezone.utc) - timedelta(hours=hours_old))
    assert by_id(deep_health.run_deep_health())["backup"]["status"] == expected


def test_backup_warns_when_unconfigured_empty_or_unreadable(env, monkeypatch, tmp_path):
    assert by_id(deep_health.run_deep_health())["backup"]["status"] == "warn"  # empty directory
    (env.BACKUP_DIR / "backup-broken").mkdir(); (env.BACKUP_DIR / "backup-broken" / "manifest.json").write_text("{not json")
    assert by_id(deep_health.run_deep_health())["backup"]["status"] == "warn"
    monkeypatch.setattr(env, "BACKUP_DIR", None)
    check = by_id(deep_health.run_deep_health())["backup"]
    assert check["status"] == "warn" and "BACKUP_DIR" in check["detail"]


def test_the_newest_backup_counts_not_the_first_one_found(env):
    write_backup(env.BACKUP_DIR, datetime.now(timezone.utc) - timedelta(hours=300), "backup-old")
    write_backup(env.BACKUP_DIR, datetime.now(timezone.utc) - timedelta(hours=3), "backup-new")
    assert by_id(deep_health.run_deep_health())["backup"]["status"] == "ok"


def test_overall_status_is_the_worst_check(env, monkeypatch):
    assert deep_health.run_deep_health()["status"] == "warn"  # no backup yet
    write_backup(env.BACKUP_DIR, datetime.now(timezone.utc))
    assert deep_health.run_deep_health()["status"] == "ok"
    monkeypatch.setattr(deep_health.shutil, "disk_usage", lambda p: Usage(100, 99, 1))
    assert deep_health.run_deep_health()["status"] == "fail"


def test_endpoint_is_private_and_returns_503_on_failure(env, monkeypatch):
    write_backup(env.BACKUP_DIR, datetime.now(timezone.utc))
    assert client.get("/internal/ops/health").status_code == 401
    assert client.get("/internal/ops/health", headers={"Authorization": "Bearer tok-user"}).status_code == 403
    ok = client.get("/internal/ops/health", headers={"Authorization": "Bearer tok-ops"})
    assert ok.status_code == 200 and ok.json()["status"] == "ok"
    Path(env.ASSET_DATABASE_PATH).unlink()
    bad = client.get("/internal/ops/health", headers={"Authorization": "Bearer tok-ops"})
    assert bad.status_code == 503 and bad.json()["status"] == "fail"


def test_the_public_health_probe_stays_minimal(env):
    body = client.get("/health").json()
    assert set(body) == {"ok", "version"}
