"""Private local asset storage and SQLite metadata repository for PoC deployments."""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import config
from app.storage import get_storage


@contextmanager
def _connect():
    # Asset metadata and Generation Jobs share the explicit storage selection.
    # PostgreSQL selection fails closed until a live-tested adapter exists.
    db = get_storage().connect(config.ASSET_DATABASE_PATH)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize() -> None:
    with _connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS workspaces (
            workspace_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS workspace_members (
            workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner','admin','editor','viewer')),
            created_at TEXT NOT NULL,
            PRIMARY KEY(workspace_id, user_id)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS assets (
            asset_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            storage_key TEXT NOT NULL UNIQUE,
            media_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            checksum_sha256 TEXT NOT NULL,
            storage_backend TEXT NOT NULL DEFAULT 'local',
            storage_bucket TEXT NOT NULL DEFAULT 'private_assets',
            gltf_version TEXT NOT NULL,
            embedded_binary INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            deleted_at TEXT
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_assets_owner_workspace ON assets(owner_id, workspace_id, deleted_at)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_assets_workspace ON assets(workspace_id, deleted_at)")
        db.execute("""CREATE TABLE IF NOT EXISTS asset_versions (
            version_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(asset_id),
            workspace_id TEXT NOT NULL, version_number INTEGER NOT NULL,
            storage_key TEXT NOT NULL UNIQUE, media_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL, checksum_sha256 TEXT NOT NULL,
            created_by TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(asset_id, version_number)
        )""")
        # Backwards-compatible locator metadata. Legacy rows are local and use
        # the historical private_assets directory until explicitly migrated.
        for table in ("assets", "asset_versions"):
            columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
            if "storage_backend" not in columns:
                db.execute(f"ALTER TABLE {table} ADD COLUMN storage_backend TEXT NOT NULL DEFAULT 'local'")
            if "storage_bucket" not in columns:
                db.execute(f"ALTER TABLE {table} ADD COLUMN storage_bucket TEXT NOT NULL DEFAULT 'private_assets'")
        db.execute("CREATE INDEX IF NOT EXISTS idx_asset_versions_asset ON asset_versions(asset_id, version_number DESC)")
        db.execute("""CREATE TABLE IF NOT EXISTS asset_relations (
            relation_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
            source_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
            target_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
            relation_type TEXT NOT NULL CHECK(relation_type IN ('derived_from','variant_of','uses_texture','paired_with')),
            created_by TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(source_asset_id, target_asset_id, relation_type),
            CHECK(source_asset_id != target_asset_id)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_asset_relations_workspace ON asset_relations(workspace_id)")
        db.execute("""CREATE TABLE IF NOT EXISTS asset_provenance (
            provenance_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
            asset_id TEXT NOT NULL REFERENCES assets(asset_id), version_number INTEGER,
            event_type TEXT NOT NULL, actor_id TEXT NOT NULL,
            details_json TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_asset_provenance_asset ON asset_provenance(asset_id, created_at DESC)")
        # D2: one row per image whose uploader confirmed the rights. Deleting the asset deletes its row; if the asset stays
        # (shared workspace) an account purge replaces user_id with 'deleted-user' (see scripts/purge_requests.py).
        db.execute("""CREATE TABLE IF NOT EXISTS upload_rights_confirmations (
            asset_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, user_id TEXT NOT NULL,
            depicts_person INTEGER NOT NULL, likeness_consent INTEGER NOT NULL,
            policy_version TEXT NOT NULL, confirmed_at TEXT NOT NULL
        )""")
        # Backfill one immutable baseline version for assets created before versioning existed.
        db.execute("""INSERT OR IGNORE INTO asset_versions(version_id, asset_id, workspace_id, version_number,
            storage_key, media_type, size_bytes, checksum_sha256, created_by, created_at)
            SELECT 'av_legacy_' || asset_id, asset_id, workspace_id, 1, storage_key, media_type,
            size_bytes, checksum_sha256, owner_id, created_at FROM assets""")
        db.execute("""INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id, version_number,
            event_type, actor_id, details_json, created_at)
            SELECT 'ap_legacy_' || a.asset_id, a.workspace_id, a.asset_id, 1,
            'asset.baseline_imported', a.owner_id, '{"source":"legacy_migration"}', a.created_at
            FROM assets a WHERE NOT EXISTS (SELECT 1 FROM asset_provenance p WHERE p.asset_id=a.asset_id)""")
        # One-time-compatible bootstrap for v0.5 databases that predate workspace RBAC.
        db.execute("""INSERT OR IGNORE INTO workspaces(workspace_id, owner_id, created_at)
            SELECT workspace_id, owner_id, MIN(created_at) FROM assets GROUP BY workspace_id""")
        db.execute("""INSERT OR IGNORE INTO workspace_members(workspace_id, user_id, role, created_at)
            SELECT workspace_id, owner_id, 'owner', MIN(created_at) FROM workspaces GROUP BY workspace_id""")
        db.execute("""INSERT OR IGNORE INTO workspace_members(workspace_id, user_id, role, created_at)
            SELECT DISTINCT a.workspace_id, a.owner_id, 'editor', a.created_at FROM assets a
            WHERE a.owner_id != (SELECT w.owner_id FROM workspaces w WHERE w.workspace_id=a.workspace_id)""")


def save_asset(*, owner_id: str, workspace_id: str, filename: str, content: bytes, validated: Any,
               upload_confirmation: dict[str, Any] | None = None) -> dict[str, Any]:
    initialize()
    asset_id = "ast_" + uuid.uuid4().hex
    from app.assets.validation import storage_suffix
    suffix = storage_suffix(validated.media_type)
    storage_key = f"{asset_id}{suffix}"
    root = config.ASSET_STORAGE_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = (root / storage_key).resolve()
    if destination.parent != root:
        raise RuntimeError("Invalid private storage path")
    checksum = hashlib.sha256(content).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    from app.assets.rights import upload_details
    import json as _json
    upload_details_json = _json.dumps(upload_details(upload_confirmation), separators=(",", ":"))
    try:
        with destination.open("xb") as handle:
            handle.write(content)
        with _connect() as db:
            # The connection is in autocommit mode (isolation_level=None), so without an explicit BEGIN each INSERT below
            # would commit on its own and a failure part-way would leave a half-written asset (rollback is a no-op).
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=?", (workspace_id, owner_id)).fetchone():
                raise ValueError("User is not a member of the workspace")
            db.execute("""INSERT INTO assets(asset_id, owner_id, workspace_id, original_filename,
                storage_key, media_type, size_bytes, checksum_sha256, gltf_version,
                embedded_binary, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (asset_id, owner_id, workspace_id, Path(filename).name[:255], storage_key,
                 validated.media_type, validated.size_bytes, checksum, validated.gltf_version or "",
                 int(validated.embedded_binary), now))
            db.execute("""INSERT INTO asset_versions(version_id, asset_id, workspace_id, version_number,
                storage_key, media_type, size_bytes, checksum_sha256, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                ("av_" + uuid.uuid4().hex, asset_id, workspace_id, 1, storage_key,
                 validated.media_type, validated.size_bytes, checksum, owner_id, now))
            db.execute("""INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id,
                version_number, event_type, actor_id, details_json, created_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                ("ap_" + uuid.uuid4().hex, workspace_id, asset_id, 1, "asset.uploaded",
                 owner_id, upload_details_json, now))
            if upload_confirmation is not None and upload_confirmation.get("rights_confirmed"):
                from app.legal import current_versions
                db.execute("""INSERT OR IGNORE INTO upload_rights_confirmations(asset_id, workspace_id, user_id,
                    depicts_person, likeness_consent, policy_version, confirmed_at) VALUES(?,?,?,?,?,?,?)""",
                    (asset_id, workspace_id, owner_id, int(bool(upload_confirmation.get("depicts_person"))),
                     int(bool(upload_confirmation.get("likeness_consent"))), current_versions()["content_policy"], now))
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return get_asset(asset_id, workspace_id)


def save_derived_image_asset(*, asset_id: str, owner_id: str, workspace_id: str,
                              source_asset_id: str, source_version_id: str,
                              source_checksum_sha256: str, filename: str, content: bytes,
                              validated: Any, run_id: str, operation: str,
                              processor_version: str) -> dict[str, Any]:
    """Idempotently persist a deterministic derived image and its lineage.

    The output file is atomically promoted before the SQLite metadata transaction.
    A crash may leave an unreferenced deterministic file; a retry verifies and
    reuses the exact bytes. SQLite/filesystem atomicity is not claimed.
    """
    initialize()
    if not asset_id.startswith("ast_") or not content:
        raise ValueError("A deterministic asset ID and non-empty image are required")
    from app.assets.validation import storage_suffix
    suffix = storage_suffix(validated.media_type)
    storage_key = f"{asset_id}{suffix}"
    root = config.ASSET_STORAGE_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = (root / storage_key).resolve()
    if destination.parent != root:
        raise RuntimeError("Invalid private storage path")
    checksum = hashlib.sha256(content).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    created_file = False
    if destination.exists():
        existing_digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if not hmac.compare_digest(existing_digest, checksum):
            raise ValueError("A deterministic output storage key already contains different bytes")
    else:
        temporary = (root / f".{asset_id}.{uuid.uuid4().hex}.tmp").resolve()
        try:
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                import os
                os.fsync(handle.fileno())
            import os
            os.replace(temporary, destination)
            created_file = True
            try:
                directory_fd = os.open(root, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
    try:
        with _connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=?",
                              (workspace_id, owner_id)).fetchone():
                raise ValueError("User is not a member of the workspace")
            source = db.execute("SELECT asset_id FROM assets WHERE asset_id=? AND workspace_id=? AND deleted_at IS NULL AND media_type LIKE 'image/%'",
                                (source_asset_id, workspace_id)).fetchone()
            source_version = db.execute("SELECT version_id,checksum_sha256 FROM asset_versions WHERE asset_id=? AND workspace_id=? AND version_id=?",
                                        (source_asset_id, workspace_id, source_version_id)).fetchone()
            if source is None or source_version is None or source_version["checksum_sha256"] != source_checksum_sha256:
                raise ValueError("Snapshotted source image version is no longer available or failed integrity checks")
            existing = db.execute("SELECT * FROM assets WHERE asset_id=? AND workspace_id=? AND deleted_at IS NULL",
                                  (asset_id, workspace_id)).fetchone()
            if existing:
                if (existing["checksum_sha256"] != checksum or existing["size_bytes"] != len(content)
                        or existing["media_type"] != validated.media_type or existing["storage_key"] != storage_key):
                    raise ValueError("Existing deterministic Photo output metadata does not match the retry")
                version = db.execute("SELECT version_id,size_bytes,checksum_sha256,storage_key FROM asset_versions WHERE asset_id=? AND version_id=?",
                                      (asset_id, "av_photo_" + run_id.removeprefix("phr_"))).fetchone()
                if (version is None or version["size_bytes"] != len(content)
                        or version["checksum_sha256"] != checksum or version["storage_key"] != storage_key):
                    raise ValueError("Existing deterministic Photo output is missing its verified immutable version")
                relation = db.execute("SELECT 1 FROM asset_relations WHERE source_asset_id=? AND target_asset_id=? AND relation_type='derived_from'",
                                      (asset_id, source_asset_id)).fetchone()
                provenance = db.execute("SELECT 1 FROM asset_provenance WHERE asset_id=? AND event_type='asset.photo_processed'",
                                         (asset_id,)).fetchone()
                if relation is None or provenance is None:
                    raise ValueError("Existing deterministic Photo output is missing its provenance or source relation")
            else:
                version_id = "av_photo_" + run_id.removeprefix("phr_")
                provenance_id = "ap_photo_" + run_id.removeprefix("phr_")
                relation_id = "ar_photo_" + run_id.removeprefix("phr_")
                details = json.dumps({"run_id": run_id, "source_asset_id": source_asset_id,
                    "source_version_id": source_version_id, "source_checksum_sha256": source_checksum_sha256,
                    "operation": operation, "processor_version": processor_version,
                    "is_ai_generated": False, "provider_dispatched": False,
                    "credit_charged": False}, separators=(",", ":"))
                db.execute("""INSERT INTO assets(asset_id,owner_id,workspace_id,original_filename,storage_key,
                    media_type,size_bytes,checksum_sha256,gltf_version,embedded_binary,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (asset_id, owner_id, workspace_id, Path(filename).name[:255], storage_key,
                     validated.media_type, len(content), checksum, "", 0, now))
                db.execute("""INSERT INTO asset_versions(version_id,asset_id,workspace_id,version_number,
                    storage_key,media_type,size_bytes,checksum_sha256,created_by,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (version_id, asset_id, workspace_id, 1, storage_key, validated.media_type,
                     len(content), checksum, owner_id, now))
                db.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                    event_type,actor_id,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)""",
                    (provenance_id, workspace_id, asset_id, 1, "asset.photo_processed", owner_id, details, now))
                db.execute("""INSERT INTO asset_relations(relation_id,workspace_id,source_asset_id,target_asset_id,
                    relation_type,created_by,created_at) VALUES(?,?,?,?,?,?,?)""",
                    (relation_id, workspace_id, asset_id, source_asset_id, "derived_from", owner_id, now))
                db.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                    event_type,actor_id,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)""",
                    ("ap_photo_relation_" + run_id.removeprefix("phr_"), workspace_id, asset_id, None,
                     "asset.relation_created", owner_id,
                     json.dumps({"relation_id": relation_id, "target_asset_id": source_asset_id,
                                 "relation_type": "derived_from"}, separators=(",", ":")), now))
                db.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                    event_type,actor_id,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)""",
                    ("ap_photo_received_" + run_id.removeprefix("phr_"), workspace_id, source_asset_id, None,
                     "asset.relation_received", owner_id,
                     json.dumps({"relation_id": relation_id, "source_asset_id": asset_id,
                                 "relation_type": "derived_from"}, separators=(",", ":")), now))
    except Exception:
        if created_file:
            with _connect() as db:
                committed = db.execute("SELECT 1 FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
            if not committed:
                destination.unlink(missing_ok=True)
        raise
    result = get_asset(asset_id, workspace_id)
    if result is None:
        raise RuntimeError("Derived Photo Asset metadata could not be reloaded")
    return result | {"version_id": "av_photo_" + run_id.removeprefix("phr_"),
                     "version_number": 1, "checksum_sha256": checksum}


def _public(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    value.pop("storage_key", None)
    value["embedded_binary"] = bool(value["embedded_binary"])
    value["asset_kind"] = "image" if str(value["media_type"]).startswith("image/") else "model"
    if value["asset_kind"] == "image":
        value["gltf_version"] = None
    return value


def get_asset(asset_id: str, workspace_id: str) -> dict[str, Any] | None:
    initialize()
    with _connect() as db:
        row = db.execute("SELECT * FROM assets WHERE asset_id=? AND workspace_id=? AND deleted_at IS NULL", (asset_id, workspace_id)).fetchone()
    return _public(row) if row else None


def get_rights_confirmation(asset_id: str, workspace_id: str) -> dict[str, Any] | None:
    """The upload rights record of a live asset in this workspace, or None when no confirmation was recorded
    (assets uploaded before enforcement have none; they stay usable and read as unconfirmed)."""
    initialize()
    with _connect() as db:
        if not db.execute("SELECT 1 FROM assets WHERE asset_id=? AND workspace_id=? AND deleted_at IS NULL", (asset_id, workspace_id)).fetchone():
            raise KeyError(asset_id)
        row = db.execute("""SELECT depicts_person, likeness_consent, policy_version, confirmed_at FROM upload_rights_confirmations
            WHERE asset_id=? AND workspace_id=?""", (asset_id, workspace_id)).fetchone()
    if row is None:
        return None
    return {"depicts_person": bool(row["depicts_person"]), "likeness_consent": bool(row["likeness_consent"]),
            "policy_version": row["policy_version"], "confirmed_at": row["confirmed_at"]}


def list_assets(workspace_id: str, *, kind: str = "all") -> list[dict[str, Any]]:
    initialize()
    if kind not in {"all", "model", "image"}:
        raise ValueError("Unsupported asset kind")
    with _connect() as db:
        if kind == "image":
            rows = db.execute("SELECT * FROM assets WHERE workspace_id=? AND deleted_at IS NULL AND media_type LIKE 'image/%' ORDER BY created_at DESC", (workspace_id,)).fetchall()
        elif kind == "model":
            rows = db.execute("SELECT * FROM assets WHERE workspace_id=? AND deleted_at IS NULL AND media_type LIKE 'model/%' ORDER BY created_at DESC", (workspace_id,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM assets WHERE workspace_id=? AND deleted_at IS NULL ORDER BY created_at DESC", (workspace_id,)).fetchall()
    return [_public(row) for row in rows]


def storage_path(asset_id: str) -> Path | None:
    initialize()
    with _connect() as db:
        row = db.execute("SELECT storage_key FROM assets WHERE asset_id=? AND deleted_at IS NULL", (asset_id,)).fetchone()
    if not row:
        return None
    root = config.ASSET_STORAGE_DIR.resolve()
    path = (root / row["storage_key"]).resolve()
    return path if path.parent == root and path.is_file() else None


def workspace_for_asset(asset_id: str) -> str | None:
    initialize()
    with _connect() as db:
        row = db.execute("SELECT workspace_id FROM assets WHERE asset_id=? AND deleted_at IS NULL", (asset_id,)).fetchone()
    return row["workspace_id"] if row else None

def delete_asset(asset_id: str, workspace_id: str, actor_id: str = "system") -> bool:
    initialize()
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT storage_key FROM assets WHERE asset_id=? AND workspace_id=? AND deleted_at IS NULL", (asset_id, workspace_id)).fetchone()
        if not row:
            return False
        generated_output_reference = db.execute("""SELECT 1 FROM asset_provenance
            WHERE asset_id=? AND event_type IN ('asset.generated_output_imported','asset.photo_processed') LIMIT 1""", (asset_id,)).fetchone()
        if generated_output_reference:
            raise ValueError("Asset is a persisted generated or processed output; use the Output retention workflow before deletion")
        product_table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_assets'").fetchone()
        if product_table:
            product_reference = db.execute("""SELECT 1 FROM product_assets pa
                JOIN products p ON p.product_id=pa.product_id
                WHERE pa.asset_id=? AND p.workspace_id=? AND p.status='ACTIVE' LIMIT 1""",
                (asset_id, workspace_id)).fetchone()
            if product_reference:
                raise ValueError("Asset is referenced by an active Product; update or archive the Product first")
        variant_table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_variant_assets'").fetchone()
        if variant_table:
            variant_reference = db.execute("""SELECT 1 FROM product_variant_assets pva
                JOIN product_variants pv ON pv.variant_id=pva.variant_id
                WHERE pva.asset_id=? AND pv.workspace_id=? AND pv.status='ACTIVE' LIMIT 1""",
                (asset_id, workspace_id)).fetchone()
            if variant_reference:
                raise ValueError("Asset is referenced by an active Product Variant; update or archive the Variant first")
        character_table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='character_assets'").fetchone()
        if character_table:
            character_reference = db.execute("""SELECT 1 FROM character_assets ca
                JOIN characters c ON c.character_id=ca.character_id
                WHERE ca.asset_id=? AND c.workspace_id=? AND c.deleted_at IS NULL LIMIT 1""",
                (asset_id, workspace_id)).fetchone()
            if character_reference:
                raise ValueError("Asset is referenced by a Character; update or delete the Character first")
        for link_table, draft_table, feature_name in (
            ("photo_draft_assets", "photo_drafts", "Photo Draft"),
            ("lookbook_draft_assets", "lookbook_drafts", "Lookbook Draft"),
        ):
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (link_table,)).fetchone()
            if exists:
                referenced = db.execute(f"""SELECT 1 FROM {link_table} links
                    JOIN {draft_table} drafts ON drafts.draft_id=links.draft_id
                    WHERE links.asset_id=? AND drafts.workspace_id=? AND drafts.archived_at IS NULL LIMIT 1""",
                    (asset_id, workspace_id)).fetchone()
                if referenced:
                    raise ValueError(f"Asset is referenced by an active {feature_name}; archive the draft first")
        version_rows = db.execute("SELECT storage_key FROM asset_versions WHERE asset_id=?", (asset_id,)).fetchall()
        keys = {row["storage_key"], *(item["storage_key"] for item in version_rows)}
        now = datetime.now(timezone.utc).isoformat()
        db.execute("UPDATE assets SET deleted_at=? WHERE asset_id=? AND workspace_id=?", (now, asset_id, workspace_id))
        # D2 / 30-day deletion decision: when the asset is deleted its rights record is deleted with it.
        db.execute("DELETE FROM upload_rights_confirmations WHERE asset_id=? AND workspace_id=?", (asset_id, workspace_id))
        db.execute("INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id, version_number, event_type, actor_id, details_json, created_at) VALUES(?,?,?,?,?,?,?,?)",
                   ("ap_" + uuid.uuid4().hex, workspace_id, asset_id, None, "asset.deleted", actor_id, '{"source":"user_delete"}', now))
    root = config.ASSET_STORAGE_DIR.resolve()
    for key in keys:
        path = (root / key).resolve()
        if path.parent == root:
            path.unlink(missing_ok=True)
    return True




def create_workspace(workspace_id: str, owner_id: str) -> dict[str, str]:
    initialize()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute("INSERT INTO workspaces(workspace_id, owner_id, created_at) VALUES(?,?,?)", (workspace_id, owner_id, now))
        db.execute("INSERT INTO workspace_members(workspace_id, user_id, role, created_at) VALUES(?,?,?,?)", (workspace_id, owner_id, "owner", now))
    return {"workspace_id": workspace_id, "owner_id": owner_id, "role": "owner", "created_at": now}


def workspace_role(workspace_id: str, user_id: str) -> str | None:
    initialize()
    with _connect() as db:
        row = db.execute("SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?", (workspace_id, user_id)).fetchone()
    return row["role"] if row else None


def list_workspaces(user_id: str) -> list[dict[str, Any]]:
    initialize()
    with _connect() as db:
        rows = db.execute("""SELECT w.workspace_id, w.owner_id, w.created_at, m.role
            FROM workspaces w JOIN workspace_members m ON m.workspace_id=w.workspace_id
            WHERE m.user_id=? ORDER BY w.created_at DESC""", (user_id,)).fetchall()
    return [dict(row) for row in rows]


def add_workspace_member(workspace_id: str, user_id: str, role: str) -> dict[str, str]:
    initialize()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        db.execute("INSERT INTO workspace_members(workspace_id, user_id, role, created_at) VALUES(?,?,?,?)", (workspace_id, user_id, role, now))
    return {"workspace_id": workspace_id, "user_id": user_id, "role": role, "created_at": now}


def audit_workspace_assets(workspace_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Verify stored asset bytes against immutable upload metadata without exposing paths."""
    initialize()
    with _connect() as db:
        total_row = db.execute(
            "SELECT COUNT(*) AS n FROM assets WHERE workspace_id=? AND deleted_at IS NULL",
            (workspace_id,),
        ).fetchone()
        rows = db.execute(
            "SELECT asset_id, storage_key, size_bytes, checksum_sha256 FROM assets "
            "WHERE workspace_id=? AND deleted_at IS NULL ORDER BY created_at DESC, asset_id LIMIT ? OFFSET ?",
            (workspace_id, limit, offset),
        ).fetchall()
    root = config.ASSET_STORAGE_DIR.resolve()
    items: list[dict[str, Any]] = []
    for row in rows:
        path = (root / row["storage_key"]).resolve()
        if path.parent != root or not path.is_file():
            status = "missing"
        else:
            digest = hashlib.sha256()
            actual_size = 0
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    actual_size += len(chunk)
                    digest.update(chunk)
            if actual_size != row["size_bytes"]:
                status = "size_mismatch"
            elif not hmac.compare_digest(digest.hexdigest(), row["checksum_sha256"]):
                status = "checksum_mismatch"
            else:
                status = "ok"
        items.append({"asset_id": row["asset_id"], "status": status})
    counts = {key: sum(1 for item in items if item["status"] == key)
              for key in ("ok", "missing", "size_mismatch", "checksum_mismatch")}
    return {"workspace_id": workspace_id, "total": int(total_row["n"]),
            "limit": limit, "offset": offset, "checked": len(items),
            "counts": counts, "items": items}


def get_asset_version_record(asset_id: str, workspace_id: str, version_id: str) -> dict[str, Any] | None:
    """Return an internal immutable version record, including private storage key."""
    initialize()
    with _connect() as db:
        row = db.execute("""SELECT v.*,a.original_filename FROM asset_versions v
            JOIN assets a ON a.asset_id=v.asset_id AND a.workspace_id=v.workspace_id
            WHERE v.asset_id=? AND v.workspace_id=? AND v.version_id=? AND a.deleted_at IS NULL""",
            (asset_id, workspace_id, version_id)).fetchone()
    return dict(row) if row else None


class AssetVersionIntegrityError(ValueError):
    """A historical version is missing or no longer matches its immutable metadata."""


def restore_asset_version(*, asset_id: str, workspace_id: str, version_id: str,
                          actor_id: str) -> dict[str, Any]:
    """Restore verified historical bytes as a NEW immutable current version.

    The historical row and file are never modified. The new version is created
    under a unique key, and the current asset pointer plus provenance event are
    committed in one SQLite write transaction. Filesystem/SQLite crash atomicity
    is not claimed; a crash may leave an orphan for the existing dry-run cleanup.
    """
    from app.assets.validation import validate_gltf_upload, validate_image_upload, AssetValidationError
    initialize()
    root = config.ASSET_STORAGE_DIR.resolve()
    with _connect() as db:
        source = db.execute("""SELECT v.*, a.original_filename
            FROM asset_versions v JOIN assets a ON a.asset_id=v.asset_id
            WHERE v.asset_id=? AND v.workspace_id=? AND v.version_id=? AND a.deleted_at IS NULL""",
            (asset_id, workspace_id, version_id)).fetchone()
    if not source:
        raise LookupError("Asset version not found")
    storage_key = source["storage_key"]
    if Path(storage_key).name != storage_key:
        raise AssetVersionIntegrityError("Historical version storage reference is invalid")
    source_path = (root / storage_key).resolve()
    if source_path.parent != root or not source_path.is_file():
        raise AssetVersionIntegrityError("Historical version file is missing")
    try:
        content = source_path.read_bytes()
    except OSError as exc:
        raise AssetVersionIntegrityError("Historical version file cannot be read") from exc
    if len(content) != int(source["size_bytes"]):
        raise AssetVersionIntegrityError("Historical version size does not match its recorded metadata")
    checksum = hashlib.sha256(content).hexdigest()
    if not hmac.compare_digest(checksum, source["checksum_sha256"]):
        raise AssetVersionIntegrityError("Historical version checksum does not match its recorded metadata")
    filename = str(source["original_filename"] or "restored.glb")
    from app.assets.validation import storage_suffix
    suffix = storage_suffix(source["media_type"])
    filename = Path(filename).stem + suffix
    try:
        if str(source["media_type"]).startswith("image/"):
            validated = validate_image_upload(filename, content, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
        else:
            validated = validate_gltf_upload(filename, content, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
    except AssetValidationError as exc:
        raise AssetVersionIntegrityError("Historical version no longer passes its media validation") from exc

    now = datetime.now(timezone.utc).isoformat()
    new_version_id = "av_" + uuid.uuid4().hex
    new_storage_key = f"{asset_id}_{new_version_id}{suffix}"
    destination = (root / new_storage_key).resolve()
    if destination.parent != root:
        raise RuntimeError("Invalid private storage path")
    root.mkdir(parents=True, exist_ok=True)
    created_file = False
    try:
        with _connect() as db:
            # Serialize restore against uploads/restores/deletes before selecting
            # the next version number and changing the current pointer.
            db.execute("BEGIN IMMEDIATE")
            asset = db.execute("SELECT * FROM assets WHERE asset_id=? AND workspace_id=? AND deleted_at IS NULL",
                               (asset_id, workspace_id)).fetchone()
            current_source = db.execute("SELECT 1 FROM asset_versions WHERE asset_id=? AND workspace_id=? AND version_id=?",
                                        (asset_id, workspace_id, version_id)).fetchone()
            if not asset or not current_source:
                raise LookupError("Asset or historical version not found")
            current = db.execute("SELECT COALESCE(MAX(version_number),0) AS n FROM asset_versions WHERE asset_id=?",
                                 (asset_id,)).fetchone()["n"]
            version_number = int(current) + 1
            with destination.open("xb") as handle:
                created_file = True
                handle.write(content)
                handle.flush()
            db.execute("""INSERT INTO asset_versions(version_id, asset_id, workspace_id, version_number,
                storage_key, media_type, size_bytes, checksum_sha256, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (new_version_id, asset_id, workspace_id, version_number, new_storage_key,
                 validated.media_type, validated.size_bytes, checksum, actor_id, now))
            db.execute("""UPDATE assets SET original_filename=?, storage_key=?, media_type=?, size_bytes=?,
                checksum_sha256=?, gltf_version=?, embedded_binary=? WHERE asset_id=? AND workspace_id=?""",
                (filename, new_storage_key, validated.media_type, validated.size_bytes, checksum,
                 validated.gltf_version or "", int(validated.embedded_binary), asset_id, workspace_id))
            import json
            db.execute("""INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id,
                version_number, event_type, actor_id, details_json, created_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                ("ap_" + uuid.uuid4().hex, workspace_id, asset_id, version_number,
                 "asset.version_restored", actor_id,
                 json.dumps({"version_id": new_version_id, "restored_from_version_id": version_id,
                             "restored_from_version_number": int(source["version_number"]),
                             "previous_version": int(current)}, separators=(",", ":")), now))
    except Exception:
        if created_file:
            destination.unlink(missing_ok=True)
        raise
    return get_asset(asset_id, workspace_id) | {"version_number": version_number,
        "version_id": new_version_id, "restored_from_version_id": version_id}


def create_asset_version(*, asset_id: str, workspace_id: str, actor_id: str,
                         filename: str, content: bytes, validated: Any,
                         upload_confirmation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist a new immutable asset version and atomically promote it as current."""
    initialize()
    root = config.ASSET_STORAGE_DIR.resolve(); root.mkdir(parents=True, exist_ok=True)
    from app.assets.validation import storage_suffix
    suffix = storage_suffix(validated.media_type)
    now = datetime.now(timezone.utc).isoformat(); checksum = hashlib.sha256(content).hexdigest()
    version_id = "av_" + uuid.uuid4().hex
    storage_key = f"{asset_id}_{version_id}{suffix}"
    destination = (root / storage_key).resolve()
    if destination.parent != root:
        raise RuntimeError("Invalid private storage path")
    created_file = False
    try:
        with _connect() as db:
            db.execute("BEGIN IMMEDIATE")
            asset = db.execute("SELECT * FROM assets WHERE asset_id=? AND workspace_id=? AND deleted_at IS NULL",
                               (asset_id, workspace_id)).fetchone()
            if not asset:
                raise LookupError("Asset not found")
            current = db.execute("SELECT COALESCE(MAX(version_number),0) AS n FROM asset_versions WHERE asset_id=?",
                                 (asset_id,)).fetchone()["n"]
            version_number = int(current) + 1
            with destination.open("xb") as handle:
                created_file = True
                handle.write(content)
                handle.flush()
            db.execute("""INSERT INTO asset_versions(version_id, asset_id, workspace_id, version_number,
                storage_key, media_type, size_bytes, checksum_sha256, created_by, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (version_id, asset_id, workspace_id, version_number, storage_key, validated.media_type,
                 validated.size_bytes, checksum, actor_id, now))
            db.execute("""UPDATE assets SET original_filename=?, storage_key=?, media_type=?, size_bytes=?,
                checksum_sha256=?, gltf_version=?, embedded_binary=? WHERE asset_id=? AND workspace_id=?""",
                (Path(filename).name[:255], storage_key, validated.media_type, validated.size_bytes,
                 checksum, validated.gltf_version or "", int(validated.embedded_binary), asset_id, workspace_id))
            import json
            db.execute("""INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id,
                version_number, event_type, actor_id, details_json, created_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                ("ap_" + uuid.uuid4().hex, workspace_id, asset_id, version_number,
                 "asset.version_created", actor_id, json.dumps({"version_id": version_id,
                 "previous_version": int(current), **({"rights": dict(upload_confirmation)} if upload_confirmation is not None else {})},
                 separators=(",", ":")), now))
    except Exception:
        if created_file:
            destination.unlink(missing_ok=True)
        raise
    return get_asset(asset_id, workspace_id) | {"version_number": version_number, "version_id": version_id}


ALLOWED_RELATION_TYPES = {"derived_from", "variant_of", "uses_texture", "paired_with"}

def list_asset_versions(asset_id: str, workspace_id: str) -> list[dict[str, Any]]:
    initialize()
    with _connect() as db:
        rows = db.execute("""SELECT v.version_id, v.asset_id, v.workspace_id, v.version_number,
            v.media_type, v.size_bytes, v.checksum_sha256, v.created_by, v.created_at,
            CASE WHEN v.storage_key=a.storage_key THEN 1 ELSE 0 END AS is_current
            FROM asset_versions v JOIN assets a ON a.asset_id=v.asset_id
            WHERE v.asset_id=? AND v.workspace_id=? ORDER BY v.version_number DESC""",
            (asset_id, workspace_id)).fetchall()
    values = [dict(row) for row in rows]
    for item in values:
        item["is_current"] = bool(item["is_current"])
    return values

def list_asset_provenance(asset_id: str, workspace_id: str, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    initialize()
    with _connect() as db:
        rows = db.execute("""SELECT provenance_id, asset_id, version_number, event_type,
            actor_id, details_json, created_at FROM asset_provenance
            WHERE asset_id=? AND workspace_id=? ORDER BY created_at DESC, provenance_id DESC LIMIT ? OFFSET ?""",
            (asset_id, workspace_id, limit, offset)).fetchall()
    import json
    values = []
    for row in rows:
        item = dict(row); item["details"] = json.loads(item.pop("details_json")); values.append(item)
    return values

def create_asset_relation(*, workspace_id: str, source_asset_id: str, target_asset_id: str,
                          relation_type: str, actor_id: str) -> dict[str, Any]:
    if relation_type not in ALLOWED_RELATION_TYPES:
        raise ValueError("Unsupported relation type")
    if source_asset_id == target_asset_id:
        raise ValueError("An asset cannot be related to itself")
    initialize(); now = datetime.now(timezone.utc).isoformat(); relation_id = "ar_" + uuid.uuid4().hex
    import json
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute("SELECT asset_id FROM assets WHERE workspace_id=? AND deleted_at IS NULL AND asset_id IN (?,?)",
                          (workspace_id, source_asset_id, target_asset_id)).fetchall()
        if len(rows) != 2:
            raise LookupError("Both assets must exist in the same workspace")
        if relation_type == "derived_from":
            cycle = db.execute("""WITH RECURSIVE reachable(asset_id) AS (
                SELECT target_asset_id FROM asset_relations
                WHERE workspace_id=? AND source_asset_id=? AND relation_type='derived_from'
                UNION
                SELECT r.target_asset_id FROM asset_relations r
                JOIN reachable p ON r.source_asset_id=p.asset_id
                WHERE r.workspace_id=? AND r.relation_type='derived_from'
            ) SELECT 1 FROM reachable WHERE asset_id=? LIMIT 1""",
                (workspace_id, target_asset_id, workspace_id, source_asset_id)).fetchone()
            if cycle:
                raise ValueError("derived_from relation would create a cycle")
        db.execute("""INSERT INTO asset_relations(relation_id, workspace_id, source_asset_id,
            target_asset_id, relation_type, created_by, created_at) VALUES(?,?,?,?,?,?,?)""",
            (relation_id, workspace_id, source_asset_id, target_asset_id, relation_type, actor_id, now))
        db.execute("""INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id,
            version_number, event_type, actor_id, details_json, created_at) VALUES(?,?,?,?,?,?,?,?)""",
            ("ap_" + uuid.uuid4().hex, workspace_id, source_asset_id, None, "asset.relation_created",
             actor_id, json.dumps({"relation_id": relation_id, "target_asset_id": target_asset_id,
                                  "relation_type": relation_type}, separators=(",", ":")), now))
        db.execute("""INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id,
            version_number, event_type, actor_id, details_json, created_at) VALUES(?,?,?,?,?,?,?,?)""",
            ("ap_" + uuid.uuid4().hex, workspace_id, target_asset_id, None, "asset.relation_received",
             actor_id, json.dumps({"relation_id": relation_id, "source_asset_id": source_asset_id,
                                  "relation_type": relation_type}, separators=(",", ":")), now))
    return {"relation_id": relation_id, "workspace_id": workspace_id, "source_asset_id": source_asset_id,
            "target_asset_id": target_asset_id, "relation_type": relation_type,
            "created_by": actor_id, "created_at": now}


def list_asset_relations(asset_id: str, workspace_id: str) -> list[dict[str, Any]]:
    initialize()
    with _connect() as db:
        rows = db.execute("""SELECT relation_id, workspace_id, source_asset_id, target_asset_id,
            relation_type, created_by, created_at FROM asset_relations
            WHERE workspace_id=? AND (source_asset_id=? OR target_asset_id=?) ORDER BY created_at DESC""",
            (workspace_id, asset_id, asset_id)).fetchall()
    return [dict(row) for row in rows]
