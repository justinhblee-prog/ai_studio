from app.sql import sqlite_operations as sql


def test_operations_snapshot_queries_cover_all_durable_queues():
    assert "generation_worker_heartbeats" in sql.HEARTBEATS
    assert "generation_outbox" in sql.OUTBOX_AGGREGATES
    assert "generation_poll_tasks" in sql.POLL_AGGREGATES
    assert "generation_ops_alerts" in sql.ALERT_AGGREGATES
    assert "generation_ops_alert_deliveries" in sql.DELIVERY_AGGREGATES


def test_alert_fingerprint_upsert_and_resolution_statements_are_scoped():
    assert "WHERE fingerprint=?" in sql.ALERT_BY_FINGERPRINT
    assert "WHERE fingerprint=?" in sql.UPDATE_ALERT
    assert "WHERE fingerprint=? AND status='active'" in sql.RESOLVE_ALERT
    assert "ON CONFLICT(alert_id,destination)" in sql.UPSERT_DELIVERY


def test_alert_delivery_claim_uses_pending_compare_and_set():
    assert "status='pending'" in sql.SELECT_READY_DELIVERY
    assert "status='pending'" in sql.CLAIM_DELIVERY
    assert "attempts=attempts+1" in sql.CLAIM_DELIVERY


def test_delivery_terminal_and_retry_statements_are_explicit():
    assert "status='delivered'" in sql.DELIVERY_MARK_SENT
    assert "status='failed'" in sql.DELIVERY_MARK_FAILED
    assert "status='pending'" in sql.DELIVERY_RESCHEDULE
