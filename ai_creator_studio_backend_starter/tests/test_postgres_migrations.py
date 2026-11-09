from pathlib import Path

from app.postgres import MIGRATION_DIR, migration_files


def test_postgres_migration_versions_are_unique_and_ordered():
    files = migration_files()
    assert files
    versions = [int(path.name.split("_", 1)[0]) for path in files]
    assert versions == sorted(versions)
    assert len(versions) == len(set(versions))


def test_core_migration_creates_runtime_aggregates_and_leases():
    sql = (MIGRATION_DIR / "0001_generation_core.sql").read_text(encoding="utf-8")
    expected = {
        "generation_jobs", "generation_executions", "generation_job_events",
        "generation_outputs", "generation_output_asset_links", "generation_idempotency",
        "generation_outbox", "generation_worker_heartbeats", "generation_poll_tasks",
        "generation_ops_alerts", "generation_ops_alert_deliveries",
        "generation_output_review_events", "generation_output_export_events",
    }
    for table in expected:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
    assert "lease_expires_at TIMESTAMPTZ" in sql
    assert "PRIMARY KEY(workspace_id, idempotency_key)" in sql
    assert "pg_advisory_xact_lock" not in sql  # lock is applied by the runner, not schema DDL


def test_append_only_event_guard_covers_update_and_delete():
    sql = (MIGRATION_DIR / "0001_generation_core.sql").read_text(encoding="utf-8")
    assert "BEFORE UPDATE OR DELETE ON generation_output_review_events" in sql
    assert "BEFORE UPDATE OR DELETE ON generation_output_export_events" in sql


def test_migration_runner_rejects_missing_database_url(monkeypatch):
    from app import config
    from app.postgres import PostgreSQLNotConfigured, connect
    monkeypatch.setattr(config, "DATABASE_URL", "")
    try:
        connect(connect_factory=lambda *_a, **_k: None)
    except PostgreSQLNotConfigured:
        pass
    else:
        raise AssertionError("PostgreSQL connect must fail closed without DATABASE_URL")


def test_migration_runner_applies_pending_files_atomically(tmp_path, monkeypatch):
    from app import config
    from app.postgres import apply_migrations
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://test.invalid/acs")

    migration = tmp_path / "0001_sample.sql"
    migration.write_text("CREATE TABLE sample_table(id INTEGER);", encoding="utf-8")

    class Result:
        def __init__(self, rows=()):
            self._rows = list(rows)
        def fetchall(self):
            return self._rows

    class Transaction:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False

    class Connection:
        def __init__(self):
            self.statements = []
            self.closed = False
        def transaction(self):
            return Transaction()
        def execute(self, query, params=None, **kwargs):
            self.statements.append((query, params, kwargs))
            if "SELECT version, checksum_sha256 FROM acs_schema_migrations" in query:
                return Result()
            return Result()
        def close(self):
            self.closed = True

    connection = Connection()
    result = apply_migrations(connect_factory=lambda *_a, **_k: connection, directory=tmp_path)
    assert result.applied == ("0001_sample.sql",)
    assert result.already_applied == ()
    assert any("CREATE TABLE sample_table" in item[0] for item in connection.statements)
    assert connection.closed


def test_postgres_job_adapter_create_is_one_atomic_idempotent_unit(monkeypatch):
    from contextlib import AbstractContextManager
    from app.repositories import postgres_job

    statements = []
    class Cursor:
        def fetchone(self):
            return None
        def fetchall(self):
            return []
    class FakeConnection(AbstractContextManager):
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def execute(self, query, params=None):
            statements.append((query, params))
            return Cursor()
    monkeypatch.setattr(postgres_job, "connect", lambda: FakeConnection())
    monkeypatch.setattr(postgres_job.PostgreSQLJobRepository, "_jsonb", staticmethod(lambda value: value))
    repo = postgres_job.PostgreSQLJobRepository()
    monkeypatch.setattr(repo, "get", lambda job_id: {"job_id": job_id, "status": "queued"})
    job = {"job_id": "job_test_1", "workspace_id": "ws_1", "owner_id": "user_1", "status": "queued",
           "provider": "mock", "payload_hash": "sha256", "payload": {"prompt": "test"}}
    value, created = repo.create(job, "idem_1")
    assert created is True and value["job_id"] == "job_test_1"
    sql = [item[0] for item in statements]
    assert "pg_advisory_xact_lock" in sql[0]
    assert any("INSERT INTO generation_jobs" in item for item in sql)
    assert any("INSERT INTO generation_executions" in item for item in sql)
    assert any("INSERT INTO generation_job_events" in item for item in sql)
    assert any("INSERT INTO generation_idempotency" in item for item in sql)
    assert any("INSERT INTO generation_outbox" in item for item in sql)


def test_postgres_job_adapter_idempotency_rejects_payload_mismatch(monkeypatch):
    from contextlib import AbstractContextManager
    from app.repositories import postgres_job

    class Cursor:
        def fetchone(self):
            return {"job_id": "job_existing", "payload_json": {}, "idem_payload_hash": "old-hash"}
    class FakeConnection(AbstractContextManager):
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, *_args, **_kwargs): return Cursor()
    monkeypatch.setattr(postgres_job, "connect", lambda: FakeConnection())
    repo = postgres_job.PostgreSQLJobRepository()
    job = {"job_id": "job_new", "workspace_id": "ws_1", "owner_id": "user_1", "status": "queued",
           "provider": "mock", "payload_hash": "new-hash", "payload": {}}
    try:
        repo.create(job, "same-key")
    except ValueError as exc:
        assert "different payload" in str(exc)
    else:
        raise AssertionError("idempotency key payload mismatch must be rejected")


def test_postgres_outbox_claim_uses_skip_locked_and_lease_fencing(monkeypatch):
    from contextlib import AbstractContextManager
    from app.repositories import postgres_outbox

    calls = []
    class Cursor:
        def __init__(self, row=None, rows=None): self.row, self.rows = row, rows or []
        def fetchone(self): return self.row
        def fetchall(self): return self.rows
    class FakeConnection(AbstractContextManager):
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            calls.append((query, params))
            if "SELECT event_id,job_id FROM generation_outbox" in query:
                return Cursor(rows=[{"event_id": "obx_expired", "job_id": "job_expired"}])
            if "WITH candidate AS" in query:
                return Cursor(row={"event_id": "obx_1", "status": "processing", "claimed_by": "worker-a"})
            return Cursor()
    monkeypatch.setattr(postgres_outbox, "connect", lambda: FakeConnection())
    monkeypatch.setattr(postgres_outbox.PostgreSQLOutboxRepository, "_jsonb", staticmethod(lambda value: value))
    row = postgres_outbox.PostgreSQLOutboxRepository().claim_next_outbox("worker-a", 45)
    assert row["event_id"] == "obx_1"
    sql = "\n".join(item[0] for item in calls)
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "lease_expires_at" in sql
    assert "needs_reconciliation" in sql


def test_postgres_outbox_completion_is_fenced_by_worker_and_unexpired_lease(monkeypatch):
    from contextlib import AbstractContextManager
    from datetime import datetime, timedelta, timezone
    from app.repositories import postgres_outbox

    calls = []
    class Cursor:
        def __init__(self, row=None): self.row = row
        def fetchone(self): return self.row
    class FakeConnection(AbstractContextManager):
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            calls.append((query, params))
            if "SELECT status,claimed_by,lease_expires_at" in query:
                return Cursor({"status": "processing", "claimed_by": "worker-a", "lease_expires_at": datetime.now(timezone.utc) + timedelta(minutes=1)})
            if "SELECT status FROM generation_jobs" in query:
                return Cursor({"status": "queued"})
            if "RETURNING job_id" in query:
                return Cursor({"job_id": "job_1"})
            if "RETURNING event_id" in query:
                return Cursor({"event_id": "obx_1"})
            return Cursor()
    monkeypatch.setattr(postgres_outbox, "connect", lambda: FakeConnection())
    monkeypatch.setattr(postgres_outbox.PostgreSQLOutboxRepository, "_jsonb", staticmethod(lambda value: value))
    repo = postgres_outbox.PostgreSQLOutboxRepository()
    monkeypatch.setattr(repo, "get_job", lambda job_id: {"job_id": job_id, "status": "running"})
    result = repo.complete_outbox_submission("obx_1", "job_1", "provider-req", "worker-a")
    assert result["status"] == "running"
    sql = "\n".join(item[0] for item in calls)
    assert "claimed_by=%s" in sql
    assert "lease_expires_at>%s" in sql
    assert "INSERT INTO generation_poll_tasks" in sql


def test_postgres_outbox_claim_places_limit_before_lock_clause():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app" / "repositories" / "postgres_outbox.py").read_text(encoding="utf-8")
    assert "ORDER BY created_at,event_id LIMIT 1\n                    FOR UPDATE SKIP LOCKED" in source


def test_postgres_poll_claim_requeues_expired_safe_task_then_skip_locked_claims(monkeypatch):
    from contextlib import AbstractContextManager
    from app.repositories import postgres_poll
    calls = []
    class Cursor:
        def fetchone(self): return {"task_id": "poll_1", "status": "processing", "claimed_by": "worker-b"}
    class FakeConnection(AbstractContextManager):
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            calls.append((query, params))
            return Cursor()
    monkeypatch.setattr(postgres_poll, "connect", lambda: FakeConnection())
    row = postgres_poll.PostgreSQLPollRepository().claim_next_poll_task("worker-b", 30)
    assert row["task_id"] == "poll_1"
    sql = "\n".join(item[0] for item in calls)
    assert "lease expired; safe GET/output task requeued" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "ORDER BY available_at,created_at,task_id LIMIT 1" in sql


def test_postgres_poll_renewal_requires_live_owner_lease(monkeypatch):
    from contextlib import AbstractContextManager
    from app.repositories import postgres_poll
    calls = []
    class Cursor:
        def fetchone(self): return None
    class FakeConnection(AbstractContextManager):
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            calls.append((query, params))
            return Cursor()
    monkeypatch.setattr(postgres_poll, "connect", lambda: FakeConnection())
    ok = postgres_poll.PostgreSQLPollRepository().renew_poll_task_lease("poll_1", "worker-a", 45)
    assert ok is False
    sql = calls[0][0]
    assert "claimed_by=%s" in sql
    assert "lease_expires_at>%s" in sql


def test_postgres_operations_alert_delivery_claim_uses_skip_locked(monkeypatch):
    from contextlib import AbstractContextManager
    from app.repositories import postgres_operations
    calls = []
    class Cursor:
        def fetchone(self): return {"delivery_id": "delivery_1", "status": "processing", "details_json": {}}
    class FakeConnection(AbstractContextManager):
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            calls.append((query, params))
            return Cursor()
    monkeypatch.setattr(postgres_operations, "connect", lambda: FakeConnection())
    row = postgres_operations.PostgreSQLOperationsRepository().claim_alert_delivery("ops-worker", 90)
    assert row["delivery_id"] == "delivery_1"
    sql = "\n".join(item[0] for item in calls)
    assert "FOR UPDATE OF d SKIP LOCKED" in sql
    assert "lease_expires_at" in sql


def test_postgres_operations_alert_finish_requires_current_owner_and_live_lease(monkeypatch):
    from contextlib import AbstractContextManager
    from app.repositories import postgres_operations
    calls = []
    class Cursor:
        def __init__(self, row=None): self.row = row
        def fetchone(self): return self.row
    class FakeConnection(AbstractContextManager):
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            calls.append((query, params))
            if "SELECT attempts" in query: return Cursor({"attempts": 1})
            if "RETURNING delivery_id" in query: return Cursor({"delivery_id": "delivery_1"})
            return Cursor()
    monkeypatch.setattr(postgres_operations, "connect", lambda: FakeConnection())
    ok = postgres_operations.PostgreSQLOperationsRepository().finish_alert_delivery(
        "delivery_1", worker_id="ops-worker", delivered=True
    )
    assert ok is True
    sql = "\n".join(item[0] for item in calls)
    assert "claimed_by=%s" in sql
    assert "lease_expires_at>%s" in sql
