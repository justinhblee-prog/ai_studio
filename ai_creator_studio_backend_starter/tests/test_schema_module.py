import sqlite3

from app.schema_sqlite import (
    CORE_SCHEMA, OUTBOX_SCHEMA, POLL_SCHEMA, OPERATIONS_SCHEMA, initialize_schema,
)


def test_schema_is_grouped_by_persistence_aggregate():
    assert "generation_jobs" in CORE_SCHEMA
    assert "generation_outbox" in OUTBOX_SCHEMA
    assert "generation_poll_tasks" in POLL_SCHEMA
    assert "generation_ops_alerts" in OPERATIONS_SCHEMA
    assert "generation_ops_alert_deliveries" in OPERATIONS_SCHEMA
    assert "generation_output_asset_links" in CORE_SCHEMA


def test_schema_initialization_is_idempotent_and_keeps_migration_history():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    initialize_schema(connection)
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"generation_jobs", "generation_outbox", "generation_poll_tasks", "generation_ops_alerts", "generation_ops_alert_deliveries", "generation_output_asset_links"}.issubset(tables)
    output_columns = {row[1] for row in connection.execute("PRAGMA table_info(generation_outputs)")}
    assert "checksum_sha256" in output_columns
    versions = {row[0] for row in connection.execute("SELECT version FROM generation_schema_migrations")}
    assert versions == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
    connection.close()


def test_repository_module_no_longer_embeds_schema_ddl():
    from pathlib import Path
    source = Path("app/job_repository.py").read_text()
    assert "CREATE TABLE IF NOT EXISTS generation_jobs" not in source
    assert "initialize_schema(conn)" in source


def test_schema_migrates_legacy_output_rows_with_checksum_and_link_outbox():
    connection = sqlite3.connect(":memory:")
    connection.execute("""CREATE TABLE generation_outputs (
        output_id TEXT PRIMARY KEY, job_id TEXT NOT NULL UNIQUE, storage_key TEXT NOT NULL,
        media_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, created_at TEXT NOT NULL
    )""")
    connection.execute("INSERT INTO generation_outputs VALUES('out_legacy','job_legacy','legacy.png','image/png',100,'2026-01-01T00:00:00+00:00')")
    initialize_schema(connection)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(generation_outputs)")}
    assert "checksum_sha256" in columns
    assert connection.execute("SELECT output_id,checksum_sha256 FROM generation_outputs").fetchone() == ("out_legacy", None)
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "generation_output_asset_links" in tables
    assert "generation_output_asset_link_events" in tables
    assert "generation_output_review_events" in tables
    assert "generation_output_export_events" in tables
    connection.execute("DELETE FROM generation_schema_migrations WHERE version=7")
    connection.execute("""INSERT INTO generation_jobs(job_id,workspace_id,owner_id,status,provider,payload_hash,payload_json,created_at,updated_at)
        VALUES('job_backfill','ws-backfill','user-backfill','succeeded','mock','hash','{}','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')""")
    connection.execute("INSERT INTO generation_outputs(output_id,job_id,storage_key,media_type,size_bytes,created_at) VALUES(?,?,?,?,?,?)",
                       ('out_backfill','job_backfill','job_backfill.attempt-1.abc.png','image/png',100,'2026-01-01T00:00:00+00:00'))
    initialize_schema(connection)
    link = connection.execute("SELECT status,workspace_id,owner_id FROM generation_output_asset_links WHERE output_id='out_backfill'").fetchone()
    assert link == ('pending', 'ws-backfill', 'user-backfill')
    connection.close()


def test_schema_migrates_existing_alert_deliveries_with_lease_fencing_columns():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    connection.execute("""INSERT INTO generation_ops_alerts
        (alert_id,fingerprint,alert_type,severity,status,title,details_json,first_seen_at,last_seen_at)
        VALUES('legacy-alert','legacy-fingerprint','worker_stale','warning','active','Legacy','{}','2026-11-05T00:00:00+00:00','2026-11-05T00:00:00+00:00')""")
    connection.execute("""INSERT INTO generation_ops_alert_deliveries
        (delivery_id,alert_id,destination,status,attempts,available_at,claimed_at,created_at)
        VALUES('legacy-delivery','legacy-alert','https://example.test','processing',1,'2026-11-05T00:00:00+00:00','2026-11-05T00:00:00+00:00','2026-11-05T00:00:00+00:00')""")
    connection.execute("ALTER TABLE generation_ops_alert_deliveries DROP COLUMN claimed_by")
    connection.execute("ALTER TABLE generation_ops_alert_deliveries DROP COLUMN lease_expires_at")
    connection.execute("DELETE FROM generation_schema_migrations WHERE version=10")
    initialize_schema(connection)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(generation_ops_alert_deliveries)")}
    assert {"claimed_by", "lease_expires_at"}.issubset(columns)
    assert connection.execute("SELECT 1 FROM generation_schema_migrations WHERE version=10").fetchone()
    legacy = connection.execute("SELECT claimed_by,lease_expires_at FROM generation_ops_alert_deliveries WHERE delivery_id='legacy-delivery'").fetchone()
    assert legacy[0] == "legacy-unknown" and legacy[1] is not None
    connection.close()
