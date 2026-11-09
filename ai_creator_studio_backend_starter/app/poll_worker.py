"""Durable Provider status-poll and output-persistence worker.

Run independently from the API/outbox dispatcher with: python -m app.poll_worker
Polling is a safe GET operation and may be retried after a lease expires. Provider
submission is never repeated by this worker. All retries are bounded.
"""
from __future__ import annotations
import asyncio
import hashlib
import os
import socket
import uuid
from typing import Any

from app import config
from app.worker_repositories import build_poll_repository

from app.providers.base import ProviderAdapterError
from app.output_store import OutputStoreError, get_stored_output, output_storage_lock, save_provider_output_artifact
from app.job_state import InvalidJobTransition

WORKER_ID = os.getenv("POLL_WORKER_ID", f"poll-{socket.gethostname()}-{uuid.uuid4().hex[:8]}")
POLL_SECONDS = config.POLL_WORKER_POLL_SECONDS
LEASE_SECONDS = config.POLL_WORKER_LEASE_SECONDS
MAX_ATTEMPTS = max(1, config.POLL_RETRY_MAX_ATTEMPTS)


def _backoff(attempt: int) -> float:
    return min(config.POLL_RETRY_MAX_SECONDS,
               config.POLL_RETRY_BASE_SECONDS * (2 ** max(0, attempt - 1)))


def _retry_delay(attempt: int, retry_after: Any = None) -> float:
    delay = _backoff(attempt)
    if isinstance(retry_after, (int, float)) and retry_after >= 0:
        delay = max(delay, min(float(retry_after), config.POLL_RETRY_AFTER_MAX_SECONDS))
    return min(max(delay, 0.0), config.POLL_RETRY_AFTER_MAX_SECONDS)


async def _process_status(task: dict[str, Any], job: dict[str, Any], worker_id: str, repository) -> None:
    from app import main
    provider = main.get_provider_for_job(job)
    result = await provider.status(job["provider_request_id"])
    state = result.get("status", "running")
    if state == "failed":
        repository.fail_provider_poll_task(
            task["task_id"], worker_id, job["job_id"],
            error_code="PROVIDER_GENERATION_FAILED",
            message=result.get("message") or "Provider generation failed.",
            event_type="PROVIDER_FAILED",
        )
        return
    if state == "succeeded" and result.get("output_url"):
        # Job transition + poll phase handoff are one DB transaction. A worker crash
        # cannot leave a post_processing Job attached to a status-poll task.
        repository.mark_provider_succeeded_for_poll(
            task["task_id"], worker_id, job["job_id"], result["output_url"])
        return
    if state == "succeeded" and not result.get("output_url"):
        repository.fail_provider_poll_task(
            task["task_id"], worker_id, job["job_id"],
            error_code="PROVIDER_OUTPUT_MISSING",
            message="Provider reported completion without an output image.",
            event_type="PROVIDER_OUTPUT_MISSING",
        )
        return
    attempt = int(task["attempts"])
    if attempt >= MAX_ATTEMPTS:
        repository.exhaust_poll_task(task["task_id"], worker_id, job["job_id"],
                                         phase="status", error="Provider remained non-terminal after the bounded polling budget.")
        return
    repository.reschedule_poll_task(task["task_id"], worker_id,
        delay_seconds=_retry_delay(attempt, result.get("retry_after_seconds")),
        error="Provider reports the generation is still running.")


async def _renew_output_lease_until_cancelled(task_id: str, worker_id: str, repository) -> None:
    """Keep a long output download fenced by a periodically renewed live lease."""
    interval = max(0.1, min(30.0, LEASE_SECONDS / 3))
    while True:
        await asyncio.sleep(interval)
        renewed = await asyncio.to_thread(
            repository.renew_poll_task_lease, task_id, worker_id, LEASE_SECONDS
        )
        if not renewed:
            raise InvalidJobTransition("Output task lease was lost during output download.")


async def _save_output_with_live_lease(url: str, job_id: str, attempt_id: str,
                                       task_id: str, worker_id: str, repository):
    """Cancel an in-flight download as soon as lease renewal is fenced out."""
    heartbeat = asyncio.create_task(
        _renew_output_lease_until_cancelled(task_id, worker_id, repository)
    )
    download = asyncio.create_task(save_provider_output_artifact(url, job_id, attempt_id))
    try:
        done, _pending = await asyncio.wait(
            {heartbeat, download}, return_when=asyncio.FIRST_COMPLETED
        )
        if heartbeat in done:
            error = heartbeat.exception()
            if error is not None:
                download.cancel()
                await asyncio.gather(download, return_exceptions=True)
                raise error
            raise InvalidJobTransition("Output lease heartbeat stopped unexpectedly.")
        return await download
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)


async def _process_output(task: dict[str, Any], job: dict[str, Any], worker_id: str, repository) -> None:
    from app import main
    provider_output_url = job.get("provider_output_url")
    if not provider_output_url:
        # An output phase without a durable source URL requires operator review.
        repository.exhaust_poll_task(task["task_id"], worker_id, job["job_id"],
                                         phase="persist_output", error="Provider output URL is missing from the durable Job record.")
        return
    attempt_id = f"{task['task_id']}-{int(task['attempts'])}"
    # Shared lock spans file creation through DB reference commit. The cleanup
    # command takes the exclusive form before snapshotting references/deleting.
    with output_storage_lock():
        output_url, storage_key = await _save_output_with_live_lease(
            provider_output_url, job["job_id"], attempt_id,
            task["task_id"], worker_id, repository,
        )
        path = get_stored_output(job["job_id"], storage_key)
        if path is None:
            raise OutputStoreError("Output file was not found after storage.")
        media_type = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}.get(path.suffix, "application/octet-stream")
        checksum_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        finalized = repository.finalize_output_success(
            task["task_id"], worker_id, job["job_id"], storage_key=storage_key,
            media_type=media_type, size_bytes=path.stat().st_size, output_url=output_url,
            checksum_sha256=checksum_sha256,
        )
        if not finalized:
            # This attempt owns a unique immutable file; it can safely remove only
            # its own uncommitted artifact, never another Worker's output.
            path.unlink(missing_ok=True)
            raise InvalidJobTransition("Output task lease was lost before atomic finalization.")


async def process_one(worker_id: str | None = None, repository=None) -> bool:
    worker_id = worker_id or WORKER_ID
    repository = repository or build_poll_repository()
    task = repository.claim_next_poll_task(worker_id, LEASE_SECONDS)
    if task is None:
        return False
    job = repository.get_job(task["job_id"])
    if job is None:
        repository.exhaust_poll_task(task["task_id"], worker_id, task["job_id"],
                                         phase=task["phase"], error="Job record missing for poll task.")
        return True
    if job["status"] in {"succeeded", "failed"}:
        repository.complete_poll_task(task["task_id"], worker_id)
        return True
    try:
        if task["phase"] == "persist_output":
            await _process_output(task, job, worker_id, repository)
        else:
            await _process_status(task, job, worker_id, repository)
    except InvalidJobTransition:
        # Another valid worker may have won the state transition. Re-read before deciding.
        latest = repository.get_job(task["job_id"])
        if latest and latest["status"] in {"succeeded", "failed"}:
            repository.complete_poll_task(task["task_id"], worker_id)
        else:
            _retry_or_exhaust(task, worker_id, job, "Concurrent lifecycle update requires a retry.", repository=repository)
    except Exception as exc:
        retry_after = getattr(exc, "retry_after_seconds", None)
        retryable = getattr(exc, "retryable", True)
        if not retryable:
            repository.exhaust_poll_task(task["task_id"], worker_id, job["job_id"],
                                             phase=task["phase"], error=type(exc).__name__)
        else:
            _retry_or_exhaust(task, worker_id, job, type(exc).__name__, retry_after, repository=repository)
    return True


def _retry_or_exhaust(task: dict[str, Any], worker_id: str, job: dict[str, Any],
                      error: str, retry_after: Any = None, repository=None) -> None:
    repository = repository or build_poll_repository()
    attempt = int(task["attempts"])
    if attempt >= MAX_ATTEMPTS:
        repository.exhaust_poll_task(task["task_id"], worker_id, job["job_id"],
                                         phase=task["phase"], error=error)
        return
    repository.reschedule_poll_task(task["task_id"], worker_id,
        delay_seconds=_retry_delay(attempt, retry_after), error=error)
    if task["phase"] == "persist_output":
        repository.update_job(job["job_id"], {
            "error_code": "OUTPUT_SAVE_PENDING",
            "message": "Output storage is temporarily unavailable; the polling worker will retry."},
            event_type="OUTPUT_PERSIST_RETRYABLE_ERROR")


async def run_forever(repository=None) -> None:
    repository = repository or build_poll_repository()
    repository.initialize()
    while True:
        repository.heartbeat_worker(WORKER_ID, "running", {
            "worker_type": "provider_poll", "poll_seconds": POLL_SECONDS,
            "max_attempts": MAX_ATTEMPTS})
        did_work = await process_one(WORKER_ID, repository)
        if not did_work:
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_forever())
