"""PostgreSQL Generation Job aggregate adapter (initial vertical slice).

This adapter is intentionally not wired into the runtime factory yet. It must
pass the same contract suite and live multi-instance tests before activation.
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.postgres import connect
from app.job_state import ALLOWED_TRANSITIONS, InvalidJobTransition


class PostgreSQLJobRepository:
    backend = "postgresql"
    _ALLOWED_UPDATES = {"provider_request_id", "output_url", "error_code", "message", "provider_output_url"}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _decode(row: dict[str, Any] | None):
        if row is None:
            return None
        value = dict(row)
        payload = value.pop("payload_json")
        value["payload"] = payload if isinstance(payload, (dict, list)) else json.loads(payload)
        return value

    @staticmethod
    def _jsonb(value: Any):
        try:
            from psycopg.types.json import Jsonb
            return Jsonb(value)
        except ImportError as exc:
            raise RuntimeError("psycopg 3 is required for PostgreSQL Job repository") from exc

    def initialize(self) -> None:
        from app.postgres import apply_migrations
        apply_migrations()

    def create(self, job: dict[str, Any], idempotency_key: str | None = None):
        now = self._now()
        with connect() as conn:
            if idempotency_key:
                # Serialize identical workspace/key requests, including the absent-row case.
                lock_key = f"{job['workspace_id']}:{idempotency_key}"
                conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))
                existing = conn.execute(
                    """SELECT j.*, i.payload_hash AS idem_payload_hash
                    FROM generation_idempotency i JOIN generation_jobs j ON j.job_id=i.job_id
                    WHERE i.workspace_id=%s AND i.idempotency_key=%s""",
                    (job["workspace_id"], idempotency_key),
                ).fetchone()
                if existing:
                    if existing["idem_payload_hash"] != job["payload_hash"]:
                        raise ValueError("Idempotency key was already used with a different payload")
                    return self._decode(existing), False

            conn.execute(
                """INSERT INTO generation_jobs
                (job_id,workspace_id,owner_id,status,provider,model,provider_request_id,output_url,
                 error_code,message,payload_hash,payload_json,provider_output_url,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (job["job_id"], job["workspace_id"], job["owner_id"], job["status"], job["provider"],
                 job.get("model"), job.get("provider_request_id"), job.get("output_url"), job.get("error_code"),
                 job.get("message"), job["payload_hash"], self._jsonb(job["payload"]),
                 job.get("provider_output_url"), now, now),
            )
            conn.execute(
                """INSERT INTO generation_executions
                (execution_id,job_id,attempt_no,status,provider,started_at)
                VALUES (%s,%s,1,'queued',%s,%s)""",
                ("exec_" + uuid.uuid4().hex, job["job_id"], job["provider"], now),
            )
            conn.execute(
                """INSERT INTO generation_job_events
                (job_id,from_status,to_status,event_type,actor_id,payload_json,created_at)
                VALUES (%s,NULL,'queued','JOB_CREATED',%s,%s,%s)""",
                (job["job_id"], job["owner_id"], self._jsonb({}), now),
            )
            if idempotency_key:
                conn.execute(
                    """INSERT INTO generation_idempotency
                    (workspace_id,idempotency_key,payload_hash,job_id,created_at)
                    VALUES (%s,%s,%s,%s,%s)""",
                    (job["workspace_id"], idempotency_key, job["payload_hash"], job["job_id"], now),
                )
            conn.execute(
                """INSERT INTO generation_outbox
                (event_id,job_id,event_type,payload_json,status,available_at,created_at)
                VALUES (%s,%s,'SUBMIT_GENERATION',%s,'pending',%s,%s)""",
                ("obx_" + uuid.uuid4().hex, job["job_id"], self._jsonb({}), now, now),
            )
        return self.get(job["job_id"]), True

    def get(self, job_id: str):
        with connect() as conn:
            row = conn.execute("SELECT * FROM generation_jobs WHERE job_id=%s", (job_id,)).fetchone()
        return self._decode(row)

    def get_idempotent(self, workspace_id: str, key: str):
        with connect() as conn:
            row = conn.execute(
                """SELECT j.*, i.payload_hash AS idem_payload_hash
                FROM generation_idempotency i JOIN generation_jobs j ON j.job_id=i.job_id
                WHERE i.workspace_id=%s AND i.idempotency_key=%s""",
                (workspace_id, key),
            ).fetchone()
        if not row:
            return None
        return self._decode(row), row["idem_payload_hash"]

    def list_for_workspace(self, workspace_id: str, *, limit: int = 50, offset: int = 0):
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError("Invalid workspace job pagination")
        with connect() as conn:
            rows = conn.execute(
                """SELECT * FROM generation_jobs WHERE workspace_id=%s
                ORDER BY created_at DESC, job_id DESC LIMIT %s OFFSET %s""",
                (workspace_id, limit, offset),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def transition(self, job_id: str, target: str, **kwargs: Any):
        updates = kwargs.get("updates") or {}
        actor_id = kwargs.get("actor_id")
        event_type = kwargs.get("event_type", "STATUS_CHANGED")
        if set(updates) - self._ALLOWED_UPDATES:
            raise ValueError("Unsupported job update field")
        now = self._now()
        with connect() as conn:
            row = conn.execute("SELECT * FROM generation_jobs WHERE job_id=%s FOR UPDATE", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            current = row["status"]
            if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise InvalidJobTransition(f"Job status transition not allowed: {current} -> {target}")
            assignments = ["status=%s", "updated_at=%s", "version=version+1"]
            values: list[Any] = [target, now]
            for key, value in updates.items():
                assignments.append(f"{key}=%s")
                values.append(value)
            values.append(job_id)
            conn.execute(f"UPDATE generation_jobs SET {','.join(assignments)} WHERE job_id=%s", values)
            conn.execute(
                """INSERT INTO generation_job_events
                (job_id,from_status,to_status,event_type,actor_id,payload_json,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (job_id, current, target, event_type, actor_id, self._jsonb(updates), now),
            )
            if target in {"succeeded", "failed"}:
                conn.execute(
                    """UPDATE generation_executions SET status=%s,finished_at=%s,error_code=%s
                    WHERE job_id=%s AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=%s)""",
                    (target, now, updates.get("error_code"), job_id, job_id),
                )
            elif target == "running":
                conn.execute(
                    """UPDATE generation_executions SET status='running',provider_request_id=%s
                    WHERE job_id=%s AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=%s)""",
                    (updates.get("provider_request_id"), job_id, job_id),
                )
            elif target == "post_processing":
                conn.execute(
                    """UPDATE generation_executions SET status='post_processing',
                    provider_request_id=COALESCE(%s,provider_request_id)
                    WHERE job_id=%s AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=%s)""",
                    (updates.get("provider_request_id"), job_id, job_id),
                )
        return self.get(job_id)

    def update(self, job_id: str, updates: dict[str, Any], **kwargs: Any):
        if set(updates) - self._ALLOWED_UPDATES:
            raise ValueError("Unsupported job update field")
        event_type = kwargs.get("event_type", "JOB_UPDATED")
        now = self._now()
        with connect() as conn:
            row = conn.execute("SELECT status FROM generation_jobs WHERE job_id=%s FOR UPDATE", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            assignments = [f"{key}=%s" for key in updates]
            values: list[Any] = list(updates.values())
            assignments.extend(["updated_at=%s", "version=version+1"])
            values.extend([now, job_id])
            conn.execute(f"UPDATE generation_jobs SET {','.join(assignments)} WHERE job_id=%s", values)
            conn.execute(
                """INSERT INTO generation_job_events
                (job_id,from_status,to_status,event_type,payload_json,created_at)
                VALUES (%s,%s,%s,%s,%s,%s)""",
                (job_id, row["status"], row["status"], event_type, self._jsonb(updates), now),
            )
        return self.get(job_id)

    def list_executions(self, job_id: str, *, limit: int = 20, cursor: str | None = None):
        if not 1 <= limit <= 200:
            raise ValueError("Invalid execution history limit")
        before_attempt = None
        if cursor:
            try:
                token = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
                prefix, raw_attempt = token.split(":", 1)
                before_attempt = int(raw_attempt)
                if prefix != "exec" or before_attempt < 1:
                    raise ValueError
            except Exception as exc:
                raise ValueError("Invalid execution history cursor") from exc
        query = """SELECT e.execution_id,e.job_id,e.attempt_no,e.status,e.provider,e.provider_request_id,
            e.started_at,e.finished_at,e.error_code,j.model FROM generation_executions e
            JOIN generation_jobs j ON j.job_id=e.job_id WHERE e.job_id=%s"""
        args: list[Any] = [job_id]
        if before_attempt is not None:
            query += " AND e.attempt_no<%s"
            args.append(before_attempt)
        query += " ORDER BY e.attempt_no DESC LIMIT %s"
        args.append(limit + 1)
        with connect() as conn:
            rows = conn.execute(query, args).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        status_map = {"queued": "PENDING", "submitted": "SUBMITTED", "running": "RUNNING", "post_processing": "RUNNING",
                      "succeeded": "SUCCEEDED", "failed": "FAILED", "cancelled": "CANCELED", "canceled": "CANCELED", "unknown": "UNKNOWN"}
        items = [{"id": r["execution_id"], "job_id": r["job_id"], "provider_id": r["provider"],
                  "model_id": r["model"], "attempt_number": r["attempt_no"],
                  "status": ("REQUIRES_RECONCILIATION" if r["status"] == "unknown" and r["error_code"] == "PROVIDER_START_UNKNOWN" else status_map.get(r["status"], "UNKNOWN")),
                  "provider_request_id": r["provider_request_id"],
                  "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                  "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
                  "error_code": r["error_code"], "created_at": r["started_at"].isoformat() if r["started_at"] else None}
                 for r in rows]
        next_cursor = None
        if has_more and rows:
            token = f"exec:{rows[-1]['attempt_no']}".encode("ascii")
            next_cursor = base64.urlsafe_b64encode(token).decode("ascii").rstrip("=")
        return {"data": items, "meta": {"next_cursor": next_cursor, "has_more": has_more}}

    def list_outputs(self, job_id: str):
        with connect() as conn:
            rows = conn.execute(
                """SELECT o.output_id,o.job_id,o.media_type,o.size_bytes,o.created_at,o.checksum_sha256,
                l.status AS asset_link_status,l.asset_id,l.asset_version_id,l.provenance_id,
                COALESCE(l.checksum_sha256,o.checksum_sha256) AS resolved_checksum
                FROM generation_outputs o LEFT JOIN generation_output_asset_links l ON l.output_id=o.output_id
                WHERE o.job_id=%s ORDER BY o.created_at DESC,o.output_id DESC""", (job_id,)
            ).fetchall()
        return {"data": [{"id": r["output_id"], "job_id": r["job_id"], "mime_type": r["media_type"],
                           "size_bytes": r["size_bytes"], "created_at": r["created_at"].isoformat(),
                           "checksum_sha256": r["resolved_checksum"], "asset_link_status": r["asset_link_status"] or "not_queued",
                           "asset_id": r["asset_id"], "asset_version_id": r["asset_version_id"],
                           "provenance_record_id": r["provenance_id"]} for r in rows], "meta": {}}

    def cancel_queued(self, job_id: str, *, actor_id: str, reason: str | None = None):
        now = self._now()
        with connect() as conn:
            # Lock order must match complete_outbox_submission (outbox row, then job row); the reverse order
            # deadlocks when a worker finishes dispatch while the job is still 'queued'.
            outbox = conn.execute(
                """SELECT * FROM generation_outbox WHERE job_id=%s AND event_type='SUBMIT_GENERATION'
                ORDER BY created_at DESC LIMIT 1 FOR UPDATE""", (job_id,)
            ).fetchone()
            job = conn.execute("SELECT * FROM generation_jobs WHERE job_id=%s FOR UPDATE", (job_id,)).fetchone()
            if job is None:
                raise KeyError(job_id)
            if job["status"] != "queued":
                raise ValueError("Only queued jobs can be cancelled; provider submission may already have started.")
            if outbox is None or outbox["status"] != "pending":
                raise ValueError("Job dispatch is already claimed or requires reconciliation; cancellation is unsafe.")
            message = "Cancelled before provider submission."
            if reason:
                message += " Reason: " + reason[:500]
            conn.execute(
                """UPDATE generation_jobs SET status='failed',error_code='JOB_CANCELLED',message=%s,
                updated_at=%s,version=version+1 WHERE job_id=%s AND status='queued'""", (message, now, job_id)
            )
            conn.execute(
                """UPDATE generation_outbox SET status='processed',processed_at=%s,
                last_error='Cancelled before provider submission.' WHERE event_id=%s AND status='pending'""", (now, outbox["event_id"])
            )
            conn.execute(
                """UPDATE generation_executions SET status='failed',finished_at=%s,error_code='JOB_CANCELLED'
                WHERE job_id=%s AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=%s)""", (now, job_id, job_id)
            )
            payload = {"error_code": "JOB_CANCELLED", "reason": (reason or "")[:500], "outbox_event_id": outbox["event_id"]}
            conn.execute(
                """INSERT INTO generation_job_events
                (job_id,from_status,to_status,event_type,actor_id,payload_json,created_at)
                VALUES (%s,'queued','failed','JOB_CANCELLED_BEFORE_DISPATCH',%s,%s,%s)""",
                (job_id, actor_id, self._jsonb(payload), now),
            )
        return self.get(job_id)
