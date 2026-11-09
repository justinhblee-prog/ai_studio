"""Operational monitor and optional HTTPS alert webhook dispatcher.

Run as an independent process: python -m app.monitor_worker
The default deployment persists alerts locally and does not send outbound notifications.
"""
from __future__ import annotations
import asyncio
import os
import socket
import uuid
from urllib.parse import urlparse
import httpx
from app import config
from app.worker_repositories import build_operations_repository


WORKER_ID = os.getenv("OPS_MONITOR_WORKER_ID", f"{socket.gethostname()}-ops-{uuid.uuid4().hex[:8]}")
POLL_SECONDS = max(1.0, config.OPS_MONITOR_POLL_SECONDS)


def _webhook_destination() -> str | None:
    value = config.OPS_ALERT_WEBHOOK_URL
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise RuntimeError("OPS_ALERT_WEBHOOK_URL must be an HTTPS URL without embedded credentials")
    return value


def evaluate_once(repository=None) -> list[dict]:
    repository = repository or build_operations_repository()
    return repository.evaluate_operational_alerts(
        required_worker_types=config.REQUIRED_WORKER_TYPES,
        worker_stale_seconds=config.OPS_ALERT_WORKER_STALE_SECONDS,
        queue_age_seconds=config.OPS_ALERT_QUEUE_AGE_SECONDS,
        webhook_destination=_webhook_destination(),
    )


async def dispatch_one(repository=None) -> bool:
    repository = repository or build_operations_repository()
    destination = _webhook_destination()
    if not destination:
        return False
    delivery = repository.claim_alert_delivery(WORKER_ID, lease_seconds=120)
    if delivery is None:
        return False
    headers = {"Content-Type": "application/json"}
    if config.OPS_ALERT_WEBHOOK_TOKEN:
        headers["Authorization"] = f"Bearer {config.OPS_ALERT_WEBHOOK_TOKEN}"
    payload = {
        "event": "ai_creator_studio.operational_alert",
        "alert_id": delivery["alert_id"],
        "fingerprint": delivery["fingerprint"],
        "alert_type": delivery["alert_type"],
        "severity": delivery["severity"],
        "status": delivery["alert_status"],
        "title": delivery["title"],
        "details": delivery["details"],
        "created_at": delivery["created_at"],
    }
    try:
        async with httpx.AsyncClient(timeout=config.OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS,
                                     follow_redirects=False) as client:
            response = await client.post(destination, json=payload, headers=headers)
        if 200 <= response.status_code < 300:
            repository.finish_alert_delivery(delivery["delivery_id"], worker_id=WORKER_ID, delivered=True)
        else:
            repository.finish_alert_delivery(delivery["delivery_id"], worker_id=WORKER_ID, delivered=False,
                error=f"webhook_http_{response.status_code}",
                retry_delay_seconds=min(300, 2 ** min(delivery["attempts"], 8)),
                max_attempts=config.OPS_ALERT_WEBHOOK_MAX_ATTEMPTS)
    except Exception as exc:
        repository.finish_alert_delivery(delivery["delivery_id"], worker_id=WORKER_ID, delivered=False,
            error=type(exc).__name__,
            retry_delay_seconds=min(300, 2 ** min(delivery["attempts"], 8)),
            max_attempts=config.OPS_ALERT_WEBHOOK_MAX_ATTEMPTS)
    return True


async def run_once(repository=None) -> dict:
    repository = repository or build_operations_repository()
    alerts = evaluate_once(repository)
    delivered = await dispatch_one(repository)
    repository.heartbeat_worker(WORKER_ID, "running", {
        "worker_type": "ops_monitor", "poll_seconds": POLL_SECONDS,
        "active_alerts_seen": len(alerts), "webhook_configured": bool(config.OPS_ALERT_WEBHOOK_URL),
        "delivery_attempted": delivered,
    })
    return {"active_alerts": alerts, "delivery_attempted": delivered}


async def run_forever(repository=None) -> None:
    repository = repository or build_operations_repository()
    repository.initialize()
    while True:
        try:
            await run_once(repository)
        except Exception as exc:
            repository.heartbeat_worker(WORKER_ID, "error", {
                "worker_type": "ops_monitor", "error_type": type(exc).__name__})
        await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_forever())
