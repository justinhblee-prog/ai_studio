"""PostgreSQL worker heartbeat and alert delivery adapters."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.postgres import connect
from app.repositories.lease_validation import validate_worker_id, validate_worker_lease


class PostgreSQLOperationsRepository:
    backend = "postgresql"

    @staticmethod
    def _jsonb(value: Any):
        try:
            from psycopg.types.json import Jsonb
            return Jsonb(value)
        except ImportError as exc:
            raise RuntimeError("psycopg 3 is required for PostgreSQL Operations repository") from exc

    def heartbeat(self, worker_id: str, state: str, metadata: dict[str, Any] | None = None) -> None:
        validate_worker_id(worker_id)
        if not isinstance(state, str) or not state.strip():
            raise ValueError("state must be a non-empty string")
        now = datetime.now(timezone.utc)
        with connect() as conn:
            conn.execute(
                """INSERT INTO generation_worker_heartbeats(worker_id,started_at,last_seen_at,state,metadata_json)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT(worker_id) DO UPDATE SET last_seen_at=EXCLUDED.last_seen_at,
                state=EXCLUDED.state,metadata_json=EXCLUDED.metadata_json""",
                (worker_id, now, now, state, self._jsonb(metadata or {})),
            )

    def claim_alert_delivery(self, worker_id: str, lease_seconds: int = 120):
        validate_worker_lease(worker_id, lease_seconds)
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=lease_seconds)
        with connect() as conn:
            # Alert webhook delivery retries are bounded by the caller's max_attempts policy.
            conn.execute(
                """UPDATE generation_ops_alert_deliveries SET status='pending',claimed_at=NULL,
                claimed_by=NULL,lease_expires_at=NULL,available_at=%s
                WHERE status='processing' AND lease_expires_at IS NOT NULL AND lease_expires_at<=%s""", (now, now)
            )
            return conn.execute(
                """WITH candidate AS (
                    SELECT d.delivery_id FROM generation_ops_alert_deliveries d
                    WHERE d.status='pending' AND d.available_at<=%s
                    ORDER BY d.created_at,d.delivery_id LIMIT 1
                    FOR UPDATE OF d SKIP LOCKED
                )
                UPDATE generation_ops_alert_deliveries d SET status='processing',attempts=d.attempts+1,
                claimed_at=%s,claimed_by=%s,lease_expires_at=%s
                FROM candidate c, generation_ops_alerts a
                WHERE d.delivery_id=c.delivery_id AND a.alert_id=d.alert_id
                RETURNING d.*,a.alert_type,a.severity,a.title,a.details_json,a.fingerprint,a.status AS alert_status""",
                (now, now, worker_id, lease_until),
            ).fetchone()

    def finish_alert_delivery(self, delivery_id: str, *, worker_id: str, delivered: bool,
                              error: str | None = None, retry_delay_seconds: float = 30,
                              max_attempts: int = 8) -> bool:
        validate_worker_id(worker_id)
        if not isinstance(delivery_id, str) or not delivery_id.strip():
            raise ValueError("delivery_id must be a non-empty string")
        if not isinstance(delivered, bool):
            raise ValueError("delivered must be a boolean")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if isinstance(retry_delay_seconds, bool) or not isinstance(retry_delay_seconds, (int, float)) or retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")
        if error is not None and not isinstance(error, str):
            raise ValueError("error must be a string or None")
        now = datetime.now(timezone.utc)
        with connect() as conn:
            row = conn.execute(
                """SELECT attempts FROM generation_ops_alert_deliveries
                WHERE delivery_id=%s AND status='processing' AND claimed_by=%s AND lease_expires_at>%s
                FOR UPDATE""", (delivery_id, worker_id, now)
            ).fetchone()
            if row is None:
                return False
            if delivered:
                changed = conn.execute(
                    """UPDATE generation_ops_alert_deliveries SET status='delivered',delivered_at=%s,
                    claimed_at=NULL,claimed_by=NULL,lease_expires_at=NULL,last_error=NULL
                    WHERE delivery_id=%s AND status='processing' AND claimed_by=%s AND lease_expires_at>%s
                    RETURNING delivery_id""", (now, delivery_id, worker_id, now)
                ).fetchone()
            elif int(row["attempts"]) >= max_attempts:
                changed = conn.execute(
                    """UPDATE generation_ops_alert_deliveries SET status='failed',claimed_at=NULL,
                    claimed_by=NULL,lease_expires_at=NULL,last_error=%s
                    WHERE delivery_id=%s AND status='processing' AND claimed_by=%s AND lease_expires_at>%s
                    RETURNING delivery_id""", ((error or "delivery failed")[:500], delivery_id, worker_id, now)
                ).fetchone()
            else:
                available = now + timedelta(seconds=max(1, retry_delay_seconds))
                changed = conn.execute(
                    """UPDATE generation_ops_alert_deliveries SET status='pending',available_at=%s,
                    claimed_at=NULL,claimed_by=NULL,lease_expires_at=NULL,last_error=%s
                    WHERE delivery_id=%s AND status='processing' AND claimed_by=%s AND lease_expires_at>%s
                    RETURNING delivery_id""",
                    (available, (error or "delivery failed")[:500], delivery_id, worker_id, now),
                ).fetchone()
        return changed is not None
