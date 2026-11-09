from app.sql import sqlite_worker


def test_worker_sql_claim_statements_keep_compare_and_set_guards():
    assert "status='pending'" in sqlite_worker.OUTBOX_CLAIM
    assert "status='pending'" in sqlite_worker.POLL_CLAIM
    assert "attempts=attempts+1" in sqlite_worker.OUTBOX_CLAIM
    assert "attempts=attempts+1" in sqlite_worker.POLL_CLAIM


def test_worker_sql_ready_order_is_deterministic():
    assert "ORDER BY created_at,event_id" in sqlite_worker.OUTBOX_SELECT_READY
    assert "ORDER BY available_at,created_at" in sqlite_worker.POLL_SELECT_READY


def test_outbox_expired_lease_is_not_automatically_replayed():
    assert "needs_reconciliation" in sqlite_worker.OUTBOX_EXPIRE_MARK
    assert "PROVIDER_START_UNKNOWN" in sqlite_worker.OUTBOX_EXPIRE_JOB
    assert "unknown" in sqlite_worker.OUTBOX_EXPIRE_EXECUTION


def test_poll_expired_lease_is_safe_to_requeue():
    assert "status='pending'" in sqlite_worker.POLL_REQUEUE_EXPIRED
    assert "safe GET/output task requeued" in sqlite_worker.POLL_REQUEUE_EXPIRED
