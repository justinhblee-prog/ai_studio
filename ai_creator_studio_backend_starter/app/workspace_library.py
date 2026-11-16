"""R-045: the workspace's own library ("my library"): model / garment / prop / bg / pose / 3d / render items.

An item is NOT a new kind of file: it is a labelled pointer to an ordinary workspace asset (so rights confirmation, provenance, versions,
roles, takedown holds, purge and backup all keep working unchanged). The platform-owned default library (R-032) is separate.
Origin is decided by the SERVER from the asset's provenance, never by the client, so an AI generated output cannot be filed as an upload:
  asset.generated_output_imported -> "ai", asset.photo_processed / asset.photo_steps -> "work", everything else -> "upload".
Read = any member (viewer or higher), write = editor or higher. Items whose asset is on hold (L-08) are hidden like the asset itself.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app import config, image_thumbs, takedown
from app.assets import store
from app.assets.rights import build_upload_confirmation
from app.assets.routes import current_user, require_role
from app.assets.validation import AssetValidationError, validate_gltf_upload, validate_image_upload
from app.ports.asset_bytes import get_asset_bytes_port

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/library", tags=["workspace-library"])
Kind = Literal["model", "garment", "prop", "bg", "pose", "3d", "render"]
KINDS = ("model", "garment", "prop", "bg", "pose", "3d", "render")
AI_EVENTS = {"asset.generated_output_imported"}
WORK_EVENTS = {"asset.photo_processed", "asset.photo_steps", "asset.model_candidate", "asset.video_output"}
MAX_TAGS, MAX_TAG_LEN, MAX_NAME = 10, 30, 120
MAX_ATTRS = 20     # R-058: free key/value attributes per item (same value rule as the model drafts: text <= 60 characters or a whole number 0-9999)
DDL = """CREATE TABLE IF NOT EXISTS workspace_library_items (
    item_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, asset_id TEXT NOT NULL, kind TEXT NOT NULL, origin TEXT NOT NULL,
    name TEXT NOT NULL, tags_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(workspace_id, asset_id))"""


THUMB_DDL = """CREATE TABLE IF NOT EXISTS workspace_library_thumbnails (
    item_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, asset_id TEXT NOT NULL, created_at TEXT NOT NULL)"""
THUMB_MAX_BYTES, THUMB_MAX_EDGE = 2 * 1024 * 1024, 1024


def _init(db) -> None:
    db.execute(DDL)
    if not any(r["name"] == "attrs_json" for r in db.execute("PRAGMA table_info(workspace_library_items)").fetchall()):
        db.execute("ALTER TABLE workspace_library_items ADD COLUMN attrs_json TEXT NOT NULL DEFAULT '{}'")
    db.execute(THUMB_DDL)
    db.execute("CREATE INDEX IF NOT EXISTS idx_wli_ws ON workspace_library_items(workspace_id, kind, created_at)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LibraryItemOut(BaseModel):
    item_id: str
    workspace_id: str
    asset_id: str
    kind: str
    origin: str
    is_ai_generated: bool
    name: str
    tags: list[str]
    attrs: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: str
    updated_at: str
    original_filename: str
    media_type: str
    size_bytes: int
    thumbnail_asset_id: str | None = None
    thumbs: dict[str, str] | None = None      # R-061: signed addresses of the 480 / 960 px display pictures (images only)


class LibraryListOut(BaseModel):
    items: list[LibraryItemOut]
    total: int


class AttachIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=3, max_length=80)
    kind: Kind
    name: str | None = Field(default=None, max_length=MAX_NAME)
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS)
    attrs: dict[str, Any] | None = None


class PatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=MAX_NAME)
    tags: list[str] | None = Field(default=None, max_length=MAX_TAGS)
    attrs: dict[str, Any] | None = None     # replaces the whole attribute set; {} clears it


def _clean_name(value: str | None, fallback: str) -> str:
    name = (value if value is not None else fallback).strip()
    if not name:
        raise HTTPException(status_code=422, detail={"code": "LIBRARY_NAME_REQUIRED", "message": "name must not be blank"})
    return name[:MAX_NAME]


def _clean_attrs(value: Any) -> dict[str, Any]:
    """R-058: free keys and values (the catalogue belongs to the design window). Keys: lowercase letters, digits, underscore. Values: a text of at most 60
    characters or a whole number 0-9999 (the R-055 rule), or a short list of them. Flat only; at most MAX_ATTRS keys. An empty object is allowed (clears)."""
    from app.model_drafts import KEY_RE, MAX_LIST, _norm, _scalar_ok
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail={"code": "ATTRS_INVALID", "message": "attrs must be an object of keys and values"})
    if len(value) > MAX_ATTRS:
        raise HTTPException(status_code=422, detail={"code": "ATTRS_TOO_MANY", "message": f"at most {MAX_ATTRS} attributes"})
    out: dict[str, Any] = {}
    for key, v in value.items():
        if not isinstance(key, str) or not KEY_RE.match(key):
            raise HTTPException(status_code=422, detail={"code": "ATTR_KEY_INVALID", "message": "attribute keys are lowercase letters, digits and underscores"})
        items = v if isinstance(v, list) else [v]
        if not items or len(items) > MAX_LIST or any(not _scalar_ok(i) or (isinstance(i, str) and not i.strip()) for i in items):
            raise HTTPException(status_code=422, detail={"code": "ATTR_VALUE_INVALID", "message": f"{key}: give a short text or a whole number 0-9999, or a short list of them"})
        out[key] = [_norm(i) for i in v] if isinstance(v, list) else _norm(v)
    return out


def _clean_tags(values: list[str]) -> list[str]:
    out: list[str] = []
    for raw in values:
        tag = str(raw).strip()
        if not tag:
            continue
        if len(tag) > MAX_TAG_LEN:
            raise HTTPException(status_code=422, detail={"code": "LIBRARY_TAG_TOO_LONG", "message": f"a tag has at most {MAX_TAG_LEN} characters"})
        if tag not in out:
            out.append(tag)
    return out


def _origin_of(db, asset_id: str) -> str:
    events = {r["event_type"] for r in db.execute("SELECT event_type FROM asset_provenance WHERE asset_id=?", (asset_id,)).fetchall()}
    if events & AI_EVENTS:
        return "ai"
    if events & WORK_EVENTS:
        return "work"
    return "upload"


_SELECT = """SELECT i.*, a.original_filename, a.media_type, a.size_bytes, a.owner_id AS asset_owner, t.asset_id AS thumbnail_asset_id
    FROM workspace_library_items i JOIN assets a ON a.asset_id=i.asset_id AND a.workspace_id=i.workspace_id AND a.deleted_at IS NULL
    LEFT JOIN workspace_library_thumbnails t ON t.item_id=i.item_id"""


def _out(row) -> dict[str, Any]:
    return {"item_id": row["item_id"], "workspace_id": row["workspace_id"], "asset_id": row["asset_id"], "kind": row["kind"], "origin": row["origin"],
            "is_ai_generated": row["origin"] == "ai", "name": row["name"], "tags": json.loads(row["tags_json"]), "attrs": json.loads(row["attrs_json"] or "{}"), "created_by": row["created_by"],
            "created_at": row["created_at"], "updated_at": row["updated_at"], "original_filename": row["original_filename"],
            "media_type": row["media_type"], "size_bytes": row["size_bytes"], "thumbnail_asset_id": row["thumbnail_asset_id"],
            "thumbs": image_thumbs.urls_for(row["asset_id"], row["media_type"])}


def _check_caps(db, workspace_id: str, kind: str) -> None:
    n = db.execute("SELECT COUNT(*) AS n FROM workspace_library_items WHERE workspace_id=?", (workspace_id,)).fetchone()["n"]
    if n >= config.WORKSPACE_LIBRARY_MAX_ITEMS:
        raise HTTPException(status_code=409, detail={"code": "LIBRARY_FULL", "message": f"at most {config.WORKSPACE_LIBRARY_MAX_ITEMS} items per workspace"})
    if kind == "3d":
        n3 = db.execute("SELECT COUNT(*) AS n FROM workspace_library_items WHERE workspace_id=? AND kind='3d'", (workspace_id,)).fetchone()["n"]
        if n3 >= config.WORKSPACE_LIBRARY_MAX_3D:
            raise HTTPException(status_code=409, detail={"code": "LIBRARY_3D_FULL", "message": f"at most {config.WORKSPACE_LIBRARY_MAX_3D} 3D items per workspace"})


def _insert(db, workspace_id: str, user_id: str, asset_id: str, kind: str, name: str, tags: list[str], attrs: dict[str, Any] | None = None) -> dict[str, Any]:
    item_id, now = "wli_" + uuid.uuid4().hex, _now()
    db.execute("INSERT INTO workspace_library_items(item_id, workspace_id, asset_id, kind, origin, name, tags_json, attrs_json, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (item_id, workspace_id, asset_id, kind, _origin_of(db, asset_id), name, json.dumps(tags, ensure_ascii=False), json.dumps(attrs or {}, ensure_ascii=False), user_id, now, now))
    image_thumbs.prepare(asset_id)      # R-061: the display pictures are made now (best effort; they are rebuilt on first request otherwise)
    return _out(db.execute(_SELECT + " WHERE i.item_id=?", (item_id,)).fetchone())


def _visible(row, user_id: str) -> bool:
    return takedown.visible_to(row["asset_id"], user_id)


@router.get("", response_model=LibraryListOut, operation_id="listWorkspaceLibrary")
async def list_items(workspace_id: str, kind: Kind | None = None, origin: Literal["ai", "upload", "work"] | None = None,
                     q: str | None = Query(default=None, max_length=80), attr: list[str] = Query(default_factory=list, max_length=10),
                     limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
                     user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    wanted = _parse_attr_filters(attr)
    sql, args = _SELECT + " WHERE i.workspace_id=?", [workspace_id]
    if kind:
        sql += " AND i.kind=?"; args.append(kind)
    if origin:
        sql += " AND i.origin=?"; args.append(origin)
    if q and q.strip():
        like = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql += " AND (i.name LIKE ? ESCAPE '\\' OR i.tags_json LIKE ? ESCAPE '\\')"; args += [like, like]
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = [r for r in db.execute(sql + " ORDER BY i.created_at DESC, i.item_id", args).fetchall() if _visible(r, user_id) and _attrs_match(r, wanted)]
    return {"items": [_out(r) for r in rows[offset:offset + limit]], "total": len(rows)}


def _parse_attr_filters(values: list[str]) -> list[tuple[str, str]]:
    """``attr=key:value`` (repeat for several; all must match). A list-valued attribute matches when it contains the value. Numbers compare as text."""
    out = []
    for raw in values:
        key, sep, value = raw.partition(":")
        if not sep or not key or not value.strip() or len(raw) > 100:
            raise HTTPException(status_code=422, detail={"code": "ATTR_FILTER_INVALID", "message": "attr must look like key:value"})
        out.append((key.strip(), value.strip()))
    return out


def _attrs_match(row, wanted: list[tuple[str, str]]) -> bool:
    if not wanted:
        return True
    attrs = json.loads(row["attrs_json"] or "{}")
    for key, value in wanted:
        have = attrs.get(key)
        have = have if isinstance(have, list) else [have]
        if value not in [str(h) for h in have if h is not None]:
            return False
    return True


@router.get("/facets", operation_id="listWorkspaceLibraryFacets")
async def facets(workspace_id: str, kind: Kind | None = None, user_id: str = Depends(current_user)):
    """For building filters: every attribute key in use (optionally within one kind) with its values and how many items carry each."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    sql, args = _SELECT + " WHERE i.workspace_id=?", [workspace_id]
    if kind:
        sql += " AND i.kind=?"; args.append(kind)
    out: dict[str, dict[str, int]] = {}
    with store._connect() as db:
        store.initialize()
        _init(db)
        for r in db.execute(sql, args).fetchall():
            if not _visible(r, user_id):
                continue
            for key, v in json.loads(r["attrs_json"] or "{}").items():
                for item in (v if isinstance(v, list) else [v]):
                    counts = out.setdefault(key, {})
                    counts[str(item)] = counts.get(str(item), 0) + 1
    return {"kind": kind, "facets": [{"key": k, "values": [{"value": val, "count": n} for val, n in sorted(c.items())]} for k, c in sorted(out.items())]}


@router.get("/{item_id}", response_model=LibraryItemOut, operation_id="getWorkspaceLibraryItem")
async def get_item(workspace_id: str, item_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    with store._connect() as db:
        store.initialize()
        _init(db)
        row = db.execute(_SELECT + " WHERE i.item_id=? AND i.workspace_id=?", (item_id, workspace_id)).fetchone()
    if row is None or not _visible(row, user_id):
        raise HTTPException(status_code=404, detail="Library item not found")
    return _out(row)


@router.post("/attach", status_code=201, response_model=LibraryItemOut, operation_id="attachWorkspaceLibraryItem")
async def attach(workspace_id: str, body: AttachIn, user_id: str = Depends(current_user)):
    """File an EXISTING asset of this workspace (an upload, a photo result, a generated output) under a kind."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    asset = store.get_asset(body.asset_id, workspace_id)
    if asset is None or not takedown.visible_to(body.asset_id, user_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    if (body.kind == "3d") != (asset["asset_kind"] == "model"):
        raise HTTPException(status_code=422, detail={"code": "LIBRARY_KIND_MISMATCH", "message": "kind 3d needs a 3D model asset; every other kind needs an image"})
    name, tags, attrs = _clean_name(body.name, Path(asset["original_filename"]).stem), _clean_tags(body.tags), _clean_attrs(body.attrs)
    with store._connect() as db:
        _init(db)
        if db.execute("SELECT 1 FROM workspace_library_items WHERE workspace_id=? AND asset_id=?", (workspace_id, body.asset_id)).fetchone():
            raise HTTPException(status_code=409, detail={"code": "LIBRARY_ALREADY_FILED", "message": "this asset is already in the library"})
        _check_caps(db, workspace_id, body.kind)
        return _insert(db, workspace_id, user_id, body.asset_id, body.kind, name, tags, attrs)


class FromJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(min_length=4, max_length=80)
    output_id: str | None = Field(default=None, min_length=4, max_length=80)     # a try-on job with several outputs: which one (default: the newest)
    name: str | None = Field(default=None, max_length=MAX_NAME)
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS)
    attrs: dict[str, Any] | None = None
    source_asset_ids: list[str] = Field(default_factory=list, max_length=10)     # extra inputs the caller wants recorded (same workspace only)


def _job_result(workspace_id: str, user_id: str, job_id: str, output_id: str | None) -> tuple[str, str, dict[str, Any], list[str]]:
    """(service, result asset id, defaults for the attributes, input asset ids) of a FINISHED job of this workspace. Raises 404/409."""
    from app.dependencies import get_job_repository
    with store._connect() as db:
        _init(db)
        has = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='video_jobs'").fetchone()
        video = db.execute("SELECT * FROM video_jobs WHERE job_id=? AND workspace_id=?", (job_id, workspace_id)).fetchone() if has else None
    if video is not None:
        if video["status"] != "succeeded" or not video["output_asset_id"]:
            raise HTTPException(status_code=409, detail={"code": "JOB_NOT_FINISHED", "message": "the video job has not succeeded"})
        qc = json.loads(video["qc_json"]) if video["qc_json"] else None
        if qc is not None and not qc.get("passed", True):
            raise HTTPException(status_code=409, detail={"code": "JOB_QC_FAILED", "message": "the video failed its quality check"})
        inputs = []
        for item_id in json.loads(video["input_item_ids_json"]):
            with store._connect() as db:
                row = db.execute("SELECT asset_id FROM workspace_library_items WHERE item_id=? AND workspace_id=?", (item_id, workspace_id)).fetchone()
            if row:
                inputs.append(row["asset_id"])
        return "video", video["output_asset_id"], {}, inputs
    job = get_job_repository().get(job_id)
    if not job or job["workspace_id"] != workspace_id:          # another workspace's job is indistinguishable from a missing one
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "succeeded":
        raise HTTPException(status_code=409, detail={"code": "JOB_NOT_FINISHED", "message": "the job has not succeeded"})
    outputs = get_job_repository().list_outputs(job_id)["data"]
    if output_id is not None:
        outputs = [o for o in outputs if o["id"] == output_id]
    if not outputs:
        raise HTTPException(status_code=404, detail="Output not found")
    out = outputs[0]
    if out.get("asset_link_status") != "linked" or not out.get("asset_id"):
        raise HTTPException(status_code=409, detail={"code": "OUTPUT_NOT_LINKED", "message": "the result is not stored as an asset yet"})
    from app.repositories.output_review import build_output_review_repository
    review = build_output_review_repository().get_review(job_id, out["id"])
    if not review or review["status"] != "approved":      # R-046: a generated result is delivered only after it is approved
        raise HTTPException(status_code=409, detail={"code": "OUTPUT_NOT_APPROVED", "message": "approve the result before filing it in the library"})
    payload = job.get("payload") or {}
    from app import tryon_inputs
    defaults = {k: payload[k] for k in ("style", "region") if payload.get(k)}
    return "tryon", out["asset_id"], defaults, tryon_inputs.asset_ids_of(payload)


@router.post("/from-job", status_code=201, response_model=LibraryItemOut, operation_id="fileWorkspaceLibraryFromJob")
async def from_job(workspace_id: str, body: FromJobIn, response: Response, user_id: str = Depends(current_user)):
    """R-060: file a FINISHED job's result under ``render``. Idempotent: the same result is filed once (a repeat returns the existing item with 200).
    The server records ``service``, ``style``, ``region`` and ``source_asset_ids`` (the inputs it knows about plus the caller's extra ones, which must be
    live assets of THIS workspace); the caller may add other attributes (e.g. ``sku``). Generation-job results must be approved first (R-046)."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    service, asset_id, defaults, inputs = _job_result(workspace_id, user_id, body.job_id, body.output_id)
    asset = store.get_asset(asset_id, workspace_id)
    if asset is None or not takedown.visible_to(asset_id, user_id):
        raise HTTPException(status_code=409, detail={"code": "OUTPUT_UNAVAILABLE", "message": "the result asset is gone"})
    for src in body.source_asset_ids:
        if not isinstance(src, str) or store.get_asset(src, workspace_id) is None or not takedown.visible_to(src, user_id):
            raise HTTPException(status_code=422, detail={"code": "SOURCE_ASSET_INVALID", "message": "source_asset_ids must be live assets of this workspace"})
    name, tags = _clean_name(body.name, "결과 " + body.job_id[-6:]), _clean_tags(body.tags)
    attrs = _clean_attrs(body.attrs)
    sources = list(dict.fromkeys([a for a in inputs if a != asset_id] + [a for a in body.source_asset_ids if a != asset_id]))[:10]
    attrs.update({"service": service, **defaults})
    if sources:
        attrs["source_asset_ids"] = sources
    attrs = _clean_attrs(attrs)
    with store._connect() as db:
        _init(db)
        existing = db.execute(_SELECT + " WHERE i.workspace_id=? AND i.asset_id=?", (workspace_id, asset_id)).fetchone()
        if existing is not None:      # already filed (e.g. by the approval): keep it, only add the server-known attributes it lacks
            have = json.loads(existing["attrs_json"] or "{}")
            merged = {**attrs, **have}
            if merged != have:
                db.execute("UPDATE workspace_library_items SET attrs_json=?, updated_at=? WHERE item_id=?", (json.dumps(merged, ensure_ascii=False), _now(), existing["item_id"]))
                existing = db.execute(_SELECT + " WHERE i.item_id=?", (existing["item_id"],)).fetchone()
            response.status_code = 200
            return _out(existing)
        _check_caps(db, workspace_id, "render")
        return _insert(db, workspace_id, user_id, asset_id, "render", name, tags, attrs)


@router.post("", status_code=201, response_model=LibraryItemOut, operation_id="uploadWorkspaceLibraryItem")
async def upload(workspace_id: str, kind: Kind = Form(...), file: UploadFile = File(...), name: str | None = Form(default=None, max_length=MAX_NAME),
                 tags: str | None = Form(default=None, max_length=400), rights_confirmed: bool | None = Form(default=None),
                 depicts_person: bool | None = Form(default=None), likeness_consent: bool | None = Form(default=None),
                 attrs: str | None = Form(default=None, max_length=4000), user_id: str = Depends(current_user)):
    """Upload a file straight into the library: images carry the same rights/likeness declaration as every image upload (L-04, recorded in
    asset_provenance); a 3D item must be a .glb/.gltf (validated, external references refused)."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    from app import rate_limit    # R-067
    rate_limit.check("upload", user_id, workspace_id)
    filename = Path(file.filename or "item").name
    limit = config.WORKSPACE_LIBRARY_MAX_3D_BYTES if kind == "3d" else config.ASSET_MAX_UPLOAD_BYTES
    content = await file.read(limit + 1)
    await file.close()
    if len(content) > limit:
        raise HTTPException(status_code=413, detail="File exceeds the upload size limit")
    try:
        parsed_attrs = json.loads(attrs) if attrs and attrs.strip() else None
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "ATTRS_INVALID", "message": "attrs must be a JSON object"})
    clean_name, clean_tags, clean_attrs = _clean_name(name, Path(filename).stem), _clean_tags([t for t in (tags or "").split(",")]), _clean_attrs(parsed_attrs)
    try:
        if kind == "3d":
            validated, confirmation = validate_gltf_upload(filename, content, max_bytes=limit), None
        else:
            validated = validate_image_upload(filename, content, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
            confirmation = build_upload_confirmation(rights_confirmed, depicts_person, likeness_consent)
    except AssetValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    with store._connect() as db:   # the cap is checked BEFORE the file is stored so a refusal leaves nothing behind
        _init(db)
        _check_caps(db, workspace_id, kind)
    try:
        saved = (get_asset_bytes_port().save(workspace_id, user_id, filename, content, validated) if kind == "3d"
                 else get_asset_bytes_port().save(workspace_id, user_id, filename, content, validated, upload_confirmation=confirmation))
    except Exception as exc:
        from app.assets.routes import _store_failure
        _store_failure(exc, "Library item could not be stored")
    with store._connect() as db:
        _init(db)
        return _insert(db, workspace_id, user_id, saved["asset_id"], kind, clean_name, clean_tags, clean_attrs)


@router.patch("/{item_id}", response_model=LibraryItemOut, operation_id="updateWorkspaceLibraryItem")
async def update_item(workspace_id: str, item_id: str, body: PatchIn, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    if body.name is None and body.tags is None and body.attrs is None:
        raise HTTPException(status_code=422, detail={"code": "LIBRARY_NOTHING_TO_CHANGE", "message": "send a name, tags or attrs"})
    with store._connect() as db:
        _init(db)
        row = db.execute(_SELECT + " WHERE i.item_id=? AND i.workspace_id=?", (item_id, workspace_id)).fetchone()
        if row is None or not _visible(row, user_id):
            raise HTTPException(status_code=404, detail="Library item not found")
        name = _clean_name(body.name, row["name"]) if body.name is not None else row["name"]
        tags = _clean_tags(body.tags) if body.tags is not None else json.loads(row["tags_json"])
        attrs = _clean_attrs(body.attrs) if body.attrs is not None else json.loads(row["attrs_json"] or "{}")
        db.execute("UPDATE workspace_library_items SET name=?, tags_json=?, attrs_json=?, updated_at=? WHERE item_id=?",
                   (name, json.dumps(tags, ensure_ascii=False), json.dumps(attrs, ensure_ascii=False), _now(), item_id))
        return _out(db.execute(_SELECT + " WHERE i.item_id=?", (item_id,)).fetchone())


@router.delete("/{item_id}", status_code=204, operation_id="removeWorkspaceLibraryItem")
async def remove_item(workspace_id: str, item_id: str, delete_asset: bool = Query(default=False), user_id: str = Depends(current_user)):
    """Takes the item out of the library. The asset stays in the workspace unless delete_asset=true, which goes through the normal asset
    deletion (so references from products/characters and generated-output retention still block it)."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    with store._connect() as db:
        _init(db)
        row = db.execute("SELECT * FROM workspace_library_items WHERE item_id=? AND workspace_id=?", (item_id, workspace_id)).fetchone()
        if row is None or not takedown.visible_to(row["asset_id"], user_id):
            raise HTTPException(status_code=404, detail="Library item not found")
        asset_id = row["asset_id"]
    if delete_asset:
        try:
            if not store.delete_asset(asset_id, workspace_id, user_id):
                raise HTTPException(status_code=404, detail="Asset not found")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"code": "ASSET_IN_USE", "message": str(exc)}) from exc
    thumb = _drop_thumbnail_row(item_id)
    with store._connect() as db:
        _init(db)
        db.execute("DELETE FROM workspace_library_items WHERE item_id=?", (item_id,))
    _delete_thumbnail_asset(thumb, workspace_id, user_id)
    return None


def file_item(workspace_id: str, asset_id: str | None, user_id: str, kind: str, name: str, attrs: dict[str, Any] | None = None) -> str:
    """File an existing asset under ``kind`` without ever raising: 'filed', 'exists', 'full' or 'skipped'. Origin comes from the provenance."""
    if not asset_id:
        return "skipped"
    try:
        with store._connect() as db:
            _init(db)
            if db.execute("SELECT 1 FROM workspace_library_items WHERE workspace_id=? AND asset_id=?", (workspace_id, asset_id)).fetchone():
                return "exists"
            try:
                _check_caps(db, workspace_id, kind)
            except HTTPException:
                return "full"
            _insert(db, workspace_id, user_id, asset_id, kind, _clean_name(name, "item"), [], attrs or {})
        return "filed"
    except Exception:  # noqa: BLE001
        return "skipped"


def attrs_for_tryon_job(job: dict[str, Any], result_asset_id: str | None) -> dict[str, Any]:
    """R-059 follow-up: what the server knows about a try-on result: service, style, region and the input assets (never raises)."""
    try:
        from app import tryon_inputs
        payload = job.get("payload") or {}
        attrs: dict[str, Any] = {"service": "tryon", **{k: payload[k] for k in ("style", "region") if payload.get(k)}}
        sources = [a for a in dict.fromkeys(tryon_inputs.asset_ids_of(payload)) if a != result_asset_id][:10]
        if sources:
            attrs["source_asset_ids"] = sources
        return _clean_attrs(attrs)
    except Exception:  # noqa: BLE001
        return {"service": "tryon"}


def file_generated_output(workspace_id: str, asset_id: str | None, user_id: str, name: str, attrs: dict[str, Any] | None = None) -> str:
    """R-046: file an APPROVED generated output under 'render' (never raises, so an approval cannot fail because of the library)."""
    return file_item(workspace_id, asset_id, user_id, "render", name, attrs)


def _drop_thumbnail_row(item_id: str) -> str | None:
    with store._connect() as db:
        _init(db)
        row = db.execute("SELECT asset_id FROM workspace_library_thumbnails WHERE item_id=?", (item_id,)).fetchone()
        db.execute("DELETE FROM workspace_library_thumbnails WHERE item_id=?", (item_id,))
    return row["asset_id"] if row else None


def _delete_thumbnail_asset(asset_id: str | None, workspace_id: str, user_id: str) -> None:
    if asset_id:
        try:
            store.delete_asset(asset_id, workspace_id, user_id)
        except Exception:  # noqa: BLE001 - a thumbnail that cannot be removed simply stays as an ordinary asset
            pass


@router.put("/{item_id}/thumbnail", response_model=LibraryItemOut, operation_id="putWorkspaceLibraryThumbnail")
async def put_thumbnail(workspace_id: str, item_id: str, file: UploadFile = File(...), user_id: str = Depends(current_user)):
    """R-049: the picture shown for a 3D item. The server has no GPU renderer, so the browser's 3D viewer renders it and uploads the result
    (a small PNG/JPEG/WebP, at most 1024 px and 2 MB). Replacing it removes the previous one. Only 3D items have a thumbnail (other kinds ARE images)."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    with store._connect() as db:
        _init(db)
        row = db.execute(_SELECT + " WHERE i.item_id=? AND i.workspace_id=?", (item_id, workspace_id)).fetchone()
    if row is None or not _visible(row, user_id):
        raise HTTPException(status_code=404, detail="Library item not found")
    if row["kind"] != "3d":
        raise HTTPException(status_code=422, detail={"code": "LIBRARY_THUMBNAIL_KIND", "message": "only 3D items have a thumbnail"})
    content = await file.read(THUMB_MAX_BYTES + 1)
    await file.close()
    if len(content) > THUMB_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Thumbnail exceeds the size limit")
    filename = Path(file.filename or "thumbnail.png").name
    try:
        validated = validate_image_upload(filename, content, max_bytes=THUMB_MAX_BYTES, max_dimension=THUMB_MAX_EDGE)
    except AssetValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    saved = store.save_asset(owner_id=user_id, workspace_id=workspace_id, filename=filename, content=content, validated=validated,
                             provenance_event="asset.thumbnail",
                             provenance_extra={"item_id": item_id, "source_asset_id": row["asset_id"], "mode": "client_render", "is_ai_generated": False})
    old = _drop_thumbnail_row(item_id)
    with store._connect() as db:
        _init(db)
        db.execute("INSERT INTO workspace_library_thumbnails(item_id, workspace_id, asset_id, created_at) VALUES (?,?,?,?)", (item_id, workspace_id, saved["asset_id"], _now()))
        out = _out(db.execute(_SELECT + " WHERE i.item_id=?", (item_id,)).fetchone())
    _delete_thumbnail_asset(old, workspace_id, user_id)
    return out


class ModelInfoOut(BaseModel):
    item_id: str
    format: str
    gltf_version: str | None
    generator: str | None
    scenes: int
    nodes: int
    meshes: int
    primitives: int
    triangles: int | None
    materials: int
    textures: int
    images: int
    animations: int
    skins: int
    cameras: int
    extensions_used: list[str]
    size_bytes: int


def gltf_document(content: bytes) -> tuple[str, dict[str, Any]]:
    """The JSON of a .glb (first chunk) or .gltf. Only the document is read; no buffer, image or script is decoded or executed."""
    import struct
    if content[:4] == b"glTF":
        if len(content) < 20:
            raise ValueError("truncated glb")
        length, kind = struct.unpack_from("<II", content, 12)
        if kind != 0x4E4F534A or 20 + length > len(content):
            raise ValueError("the first glb chunk is not JSON")
        return "glb", json.loads(content[20:20 + length].decode("utf-8"))
    return "gltf", json.loads(content.decode("utf-8"))


def gltf_stats(doc: dict[str, Any]) -> dict[str, Any]:
    def n(key: str) -> int:
        value = doc.get(key)
        return len(value) if isinstance(value, list) else 0
    accessors = doc.get("accessors") if isinstance(doc.get("accessors"), list) else []
    primitives, triangles, counted = 0, 0, True
    for mesh in doc.get("meshes") or []:
        for prim in (mesh.get("primitives") or []) if isinstance(mesh, dict) else []:
            primitives += 1
            mode = prim.get("mode", 4) if isinstance(prim, dict) else 4
            index = prim.get("indices") if isinstance(prim, dict) else None
            position = (prim.get("attributes") or {}).get("POSITION") if isinstance(prim, dict) else None
            source = index if isinstance(index, int) else position
            if mode != 4 or not isinstance(source, int) or not (0 <= source < len(accessors)) or not isinstance(accessors[source].get("count"), int):
                counted = False   # strips/fans or missing counts: do not guess
                continue
            triangles += accessors[source]["count"] // 3
    asset = doc.get("asset") if isinstance(doc.get("asset"), dict) else {}
    used = doc.get("extensionsUsed") if isinstance(doc.get("extensionsUsed"), list) else []
    return {"gltf_version": asset.get("version") if isinstance(asset.get("version"), str) else None,
            "generator": str(asset.get("generator"))[:120] if asset.get("generator") else None,
            "scenes": n("scenes"), "nodes": n("nodes"), "meshes": n("meshes"), "primitives": primitives,
            "triangles": triangles if counted else None, "materials": n("materials"), "textures": n("textures"), "images": n("images"),
            "animations": n("animations"), "skins": n("skins"), "cameras": n("cameras"),
            "extensions_used": [str(x)[:60] for x in used[:30] if isinstance(x, str)]}


@router.get("/{item_id}/model-info", response_model=ModelInfoOut, operation_id="getWorkspaceLibraryModelInfo")
async def model_info(workspace_id: str, item_id: str, user_id: str = Depends(current_user)):
    """R-049: counts read from the 3D file's own JSON (meshes, triangles, materials, textures, animations ...) for the library and the viewer."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    with store._connect() as db:
        _init(db)
        row = db.execute(_SELECT + " WHERE i.item_id=? AND i.workspace_id=?", (item_id, workspace_id)).fetchone()
    if row is None or not _visible(row, user_id):
        raise HTTPException(status_code=404, detail="Library item not found")
    if row["kind"] != "3d":
        raise HTTPException(status_code=422, detail={"code": "LIBRARY_INFO_KIND", "message": "only 3D items have model information"})
    path = store.storage_path(row["asset_id"])
    if path is None:
        raise HTTPException(status_code=409, detail="The 3D file is missing")
    try:
        fmt, doc = gltf_document(path.read_bytes())
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail={"code": "MODEL_UNREADABLE", "message": "The 3D file could not be read."}) from exc
    return {"item_id": item_id, "format": fmt, "size_bytes": row["size_bytes"], **gltf_stats(doc)}
