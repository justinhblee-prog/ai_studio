"""Structured access log (L-05): one JSON line per HTTP request, no personal data or secrets by default.

What is logged: UTC time, request id, method, the ROUTE TEMPLATE (never the raw path), status, duration, an optional
workspace id and a pseudonymous actor. What is never logged: query strings (they carry signed-URL signatures), headers,
bodies, bearer tokens, raw paths of unmatched requests, client IPs (unless ACCESS_LOG_CLIENT_IP is on).

The field list and the retention default are engineering choices, NOT a reviewed legal specification (see docs/LAUNCH_STATUS.md).
"""
from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app import config

LOGGER_NAME = "acs.access"
# The complete list of keys a log line can carry. docs/RUNBOOK.md section 3-1 documents exactly these (tests/test_access_log.py
# compares the two). ``error`` appears only for an unhandled exception, ``client_ip`` only when ACCESS_LOG_CLIENT_IP is on.
LOGGED_FIELDS = ("ts", "event", "request_id", "method", "route", "status", "duration_ms", "workspace_id", "actor")
OPTIONAL_FIELDS = ("error", "client_ip")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_WORKSPACE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")


def safe_request_id(candidate: str | None) -> str:
    """Accept a caller-supplied id only if it is a short plain token; anything else (newlines, spaces...) is replaced."""
    return candidate if candidate and _REQUEST_ID.fullmatch(candidate) else uuid.uuid4().hex


def actor_label(user_id: str | None) -> str | None:
    mode = config.ACCESS_LOG_ACTOR
    if not user_id or mode == "none":
        return None
    if mode == "plain":
        return user_id
    salt = (config.ASSET_SIGNING_SECRET or "acs-access-log").encode()
    return "h_" + hashlib.sha256(salt + b"\0" + user_id.encode()).hexdigest()[:16]


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        request_id = safe_request_id(request.headers.get("x-request-id"))
        error = None
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as exc:  # noqa: BLE001 - logged by class name only, then re-raised for the normal 500 handling
            status, error, response = 500, type(exc).__name__, None
            self._emit(request, request_id, status, started, error)
            raise
        response.headers["X-Request-ID"] = request_id
        self._emit(request, request_id, status, started, None)
        return response

    @staticmethod
    def _emit(request: Request, request_id: str, status: int, started: float, error: str | None) -> None:
        logger = logging.getLogger(LOGGER_NAME)
        if not config.ACCESS_LOG_ENABLED or not logger.isEnabledFor(logging.INFO):
            return
        route = request.scope.get("route")
        template = getattr(route, "path", None) or "unmatched"
        workspace = request.path_params.get("workspace_id") or request.query_params.get("workspace_id")
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "event": "http_request",
            "request_id": request_id, "method": request.method, "route": template, "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "workspace_id": workspace if isinstance(workspace, str) and _WORKSPACE_ID.fullmatch(workspace) else None,
            "actor": actor_label(getattr(request.state, "actor", None)),
        }
        if error:
            record["error"] = error
        if config.ACCESS_LOG_CLIENT_IP and request.client:
            record["client_ip"] = request.client.host
        logger.info(json.dumps(record, ensure_ascii=False, separators=(",", ":")))


def configure_access_log() -> logging.Logger:
    """Attach the handler once: a daily-rotating file with bounded retention if ACCESS_LOG_DIR is set, else stdout."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        if getattr(handler, "_acs_access", False):
            logger.removeHandler(handler)
            handler.close()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if config.ACCESS_LOG_DIR is not None:
        directory = Path(config.ACCESS_LOG_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.handlers.TimedRotatingFileHandler(
            directory / "access.log", when="midnight", utc=True, backupCount=config.ACCESS_LOG_RETENTION_DAYS, encoding="utf-8")
    else:
        handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler._acs_access = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    return logger
