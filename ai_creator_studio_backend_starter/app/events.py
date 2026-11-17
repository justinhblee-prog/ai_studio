"""B-18 (draft): the event envelope and signing for "job finished" / "review status changed" notices. NOT wired to anything: nothing here sends a request,
reads a secret from the environment or stores a subscription. It fixes the SHAPE so an outgoing webhook, a polling feed or the homepage adapter can share it later.

Envelope (JSON, UTF-8, keys sorted when signed): ``id`` (``evt_`` + 32 hex), ``type`` (one of EVENT_TYPES), ``version`` (1), ``occurred_at`` (UTC ISO-8601 with Z),
``workspace_id``, ``data`` (identifiers and states ONLY: no names, e-mail addresses, prompts, comments, file contents or signed URLs; the receiver fetches details with its own login).
Signature: ``t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<body>">`` so a copied body cannot be replayed outside TOLERANCE_SECONDS. The signing secret is passed in by the caller.
Delivery semantics for the later step: at least once, so receivers de-duplicate on ``id``; no ordering guarantee beyond ``occurred_at``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 1
TOLERANCE_SECONDS = 300
EVENT_TYPES = {
    "job.completed": {"job_id", "status"},
    "job.failed": {"job_id", "status", "error_code"},
    "job.canceled": {"job_id", "status"},
    "review.requested": {"review_id", "asset_id", "status"},
    "review.approved": {"review_id", "asset_id", "status"},
    "review.changes_requested": {"review_id", "asset_id", "status"},
    "review.rejected": {"review_id", "asset_id", "status"},
    "review.withdrawn": {"review_id", "asset_id", "status"},
}
FORBIDDEN_DATA_KEYS = {"comment", "email", "name", "prompt", "url", "signed_url", "token", "password", "secret", "content"}
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class EventError(ValueError):
    pass


def build_event(event_type: str, workspace_id: str, data: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
    """A validated envelope. ``data`` must hold exactly the keys the type declares, every value a short identifier/state string (no free text)."""
    if event_type not in EVENT_TYPES:
        raise EventError(f"unknown event type: {event_type}")
    if not isinstance(workspace_id, str) or not _ID.match(workspace_id):
        raise EventError("workspace_id must be a short identifier")
    if set(data) != EVENT_TYPES[event_type]:
        raise EventError(f"{event_type} data must have exactly: {sorted(EVENT_TYPES[event_type])}")
    for key, value in data.items():
        if key in FORBIDDEN_DATA_KEYS or not isinstance(value, str) or not _ID.match(value):
            raise EventError(f"data.{key} must be a short identifier or state, never free text")
    stamp = datetime.fromtimestamp(time.time() if now is None else now, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": "evt_" + secrets.token_hex(16), "type": event_type, "version": SCHEMA_VERSION, "occurred_at": stamp, "workspace_id": workspace_id, "data": dict(data)}


def serialize(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sign(body: str, secret: bytes, *, now: float | None = None) -> str:
    if not secret or len(secret) < 16:
        raise EventError("signing secret must be at least 16 bytes")
    t = int(time.time() if now is None else now)
    mac = hmac.new(secret, f"{t}.{body}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"t={t},v1={mac}"


def verify(body: str, header: str, secret: bytes, *, now: float | None = None, tolerance: int = TOLERANCE_SECONDS) -> bool:
    """False for any malformed header, wrong signature, or timestamp outside the tolerance (either direction)."""
    m = re.fullmatch(r"t=(\d{1,12}),v1=([0-9a-f]{64})", header or "")
    if not m or not secret:
        return False
    t = int(m.group(1))
    if abs((time.time() if now is None else now) - t) > tolerance:
        return False
    expected = hmac.new(secret, f"{t}.{body}".encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, m.group(2))
