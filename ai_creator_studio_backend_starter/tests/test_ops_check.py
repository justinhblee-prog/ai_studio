import os, sqlite3, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ops_check
from app.schema_sqlite import initialize_schema

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
iso = lambda d: d.isoformat()


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
    initialize_schema(c)
    c.execute("CREATE TABLE deletion_requests(request_id TEXT, status TEXT, requested_at TEXT)")
    return c


def levels(conn, **kw):
    return {r["check"]: r["level"] for r in ops_check.run_checks(conn, now=NOW, **kw)}


def beat(conn, seen, state="running"):
    conn.execute("INSERT INTO generation_worker_heartbeats(worker_id,started_at,last_seen_at,state,metadata_json) VALUES('w',?,?,?,'{}')", (iso(seen), iso(seen), state))


def job(conn, jid, status="running", provider="fashn", ws="w1", created=None, updated=None):
    created = created or NOW - timedelta(minutes=1)
    conn.execute("INSERT INTO generation_jobs(job_id,workspace_id,owner_id,status,provider,model,payload_hash,payload_json,created_at,updated_at,version) VALUES(?,?,?,?,?,?,?,?,?,?,1)",
                 (jid, ws, "u", status, provider, "m", "h", "{}", iso(created), iso(updated or created)))


def test_worker_heartbeat_fresh_stale_and_stopped(conn):
    assert levels(conn)["worker_heartbeat"] == ops_check.CRIT
    beat(conn, NOW - timedelta(seconds=10)); assert levels(conn)["worker_heartbeat"] == ops_check.OK
    conn.execute("DELETE FROM generation_worker_heartbeats"); beat(conn, NOW - timedelta(seconds=300))
    assert levels(conn)["worker_heartbeat"] == ops_check.CRIT
    conn.execute("DELETE FROM generation_worker_heartbeats"); beat(conn, NOW, state="stopped")
    assert levels(conn)["worker_heartbeat"] == ops_check.CRIT


def test_stuck_jobs_only_unfinished_and_old(conn):
    job(conn, "ok1", status="succeeded", created=NOW - timedelta(hours=5))
    job(conn, "failed_old", status="failed", created=NOW - timedelta(hours=5))
    job(conn, "fresh", status="running")
    assert levels(conn)["stuck_jobs"] == ops_check.OK
    job(conn, "stuck", status="running", created=NOW - timedelta(minutes=45))
    assert levels(conn)["stuck_jobs"] == ops_check.WARN


def test_cost_cap_levels_ignore_mock_and_previous_month(conn):
    job(conn, "m1", provider="mock"); job(conn, "old", created=NOW - timedelta(days=40))
    assert levels(conn, ws_limit=3, global_limit=0)["cost_cap"] == ops_check.OK
    for i in range(4): job(conn, f"j{i}")
    assert levels(conn, ws_limit=5, global_limit=0)["cost_cap"] == ops_check.WARN   # 4/5 >= 80%
    job(conn, "j4")
    assert levels(conn, ws_limit=5, global_limit=0)["cost_cap"] == ops_check.CRIT
    assert levels(conn, ws_limit=0, global_limit=5)["cost_cap"] == ops_check.CRIT
    assert levels(conn, ws_limit=0, global_limit=6)["cost_cap"] == ops_check.WARN   # 5/6 >= 80%



def test_deletion_due_and_missing_table(conn):
    conn.execute("INSERT INTO deletion_requests VALUES('r1','pending',?)", (iso(NOW - timedelta(days=3)),))
    assert levels(conn)["deletion_due"] == ops_check.OK
    conn.execute("INSERT INTO deletion_requests VALUES('r2','pending',?)", (iso(NOW - timedelta(days=8)),))
    assert levels(conn)["deletion_due"] == ops_check.WARN
    conn.execute("UPDATE deletion_requests SET status='cancelled'")
    assert levels(conn)["deletion_due"] == ops_check.OK
    conn.execute("DROP TABLE deletion_requests")
    assert "deletion_due" not in levels(conn)


def make_backup(root, name, created):
    d = root / name; d.mkdir()
    (d / "manifest.json").write_text('{"created_at": "%s"}' % iso(created))
    return d


def test_backup_age(conn, tmp_path):
    assert levels(conn, backup_dir=tmp_path)["backup_age"] == ops_check.CRIT
    d = make_backup(tmp_path, "backup-20261120T110000Z", NOW - timedelta(hours=1))
    assert levels(conn, backup_dir=tmp_path)["backup_age"] == ops_check.OK
    (d / "manifest.json").write_text('{"created_at": "%s"}' % iso(NOW - timedelta(hours=50)))
    assert levels(conn, backup_dir=tmp_path)["backup_age"] == ops_check.CRIT


def test_a_folder_without_a_manifest_or_with_a_broken_one_is_not_a_backup(conn, tmp_path):
    (tmp_path / "backup-20261120T110000Z").mkdir()                      # half-written: no manifest yet
    bad = tmp_path / "backup-20261120T115900Z"; bad.mkdir(); (bad / "manifest.json").write_text("{not json")
    assert levels(conn, backup_dir=tmp_path)["backup_age"] == ops_check.CRIT


def test_idle_and_working_workers_are_alive_and_a_stopped_one_is_not(conn):
    for state in ("running", "idle", "working"):
        conn.execute("DELETE FROM generation_worker_heartbeats"); beat(conn, NOW - timedelta(seconds=5), state=state)
        assert levels(conn)["worker_heartbeat"] == ops_check.OK, state
    conn.execute("DELETE FROM generation_worker_heartbeats"); beat(conn, NOW - timedelta(seconds=5), state="stopped")
    assert levels(conn)["worker_heartbeat"] == ops_check.CRIT


def test_a_malformed_limit_setting_falls_back_to_the_default_instead_of_crashing(conn, monkeypatch):
    monkeypatch.setenv("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "lots"); monkeypatch.setenv("AI_JOB_LIMIT_GLOBAL_MONTH", "-3")
    for i in range(3): job(conn, f"j{i}")
    assert levels(conn)["cost_cap"] == ops_check.OK


def test_cli_is_read_only_and_exit_code(tmp_path):
    db = tmp_path / "x.sqlite3"
    c = sqlite3.connect(db); initialize_schema(c); c.commit(); c.close()
    before = db.read_bytes()
    r = subprocess.run([sys.executable, "scripts/ops_check.py", "--db", str(db), "--json"], cwd=Path(__file__).resolve().parents[1],
                       capture_output=True, text=True)
    assert r.returncode == ops_check.CRIT and '"CRITICAL"' in r.stdout   # no worker running
    assert db.read_bytes() == before
    missing = subprocess.run([sys.executable, "scripts/ops_check.py", "--db", str(tmp_path / "nope.sqlite3")], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert missing.returncode == ops_check.CRIT
