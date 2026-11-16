"""R-065: the audit record of data export and deletion.

``data_lifecycle_audit`` is append-only (the database refuses UPDATE and DELETE) and it SURVIVES deletions: it holds an event name, the scope, the request / export id, a ONE-WAY HASH of
the subject (user or workspace id) and counts. It never holds names, e-mail addresses, file names or content, so keeping it after the data is gone keeps nothing about the person.
How long it is kept is a legal decision (pending); nothing deletes it.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Any

EVENTS = ("export.created", "export.downloaded", "export.deleted", "export.expired", "deletion.requested", "deletion.cancelled", "deletion.completed")


def subject_hash(subject: str | None) -> str | None:
    return hashlib.sha256(("lifecycle-subject:" + subject).encode()).hexdigest()[:20] if subject else None


def init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS data_lifecycle_audit (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, event TEXT NOT NULL, scope TEXT, request_id TEXT, subject_hash TEXT,
        rows INTEGER, files INTEGER, size_bytes INTEGER)""")
    for kind in ("UPDATE", "DELETE"):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS trg_data_lifecycle_audit_no_{kind.lower()} BEFORE {kind} ON data_lifecycle_audit
            BEGIN SELECT RAISE(ABORT, 'data lifecycle audit is append-only'); END""")


def record(db, event: str, *, scope: str | None = None, request_id: str | None = None, subject: str | None = None, rows: int | None = None,
           files: int | None = None, size_bytes: int | None = None, at: str | None = None) -> None:
    """Never raises: an audit failure must not undo a deletion that already happened; it is reported by the caller's own checks."""
    try:
        if event not in EVENTS:
            raise ValueError(event)
        init(db)
        db.execute("INSERT INTO data_lifecycle_audit(at, event, scope, request_id, subject_hash, rows, files, size_bytes) VALUES (?,?,?,?,?,?,?,?)",
                   (at or datetime.now(timezone.utc).isoformat(), event, scope, request_id, subject_hash(subject), rows, files, size_bytes))
    except sqlite3.Error:
        pass
