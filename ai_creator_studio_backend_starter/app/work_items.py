"""R-069: "my work" items: one general store for what the homepage calls a work item (a title, a service, a status and the pictures it is about).

An item belongs to a workspace: ``kind`` (the service: a short lowercase label), ``title``, ``status`` (the homepage's own words, e.g. draft / req / ok / chg / rej / done: the server checks only the SHAPE,
it does not run a state machine), free ``attrs`` (the R-058 rule: short texts or whole numbers), and ``asset_ids`` (live assets of the same workspace). Nothing is deleted: ``archive`` hides an item, ``restore``
brings it back. Every change (created, updated, status, archived, restored) is written to an append-only history with who and when.
A work item's ``status`` is a LABEL for the screen. It grants nothing: approving something for export is the review record (``/reviews``, owner / admin only). When an item points to assets, the response shows
each asset's latest REVIEW status next to the item's own status, so the screen can show both without mixing them up.
The existing photo / lookbook / project / product records are untouched; work items run next to them.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app import config, takedown
from app.assets import store
from app.assets.routes import current_user, require_role

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/work-items", tags=["work-items"])
KIND_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,19}$")
STATUS_RE = re.compile(r"^[a-z][a-z0-9_-]{0,15}$")
MAX_ASSETS = 20
WRITERS = {"owner", "admin", "editor"}
READERS = {"owner", "admin", "editor", "viewer"}
# what the homepage shows for each asset review status (reply 40 point 4)
REVIEW_TO_SCREEN = {"none": "draft", "requested": "req", "approved": "ok", "changes_requested": "chg", "rejected": "rej", "withdrawn": "draft"}


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS work_items (
        item_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL, attrs_json TEXT NOT NULL DEFAULT '{}',
        asset_ids_json TEXT NOT NULL DEFAULT '[]', created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived_at TEXT, version INTEGER NOT NULL DEFAULT 1)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_work_items_ws ON work_items(workspace_id, archived_at, updated_at)")
    db.execute("""CREATE TABLE IF NOT EXISTS work_item_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL, workspace_id TEXT NOT NULL, at TEXT NOT NULL, actor_id TEXT NOT NULL, event TEXT NOT NULL,
        from_status TEXT, to_status TEXT, changed_json TEXT NOT NULL DEFAULT '[]')""")
    for kind in ("UPDATE", "DELETE"):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS trg_work_item_events_no_{kind.lower()} BEFORE {kind} ON work_item_events
            BEGIN SELECT RAISE(ABORT, 'work item history is append-only'); END""")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_kind(value: str) -> str:
    if not KIND_RE.match(value or ""):
        raise HTTPException(status_code=422, detail={"code": "WORK_KIND_INVALID", "message": "kind: lowercase letters, digits, hyphen (at most 20)"})
    return value


def _check_status(value: str) -> str:
    if not STATUS_RE.match(value or ""):
        raise HTTPException(status_code=422, detail={"code": "WORK_STATUS_INVALID", "message": "status: a lowercase word (letters, digits, _ or -, at most 16, starting with a letter)"})
    return value


def _check_title(value: str | None) -> str:
    text = "".join(ch for ch in (value or "") if ch in "\t" or ord(ch) >= 32).strip()
    if not text or len(text) > 120:
        raise HTTPException(status_code=422, detail={"code": "WORK_TITLE_INVALID", "message": "title: 1 to 120 characters"})
    return text


def _check_assets(workspace_id: str, user_id: str, ids: list[str]) -> list[str]:
    if not isinstance(ids, list) or len(ids) > MAX_ASSETS or any(not isinstance(i, str) for i in ids):
        raise HTTPException(status_code=422, detail={"code": "WORK_ASSET_INVALID", "message": f"asset_ids: a list of at most {MAX_ASSETS} asset ids"})
    out = list(dict.fromkeys(ids))
    for aid in out:
        if store.get_asset(aid, workspace_id) is None or not takedown.visible_to(aid, user_id):
            raise HTTPException(status_code=422, detail={"code": "WORK_ASSET_INVALID", "message": "every asset must be a live asset of this workspace"})
    return out


def _attrs(value: Any) -> dict[str, Any]:
    from app.workspace_library import _clean_attrs
    return _clean_attrs(value)


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(max_length=40)
    title: str = Field(max_length=500)
    status: str = Field(default="draft", max_length=40)
    attrs: dict[str, Any] | None = None
    asset_ids: list[Any] = Field(default_factory=list, max_length=100)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str | None = Field(default=None, max_length=40)
    title: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=40)
    attrs: dict[str, Any] | None = None           # replaces the whole set; {} clears it
    asset_ids: list[Any] | None = Field(default=None, max_length=100)
    expected_version: int | None = None           # optional: refuse when someone else changed the item meanwhile


class AssetState(BaseModel):
    asset_id: str
    state: Literal["live", "gone"]
    review_status: str
    screen_status: str
    exportable: bool


class ItemOut(BaseModel):
    item_id: str
    workspace_id: str
    kind: str
    title: str
    status: str
    attrs: dict[str, Any]
    asset_ids: list[str]
    assets: list[AssetState]
    asset_review_summary: str | None
    created_by: str
    created_at: str
    updated_at: str
    archived_at: str | None
    version: int


class ItemListOut(BaseModel):
    items: list[ItemOut]
    total: int


class EventOut(BaseModel):
    at: str
    actor_id: str
    event: str
    from_status: str | None
    to_status: str | None
    changed: list[str]


def _asset_states(db, workspace_id: str, ids: list[str]) -> list[dict[str, Any]]:
    out = []
    review_table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='asset_reviews'").fetchone() is not None
    for aid in ids:
        live = db.execute("SELECT 1 FROM assets WHERE asset_id=? AND workspace_id=? AND deleted_at IS NULL", (aid, workspace_id)).fetchone() is not None
        row = db.execute("SELECT status FROM asset_reviews WHERE workspace_id=? AND asset_id=? ORDER BY requested_at DESC, rowid DESC LIMIT 1", (workspace_id, aid)).fetchone() if review_table else None
        status = row["status"] if row else "none"
        out.append({"asset_id": aid, "state": "live" if live else "gone", "review_status": status, "screen_status": REVIEW_TO_SCREEN.get(status, "draft"), "exportable": status == "approved" and live})
    return out


def _summary(states: list[dict[str, Any]]) -> str | None:
    """One screen status for the item's assets: any rejected -> rej, else any changes requested -> chg, else any requested -> req, else all approved -> ok, else draft. None without assets."""
    live = [s for s in states if s["state"] == "live"]
    if not live:
        return None
    kinds = {s["review_status"] for s in live}
    for key, shown in (("rejected", "rej"), ("changes_requested", "chg"), ("requested", "req")):
        if key in kinds:
            return shown
    return "ok" if kinds == {"approved"} else "draft"


def _out(db, row) -> dict[str, Any]:
    ids = json.loads(row["asset_ids_json"])
    states = _asset_states(db, row["workspace_id"], ids)
    return {"item_id": row["item_id"], "workspace_id": row["workspace_id"], "kind": row["kind"], "title": row["title"], "status": row["status"],
            "attrs": json.loads(row["attrs_json"] or "{}"), "asset_ids": ids, "assets": states, "asset_review_summary": _summary(states), "created_by": row["created_by"],
            "created_at": row["created_at"], "updated_at": row["updated_at"], "archived_at": row["archived_at"], "version": row["version"]}


def _event(db, item_id: str, workspace_id: str, actor: str, event: str, from_status: str | None, to_status: str | None, changed: list[str]) -> None:
    db.execute("INSERT INTO work_item_events(item_id, workspace_id, at, actor_id, event, from_status, to_status, changed_json) VALUES (?,?,?,?,?,?,?,?)",
               (item_id, workspace_id, _now(), actor, event, from_status, to_status, json.dumps(changed)))


def _row(db, workspace_id: str, item_id: str):
    row = db.execute("SELECT * FROM work_items WHERE item_id=? AND workspace_id=?", (item_id, workspace_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    return row


@router.post("", status_code=201, response_model=ItemOut, operation_id="createWorkItem")
async def create_item(workspace_id: str, body: ItemIn, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, WRITERS)
    kind, status, title = _check_kind(body.kind), _check_status(body.status), _check_title(body.title)
    attrs, ids = _attrs(body.attrs), _check_assets(workspace_id, user_id, body.asset_ids)
    with store._connect() as db:
        store.initialize()
        _init(db)
        if db.execute("SELECT COUNT(*) AS n FROM work_items WHERE workspace_id=?", (workspace_id,)).fetchone()["n"] >= config.WORK_ITEMS_MAX:
            raise HTTPException(status_code=409, detail={"code": "WORK_ITEMS_FULL", "message": f"at most {config.WORK_ITEMS_MAX} work items per workspace (archived items count too)"})
        item_id, now = "wk_" + uuid.uuid4().hex, _now()
        db.execute("INSERT INTO work_items(item_id, workspace_id, kind, title, status, attrs_json, asset_ids_json, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (item_id, workspace_id, kind, title, status, json.dumps(attrs, ensure_ascii=False), json.dumps(ids), user_id, now, now))
        _event(db, item_id, workspace_id, user_id, "created", None, status, [])
        return _out(db, _row(db, workspace_id, item_id))


@router.get("", response_model=ItemListOut, operation_id="listWorkItems")
async def list_items(workspace_id: str, kind: str | None = Query(default=None, max_length=20), status: str | None = Query(default=None, max_length=16),
                     q: str | None = Query(default=None, max_length=80), asset_id: str | None = Query(default=None, max_length=80), archived: bool = False,
                     limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), user_id: str = Depends(current_user)):
    """Newest change first. ``archived=true`` lists the archived items INSTEAD of the active ones."""
    require_role(workspace_id, user_id, READERS)
    sql, args = "SELECT * FROM work_items WHERE workspace_id=? AND archived_at IS " + ("NOT NULL" if archived else "NULL"), [workspace_id]
    if kind:
        sql += " AND kind=?"; args.append(kind)
    if status:
        sql += " AND status=?"; args.append(status)
    if q and q.strip():
        sql += " AND title LIKE ? ESCAPE '\\'"; args.append("%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    if asset_id:
        sql += " AND asset_ids_json LIKE ?"; args.append('%"' + asset_id.replace("%", "").replace("_", "") + '"%')
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = db.execute(sql + " ORDER BY updated_at DESC, item_id", args).fetchall()
        if asset_id:
            rows = [r for r in rows if asset_id in json.loads(r["asset_ids_json"])]
        return {"items": [_out(db, r) for r in rows[offset:offset + limit]], "total": len(rows)}


@router.get("/{item_id}", response_model=ItemOut, operation_id="getWorkItem")
async def get_item(workspace_id: str, item_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, READERS)
    with store._connect() as db:
        store.initialize()
        _init(db)
        return _out(db, _row(db, workspace_id, item_id))


@router.patch("/{item_id}", response_model=ItemOut, operation_id="updateWorkItem")
async def update_item(workspace_id: str, item_id: str, body: ItemPatch, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, WRITERS)
    fields = body.model_fields_set - {"expected_version"}
    if not fields:
        raise HTTPException(status_code=422, detail={"code": "WORK_NOTHING_TO_CHANGE", "message": "send at least one field"})
    with store._connect() as db:
        store.initialize()
        _init(db)
        row = _row(db, workspace_id, item_id)
        if row["archived_at"]:
            raise HTTPException(status_code=409, detail={"code": "WORK_ITEM_ARCHIVED", "message": "restore the item before changing it"})
        if body.expected_version is not None and body.expected_version != row["version"]:
            raise HTTPException(status_code=409, detail={"code": "WORK_ITEM_CHANGED", "message": "the item was changed by someone else; reload it", "version": row["version"]})
        new = {"kind": row["kind"], "title": row["title"], "status": row["status"], "attrs_json": row["attrs_json"], "asset_ids_json": row["asset_ids_json"]}
        changed: list[str] = []
        if "kind" in fields:
            new["kind"] = _check_kind(body.kind or "")
        if "title" in fields:
            new["title"] = _check_title(body.title)
        if "status" in fields:
            new["status"] = _check_status(body.status or "")
        if "attrs" in fields:
            if body.attrs is None:
                raise HTTPException(status_code=422, detail={"code": "ATTRS_INVALID", "message": "attrs must be an object ({} clears it)"})
            new["attrs_json"] = json.dumps(_attrs(body.attrs), ensure_ascii=False)
        if "asset_ids" in fields:
            if body.asset_ids is None:
                raise HTTPException(status_code=422, detail={"code": "WORK_ASSET_INVALID", "message": "asset_ids must be a list ([] clears it)"})
            new["asset_ids_json"] = json.dumps(_check_assets(workspace_id, user_id, body.asset_ids))
        changed = [k.replace("_json", "") for k in new if new[k] != row[k]]
        if not changed:
            return _out(db, row)
        cur = db.execute("UPDATE work_items SET kind=?, title=?, status=?, attrs_json=?, asset_ids_json=?, updated_at=?, version=version+1 WHERE item_id=? AND version=?",
                         (new["kind"], new["title"], new["status"], new["attrs_json"], new["asset_ids_json"], _now(), item_id, row["version"]))
        if cur.rowcount != 1:
            raise HTTPException(status_code=409, detail={"code": "WORK_ITEM_CHANGED", "message": "the item was changed by someone else; reload it"})
        other = [c for c in changed if c != "status"]
        if new["status"] != row["status"]:        # one history line; other fields changed in the same call are listed on it
            _event(db, item_id, workspace_id, user_id, "status", row["status"], new["status"], other)
        else:
            _event(db, item_id, workspace_id, user_id, "updated", row["status"], row["status"], other)
        return _out(db, _row(db, workspace_id, item_id))


@router.delete("/{item_id}", status_code=204, operation_id="archiveWorkItem")
async def archive_item(workspace_id: str, item_id: str, user_id: str = Depends(current_user)):
    """Nothing is deleted: the item is archived (hidden from the list; ``restore`` brings it back)."""
    require_role(workspace_id, user_id, WRITERS)
    with store._connect() as db:
        store.initialize()
        _init(db)
        row = _row(db, workspace_id, item_id)
        if not row["archived_at"]:
            db.execute("UPDATE work_items SET archived_at=?, updated_at=?, version=version+1 WHERE item_id=?", (_now(), _now(), item_id))
            _event(db, item_id, workspace_id, user_id, "archived", row["status"], row["status"], [])
    return None


@router.post("/{item_id}/restore", response_model=ItemOut, operation_id="restoreWorkItem")
async def restore_item(workspace_id: str, item_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, WRITERS)
    with store._connect() as db:
        store.initialize()
        _init(db)
        row = _row(db, workspace_id, item_id)
        if row["archived_at"]:
            db.execute("UPDATE work_items SET archived_at=NULL, updated_at=?, version=version+1 WHERE item_id=?", (_now(), item_id))
            _event(db, item_id, workspace_id, user_id, "restored", row["status"], row["status"], [])
        return _out(db, _row(db, workspace_id, item_id))


@router.get("/{item_id}/events", response_model=list[EventOut], operation_id="listWorkItemEvents")
async def item_events(workspace_id: str, item_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, READERS)
    with store._connect() as db:
        store.initialize()
        _init(db)
        _row(db, workspace_id, item_id)
        rows = db.execute("SELECT at, actor_id, event, from_status, to_status, changed_json FROM work_item_events WHERE item_id=? ORDER BY event_id", (item_id,)).fetchall()
    return [{"at": r["at"], "actor_id": r["actor_id"], "event": r["event"], "from_status": r["from_status"], "to_status": r["to_status"], "changed": json.loads(r["changed_json"])} for r in rows]
