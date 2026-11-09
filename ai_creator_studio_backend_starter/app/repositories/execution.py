"""Execution-attempt persistence port and SQLite SQL adapter."""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExecutionRepository(Protocol):
    def apply_job_transition_in_transaction(self, connection: Any, *, job_id: str,
                                            target_status: str, updates: dict[str, Any],
                                            finished_at: str) -> None: ...
    def create_initial_attempt_in_transaction(self, connection: Any, *, job_id: str,
                                              execution_id: str, provider: str,
                                              started_at: str) -> None: ...


class SQLiteExecutionRepository:
    """Mutates the latest Execution using the caller's Job transaction."""
    backend = "sqlite"

    def create_initial_attempt_in_transaction(self, connection: Any, *, job_id: str,
                                              execution_id: str, provider: str,
                                              started_at: str) -> None:
        connection.execute(
            """INSERT INTO generation_executions
            (execution_id,job_id,attempt_no,status,provider,started_at)
            VALUES(?,?,1,'queued',?,?)""",
            (execution_id, job_id, provider, started_at),
        )

    def apply_job_transition_in_transaction(self, connection: Any, *, job_id: str,
                                            target_status: str, updates: dict[str, Any],
                                            finished_at: str) -> None:
        if target_status in {"succeeded", "failed"}:
            connection.execute(
                """UPDATE generation_executions SET status=?,finished_at=?,error_code=?
                WHERE job_id=? AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=?)""",
                (target_status, finished_at, updates.get("error_code"), job_id, job_id),
            )
        elif target_status == "running":
            connection.execute(
                """UPDATE generation_executions SET status='running',provider_request_id=?
                WHERE job_id=? AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=?)""",
                (updates.get("provider_request_id"), job_id, job_id),
            )
        elif target_status == "post_processing":
            connection.execute(
                """UPDATE generation_executions SET status='post_processing',provider_request_id=COALESCE(?,provider_request_id)
                WHERE job_id=? AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=?)""",
                (updates.get("provider_request_id"), job_id, job_id),
            )
        elif target_status == "unknown":
            connection.execute(
                """UPDATE generation_executions SET status='unknown',error_code=?
                WHERE job_id=? AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=?)""",
                (updates.get("error_code"), job_id, job_id),
            )
