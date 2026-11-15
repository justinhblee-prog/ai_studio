"""Platform-owned default asset library (R-032): storage, queries and the copy into a workspace. No HTTP here.

Design rules (decided by the design window):
- Library items belong to the platform, not to a workspace. Every signed-in user may read PUBLISHED items; nobody can change or
  delete one through the API. Items are added or changed only through ``upsert_item`` (used by the import script, R-034).
- Using an item COPIES it into the caller's workspace as an ordinary asset (the original id and version are recorded in the copy's
  provenance). A later change or retirement of the item therefore never breaks work already made from the copy, and the copy follows
  the same deletion / retention rules as any other asset.
- An item without a confirmed right (``rights_confirmed``) or with an unknown category, source or model attribute is refused.
- The two library tables carry no workspace_id / owner_id / created_by column on purpose, and are listed as GLOBAL in the purge script.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from app import config

CATEGORIES = ("model", "top", "bottom", "dress", "outer", "bag", "hat", "eyewear", "shoes", "jewelry", "headwear", "belt_scarf", "background")
SOURCES = ("ai_generated", "licensed", "self_made")
STATUSES = ("draft", "published", "retired")
MODEL_ATTRIBUTES = {
    "skin_tone": ("1", "2", "3", "4", "5", "6"),
    "hair": ("straight", "wavy", "curly", "short", "covered"),
    "body_type": ("slim", "regular", "plus"),
    "age_range": ("20s", "30s", "40s", "50s"),
    "region_style": ("east_asia", "southeast_asia", "south_asia", "middle_east", "africa", "europe", "latin_america"),
}
ITEM_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
IMPORT_EVENT = "asset.imported_from_library"
PREVIEW_TTL_SECONDS = 300

LIBRARY_DDL = (
    """CREATE TABLE IF NOT EXISTS library_items (
        item_id TEXT PRIMARY KEY,
        category TEXT NOT NULL CHECK(category IN ('model','top','bottom','dress','outer','bag','hat','eyewear','shoes','jewelry','headwear','belt_scarf','background')),
        subcategory TEXT, name_ko TEXT NOT NULL, name_en TEXT,
        tags_json TEXT NOT NULL DEFAULT '[]', attributes_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL CHECK(status IN ('draft','published','retired')),
        version INTEGER NOT NULL CHECK(version >= 1),
        source TEXT NOT NULL CHECK(source IN ('ai_generated','licensed','self_made')),
        tool_and_date TEXT NOT NULL,
        rights_confirmed INTEGER NOT NULL CHECK(rights_confirmed = 1),
        is_placeholder INTEGER NOT NULL DEFAULT 0,
        note TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_library_items_listing ON library_items(status, category, item_id)",
    """CREATE TABLE IF NOT EXISTS library_item_versions (
        item_id TEXT NOT NULL REFERENCES library_items(item_id),
        version INTEGER NOT NULL,
        storage_key TEXT NOT NULL UNIQUE, media_type TEXT NOT NULL, size_bytes INTEGER NOT NULL,
        checksum_sha256 TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(item_id, version)
    )""",
)


class LibraryError(ValueError):
    """A library rule was broken. ``code`` is stable; ``status`` is the HTTP status a route should use."""

    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status


class LibraryLimitError(LibraryError):
    def __init__(self, limit: int, used: int):
        super().__init__("LIBRARY_IMPORT_LIMIT", "Daily library import limit reached for this workspace.", 429)
        self.limit, self.used = limit, used


def _db():
    from app.assets import store
    store.initialize()
    return store._connect()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------------------------------- validation
def _text(value: Any, name: str, *, required: bool = False, max_len: int = 200) -> str | None:
    text = str(value).strip() if value is not None else ""
    if not text:
        if required:
            raise LibraryError("LIBRARY_FIELD_REQUIRED", f"{name} is required.")
        return None
    if len(text) > max_len:
        raise LibraryError("LIBRARY_FIELD_TOO_LONG", f"{name} is too long.")
    return text


def validate_item_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Normalised, validated metadata or LibraryError. Never touches the database or the files."""
    item_id = str(fields.get("item_id") or "").strip()
    if not ITEM_ID.match(item_id):
        raise LibraryError("LIBRARY_ID_INVALID", "item_id must be 2-64 lowercase letters, digits or hyphens.")
    category = str(fields.get("category") or "").strip()
    if category not in CATEGORIES:
        raise LibraryError("LIBRARY_CATEGORY_INVALID", "Unknown library category.")
    source = str(fields.get("source") or "").strip()
    if source not in SOURCES:
        raise LibraryError("LIBRARY_SOURCE_INVALID", "source must be ai_generated, licensed or self_made.")
    if fields.get("rights_confirmed") is not True:
        raise LibraryError("LIBRARY_RIGHTS_NOT_CONFIRMED", "The right to provide this image must be confirmed (rights_confirmed).")
    status = str(fields.get("status") or "published").strip()
    if status not in STATUSES:
        raise LibraryError("LIBRARY_STATUS_INVALID", "Unknown status.")
    tags = fields.get("tags") or []
    if not isinstance(tags, (list, tuple)) or any(not isinstance(t, str) for t in tags) or len(tags) > 30:
        raise LibraryError("LIBRARY_TAGS_INVALID", "tags must be up to 30 text values.")
    attributes = {k: str(v).strip() for k, v in (fields.get("attributes") or {}).items() if str(v).strip()}
    if category == "model":
        missing = [k for k in MODEL_ATTRIBUTES if k not in attributes]
        if missing:
            raise LibraryError("LIBRARY_ATTRIBUTE_MISSING", "Model items need: " + ", ".join(missing))
    elif attributes:
        raise LibraryError("LIBRARY_ATTRIBUTE_NOT_ALLOWED", "Only model items carry attributes.")
    for key, value in attributes.items():
        if key not in MODEL_ATTRIBUTES or value not in MODEL_ATTRIBUTES[key]:
            raise LibraryError("LIBRARY_ATTRIBUTE_INVALID", f"Invalid model attribute {key}={value}.")
    return {
        "item_id": item_id, "category": category, "subcategory": _text(fields.get("subcategory"), "subcategory", max_len=60),
        "name_ko": _text(fields.get("name_ko"), "name_ko", required=True), "name_en": _text(fields.get("name_en"), "name_en"),
        "tags": [t.strip() for t in tags if t.strip()], "attributes": attributes, "status": status, "source": source,
        "tool_and_date": _text(fields.get("tool_and_date"), "tool_and_date", required=True),
        "is_placeholder": bool(fields.get("is_placeholder")), "note": _text(fields.get("note"), "note", max_len=500),
    }


# ---------------------------------------------------------------------------------------------------- storage
def _root(create: bool = False) -> Path:
    root = config.LIBRARY_STORAGE_DIR.resolve()
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _path(key: str) -> Path:
    root = _root()
    path = (root / key).resolve()
    if Path(key).name != key or path.parent != root:
        raise RuntimeError("Invalid library storage path")
    return path


def upsert_item(fields: dict[str, Any], content: bytes, filename: str) -> dict[str, Any]:
    """Add an item, or change it. Same file bytes: only the metadata is updated (action 'updated' / 'unchanged').
    Different file bytes: a NEW version is stored and the previous version's file is kept (action 'new_version').
    Returns {"item_id", "version", "action"}. Raises LibraryError for any rule violation; nothing is written then."""
    from app.assets.validation import AssetValidationError, storage_suffix, validate_image_upload
    meta = validate_item_fields(fields)
    try:
        validated = validate_image_upload(filename, content, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
    except AssetValidationError as exc:
        raise LibraryError(exc.code, str(exc)) from exc
    from PIL import Image
    with Image.open(BytesIO(content)) as image:
        width, height = image.size
    checksum = hashlib.sha256(content).hexdigest()
    now = _now()
    written: Path | None = None
    try:
        with _db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT version FROM library_items WHERE item_id=?", (meta["item_id"],)).fetchone()
            current = None
            if row:
                current = db.execute("SELECT checksum_sha256 FROM library_item_versions WHERE item_id=? AND version=?",
                                     (meta["item_id"], row["version"])).fetchone()
            same_file = bool(current) and current["checksum_sha256"] == checksum
            version = row["version"] if same_file else (row["version"] + 1 if row else 1)
            if not same_file:
                key = f"{meta['item_id']}.v{version}{storage_suffix(validated.media_type)}"
                _root(create=True)
                target = _path(key)
                with target.open("xb") as handle:  # exclusive: an existing file is never overwritten (and never deleted below)
                    handle.write(content)
                written = target
                db.execute("""INSERT INTO library_item_versions(item_id, version, storage_key, media_type, size_bytes,
                    checksum_sha256, width, height, created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                           (meta["item_id"], version, key, validated.media_type, len(content), checksum, width, height, now))
            values = (meta["category"], meta["subcategory"], meta["name_ko"], meta["name_en"],
                      json.dumps(meta["tags"], ensure_ascii=False), json.dumps(meta["attributes"], sort_keys=True),
                      meta["status"], version, meta["source"], meta["tool_and_date"], int(meta["is_placeholder"]), meta["note"], now)
            if row is None:
                db.execute("""INSERT INTO library_items(category, subcategory, name_ko, name_en, tags_json, attributes_json, status,
                    version, source, tool_and_date, is_placeholder, note, updated_at, item_id, rights_confirmed, created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""", values + (meta["item_id"], now))
                action = "created"
            else:
                before = db.execute("SELECT * FROM library_items WHERE item_id=?", (meta["item_id"],)).fetchone()
                db.execute("""UPDATE library_items SET category=?, subcategory=?, name_ko=?, name_en=?, tags_json=?, attributes_json=?,
                    status=?, version=?, source=?, tool_and_date=?, is_placeholder=?, note=?, updated_at=? WHERE item_id=?""",
                           values + (meta["item_id"],))
                after = db.execute("SELECT * FROM library_items WHERE item_id=?", (meta["item_id"],)).fetchone()
                changed = any(before[k] != after[k] for k in before.keys() if k != "updated_at")
                action = "new_version" if not same_file else ("updated" if changed else "unchanged")
    except Exception:
        if written is not None:
            written.unlink(missing_ok=True)
        raise
    return {"item_id": meta["item_id"], "version": version, "action": action}


def set_status(item_id: str, status: str) -> None:
    """Take an item down (retired) or bring it back; used by the operations tool, never by an API route."""
    if status not in STATUSES:
        raise LibraryError("LIBRARY_STATUS_INVALID", "Unknown status.")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("UPDATE library_items SET status=?, updated_at=? WHERE item_id=?", (status, _now(), item_id)).rowcount != 1:
            raise LibraryError("LIBRARY_NOT_FOUND", "Library item not found.", 404)


# ---------------------------------------------------------------------------------------------------- reads
def _public(row, version_row) -> dict[str, Any]:
    """What any signed-in user may see. Never the storage key, checksum, tool/date, rights flag or internal note."""
    return {
        "item_id": row["item_id"], "category": row["category"], "subcategory": row["subcategory"], "name_ko": row["name_ko"],
        "name_en": row["name_en"], "tags": json.loads(row["tags_json"]), "attributes": json.loads(row["attributes_json"]),
        "version": row["version"], "media_type": version_row["media_type"], "width": version_row["width"], "height": version_row["height"],
        "source": row["source"], "is_ai_generated": row["source"] == "ai_generated", "is_placeholder": bool(row["is_placeholder"]),
    }


def _published_rows(db, category: str | None):
    sql = """SELECT i.*, v.media_type, v.width, v.height FROM library_items i
             JOIN library_item_versions v ON v.item_id=i.item_id AND v.version=i.version WHERE i.status='published'"""
    params: list[Any] = []
    if category:
        sql += " AND i.category=?"
        params.append(category)
    return db.execute(sql + " ORDER BY i.item_id", params).fetchall()


def list_items(*, category: str | None = None, q: str | None = None, attributes: dict[str, str] | None = None,
               limit: int = 24, cursor: str | None = None) -> dict[str, Any]:
    """Published items only, ordered by id; ``cursor`` is the last item_id of the previous page."""
    needle = (q or "").strip().casefold()
    wanted = {k: v for k, v in (attributes or {}).items() if v}
    with _db() as db:
        rows = _published_rows(db, category)
    items = []
    for row in rows:
        if cursor and row["item_id"] <= cursor:
            continue
        if needle and not (needle in row["name_ko"].casefold() or needle in (row["name_en"] or "").casefold()
                           or any(needle in t.casefold() for t in json.loads(row["tags_json"]))):
            continue
        if wanted:
            have = json.loads(row["attributes_json"])
            if any(have.get(k) != v for k, v in wanted.items()):
                continue
        items.append(_public(row, row))
    page = items[:limit]
    return {"items": page, "next_cursor": page[-1]["item_id"] if len(items) > limit and page else None}


def get_item(item_id: str) -> dict[str, Any] | None:
    """A published item, or None (draft and retired items do not exist for readers)."""
    with _db() as db:
        row = db.execute("""SELECT i.*, v.media_type, v.width, v.height FROM library_items i
            JOIN library_item_versions v ON v.item_id=i.item_id AND v.version=i.version
            WHERE i.item_id=? AND i.status='published'""", (item_id,)).fetchone()
    return _public(row, row) if row else None


def _read_current(item_id: str) -> tuple[dict[str, Any], bytes, str]:
    """(item, verified bytes, storage_key) of a PUBLISHED item's current version."""
    item = get_item(item_id)
    if item is None:
        raise LibraryError("LIBRARY_NOT_FOUND", "Library item not found.", 404)
    with _db() as db:
        version = db.execute("SELECT * FROM library_item_versions WHERE item_id=? AND version=?", (item_id, item["version"])).fetchone()
    try:
        content = _path(version["storage_key"]).read_bytes()
    except (OSError, RuntimeError) as exc:
        raise LibraryError("LIBRARY_FILE_UNAVAILABLE", "Library file is missing.", 409) from exc
    if len(content) != version["size_bytes"] or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), version["checksum_sha256"]):
        raise LibraryError("LIBRARY_FILE_CORRUPT", "Library file failed its integrity check.", 409)
    return item, content, version["storage_key"]


# ---------------------------------------------------------------------------------------------------- signed preview
def _signature(item_id: str, version: int, expires: int) -> str:
    secret = config.ASSET_SIGNING_SECRET.encode("utf-8")
    if len(secret) < 32:
        raise LibraryError("LIBRARY_SIGNING_NOT_CONFIGURED", "Library preview signing is not configured.", 503)
    return hmac.new(secret, f"library:{item_id}:{version}:{expires}".encode("utf-8"), hashlib.sha256).hexdigest()


def preview_url(item_id: str) -> dict[str, Any]:
    item = get_item(item_id)
    if item is None:
        raise LibraryError("LIBRARY_NOT_FOUND", "Library item not found.", 404)
    expires = int(time.time()) + PREVIEW_TTL_SECONDS
    sig = _signature(item_id, item["version"], expires)
    return {"url": f"/v1/library/items/{item_id}/versions/{item['version']}/preview?expires={expires}&signature={sig}", "expires_at": expires}


def preview_bytes(item_id: str, version: int, expires: int, signature: str) -> tuple[bytes, str]:
    now = int(time.time())
    if expires < now or expires > now + PREVIEW_TTL_SECONDS + 1:
        raise LibraryError("LIBRARY_PREVIEW_EXPIRED", "Library preview URL expired or invalid.", 403)
    if not hmac.compare_digest(_signature(item_id, version, expires), signature):
        raise LibraryError("LIBRARY_PREVIEW_EXPIRED", "Library preview URL expired or invalid.", 403)
    item, content, _ = _read_current(item_id)
    if item["version"] != version:  # a link to an older version stops working once the item has a newer one
        raise LibraryError("LIBRARY_NOT_FOUND", "Library item not found.", 404)
    return content, item["media_type"]


# ---------------------------------------------------------------------------------------------------- copy into a workspace
def import_to_workspace(item_id: str, workspace_id: str, user_id: str) -> dict[str, Any]:
    """Copy the item's current version into the workspace as an ordinary asset. The caller has already checked the role.
    The library item itself is only READ."""
    from app.assets import store
    from app.assets.validation import AssetValidationError, storage_suffix, validate_image_upload
    item, content, _ = _read_current(item_id)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with _db() as db:
        used = db.execute("SELECT COUNT(*) AS n FROM asset_provenance WHERE workspace_id=? AND event_type=? AND created_at>=?",
                          (workspace_id, IMPORT_EVENT, cutoff)).fetchone()["n"]
    if used >= config.LIBRARY_IMPORT_DAILY_LIMIT:
        raise LibraryLimitError(config.LIBRARY_IMPORT_DAILY_LIMIT, used)
    filename = f"{item_id}{storage_suffix(item['media_type'])}"
    try:
        validated = validate_image_upload(filename, content, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
    except AssetValidationError as exc:
        raise LibraryError(exc.code, str(exc), 409) from exc
    return store.save_asset(
        owner_id=user_id, workspace_id=workspace_id, filename=filename, content=content, validated=validated,
        provenance_event=IMPORT_EVENT,
        provenance_extra={"source": "library", "library_item_id": item_id, "library_item_version": item["version"],
                          "library_source": item["source"], "is_ai_generated": item["is_ai_generated"]})
