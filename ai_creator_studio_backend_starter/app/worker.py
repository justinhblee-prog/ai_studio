"""Standalone durable outbox worker.

Run beside the API process with: python -m app.worker
Expired in-flight submissions are moved to needs_reconciliation, not retried,
because provider-side idempotency is not guaranteed by the current adapters.
"""
from __future__ import annotations
import asyncio
import os
import socket
import uuid
from app.worker_repositories import build_outbox_repository


WORKER_ID = os.getenv("WORKER_ID", f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}")
POLL_SECONDS = float(os.getenv("OUTBOX_POLL_SECONDS", "1.0"))
LEASE_SECONDS = int(os.getenv("OUTBOX_LEASE_SECONDS", "90"))

async def process_one(repository=None) -> bool:
    repository = repository or build_outbox_repository()
    event = repository.claim_next_outbox(WORKER_ID, LEASE_SECONDS)
    if event is None:
        return False
    job = repository.get_job(event["job_id"])
    if job is None:
        repository.mark_outbox_unknown(event["event_id"], event["job_id"], "Job record missing for outbox event.", WORKER_ID)
        return True
    try:
        from app import main
        provider = main.get_provider_for_job(job)
        from app import cost_cap
        if provider.name != cost_cap.MOCK_PROVIDER and cost_cap.kill_switch_on():
            raise RuntimeError("AI_JOBS_DISABLED")
        from app import tryon_inputs   # R-046: signed addresses for picked library items are made NOW (short-lived, never stored)
        payload = tryon_inputs.resolve_payload(job["payload"], for_provider=provider.name != cost_cap.MOCK_PROVIDER)
        if provider.name == cost_cap.MOCK_PROVIDER:
            started = await provider.start(payload)
        else:  # R-037: stay below the provider's own concurrency and rate limits
            from app.throttle import throttle_for
            async with throttle_for(provider.name).slot():
                started = await provider.start(payload)
        request_id = started.get("request_id")
        if not request_id:
            raise RuntimeError("Provider response did not contain a request id.")
        repository.complete_outbox_submission(event["event_id"], job["job_id"], request_id, WORKER_ID)
    except Exception as exc:
        # A timeout/connection error may happen after remote acceptance. Never auto-replay.
        repository.mark_outbox_unknown(event["event_id"], job["job_id"], type(exc).__name__, WORKER_ID)
    return True

async def run_forever(repository=None) -> None:
    repository = repository or build_outbox_repository()
    repository.initialize()
    repository.heartbeat_worker(WORKER_ID, "running", {"worker_type": "outbox", "poll_seconds": POLL_SECONDS})
    while True:
        repository.heartbeat_worker(WORKER_ID, "running", {"worker_type": "outbox", "poll_seconds": POLL_SECONDS})
        did_work = await process_one(repository)
        if not did_work:
            await asyncio.sleep(POLL_SECONDS)

if __name__ == "__main__":
    asyncio.run(run_forever())
