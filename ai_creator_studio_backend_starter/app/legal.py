"""Legal document acceptance records and user data-deletion requests (SQLite runtime).

Scope and limits (do not overstate):
- Records which user accepted which version of which legal document, and records deletion requests.
- Does NOT delete any data. Deletion requests are recorded as ``pending`` for an operator to process;
  the permanent purge job is not implemented (see LEGAL_IMPLEMENTATION_GAPS L-01).
- Acceptance is not yet enforced by other routes; ``GET /v1/me/legal-status`` reports what is missing.
- SQLite only. There is no PostgreSQL port for these tables yet.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from app.assets.routes import current_user, require_role
from app.assets.store import _connect

router = APIRouter(tags=["legal"])

# Versions of the drafts currently published. Override per deployment with
# LEGAL_DOCUMENT_VERSIONS="terms=2026-12-01,privacy=2026-12-01,content_policy=2026-12-01".
DEFAULT_VERSIONS = {"terms": "draft-2026-11-09", "privacy": "draft-2026-11-09", "content_policy": "draft-2026-11-09"}
REQUEST_STATUSES = ("pending", "cancelled", "completed")


def current_versions() -> dict[str, str]:
    versions = dict(DEFAULT_VERSIONS)
    raw = os.getenv("LEGAL_DOCUMENT_VERSIONS", "").strip()
    for part in raw.split(","):
        key, sep, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if sep and key in versions and value:
            versions[key] = value
    return versions


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _initialize() -> None:
    with _connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS legal_acceptances (
            acceptance_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            document TEXT NOT NULL,
            version TEXT NOT NULL,
            accepted_at TEXT NOT NULL,
            UNIQUE(user_id, document, version)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_legal_acceptances_user ON legal_acceptances(user_id, accepted_at)")
        db.execute("""CREATE TABLE IF NOT EXISTS deletion_requests (
            request_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            scope TEXT NOT NULL CHECK(scope IN ('account','workspace_content')),
            workspace_id TEXT,
            status TEXT NOT NULL CHECK(status IN ('pending','cancelled','completed')),
            reason TEXT,
            requested_at TEXT NOT NULL,
            resolved_at TEXT
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_deletion_requests_user ON deletion_requests(user_id, requested_at)")
        # Optional consents are append-only; the newest row per (user, purpose) is the current state.
        db.execute("""CREATE TABLE IF NOT EXISTS consents (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            purpose TEXT NOT NULL,
            granted INTEGER NOT NULL CHECK(granted IN (0,1)),
            version TEXT NOT NULL,
            changed_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_consents_user_purpose ON consents(user_id, purpose, seq)")
        # At most one open request per user and target.
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_deletion_requests_open
            ON deletion_requests(user_id, scope, COALESCE(workspace_id,'')) WHERE status='pending'""")


class AcceptedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: Literal["terms", "privacy", "content_policy"]
    version: str = Field(min_length=1, max_length=64)


class AcceptanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documents: list[AcceptedDocument] = Field(min_length=1, max_length=3)


class DeletionRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["account", "workspace_content"]
    workspace_id: str | None = Field(default=None, min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=500)


CONSENT_PURPOSES = ("ai_training",)


class ConsentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    granted: bool


def _consent_state(user_id: str) -> list[dict]:
    """Current state per purpose. No row means not granted (default is refusal)."""
    version = current_versions()["privacy"]
    with _connect() as db:
        rows = db.execute("""SELECT c.purpose, c.granted, c.changed_at FROM consents c
            WHERE c.user_id=? AND c.seq=(SELECT MAX(seq) FROM consents WHERE user_id=c.user_id AND purpose=c.purpose)""", (user_id,)).fetchall()
    by_purpose = {r["purpose"]: r for r in rows}
    items = []
    for purpose in CONSENT_PURPOSES:
        row = by_purpose.get(purpose)
        items.append({"purpose": purpose, "granted": bool(row["granted"]) if row else False,
                      "changed_at": row["changed_at"] if row else None, "current_version": version})
    return items


def _status_for(user_id: str) -> dict:
    required = current_versions()
    with _connect() as db:
        rows = db.execute("""SELECT document, version, accepted_at FROM legal_acceptances
            WHERE user_id=? ORDER BY accepted_at, acceptance_id""", (user_id,)).fetchall()
    accepted = {(r["document"], r["version"]) for r in rows}
    missing = [{"document": d, "version": v} for d, v in required.items() if (d, v) not in accepted]
    return {
        "accepted": not missing,
        "required": [{"document": d, "version": v} for d, v in required.items()],
        "missing": missing,
        "history": [{"document": r["document"], "version": r["version"], "accepted_at": r["accepted_at"]} for r in rows],
    }


def _request_row(row) -> dict:
    return {key: row[key] for key in ("request_id", "scope", "workspace_id", "status", "reason", "requested_at", "resolved_at")}


@router.get("/v1/legal/documents")
async def legal_documents():
    """Public: the document versions a user must accept. ``status`` stays ``draft`` until the texts are final."""
    return {"status": "draft", "documents": [{"document": d, "version": v} for d, v in current_versions().items()]}


@router.get("/v1/me/legal-status")
async def legal_status(user_id: str = Depends(current_user)):
    _initialize()
    return _status_for(user_id)


@router.post("/v1/me/legal-acceptances")
async def accept_legal_documents(body: AcceptanceInput, user_id: str = Depends(current_user)):
    _initialize()
    required = current_versions()
    seen: set[str] = set()
    for item in body.documents:
        if item.document in seen:
            raise HTTPException(status_code=422, detail=f"Duplicate document: {item.document}")
        seen.add(item.document)
        if item.version != required[item.document]:
            raise HTTPException(status_code=409, detail=f"{item.document} version is not current; reload the documents")
    now = _now()
    with _connect() as db:
        for item in body.documents:
            db.execute("""INSERT OR IGNORE INTO legal_acceptances(acceptance_id,user_id,document,version,accepted_at)
                VALUES(?,?,?,?,?)""", ("acc_" + uuid.uuid4().hex, user_id, item.document, item.version, now))
    return _status_for(user_id)


@router.post("/v1/me/deletion-requests", status_code=201)
async def create_deletion_request(body: DeletionRequestInput, response: Response, user_id: str = Depends(current_user)):
    """Record a deletion request. Nothing is deleted here; an operator processes pending requests."""
    _initialize()
    if body.scope == "account":
        if body.workspace_id is not None:
            raise HTTPException(status_code=422, detail="workspace_id must be omitted for scope=account")
        workspace_id = None
    else:
        if not body.workspace_id:
            raise HTTPException(status_code=422, detail="workspace_id is required for scope=workspace_content")
        require_role(body.workspace_id, user_id, {"owner"})
        workspace_id = body.workspace_id
    with _connect() as db:
        existing = db.execute("""SELECT * FROM deletion_requests WHERE user_id=? AND scope=?
            AND COALESCE(workspace_id,'')=COALESCE(?,'') AND status='pending'""", (user_id, body.scope, workspace_id)).fetchone()
        if existing:
            response.status_code = 200
            return _request_row(existing)
        request_id = "del_" + uuid.uuid4().hex
        try:
            db.execute("""INSERT INTO deletion_requests(request_id,user_id,scope,workspace_id,status,reason,requested_at)
                VALUES(?,?,?,?, 'pending', ?, ?)""", (request_id, user_id, body.scope, workspace_id, body.reason, _now()))
        except sqlite3.IntegrityError:
            # A concurrent identical request won the unique-open-request index; return it instead of failing.
            existing = db.execute("""SELECT * FROM deletion_requests WHERE user_id=? AND scope=?
                AND COALESCE(workspace_id,'')=COALESCE(?,'') AND status='pending'""", (user_id, body.scope, workspace_id)).fetchone()
            if existing is None:
                raise
            response.status_code = 200
            return _request_row(existing)
        row = db.execute("SELECT * FROM deletion_requests WHERE request_id=?", (request_id,)).fetchone()
        from app import data_lifecycle     # R-065: the request itself is audited (hash of the subject, never the id or the reason)
        data_lifecycle.record(db, "deletion.requested", scope=body.scope, request_id=request_id, subject=workspace_id if body.scope == "workspace_content" else user_id)
    return _request_row(row)


@router.get("/v1/me/deletion-requests")
async def list_deletion_requests(user_id: str = Depends(current_user)):
    _initialize()
    with _connect() as db:
        rows = db.execute("""SELECT * FROM deletion_requests WHERE user_id=?
            ORDER BY requested_at DESC, request_id DESC""", (user_id,)).fetchall()
    return {"items": [_request_row(r) for r in rows]}


@router.delete("/v1/me/deletion-requests/{request_id}", status_code=204)
async def cancel_deletion_request(request_id: str, user_id: str = Depends(current_user)):
    _initialize()
    with _connect() as db:
        row = db.execute("SELECT status FROM deletion_requests WHERE request_id=? AND user_id=?", (request_id, user_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Deletion request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="Only a pending deletion request can be cancelled")
        db.execute("UPDATE deletion_requests SET status='cancelled', resolved_at=? WHERE request_id=?", (_now(), request_id))
        from app import data_lifecycle
        full = db.execute("SELECT scope, workspace_id FROM deletion_requests WHERE request_id=?", (request_id,)).fetchone()
        data_lifecycle.record(db, "deletion.cancelled", scope=full["scope"], request_id=request_id, subject=full["workspace_id"] if full["scope"] == "workspace_content" else user_id)
    return Response(status_code=204)


@router.get("/v1/me/consents")
async def list_consents(user_id: str = Depends(current_user)):
    """Optional consents (default: not granted). Separate from accepting the terms and privacy policy."""
    _initialize()
    return {"items": _consent_state(user_id)}


@router.put("/v1/me/consents/{purpose}")
async def set_consent(purpose: str, body: ConsentInput, user_id: str = Depends(current_user)):
    """Grant or withdraw an optional consent. History is kept; withdrawal takes effect immediately."""
    _initialize()
    if purpose not in CONSENT_PURPOSES:
        raise HTTPException(status_code=404, detail="Unknown consent purpose")
    with _connect() as db:
        db.execute("INSERT INTO consents(user_id,purpose,granted,version,changed_at) VALUES(?,?,?,?,?)",
                   (user_id, purpose, 1 if body.granted else 0, current_versions()["privacy"], _now()))
    return {"items": _consent_state(user_id)}
