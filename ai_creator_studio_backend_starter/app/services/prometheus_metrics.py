"""Prometheus text exposition for operational snapshots."""
from __future__ import annotations
from typing import Any


def _label(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def render_operational_metrics(snapshot: dict[str, Any]) -> str:
    lines = [
        "# HELP acs_worker_healthy Worker heartbeat health (1=healthy).",
        "# TYPE acs_worker_healthy gauge",
    ]
    for worker in snapshot.get("workers", []):
        worker_type = _label(worker.get("worker_type", "unknown"))
        lines.append(f'acs_worker_healthy{{worker_type="{worker_type}"}} {1 if worker.get("healthy") else 0}')
    for status, count in sorted(snapshot.get("outbox_counts", {}).items()):
        lines.append(f'acs_outbox_tasks{{status="{_label(status)}"}} {int(count)}')
    for key, count in sorted(snapshot.get("poll_task_counts", {}).items()):
        status, separator, phase = str(key).partition(":")
        if not separator:
            status, phase = str(key), "unknown"
        lines.append(f'acs_poll_tasks{{status="{_label(status)}",phase="{_label(phase)}"}} {int(count)}')
    for field, metric in (("oldest_pending_outbox_age_seconds", "acs_oldest_pending_outbox_age_seconds"),
                          ("oldest_pending_poll_age_seconds", "acs_oldest_pending_poll_age_seconds")):
        value = snapshot.get(field)
        if value is not None:
            lines.append(f"{metric} {float(value):.3f}")
    for key, count in sorted(snapshot.get("alerts", {}).items()):
        status, separator, severity = str(key).partition(":")
        if not separator:
            status, severity = str(key), "unknown"
        lines.append(f'acs_ops_alerts{{status="{_label(status)}",severity="{_label(severity)}"}} {int(count)}')
    return "\n".join(lines) + "\n"
