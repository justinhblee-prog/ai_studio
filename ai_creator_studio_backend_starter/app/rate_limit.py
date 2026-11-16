"""R-067: request-rate limits for the actions that cost something or can be abused, with ONE 429 format.

Rules (``POLICIES``) count hits per subject in a sliding window. Counting lives in the database (``rate_limit_hits``: hashed subjects, rows older than an hour are removed by the limiter
itself), so it holds across worker processes. A rule whose limit is 0 is off; ``RATE_LIMITS_ENABLED=0`` turns all of them off. Defaults are conservative.
Every refusal is the same shape (HTTP 429, a ``Retry-After`` header and this body) and is recorded (``rate_limit_blocked``: when, scope, workspace, user) so the operator's usage view can show it.
Not covered here, said openly: sign-up and sign-in (handled by the identity provider's own limits), per-IP limits (the server sits behind a proxy whose address handling is not decided), and the older
daily / monthly quotas (jobs, videos, imports, reports, exports, downloads), which keep their own counters but now answer in the same format.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app import config
from app.assets import store
from app.assets.routes import current_user

router = APIRouter(prefix="/internal/ops", tags=["ops-rate-limits"])
KEEP_SECONDS = 3600
# scope -> [(subject kind, config attribute holding the limit, window seconds, environment variable)]
POLICIES: dict[str, list[tuple[str, str, int, str]]] = {
    "upload": [("user", "RATE_UPLOAD_USER_PER_MINUTE", 60, "RATE_UPLOAD_USER_PER_MINUTE"), ("workspace", "RATE_UPLOAD_WORKSPACE_PER_HOUR", 3600, "RATE_UPLOAD_WORKSPACE_PER_HOUR")],
    "generate": [("user", "RATE_GENERATE_USER_PER_MINUTE", 60, "RATE_GENERATE_USER_PER_MINUTE"), ("workspace", "RATE_GENERATE_WORKSPACE_PER_HOUR", 3600, "RATE_GENERATE_WORKSPACE_PER_HOUR")],
    "download": [("user", "RATE_DOWNLOAD_USER_PER_MINUTE", 60, "RATE_DOWNLOAD_USER_PER_MINUTE")],
    "report": [("user", "RATE_REPORT_USER_PER_MINUTE", 60, "RATE_REPORT_USER_PER_MINUTE")],
}


def _hash(kind: str, subject: str) -> str:
    return hashlib.sha256(f"rate:{kind}:{subject}".encode()).hexdigest()[:20]


def _init(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS rate_limit_hits (hit_id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, kind TEXT NOT NULL, subject TEXT NOT NULL, at REAL NOT NULL)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_rate_hits ON rate_limit_hits(scope, kind, subject, at)")
    db.execute("""CREATE TABLE IF NOT EXISTS rate_limit_blocked (
        blocked_id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, scope TEXT NOT NULL, kind TEXT NOT NULL, workspace_id TEXT, user_id TEXT)""")


def too_many(code: str, message: str, retry_after_seconds: int, *, estimated: bool = False, **extra: Any) -> HTTPException:
    """The one 429 answer: ``Retry-After`` header and ``detail = {code, message, retry_after_seconds, retry_at, ...extra}``."""
    seconds = max(1, int(retry_after_seconds))
    detail: dict[str, Any] = {"code": code, "message": message, "retry_after_seconds": seconds,
                              "retry_at": (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(), **extra}
    if estimated:
        detail["retry_estimated"] = True
    return HTTPException(status_code=429, headers={"Retry-After": str(seconds)}, detail=detail)


def seconds_until_window_frees(oldest_iso: str | None, window_seconds: int, fallback: int = 3600) -> tuple[int, bool]:
    """(seconds, estimated?) until the oldest counted event leaves a rolling window; the fallback is flagged as an estimate."""
    if not oldest_iso:
        return fallback, True
    try:
        oldest = datetime.fromisoformat(oldest_iso)
        oldest = oldest if oldest.tzinfo else oldest.replace(tzinfo=timezone.utc)
        return max(1, int(window_seconds - (datetime.now(timezone.utc) - oldest).total_seconds()) + 1), False
    except ValueError:
        return fallback, True


def current_limits(scope: str) -> list[tuple[str, int, int]]:
    return [(kind, int(getattr(config, attr)), window) for kind, attr, window, _ in POLICIES[scope] if int(getattr(config, attr)) > 0]


def check(scope: str, user_id: str, workspace_id: str | None = None) -> None:
    """Count one action; raise the 429 when a rule of the scope is already used up. Nothing is counted for a refused action."""
    if not config.RATE_LIMITS_ENABLED:
        return
    rules = [(k, limit, w) for k, limit, w in current_limits(scope) if k == "user" or workspace_id]
    if not rules:
        return
    now = time.time()
    subjects = {"user": user_id, "workspace": workspace_id or ""}
    with store._connect() as db:
        store.initialize()
        _init(db)
        db.execute("DELETE FROM rate_limit_hits WHERE at<?", (now - KEEP_SECONDS,))
        worst: tuple[int, str, int, int] | None = None
        for kind, limit, window in rules:
            sub = _hash(kind, subjects[kind])
            row = db.execute("SELECT COUNT(*) AS n, MIN(at) AS oldest FROM rate_limit_hits WHERE scope=? AND kind=? AND subject=? AND at>=?", (scope, kind, sub, now - window)).fetchone()
            if row["n"] >= limit:
                wait = max(1, int(row["oldest"] + window - now) + 1)
                if worst is None or wait > worst[0]:
                    worst = (wait, kind, limit, window)
        if worst is not None:
            wait, kind, limit, window = worst
            db.execute("INSERT INTO rate_limit_blocked(at, scope, kind, workspace_id, user_id) VALUES (?,?,?,?,?)",
                       (datetime.now(timezone.utc).isoformat(), scope, kind, workspace_id, user_id))
        else:
            for kind, _, _ in rules:
                db.execute("INSERT INTO rate_limit_hits(scope, kind, subject, at) VALUES (?,?,?,?)", (scope, kind, _hash(kind, subjects[kind]), now))
    if worst is not None:      # raised AFTER the transaction was committed, so the refusal itself is kept
        wait, kind, limit, window = worst
        raise too_many("RATE_LIMITED", f"too many {scope} requests; try again shortly", wait, scope=scope, limit=limit, window_seconds=window, per=kind)


# ----------------------------------------------------------------------------------------------------------------- operator view
@router.get("/rate-limits", operation_id="getOpsRateLimits")
async def ops_rate_limits(days: int = 7, user_id: str = Depends(current_user)):
    """The limits in force and how often they refused someone (counts only; no names)."""
    if user_id not in config.OPS_ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Platform operations role required")
    if not 1 <= days <= 90:
        raise HTTPException(status_code=422, detail={"code": "INVALID_RANGE", "message": "days must be 1..90"})
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    policies = [{"scope": scope, "per": kind, "limit": int(getattr(config, attr)), "window_seconds": window, "enabled": config.RATE_LIMITS_ENABLED and int(getattr(config, attr)) > 0, "env": env}
                for scope, rules in POLICIES.items() for kind, attr, window, env in rules]
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = db.execute("SELECT scope, kind, substr(at,1,10) AS day, COUNT(*) AS n FROM rate_limit_blocked WHERE at>=? GROUP BY scope, kind, day ORDER BY day, scope, kind", (since,)).fetchall()
    return {"enabled": config.RATE_LIMITS_ENABLED, "policies": policies, "blocked": [dict(r) for r in rows], "days": days,
            "coverage": {"measured": ["requests refused by these rules (count per day, scope and subject kind)"],
                         "not_measured": ["refusals by the older daily / monthly quotas (jobs, videos, imports, reports, exports, downloads): they answer in the same format but are not counted here",
                                          "sign-up / sign-in attempts (identity provider)", "per-IP limits (not implemented)"]}}
