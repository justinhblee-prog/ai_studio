"""PostgreSQL Outbox adapter with SKIP LOCKED and lease-owner fencing.

Not wired into the runtime repository factory until live multi-instance tests pass.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.postgres import connect
from app.repositories.lease_validation import validate_worker_id, validate_worker_lease


class PostgreSQLOutboxRepository:
    backend = "postgresql"

    @staticmethod
    def _jsonb(value: Any):
        try:
            from psycopg.types.json import Jsonb
            return Jsonb(value)
        except ImportError as exc:
            raise RuntimeError("psycopg 3 is required for PostgreSQL Outbox repository") from exc

    def get_job(self, job_id: str):
        from app.repositories.postgres_job import PostgreSQLJobRepository
        return PostgreSQLJobRepository().get(job_id)

    def claim_next_outbox(self, worker_id: str, lease_seconds: int = 60):
        validate_worker_lease(worker_id, lease_seconds)
        now = datetime.now(timezone.utc)
        lease_expires = now + timedelta(seconds=lease_seconds)
        with connect() as conn:
            # A dispatch lease that expires after a provider POST is ambiguous. Quarantine it;
            # never put it back into pending because the provider may have accepted the request.
            expired = conn.execute(
                """SELECT event_id,job_id FROM generation_outbox
                WHERE status='processing' AND lease_expires_at <= %s
                ORDER BY lease_expires_at,event_id FOR UPDATE SKIP LOCKED""", (now,)
            ).fetchall()
            for item in expired:
                conn.execute(
                    """UPDATE generation_outbox SET status='needs_reconciliation',
                    last_error='Worker lease expired after dispatch began; provider acceptance is unknown. Automatic replay suppressed.',
                    claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL
                    WHERE event_id=%s AND status='processing' AND lease_expires_at <= %s""",
                    (item["event_id"], now),
                )
                conn.execute(
                    """UPDATE generation_jobs SET error_code='PROVIDER_START_UNKNOWN',
                    message='Provider dispatch outcome is unknown; manual reconciliation required.',
                    updated_at=%s,version=version+1 WHERE job_id=%s AND status='queued'""",
                    (now, item["job_id"]),
                )
                conn.execute(
                    """UPDATE generation_executions SET status='unknown',error_code='PROVIDER_START_UNKNOWN'
                    WHERE job_id=%s AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=%s)""",
                    (item["job_id"], item["job_id"]),
                )
                conn.execute(
                    """INSERT INTO generation_job_events
                    (job_id,from_status,to_status,event_type,payload_json,created_at)
                    VALUES (%s,'queued','queued','OUTBOX_LEASE_EXPIRED_UNKNOWN',%s,%s)""",
                    (item["job_id"], self._jsonb({"outbox_event_id": item["event_id"]}), now),
                )

            claimed = conn.execute(
                """WITH candidate AS (
                    SELECT event_id FROM generation_outbox
                    WHERE status='pending' AND available_at <= %s
                    ORDER BY created_at,event_id LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE generation_outbox o SET status='processing',attempts=o.attempts+1,
                    claimed_by=%s,claimed_at=%s,lease_expires_at=%s
                FROM candidate c WHERE o.event_id=c.event_id
                RETURNING o.*""",
                (now, worker_id, now, lease_expires),
            ).fetchone()
            return claimed

    def complete_outbox_submission(self, event_id: str, job_id: str,
                                   provider_request_id: str, worker_id: str):
        validate_worker_id(worker_id)
        if not isinstance(event_id, str) or not event_id.strip() or not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("event_id and job_id must be non-empty strings")
        if not isinstance(provider_request_id, str) or not provider_request_id.strip():
            raise ValueError("provider_request_id must be a non-empty string")
        from app.job_state import ALLOWED_TRANSITIONS, InvalidJobTransition
        now = datetime.now(timezone.utc)
        with connect() as conn:
            outbox = conn.execute(
                """SELECT status,claimed_by,lease_expires_at FROM generation_outbox
                WHERE event_id=%s AND job_id=%s FOR UPDATE""", (event_id, job_id)
            ).fetchone()
            job = conn.execute("SELECT status FROM generation_jobs WHERE job_id=%s FOR UPDATE", (job_id,)).fetchone()
            if (outbox is None or job is None or outbox["status"] != "processing"
                    or outbox["claimed_by"] != worker_id or outbox["lease_expires_at"] is None
                    or outbox["lease_expires_at"] <= now):
                raise RuntimeError("Outbox lease is expired or not owned by this worker")
            current = job["status"]
            if "running" not in ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise InvalidJobTransition(f"Job status transition not allowed: {current} -> running")
            changed_job = conn.execute(
                """UPDATE generation_jobs SET status='running',provider_request_id=%s,
                message='Generation submitted; poll the job endpoint for status.',updated_at=%s,
                version=version+1 WHERE job_id=%s AND status=%s RETURNING job_id""",
                (provider_request_id, now, job_id, current),
            ).fetchone()
            if changed_job is None:
                raise RuntimeError("Job state changed during Outbox finalization")
            changed_outbox = conn.execute(
                """UPDATE generation_outbox SET status='processed',processed_at=%s,
                lease_expires_at=NULL,last_error=NULL,claimed_by=NULL,claimed_at=NULL
                WHERE event_id=%s AND job_id=%s AND status='processing' AND claimed_by=%s
                AND lease_expires_at>%s RETURNING event_id""",
                (now, event_id, job_id, worker_id, now),
            ).fetchone()
            if changed_outbox is None:
                raise RuntimeError("Outbox lease was lost during finalization")
            conn.execute(
                """UPDATE generation_executions SET status='running',provider_request_id=%s
                WHERE job_id=%s AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=%s)""",
                (provider_request_id, job_id, job_id),
            )
            conn.execute(
                """INSERT INTO generation_job_events
                (job_id,from_status,to_status,event_type,payload_json,created_at)
                VALUES (%s,%s,'running','PROVIDER_SUBMITTED',%s,%s)""",
                (job_id, current, self._jsonb({"provider_request_id": provider_request_id,
                                                "outbox_event_id": event_id}), now),
            )
            conn.execute(
                """INSERT INTO generation_poll_tasks
                (task_id,job_id,phase,status,attempts,available_at,created_at,updated_at)
                VALUES (%s,%s,'status','pending',0,%s,%s,%s)""",
                ("poll_" + uuid.uuid4().hex, job_id, now, now, now),
            )
        return self.get_job(job_id)

    def mark_outbox_unknown(self, event_id: str, job_id: str, error: str, worker_id: str) -> bool:
        validate_worker_id(worker_id)
        if not isinstance(event_id, str) or not event_id.strip() or not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("event_id and job_id must be non-empty strings")
        if not isinstance(error, str):
            raise ValueError("error must be a string")
        now = datetime.now(timezone.utc)
        safe_error = (error or "Provider dispatch outcome is unknown.")[:500]
        with connect() as conn:
            changed = conn.execute(
                """UPDATE generation_outbox SET status='needs_reconciliation',last_error=%s,
                lease_expires_at=NULL,claimed_by=NULL,claimed_at=NULL
                WHERE event_id=%s AND job_id=%s AND status='processing' AND claimed_by=%s
                AND lease_expires_at>%s RETURNING event_id""",
                (safe_error, event_id, job_id, worker_id, now),
            ).fetchone()
            if changed is None:
                return False
            conn.execute(
                """UPDATE generation_jobs SET error_code='PROVIDER_START_UNKNOWN',
                message='Provider dispatch outcome is unknown; manual reconciliation required.',
                updated_at=%s,version=version+1 WHERE job_id=%s AND status='queued'""", (now, job_id)
            )
            conn.execute(
                """UPDATE generation_executions SET status='unknown',error_code='PROVIDER_START_UNKNOWN'
                WHERE job_id=%s AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=%s)""",
                (job_id, job_id),
            )
            conn.execute(
                """INSERT INTO generation_job_events
                (job_id,from_status,to_status,event_type,payload_json,created_at)
                VALUES (%s,'queued','queued','PROVIDER_START_UNKNOWN',%s,%s)""",
                (job_id, self._jsonb({"outbox_event_id": event_id, "error": safe_error}), now),
            )
            return True

    def heartbeat_worker(self, worker_id: str, state: str, metadata: dict[str, Any] | None = None):
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
