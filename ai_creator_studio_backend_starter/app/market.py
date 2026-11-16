"""R-064: the marketplace list, WITHOUT payment: templates / presets are listed, edited, made public or private, searched, reported; sellers have a small public profile.

Out of scope (decisions pending): payment, settlement, refunds, fees, purchase. ``price`` is only a whole-number slot (0 = free); no currency and no payment field exist.
A paid listing's ``payload`` (the preset / template data) is shown to its seller only; free listings show it to every signed-in user. There is no purchase, so a paid
payload is never released.
Records kept for every listing: the licence scope the seller typed (free text token: the legal wording is NOT filled in here), whether the content is AI generated
(an explicit yes/no), and the seller's rights confirmation (who, when). A listing cannot be created without all three.
Sellers are shown by an opaque handle (``sel_`` + a one-way hash of the user id), never by the account id.
Operators can READ reports; resolving them (hiding a listing) is an operator write and waits for the R-052 decisions.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app import config, takedown
from app.assets import store
from app.assets.routes import current_user, require_role

router = APIRouter(tags=["market"])
KIND_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,19}$")
LICENSE_RE = re.compile(r"^[A-Za-z0-9가-힣._~+\- ]{1,40}$")
NAME_BAD = re.compile(r"[<>@\\/]|https?:|www\.", re.I)
MAX_PRICE = 10_000_000
MAX_PAYLOAD_BYTES = 20_000
MAX_TAGS, MAX_TAG_LEN = 8, 24
REASONS = ("copyright", "likeness", "inappropriate", "fraud", "other")
WRITERS = {"owner", "admin", "editor"}


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS market_listings (
        listing_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, created_by TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
        tags_json TEXT NOT NULL, price INTEGER NOT NULL, payload_json TEXT, cover_asset_id TEXT, license_scope TEXT NOT NULL, is_ai_generated INTEGER NOT NULL,
        rights_confirmed_by TEXT NOT NULL, rights_confirmed_at TEXT NOT NULL, visibility TEXT NOT NULL CHECK(visibility IN ('private','public')),
        status TEXT NOT NULL CHECK(status IN ('active','deleted')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, published_at TEXT, version INTEGER NOT NULL DEFAULT 1)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_market_public ON market_listings(visibility, status, created_at)")
    db.execute("""CREATE TABLE IF NOT EXISTS market_reports (
        report_id TEXT PRIMARY KEY, listing_id TEXT NOT NULL REFERENCES market_listings(listing_id), reporter_id TEXT NOT NULL, reason TEXT NOT NULL, details TEXT, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL)""")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_market_reports_open ON market_reports(listing_id, reporter_id) WHERE status='open'")
    db.execute("""CREATE TABLE IF NOT EXISTS market_profiles (
        user_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, bio TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def handle_of(user_id: str) -> str:
    return "sel_" + hashlib.sha256(("market-seller:" + user_id).encode()).hexdigest()[:16]


def _clean_text(value: str | None, name: str, *, limit: int, required: bool = False) -> str:
    text = "".join(ch for ch in (value or "") if ch in "\n\t" or ord(ch) >= 32).strip()
    if required and not text:
        raise HTTPException(status_code=422, detail={"code": "MARKET_TEXT_REQUIRED", "message": f"{name} is required"})
    if len(text) > limit:
        raise HTTPException(status_code=422, detail={"code": "MARKET_TEXT_TOO_LONG", "message": f"{name} must be at most {limit} characters"})
    return text


def _clean_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for tag in tags:
        t = _clean_text(tag, "tag", limit=MAX_TAG_LEN).lower() if isinstance(tag, str) else ""
        if not t or "," in t:
            raise HTTPException(status_code=422, detail={"code": "MARKET_TAG_INVALID", "message": "tags are short texts without commas"})
        if t not in out:
            out.append(t)
    return out


def _clean_payload(payload: Any) -> str | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail={"code": "MARKET_PAYLOAD_INVALID", "message": "payload must be an object"})
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=422, detail={"code": "MARKET_PAYLOAD_TOO_LARGE", "message": f"payload must be at most {MAX_PAYLOAD_BYTES} bytes"})
    return text


def _check_price(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > MAX_PRICE:
        raise HTTPException(status_code=422, detail={"code": "MARKET_PRICE_INVALID", "message": f"price is a whole number 0..{MAX_PRICE} (0 = free)"})
    return value


def _check_license(value: str | None) -> str:
    text = (value or "").strip()
    if not LICENSE_RE.match(text):
        raise HTTPException(status_code=422, detail={"code": "MARKET_LICENSE_REQUIRED", "message": "give the licence scope as a short text (1-40 letters, digits, spaces . _ ~ + -)"})
    return text


def _check_kind(value: str) -> str:
    if not KIND_RE.match(value or ""):
        raise HTTPException(status_code=422, detail={"code": "MARKET_KIND_INVALID", "message": "kind: lowercase letters, digits, hyphen (at most 20)"})
    return value


class ListingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(min_length=2, max_length=64)
    kind: str = Field(max_length=20)
    title: str = Field(max_length=200)
    description: str = Field(default="", max_length=3000)
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS)
    price: Any = 0
    payload: Any = None
    cover_asset_id: str | None = Field(default=None, max_length=80)
    license_scope: str = Field(max_length=100)
    is_ai_generated: bool | None = None            # an explicit yes / no is required
    rights_confirmed: bool = False                  # must be true


class ListingPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str | None = Field(default=None, max_length=20)
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    tags: list[str] | None = Field(default=None, max_length=MAX_TAGS)
    price: Any = None
    payload: Any = None
    clear_payload: bool = False
    cover_asset_id: str | None = Field(default=None, max_length=80)
    clear_cover: bool = False
    license_scope: str | None = Field(default=None, max_length=100)
    is_ai_generated: bool | None = None


class PublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rights_confirmed: bool = False


class SellerOut(BaseModel):
    handle: str
    display_name: str | None


class ListingOut(BaseModel):
    listing_id: str
    kind: str
    title: str
    description: str
    tags: list[str]
    price: int
    free: bool
    cover_asset_id: str | None
    license_scope: str
    is_ai_generated: bool
    visibility: Literal["private", "public"]
    status: Literal["active", "deleted"]
    seller: SellerOut
    created_at: str
    updated_at: str
    published_at: str | None
    version: int
    payload: dict[str, Any] | None = None       # only for the seller, or for a FREE public listing
    mine: bool = False
    workspace_id: str | None = None             # only for the seller


class ListingListOut(BaseModel):
    items: list[ListingOut]
    total: int


def _may_edit(db, row, user_id: str) -> bool:
    role = None
    try:
        from app.ports.workspace import get_workspace_port
        role = get_workspace_port().role(row["workspace_id"], user_id)
    except Exception:  # noqa: BLE001
        role = None
    return role in {"owner", "admin"} or (role == "editor" and row["created_by"] == user_id)


def _out(db, row, user_id: str, *, with_payload: bool) -> dict[str, Any]:
    prof = db.execute("SELECT display_name FROM market_profiles WHERE user_id=?", (row["created_by"],)).fetchone()
    mine = _may_edit(db, row, user_id)
    payload = None
    if row["payload_json"] and with_payload and (mine or row["price"] == 0):
        payload = json.loads(row["payload_json"])
    return {"listing_id": row["listing_id"], "kind": row["kind"], "title": row["title"], "description": row["description"], "tags": json.loads(row["tags_json"]),
            "price": row["price"], "free": row["price"] == 0, "cover_asset_id": row["cover_asset_id"], "license_scope": row["license_scope"],
            "is_ai_generated": bool(row["is_ai_generated"]), "visibility": row["visibility"], "status": row["status"],
            "seller": {"handle": handle_of(row["created_by"]), "display_name": prof["display_name"] if prof else None},
            "created_at": row["created_at"], "updated_at": row["updated_at"], "published_at": row["published_at"], "version": row["version"],
            "payload": payload, "mine": mine, "workspace_id": row["workspace_id"] if mine else None}


def _cover_ok(workspace_id: str, asset_id: str | None, user_id: str) -> None:
    if asset_id is None:
        return
    asset = store.get_asset(asset_id, workspace_id)
    if asset is None or asset.get("asset_kind") != "image" or not takedown.visible_to(asset_id, user_id):
        raise HTTPException(status_code=422, detail={"code": "MARKET_COVER_INVALID", "message": "the cover must be an image asset of the seller's workspace"})


def _get(db, listing_id: str):
    return db.execute("SELECT * FROM market_listings WHERE listing_id=? AND status='active'", (listing_id,)).fetchone()


@router.post("/v1/market/listings", status_code=201, response_model=ListingOut, operation_id="createMarketListing")
async def create_listing(body: ListingIn, user_id: str = Depends(current_user)):
    require_role(body.workspace_id, user_id, WRITERS)
    if not body.rights_confirmed:
        raise HTTPException(status_code=422, detail={"code": "MARKET_RIGHTS_REQUIRED", "message": "confirm that you may sell this"})
    if body.is_ai_generated is None:
        raise HTTPException(status_code=422, detail={"code": "MARKET_AI_FLAG_REQUIRED", "message": "say whether the content is AI generated (true or false)"})
    kind, license_scope, price = _check_kind(body.kind), _check_license(body.license_scope), _check_price(body.price)
    title, desc = _clean_text(body.title, "title", limit=80, required=True), _clean_text(body.description, "description", limit=1000)
    tags, payload = _clean_tags(body.tags), _clean_payload(body.payload)
    _cover_ok(body.workspace_id, body.cover_asset_id, user_id)
    with store._connect() as db:
        _init(db)
        listing_id, now = "mkt_" + uuid.uuid4().hex, _now()
        db.execute("""INSERT INTO market_listings(listing_id, workspace_id, created_by, kind, title, description, tags_json, price, payload_json, cover_asset_id, license_scope,
            is_ai_generated, rights_confirmed_by, rights_confirmed_at, visibility, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'private','active',?,?)""",
                   (listing_id, body.workspace_id, user_id, kind, title, desc, json.dumps(tags, ensure_ascii=False), price, payload, body.cover_asset_id, license_scope,
                    1 if body.is_ai_generated else 0, user_id, now, now, now))
        return _out(db, _get(db, listing_id), user_id, with_payload=True)


@router.get("/v1/market/listings", response_model=ListingListOut, operation_id="searchMarketListings")
async def search_listings(q: str | None = Query(default=None, max_length=80), kind: str | None = Query(default=None, max_length=20), tag: str | None = Query(default=None, max_length=24),
                          free: bool | None = None, seller: str | None = Query(default=None, max_length=40),
                          sort: Literal["new", "price_asc", "price_desc"] = "new", limit: int = Query(default=24, ge=1, le=100), offset: int = Query(default=0, ge=0),
                          user_id: str = Depends(current_user)):
    """Public listings of every seller. Payloads are never in a search result."""
    sql, args = "SELECT * FROM market_listings WHERE visibility='public' AND status='active'", []
    if kind:
        sql += " AND kind=?"; args.append(kind)
    if free is True:
        sql += " AND price=0"
    elif free is False:
        sql += " AND price>0"
    if q and q.strip():
        like = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql += " AND (title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' OR tags_json LIKE ? ESCAPE '\\')"; args += [like, like, like]
    if tag and tag.strip():
        like = '%"' + tag.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + '"%'
        sql += " AND tags_json LIKE ? ESCAPE '\\'"; args.append(like)
    order = {"new": "published_at DESC, listing_id", "price_asc": "price ASC, published_at DESC, listing_id", "price_desc": "price DESC, published_at DESC, listing_id"}[sort]
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = db.execute(sql + " ORDER BY " + order, args).fetchall()
        if seller:
            rows = [r for r in rows if handle_of(r["created_by"]) == seller]
        return {"items": [_out(db, r, user_id, with_payload=False) for r in rows[offset:offset + limit]], "total": len(rows)}


@router.get("/v1/market/mine", response_model=ListingListOut, operation_id="listMyMarketListings")
async def my_listings(visibility: Literal["private", "public"] | None = None, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
                      user_id: str = Depends(current_user)):
    sql, args = "SELECT * FROM market_listings WHERE created_by=? AND status='active'", [user_id]
    if visibility:
        sql += " AND visibility=?"; args.append(visibility)
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = db.execute(sql + " ORDER BY created_at DESC, listing_id", args).fetchall()
        return {"items": [_out(db, r, user_id, with_payload=True) for r in rows[offset:offset + limit]], "total": len(rows)}


def _visible_row(db, listing_id: str, user_id: str):
    row = _get(db, listing_id)
    if row is None or (row["visibility"] != "public" and not _may_edit(db, row, user_id)):
        raise HTTPException(status_code=404, detail="Listing not found")
    return row


@router.get("/v1/market/listings/{listing_id}", response_model=ListingOut, operation_id="getMarketListing")
async def get_listing(listing_id: str, user_id: str = Depends(current_user)):
    with store._connect() as db:
        store.initialize()
        _init(db)
        return _out(db, _visible_row(db, listing_id, user_id), user_id, with_payload=True)


def _editable(db, listing_id: str, user_id: str):
    row = _get(db, listing_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if not _may_edit(db, row, user_id):
        if row["visibility"] == "public":
            raise HTTPException(status_code=403, detail="Only the seller can change this listing")
        raise HTTPException(status_code=404, detail="Listing not found")
    return row


@router.patch("/v1/market/listings/{listing_id}", response_model=ListingOut, operation_id="updateMarketListing")
async def update_listing(listing_id: str, body: ListingPatch, user_id: str = Depends(current_user)):
    fields = body.model_fields_set - {"clear_payload", "clear_cover"}
    if not fields and not body.clear_payload and not body.clear_cover:
        raise HTTPException(status_code=422, detail={"code": "MARKET_NOTHING_TO_CHANGE", "message": "send at least one field"})
    with store._connect() as db:
        store.initialize()
        _init(db)
        row = _editable(db, listing_id, user_id)
        new = {k: row[k] for k in ("kind", "title", "description", "tags_json", "price", "payload_json", "cover_asset_id", "license_scope", "is_ai_generated")}
        if "kind" in fields:
            new["kind"] = _check_kind(body.kind or "")
        if "title" in fields:
            new["title"] = _clean_text(body.title, "title", limit=80, required=True)
        if "description" in fields:
            new["description"] = _clean_text(body.description, "description", limit=1000)
        if "tags" in fields:
            new["tags_json"] = json.dumps(_clean_tags(body.tags or []), ensure_ascii=False)
        if "price" in fields:
            new["price"] = _check_price(body.price)
        if "payload" in fields:
            new["payload_json"] = _clean_payload(body.payload)
        if body.clear_payload:
            new["payload_json"] = None
        if "cover_asset_id" in fields and body.cover_asset_id is not None:
            _cover_ok(row["workspace_id"], body.cover_asset_id, user_id)
            new["cover_asset_id"] = body.cover_asset_id
        if body.clear_cover:
            new["cover_asset_id"] = None
        if "license_scope" in fields:
            new["license_scope"] = _check_license(body.license_scope)
        if "is_ai_generated" in fields:
            if body.is_ai_generated is None:
                raise HTTPException(status_code=422, detail={"code": "MARKET_AI_FLAG_REQUIRED", "message": "true or false"})
            new["is_ai_generated"] = 1 if body.is_ai_generated else 0
        cur = db.execute("""UPDATE market_listings SET kind=?, title=?, description=?, tags_json=?, price=?, payload_json=?, cover_asset_id=?, license_scope=?, is_ai_generated=?,
            updated_at=?, version=version+1 WHERE listing_id=? AND version=?""", (new["kind"], new["title"], new["description"], new["tags_json"], new["price"], new["payload_json"],
                                                                                    new["cover_asset_id"], new["license_scope"], new["is_ai_generated"], _now(), listing_id, row["version"]))
        if cur.rowcount != 1:
            raise HTTPException(status_code=409, detail={"code": "MARKET_CHANGED", "message": "the listing was changed by someone else; reload it"})
        return _out(db, _get(db, listing_id), user_id, with_payload=True)


@router.post("/v1/market/listings/{listing_id}/publish", response_model=ListingOut, operation_id="publishMarketListing")
async def publish_listing(listing_id: str, body: PublishIn, user_id: str = Depends(current_user)):
    """Makes it public. The seller confirms the rights again at this moment (recorded: who, when)."""
    with store._connect() as db:
        store.initialize()
        _init(db)
        row = _editable(db, listing_id, user_id)
        if not body.rights_confirmed:
            raise HTTPException(status_code=422, detail={"code": "MARKET_RIGHTS_REQUIRED", "message": "confirm that you may sell this"})
        from app import reviews     # reply 40: a workspace that requires reviewed exports also requires a reviewed cover picture
        reviews.require_approved(row["workspace_id"], [row["cover_asset_id"]])
        now = _now()
        db.execute("UPDATE market_listings SET visibility='public', published_at=?, rights_confirmed_by=?, rights_confirmed_at=?, updated_at=?, version=version+1 WHERE listing_id=?",
                   (row["published_at"] or now, user_id, now, now, listing_id))
        return _out(db, _get(db, listing_id), user_id, with_payload=True)


@router.post("/v1/market/listings/{listing_id}/unpublish", response_model=ListingOut, operation_id="unpublishMarketListing")
async def unpublish_listing(listing_id: str, user_id: str = Depends(current_user)):
    with store._connect() as db:
        store.initialize()
        _init(db)
        _editable(db, listing_id, user_id)
        db.execute("UPDATE market_listings SET visibility='private', updated_at=?, version=version+1 WHERE listing_id=?", (_now(), listing_id))
        return _out(db, _get(db, listing_id), user_id, with_payload=True)


@router.delete("/v1/market/listings/{listing_id}", status_code=204, operation_id="removeMarketListing")
async def remove_listing(listing_id: str, user_id: str = Depends(current_user)):
    """Takes the listing out (kept as a record for open reports; nothing is erased)."""
    with store._connect() as db:
        store.initialize()
        _init(db)
        _editable(db, listing_id, user_id)
        db.execute("UPDATE market_listings SET status='deleted', visibility='private', updated_at=?, version=version+1 WHERE listing_id=?", (_now(), listing_id))
    return None


# --------------------------------------------------------------------------------------------------------------------- reports
class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["copyright", "likeness", "inappropriate", "fraud", "other"]
    details: str | None = Field(default=None, max_length=1000)


@router.post("/v1/market/listings/{listing_id}/reports", status_code=202, operation_id="reportMarketListing")
async def report_listing(listing_id: str, body: ReportIn, user_id: str = Depends(current_user)):
    """The answer is the same whether or not the listing exists or the report changed anything (no probing for listing ids)."""
    received = {"status": "received"}
    details = _clean_text(body.details, "details", limit=1000) or None
    with store._connect() as db:
        store.initialize()
        _init(db)
        row = db.execute("SELECT * FROM market_listings WHERE listing_id=? AND status='active' AND visibility='public'", (listing_id,)).fetchone()
        if row is None or row["created_by"] == user_id:
            return received
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        filed = db.execute("SELECT COUNT(*) AS n FROM market_reports WHERE reporter_id=? AND created_at>=?", (user_id, since)).fetchone()["n"]
        if filed >= config.MARKET_REPORT_DAILY_LIMIT:
            raise HTTPException(status_code=429, detail="Too many reports today")
        if db.execute("SELECT 1 FROM market_reports WHERE listing_id=? AND reporter_id=? AND status='open'", (listing_id, user_id)).fetchone():
            return received
        db.execute("INSERT INTO market_reports(report_id, listing_id, reporter_id, reason, details, status, created_at) VALUES (?,?,?,?,?,'open',?)",
                   ("mrp_" + uuid.uuid4().hex, listing_id, user_id, body.reason, details, _now()))
    return received


@router.get("/internal/market/reports", operation_id="listMarketReports")
async def list_market_reports(status: Literal["open", "all"] = "open", user_id: str = Depends(current_user)):
    """Operators only (read). Hiding a reported listing is an operator write and is not built yet (R-052)."""
    if user_id not in config.OPS_ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Platform operations role required")
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = db.execute("""SELECT r.report_id, r.listing_id, r.reason, r.details, r.status, r.created_at, r.reporter_id, l.title, l.status AS listing_status, l.visibility
            FROM market_reports r LEFT JOIN market_listings l ON l.listing_id=r.listing_id""" + ("" if status == "all" else " WHERE r.status='open'") + " ORDER BY r.created_at").fetchall()
    return {"items": [dict(r) for r in rows]}


# --------------------------------------------------------------------------------------------------------------------- seller profile
class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(max_length=100)
    bio: str = Field(default="", max_length=1000)


class ProfileOut(BaseModel):
    handle: str
    display_name: str | None
    bio: str
    listing_count: int
    member_since: str | None


def _profile_out(db, user_id: str, row) -> dict[str, Any]:
    n = db.execute("SELECT COUNT(*) AS n FROM market_listings WHERE created_by=? AND visibility='public' AND status='active'", (user_id,)).fetchone()["n"]
    return {"handle": handle_of(user_id), "display_name": row["display_name"] if row else None, "bio": row["bio"] if row else "", "listing_count": n,
            "member_since": row["created_at"] if row else None}


@router.get("/v1/market/profile", response_model=ProfileOut, operation_id="getMyMarketProfile")
async def my_profile(user_id: str = Depends(current_user)):
    with store._connect() as db:
        store.initialize()
        _init(db)
        return _profile_out(db, user_id, db.execute("SELECT * FROM market_profiles WHERE user_id=?", (user_id,)).fetchone())


@router.put("/v1/market/profile", response_model=ProfileOut, operation_id="putMyMarketProfile")
async def put_profile(body: ProfileIn, user_id: str = Depends(current_user)):
    name = _clean_text(body.display_name, "display_name", limit=40, required=True)
    bio = _clean_text(body.bio, "bio", limit=300)
    if NAME_BAD.search(name) or NAME_BAD.search(bio):
        raise HTTPException(status_code=422, detail={"code": "MARKET_PROFILE_INVALID", "message": "no links, e-mail addresses or markup in the name or the introduction"})
    with store._connect() as db:
        store.initialize()
        _init(db)
        now = _now()
        db.execute("""INSERT INTO market_profiles(user_id, display_name, bio, created_at, updated_at) VALUES (?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name, bio=excluded.bio, updated_at=excluded.updated_at""", (user_id, name, bio, now, now))
        return _profile_out(db, user_id, db.execute("SELECT * FROM market_profiles WHERE user_id=?", (user_id,)).fetchone())


@router.get("/v1/market/sellers/{handle}", response_model=ProfileOut, operation_id="getMarketSeller")
async def get_seller(handle: str, user_id: str = Depends(current_user)):
    with store._connect() as db:
        store.initialize()
        _init(db)
        for row in db.execute("SELECT * FROM market_profiles").fetchall():
            if handle_of(row["user_id"]) == handle:
                return _profile_out(db, row["user_id"], row)
    raise HTTPException(status_code=404, detail="Seller not found")
