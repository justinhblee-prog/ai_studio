"""PostgreSQL Poll task lease adapter (claim/renew/reschedule/finalize slice).

Provider response interpretation and output persistence remain in later slices.
Not wired into runtime until live PostgreSQL concurrency tests pass.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.postgres import connect
from app.repositories.lease_validation import validate_worker_id, validate_worker_lease


class PostgreSQLPollRepository:
    backend = "postgresql"

    def claim_next_poll_task(self, worker_id: str, lease_seconds: int):
        validate_worker_lease(worker_id, lease_seconds)
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=lease_seconds)
        with connect() as conn:
            # Polling is a safe GET/output persistence operation; expired leases may be requeued.
            conn.execute(
                """UPDATE generation_poll_tasks SET status='pending',claimed_by=NULL,claimed_at=NULL,
                lease_expires_at=NULL,available_at=%s,
                last_error='Poll worker lease expired; safe GET/output task requeued.',updated_at=%s
                WHERE status='processing' AND lease_expires_at <= %s""", (now, now, now)
            )
            return conn.execute(
                """WITH candidate AS (
                    SELECT task_id FROM generation_poll_tasks
                    WHERE status='pending' AND available_at<=%s
                    ORDER BY available_at,created_at,task_id LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE generation_poll_tasks p SET status='processing',attempts=p.attempts+1,
                    claimed_by=%s,claimed_at=%s,lease_expires_at=%s,updated_at=%s
                FROM candidate c WHERE p.task_id=c.task_id
                RETURNING p.*""", (now, worker_id, now, lease_until, now)
            ).fetchone()

    def renew_poll_task_lease(self, task_id: str, worker_id: str, lease_seconds: int) -> bool:
        validate_worker_lease(worker_id, lease_seconds)
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=lease_seconds)
        with connect() as conn:
            row = conn.execute(
                """UPDATE generation_poll_tasks SET lease_expires_at=%s,updated_at=%s
                WHERE task_id=%s AND status='processing' AND claimed_by=%s AND lease_expires_at>%s
                RETURNING task_id""", (lease_until, now, task_id, worker_id, now)
            ).fetchone()
        return row is not None

    def complete_poll_task(self, task_id: str, worker_id: str) -> bool:
        validate_worker_id(worker_id)
        now = datetime.now(timezone.utc)
        with connect() as conn:
            row = conn.execute(
                """UPDATE generation_poll_tasks SET status='completed',claimed_by=NULL,claimed_at=NULL,
                lease_expires_at=NULL,last_error=NULL,updated_at=%s,completed_at=%s
                WHERE task_id=%s AND status='processing' AND claimed_by=%s AND lease_expires_at>=%s
                RETURNING task_id""", (now, now, task_id, worker_id, now)
            ).fetchone()
        return row is not None

    def reschedule_poll_task(self, task_id: str, worker_id: str, *, delay_seconds: float,
                             error: str | None = None, phase: str | None = None) -> bool:
        validate_worker_id(worker_id)
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be non-negative")
        now = datetime.now(timezone.utc)
        available = now + timedelta(seconds=delay_seconds)
        with connect() as conn:
            row = conn.execute(
                """UPDATE generation_poll_tasks SET
                attempts=CASE WHEN %s::text IS NOT NULL AND %s::text<>phase THEN 0 ELSE attempts END,
                status='pending',phase=COALESCE(%s::text,phase),available_at=%s,
                claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,last_error=%s,updated_at=%s
                WHERE task_id=%s AND status='processing' AND claimed_by=%s AND lease_expires_at>=%s
                RETURNING task_id""",
                (phase, phase, phase, available, (error or "")[:500] or None, now, task_id, worker_id, now),
            ).fetchone()
        return row is not None

    def exhaust_poll_task(self, task_id: str, worker_id: str, job_id: str, *, phase: str, error: str) -> bool:
        validate_worker_id(worker_id)
        if phase not in {"status", "persist_output"}:
            raise ValueError("Unsupported poll phase")
        now = datetime.now(timezone.utc)
        safe_error = (error or "Polling retry budget exhausted.")[:500]
        with connect() as conn:
            row = conn.execute(
                """UPDATE generation_poll_tasks SET status='needs_reconciliation',claimed_by=NULL,
                claimed_at=NULL,lease_expires_at=NULL,last_error=%s,updated_at=%s
                WHERE task_id=%s AND job_id=%s AND status='processing' AND claimed_by=%s
                AND lease_expires_at>=%s RETURNING task_id""",
                (safe_error, now, task_id, job_id, worker_id, now),
            ).fetchone()
            if row is None:
                return False
            job = conn.execute("SELECT status FROM generation_jobs WHERE job_id=%s FOR UPDATE", (job_id,)).fetchone()
            if job:
                code = "OUTPUT_SAVE_REQUIRES_REVIEW" if phase == "persist_output" else "PROVIDER_POLL_REQUIRES_REVIEW"
                message = ("Output persistence retry budget exhausted; operator review required."
                           if phase == "persist_output" else "Provider status polling retry budget exhausted; operator review required.")
                conn.execute(
                    """UPDATE generation_jobs SET error_code=%s,message=%s,updated_at=%s,version=version+1
                    WHERE job_id=%s""", (code, message, now, job_id)
                )
                conn.execute(
                    """INSERT INTO generation_job_events
                    (job_id,from_status,to_status,event_type,payload_json,created_at)
                    VALUES (%s,%s,%s,'POLL_RETRY_BUDGET_EXHAUSTED',%s,%s)""",
                    (job_id, job["status"], job["status"], self._jsonb({"phase": phase, "error": safe_error}), now),
                )
            return True

    @staticmethod
    def _jsonb(value: Any):
        try:
            from psycopg.types.json import Jsonb
            return Jsonb(value)
        except ImportError as exc:
            raise RuntimeError("psycopg 3 is required for PostgreSQL Poll repository") from exc
