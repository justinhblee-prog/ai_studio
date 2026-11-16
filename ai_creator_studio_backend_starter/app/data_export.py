"""R-065: "download my data" as a ZIP: a workspace export (owner / admin) and an account export (the caller's own records).

A workspace export holds ``manifest.json`` (what is inside and what is NOT), ``data/<table>.json`` (every workspace-scoped table, row by row) and ``assets/<asset_id>.<ext>``
(the stored ORIGINAL file of every live asset, byte for byte, GPS position included: it is the owner's own file). Assets under a rights report (held) are listed, not included.
The file is kept only for ``EXPORT_TTL_HOURS`` (default 24) and is removed when it expires or when the owner deletes it. Created / downloaded / deleted / expired events are written to the
audit record that survives deletions (hashes and counts only). Size is capped (EXPORT_MAX_BYTES) and the number of exports per workspace per day is limited.
Not complete by design (and said so in the manifest): tables that cannot be tied to the workspace by a workspace_id column are listed under ``not_included_tables``; the working copies of
display pictures (derivable) and other people's accounts' data are not included.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import config, data_lifecycle, takedown
from app.assets import store
from app.assets.routes import current_user, require_role
from app.private_file_response import PrivateFileError, open_private_file_response

router = APIRouter(tags=["data-export"])
EXCLUDE = {"deletion_requests", "data_exports", "account_exports", "data_lifecycle_audit", "generation_outbox", "generation_poll_tasks", "generation_worker_heartbeats",
           "generation_ops_alerts", "generation_ops_alert_deliveries", "acs_schema_migrations", "generation_schema_migrations", "rate_limit_hits", "library_items", "library_item_versions"}
DROP_COLUMNS = {"storage_key", "signature", "secret"}
ADMINS = {"owner", "admin"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS data_exports (
        export_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, requested_by TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('ready','expired','deleted')),
        size_bytes INTEGER NOT NULL, checksum_sha256 TEXT NOT NULL, storage_key TEXT, summary_json TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, downloaded_count INTEGER NOT NULL DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS account_exports (
        export_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('ready','expired','deleted')),
        size_bytes INTEGER NOT NULL, checksum_sha256 TEXT NOT NULL, storage_key TEXT, summary_json TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, downloaded_count INTEGER NOT NULL DEFAULT 0)""")
    data_lifecycle.init(db)


def _root() -> Path:
    path = config.ASSET_STORAGE_DIR / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remove_file(storage_key: str | None) -> None:
    if not storage_key:
        return
    root = config.ASSET_STORAGE_DIR.resolve()
    path = (root / storage_key).resolve()
    if root in path.parents:
        path.unlink(missing_ok=True)


def _expire_due(db) -> None:
    now = _now().isoformat()
    for table, who in (("data_exports", "workspace"), ("account_exports", "account")):
        for row in db.execute(f"SELECT * FROM {table} WHERE status='ready' AND expires_at<=?", (now,)).fetchall():
            _remove_file(row["storage_key"])
            db.execute(f"UPDATE {table} SET status='expired', storage_key=NULL WHERE export_id=?", (row["export_id"],))
            data_lifecycle.record(db, "export.expired", scope=who, request_id=row["export_id"], subject=row["workspace_id"] if who == "workspace" else row["user_id"], size_bytes=row["size_bytes"])


def _tables(db) -> list[str]:
    return [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _cols(db, table: str) -> list[str]:
    return [r[1] for r in db.execute(f'PRAGMA table_info("{table}")')]


def _dump_workspace(db, workspace_id: str) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    data, skipped = {}, []
    for table in _tables(db):
        if table in EXCLUDE or table in ("workspaces",):
            continue
        cols = _cols(db, table)
        if "workspace_id" not in cols:
            skipped.append(table)
            continue
        keep = [c for c in cols if c not in DROP_COLUMNS]
        rows = db.execute(f'SELECT {", ".join(chr(34) + c + chr(34) for c in keep)} FROM "{table}" WHERE workspace_id=?', (workspace_id,)).fetchall()
        if rows:
            data[table] = [dict(zip(keep, r)) for r in rows]
    ws = db.execute("SELECT * FROM workspaces WHERE workspace_id=?", (workspace_id,)).fetchone()
    if ws is not None:
        data["workspaces"] = [{k: ws[k] for k in ws.keys()}]
    return data, skipped


def _json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=1, default=str).encode("utf-8")


def _finish(db, table: str, export_id: str, tmp: Path, summary: dict[str, Any], who: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256()
    with tmp.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    key = f"exports/{export_id}.zip"
    final = config.ASSET_STORAGE_DIR / key
    tmp.replace(final)
    created = _now()
    expires = created + timedelta(hours=config.EXPORT_TTL_HOURS)
    size = final.stat().st_size
    if table == "data_exports":
        db.execute("INSERT INTO data_exports(export_id, workspace_id, requested_by, status, size_bytes, checksum_sha256, storage_key, summary_json, created_at, expires_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (export_id, who["workspace_id"], who["user_id"], "ready", size, digest.hexdigest(), key, json.dumps(summary), created.isoformat(), expires.isoformat()))
    else:
        db.execute("INSERT INTO account_exports(export_id, user_id, status, size_bytes, checksum_sha256, storage_key, summary_json, created_at, expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (export_id, who["user_id"], "ready", size, digest.hexdigest(), key, json.dumps(summary), created.isoformat(), expires.isoformat()))
    data_lifecycle.record(db, "export.created", scope="workspace" if table == "data_exports" else "account", request_id=export_id,
                          subject=who.get("workspace_id") or who["user_id"], rows=summary.get("rows"), files=summary.get("assets_included"), size_bytes=size)
    return _out(db, table, export_id)


class ExportOut(BaseModel):
    export_id: str
    scope: str
    workspace_id: str | None
    status: str
    size_bytes: int
    checksum_sha256: str
    created_at: str
    expires_at: str
    downloaded_count: int
    download_path: str | None
    summary: dict[str, Any]


def _out(db, table: str, export_id: str) -> dict[str, Any]:
    row = db.execute(f"SELECT * FROM {table} WHERE export_id=?", (export_id,)).fetchone()
    return {"export_id": row["export_id"], "scope": "workspace" if table == "data_exports" else "account", "workspace_id": row["workspace_id"] if table == "data_exports" else None,
            "status": row["status"], "size_bytes": row["size_bytes"], "checksum_sha256": row["checksum_sha256"], "created_at": row["created_at"], "expires_at": row["expires_at"],
            "downloaded_count": row["downloaded_count"], "download_path": f"/v1/exports/{row['export_id']}/download" if row["status"] == "ready" else None,
            "summary": json.loads(row["summary_json"])}


# ------------------------------------------------------------------------------------------------------------------ workspace export
@router.post("/v1/workspaces/{workspace_id}/exports", status_code=201, response_model=ExportOut, operation_id="createWorkspaceExport")
def create_workspace_export(workspace_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, ADMINS)
    store.initialize()
    with store._connect() as db:
        _init(db)
        _expire_due(db)
        since = (_now() - timedelta(days=1)).isoformat()
        used = db.execute("SELECT COUNT(*) AS n FROM data_exports WHERE workspace_id=? AND created_at>=?", (workspace_id, since)).fetchone()["n"]
        if used >= config.EXPORT_DAILY_LIMIT_PER_WORKSPACE:
            from app import rate_limit
            oldest = db.execute("SELECT MIN(created_at) AS t FROM data_exports WHERE workspace_id=? AND created_at>=?", (workspace_id, since)).fetchone()["t"]
            wait, est = rate_limit.seconds_until_window_frees(oldest, 86400)
            raise rate_limit.too_many("EXPORT_LIMIT", f"at most {config.EXPORT_DAILY_LIMIT_PER_WORKSPACE} exports per workspace per day", wait, estimated=est)
        data, skipped = _dump_workspace(db, workspace_id)
        assets, held, total = [], [], 0
        for row in db.execute("SELECT asset_id, original_filename, media_type, size_bytes FROM assets WHERE workspace_id=? AND deleted_at IS NULL ORDER BY created_at, asset_id", (workspace_id,)).fetchall():
            if takedown.state_of(row["asset_id"]) is not None:
                held.append(row["asset_id"])
                continue
            path = store.storage_path(row["asset_id"])
            if path is None or not path.is_file():
                continue
            assets.append((row, path))
            total += path.stat().st_size
        if total > config.EXPORT_MAX_BYTES:
            raise HTTPException(status_code=413, detail={"code": "EXPORT_TOO_LARGE", "message": f"the files are {total} bytes, the limit is {config.EXPORT_MAX_BYTES}; ask support for a split export"})
        export_id = "exp_" + uuid.uuid4().hex
        tmp = _root() / f"{export_id}.partial"
        files_meta = []
        try:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
                for row, path in assets:
                    arc = f"assets/{row['asset_id']}{path.suffix.lower()}"
                    sha = hashlib.sha256()
                    with path.open("rb") as src, zf.open(arc, "w", force_zip64=True) as dst:
                        for chunk in iter(lambda: src.read(1024 * 1024), b""):
                            sha.update(chunk); dst.write(chunk)
                    files_meta.append({"asset_id": row["asset_id"], "path": arc, "original_filename": row["original_filename"], "media_type": row["media_type"], "size_bytes": path.stat().st_size, "sha256": sha.hexdigest()})
                for table, rows in data.items():
                    zf.writestr(f"data/{table}.json", _json(rows))
                manifest = {"export_id": export_id, "scope": "workspace", "workspace_id": workspace_id, "created_at": _now().isoformat(), "format": 1,
                            "tables_included": sorted(data), "not_included_tables": skipped, "assets": files_meta, "held_assets_not_included": held,
                            "notes": ["assets are the stored originals, byte for byte (a GPS position in a picture is still in it)", "display pictures are derivable and not included",
                                      "other accounts' own data (consents, profiles) is not included", "tables listed under not_included_tables cannot be tied to this workspace by a workspace_id column"]}
                zf.writestr("manifest.json", _json(manifest))
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        summary = {"tables_included": sorted(data), "rows": sum(len(v) for v in data.values()), "assets_included": len(files_meta), "assets_held": len(held), "not_included_tables": skipped}
        return _finish(db, "data_exports", export_id, tmp, summary, {"workspace_id": workspace_id, "user_id": user_id})


@router.get("/v1/workspaces/{workspace_id}/exports", response_model=list[ExportOut], operation_id="listWorkspaceExports")
def list_workspace_exports(workspace_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, ADMINS)
    store.initialize()
    with store._connect() as db:
        _init(db)
        _expire_due(db)
        ids = [r["export_id"] for r in db.execute("SELECT export_id FROM data_exports WHERE workspace_id=? ORDER BY created_at DESC", (workspace_id,)).fetchall()]
        return [_out(db, "data_exports", i) for i in ids]


# ------------------------------------------------------------------------------------------------------------------- account export
def _user_rows(db, table: str, column: str, user_id: str, drop: set[str] = frozenset()) -> list[dict[str, Any]]:
    if table not in _tables(db) or column not in _cols(db, table):
        return []
    cols = [c for c in _cols(db, table) if c not in DROP_COLUMNS and c not in drop]
    rows = db.execute(f'SELECT {", ".join(chr(34) + c + chr(34) for c in cols)} FROM "{table}" WHERE "{column}"=?', (user_id,)).fetchall()
    return [dict(zip(cols, r)) for r in rows]


@router.post("/v1/me/exports", status_code=201, response_model=ExportOut, operation_id="createAccountExport")
def create_account_export(user_id: str = Depends(current_user)):
    store.initialize()
    with store._connect() as db:
        _init(db)
        _expire_due(db)
        since = (_now() - timedelta(days=1)).isoformat()
        if db.execute("SELECT COUNT(*) AS n FROM account_exports WHERE user_id=? AND created_at>=?", (user_id, since)).fetchone()["n"] >= config.EXPORT_DAILY_LIMIT_PER_WORKSPACE:
            from app import rate_limit
            oldest = db.execute("SELECT MIN(created_at) AS t FROM account_exports WHERE user_id=? AND created_at>=?", (user_id, since)).fetchone()["t"]
            wait, est = rate_limit.seconds_until_window_frees(oldest, 86400)
            raise rate_limit.too_many("EXPORT_LIMIT", f"at most {config.EXPORT_DAILY_LIMIT_PER_WORKSPACE} exports per day", wait, estimated=est)
        data = {
            "memberships": _user_rows(db, "workspace_members", "user_id", user_id), "consents": _user_rows(db, "consents", "user_id", user_id),
            "legal_acceptances": _user_rows(db, "legal_acceptances", "user_id", user_id), "deletion_requests": _user_rows(db, "deletion_requests", "user_id", user_id),
            "market_profile": _user_rows(db, "market_profiles", "user_id", user_id), "market_listings_created": _user_rows(db, "market_listings", "created_by", user_id),
            "reviews_requested": _user_rows(db, "asset_reviews", "requested_by", user_id), "content_reports_filed": _user_rows(db, "content_reports", "reporter_id", user_id),
            "market_reports_filed": _user_rows(db, "market_reports", "reporter_id", user_id)}
        data = {k: v for k, v in data.items() if v}
        owned = [m["workspace_id"] for m in data.get("memberships", []) if m.get("role") == "owner"]
        export_id = "acx_" + uuid.uuid4().hex
        tmp = _root() / f"{export_id}.partial"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for table, rows in data.items():
                zf.writestr(f"data/{table}.json", _json(rows))
            zf.writestr("manifest.json", _json({"export_id": export_id, "scope": "account", "created_at": _now().isoformat(), "format": 1, "tables_included": sorted(data),
                                                "workspaces_you_own": owned, "notes": ["the CONTENT of your workspaces is not in this file: export each workspace you own separately",
                                                                                      "your name and e-mail address are kept by the sign-in service, not by this server"]}))
        summary = {"tables_included": sorted(data), "rows": sum(len(v) for v in data.values()), "workspaces_you_own": owned}
        return _finish(db, "account_exports", export_id, tmp, summary, {"user_id": user_id})


@router.get("/v1/me/exports", response_model=list[ExportOut], operation_id="listAccountExports")
def list_account_exports(user_id: str = Depends(current_user)):
    store.initialize()
    with store._connect() as db:
        _init(db)
        _expire_due(db)
        ids = [r["export_id"] for r in db.execute("SELECT export_id FROM account_exports WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()]
        return [_out(db, "account_exports", i) for i in ids]


# ------------------------------------------------------------------------------------------------------------------ download / delete
def _find(db, export_id: str, user_id: str) -> tuple[str, Any]:
    """(table, row) when the caller may touch this export, else 404 (no difference between 'not yours' and 'does not exist')."""
    row = db.execute("SELECT * FROM data_exports WHERE export_id=?", (export_id,)).fetchone()
    if row is not None:
        from app.ports.workspace import get_workspace_port
        role = get_workspace_port().role(row["workspace_id"], user_id)
        if role in ADMINS:
            return "data_exports", row
        raise HTTPException(status_code=404, detail="Export not found")
    row = db.execute("SELECT * FROM account_exports WHERE export_id=? AND user_id=?", (export_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return "account_exports", row


@router.get("/v1/exports/{export_id}/download", operation_id="downloadExport", responses={200: {"content": {"application/zip": {}}}})
def download_export(export_id: str, user_id: str = Depends(current_user)):
    store.initialize()
    with store._connect() as db:
        _init(db)
        _expire_due(db)
        table, row = _find(db, export_id, user_id)
        from app import rate_limit    # R-067
        rate_limit.check("download", user_id, row["workspace_id"] if table == "data_exports" else None)
        if row["status"] != "ready" or not row["storage_key"]:
            raise HTTPException(status_code=410, detail={"code": "EXPORT_GONE", "message": f"this export is {row['status']}; create a new one"})
        path = (config.ASSET_STORAGE_DIR / row["storage_key"]).resolve()
        if config.ASSET_STORAGE_DIR.resolve() not in path.parents or not path.is_file():
            raise HTTPException(status_code=410, detail={"code": "EXPORT_GONE", "message": "the file is no longer available; create a new export"})
        try:
            response = open_private_file_response(path, media_type="application/zip", filename=f"{export_id}.zip", expected_size=row["size_bytes"], expected_sha256=row["checksum_sha256"], inline=False)
        except PrivateFileError as exc:
            raise HTTPException(status_code=409, detail="The export file failed its integrity check") from exc
        db.execute(f"UPDATE {table} SET downloaded_count=downloaded_count+1 WHERE export_id=?", (export_id,))
        data_lifecycle.record(db, "export.downloaded", scope="workspace" if table == "data_exports" else "account", request_id=export_id,
                              subject=row["workspace_id"] if table == "data_exports" else row["user_id"], size_bytes=row["size_bytes"])
    return response


@router.delete("/v1/exports/{export_id}", status_code=204, operation_id="deleteExport")
def delete_export(export_id: str, user_id: str = Depends(current_user)):
    store.initialize()
    with store._connect() as db:
        _init(db)
        table, row = _find(db, export_id, user_id)
        if row["status"] == "ready":
            _remove_file(row["storage_key"])
            db.execute(f"UPDATE {table} SET status='deleted', storage_key=NULL WHERE export_id=?", (export_id,))
            data_lifecycle.record(db, "export.deleted", scope="workspace" if table == "data_exports" else "account", request_id=export_id,
                                  subject=row["workspace_id"] if table == "data_exports" else row["user_id"], size_bytes=row["size_bytes"])
    return None
