"""SQLite schema installation kept outside application repository logic.

DDL is grouped by persistence aggregate. The migration ledger remains compatible
with the historical v1-v5 schema markers. This is SQLite-specific, not a
PostgreSQL migration runner.
"""
from __future__ import annotations
import sqlite3

CORE_SCHEMA = r"""
        CREATE TABLE IF NOT EXISTS generation_jobs (
            job_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued','running','post_processing','succeeded','failed')),
            provider TEXT NOT NULL,
            model TEXT,
            provider_request_id TEXT,
            output_url TEXT,
            error_code TEXT,
            message TEXT,
            payload_hash TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            provider_output_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_generation_jobs_workspace_created
            ON generation_jobs(workspace_id, created_at DESC);
        -- R-037: what each job is expected to cost (estimated from the per-job unit price; 0 for the built-in mock) and, once known, how long it
        -- took and how it ended. One row per job; deleted together with the job.
        CREATE TABLE IF NOT EXISTS generation_job_costs (
            job_id TEXT PRIMARY KEY REFERENCES generation_jobs(job_id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            estimated_cost_usd REAL NOT NULL CHECK(estimated_cost_usd >= 0),
            latency_ms INTEGER,
            error_code TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS generation_executions (
            execution_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES generation_jobs(job_id) ON DELETE CASCADE,
            attempt_no INTEGER NOT NULL,
            status TEXT NOT NULL,
            provider TEXT NOT NULL,
            provider_request_id TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            error_code TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(job_id, attempt_no)
        );
        CREATE TABLE IF NOT EXISTS generation_job_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES generation_jobs(job_id) ON DELETE CASCADE,
            from_status TEXT,
            to_status TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor_id TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_generation_events_job ON generation_job_events(job_id, event_id);
        CREATE TABLE IF NOT EXISTS generation_outputs (
            output_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL UNIQUE REFERENCES generation_jobs(job_id) ON DELETE CASCADE,
            storage_key TEXT NOT NULL,
            media_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
            created_at TEXT NOT NULL,
            checksum_sha256 TEXT
        );
        CREATE TABLE IF NOT EXISTS generation_output_asset_links (
            link_id TEXT PRIMARY KEY,
            output_id TEXT NOT NULL UNIQUE REFERENCES generation_outputs(output_id) ON DELETE CASCADE,
            job_id TEXT NOT NULL REFERENCES generation_jobs(job_id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','processing','linked','failed')),
            attempts INTEGER NOT NULL DEFAULT 0,
            available_at TEXT NOT NULL,
            claimed_by TEXT,
            claimed_at TEXT,
            lease_expires_at TEXT,
            asset_id TEXT,
            asset_version_id TEXT,
            provenance_id TEXT,
            checksum_sha256 TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_output_asset_links_ready ON generation_output_asset_links(status,available_at,created_at);
        CREATE TABLE IF NOT EXISTS generation_output_asset_link_events (
            event_id TEXT PRIMARY KEY,
            link_id TEXT NOT NULL REFERENCES generation_output_asset_links(link_id),
            output_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_output_asset_link_events ON generation_output_asset_link_events(link_id,created_at,event_id);
        CREATE TABLE IF NOT EXISTS generation_idempotency (
            workspace_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            job_id TEXT NOT NULL REFERENCES generation_jobs(job_id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            PRIMARY KEY(workspace_id, idempotency_key)
        );
"""

OUTBOX_SCHEMA = r"""        CREATE TABLE IF NOT EXISTS generation_outbox (
            event_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES generation_jobs(job_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL CHECK(status IN ('pending','processing','processed','needs_reconciliation')),
            attempts INTEGER NOT NULL DEFAULT 0,
            available_at TEXT NOT NULL,
            claimed_by TEXT,
            claimed_at TEXT,
            lease_expires_at TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            processed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_generation_outbox_ready
            ON generation_outbox(status, available_at, created_at);
        CREATE TABLE IF NOT EXISTS generation_worker_heartbeats (
            worker_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            state TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
"""

POLL_SCHEMA = r"""        CREATE TABLE IF NOT EXISTS generation_poll_tasks (
            task_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL UNIQUE REFERENCES generation_jobs(job_id) ON DELETE CASCADE,
            phase TEXT NOT NULL CHECK(phase IN ('status','persist_output')),
            status TEXT NOT NULL CHECK(status IN ('pending','processing','completed','needs_reconciliation')),
            attempts INTEGER NOT NULL DEFAULT 0,
            available_at TEXT NOT NULL,
            claimed_by TEXT,
            claimed_at TEXT,
            lease_expires_at TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_generation_poll_ready
            ON generation_poll_tasks(status, available_at, created_at);
        CREATE TABLE IF NOT EXISTS generation_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        INSERT OR IGNORE INTO generation_schema_migrations(version, applied_at) VALUES (1, CURRENT_TIMESTAMP);
        INSERT OR IGNORE INTO generation_schema_migrations(version, applied_at) VALUES (2, CURRENT_TIMESTAMP);
        INSERT OR IGNORE INTO generation_schema_migrations(version, applied_at) VALUES (3, CURRENT_TIMESTAMP);
        INSERT OR IGNORE INTO generation_schema_migrations(version, applied_at) VALUES (4, CURRENT_TIMESTAMP);
"""

OPERATIONS_SCHEMA = r"""        CREATE TABLE IF NOT EXISTS generation_ops_alerts (
            alert_id TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL UNIQUE,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL CHECK(severity IN ('warning','critical')),
            status TEXT NOT NULL CHECK(status IN ('active','resolved')),
            title TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            resolved_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_generation_ops_alerts_status ON generation_ops_alerts(status, severity, last_seen_at);
        CREATE TABLE IF NOT EXISTS generation_ops_alert_deliveries (
            delivery_id TEXT PRIMARY KEY,
            alert_id TEXT NOT NULL REFERENCES generation_ops_alerts(alert_id) ON DELETE CASCADE,
            destination TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','processing','delivered','failed')),
            attempts INTEGER NOT NULL DEFAULT 0,
            available_at TEXT NOT NULL,
            claimed_at TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            delivered_at TEXT,
            UNIQUE(alert_id, destination)
        );
        CREATE INDEX IF NOT EXISTS idx_generation_alert_delivery_ready ON generation_ops_alert_deliveries(status, available_at);
        INSERT OR IGNORE INTO generation_schema_migrations(version, applied_at) VALUES (5, CURRENT_TIMESTAMP);
        INSERT OR IGNORE INTO generation_schema_migrations(version, applied_at) VALUES (6, CURRENT_TIMESTAMP);
        INSERT OR IGNORE INTO generation_schema_migrations(version, applied_at) VALUES (8, CURRENT_TIMESTAMP);
        """

OUTPUT_REVIEW_SCHEMA = r"""
        CREATE TABLE IF NOT EXISTS generation_output_review_events (
            event_id TEXT PRIMARY KEY,
            output_id TEXT NOT NULL REFERENCES generation_outputs(output_id),
            job_id TEXT NOT NULL REFERENCES generation_jobs(job_id),
            workspace_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            decision TEXT NOT NULL CHECK(decision IN ('approved','changes_requested','rejected')),
            comment TEXT NOT NULL DEFAULT '',
            asset_id TEXT NOT NULL,
            asset_version_id TEXT NOT NULL,
            provenance_id TEXT NOT NULL,
            checksum_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_generation_output_reviews
            ON generation_output_review_events(job_id,output_id,created_at,event_id);
        CREATE TRIGGER IF NOT EXISTS trg_output_review_events_no_update
            BEFORE UPDATE ON generation_output_review_events
            BEGIN SELECT RAISE(ABORT, 'output review events are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS trg_output_review_events_no_delete
            BEFORE DELETE ON generation_output_review_events
            BEGIN SELECT RAISE(ABORT, 'output review events are append-only'); END;

        CREATE TABLE IF NOT EXISTS generation_output_export_events (
            event_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES generation_jobs(job_id),
            workspace_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            manifest_sha256 TEXT NOT NULL,
            output_count INTEGER NOT NULL CHECK(output_count > 0),
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_generation_output_exports
            ON generation_output_export_events(job_id,created_at,event_id);
        CREATE TRIGGER IF NOT EXISTS trg_output_export_events_no_update
            BEFORE UPDATE ON generation_output_export_events
            BEGIN SELECT RAISE(ABORT, 'output export events are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS trg_output_export_events_no_delete
            BEFORE DELETE ON generation_output_export_events
            BEGIN SELECT RAISE(ABORT, 'output export events are append-only'); END;
        INSERT OR IGNORE INTO generation_schema_migrations(version, applied_at) VALUES (9, CURRENT_TIMESTAMP);
        """

def initialize_schema(connection: sqlite3.Connection) -> None:
    """Apply all current SQLite schema groups in dependency order."""
    for script in (CORE_SCHEMA, OUTBOX_SCHEMA, POLL_SCHEMA, OPERATIONS_SCHEMA, OUTPUT_REVIEW_SCHEMA):
        connection.executescript(script)
    delivery_columns = {row[1] for row in connection.execute("PRAGMA table_info(generation_ops_alert_deliveries)").fetchall()}
    if "claimed_by" not in delivery_columns:
        connection.execute("ALTER TABLE generation_ops_alert_deliveries ADD COLUMN claimed_by TEXT")
    if "lease_expires_at" not in delivery_columns:
        connection.execute("ALTER TABLE generation_ops_alert_deliveries ADD COLUMN lease_expires_at TEXT")
    lease_migration_done = connection.execute("SELECT 1 FROM generation_schema_migrations WHERE version=10").fetchone()
    if lease_migration_done is None:
        # Preserve in-flight legacy deliveries while assigning a bounded lease.
        # Rows older than the former two-minute reclaim window become immediately reclaimable.
        connection.execute("""UPDATE generation_ops_alert_deliveries
            SET claimed_by=COALESCE(claimed_by,'legacy-unknown'),
                lease_expires_at=strftime('%Y-%m-%dT%H:%M:%f+00:00',claimed_at,'+2 minutes')
            WHERE status='processing' AND claimed_at IS NOT NULL AND lease_expires_at IS NULL""")
        connection.execute("INSERT OR IGNORE INTO generation_schema_migrations(version,applied_at) VALUES(10,CURRENT_TIMESTAMP)")
    output_columns = {row[1] for row in connection.execute("PRAGMA table_info(generation_outputs)").fetchall()}
    if "checksum_sha256" not in output_columns:
        connection.execute("ALTER TABLE generation_outputs ADD COLUMN checksum_sha256 TEXT")
    # Backfill only legacy Output records whose attempt-scoped private filename
    # follows the current safe resolver convention. Unsupported legacy names are
    # intentionally left unqueued for explicit operator reconciliation.
    backfill_done = connection.execute("SELECT 1 FROM generation_schema_migrations WHERE version=7").fetchone()
    if backfill_done is None:
        connection.execute("""INSERT OR IGNORE INTO generation_output_asset_links
            (link_id,output_id,job_id,workspace_id,owner_id,status,attempts,available_at,created_at,updated_at)
            SELECT 'oal_legacy_' || o.output_id,o.output_id,o.job_id,j.workspace_id,j.owner_id,'pending',0,
                   o.created_at,o.created_at,o.created_at
            FROM generation_outputs o JOIN generation_jobs j ON j.job_id=o.job_id
            WHERE j.status='succeeded' AND substr(o.storage_key,1,length(j.job_id)+9)=j.job_id || '.attempt-'""")
        connection.execute("INSERT OR IGNORE INTO generation_schema_migrations(version,applied_at) VALUES(7,CURRENT_TIMESTAMP)")
