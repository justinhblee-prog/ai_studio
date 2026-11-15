"""Default asset library API (R-032). Read-only for every signed-in user; the only write is the copy into the caller's own workspace."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app import library
from app.assets.routes import current_user, require_role
from app.viewer_responses import AssetRecordResponse

router = APIRouter(prefix="/v1/library", tags=["library"])

Category = Literal["model", "top", "bottom", "dress", "outer", "bag", "hat", "eyewear", "shoes", "jewelry", "headwear", "belt_scarf", "background"]


class LibraryItemResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    item_id: str
    category: str
    subcategory: str | None = None
    name_ko: str
    name_en: str | None = None
    tags: list[str]
    attributes: dict[str, str]
    version: int
    media_type: str
    width: int
    height: int
    source: str
    is_ai_generated: bool
    is_placeholder: bool


class LibraryListResponse(BaseModel):
    items: list[LibraryItemResponse]
    next_cursor: str | None = None


class LibraryPreviewUrlResponse(BaseModel):
    url: str
    expires_at: int


class LibraryImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]+$")


def _raise(exc: library.LibraryError):
    detail: object = {"code": exc.code, "message": str(exc)}
    if isinstance(exc, library.LibraryLimitError):
        detail = {"code": exc.code, "message": str(exc), "limit": exc.limit, "used": exc.used}
    raise HTTPException(status_code=exc.status, detail=detail) from exc


@router.get("/items", response_model=LibraryListResponse, operation_id="listLibraryItems")
async def list_library_items(category: Category | None = None, q: str | None = Query(default=None, max_length=80),
                             skin_tone: str | None = Query(default=None, max_length=10), hair: str | None = Query(default=None, max_length=20),
                             body_type: str | None = Query(default=None, max_length=20), age_range: str | None = Query(default=None, max_length=10),
                             region_style: str | None = Query(default=None, max_length=30),
                             limit: int = Query(default=24, ge=1, le=100), cursor: str | None = Query(default=None, max_length=80),
                             user_id: str = Depends(current_user)):
    attributes = {"skin_tone": skin_tone, "hair": hair, "body_type": body_type, "age_range": age_range, "region_style": region_style}
    return library.list_items(category=category, q=q, attributes={k: v for k, v in attributes.items() if v}, limit=limit, cursor=cursor)


@router.get("/items/{item_id}", response_model=LibraryItemResponse, operation_id="getLibraryItem")
async def get_library_item(item_id: str, user_id: str = Depends(current_user)):
    item = library.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    return item


@router.get("/items/{item_id}/preview-url", response_model=LibraryPreviewUrlResponse, operation_id="getLibraryItemPreviewUrl")
async def library_preview_url(item_id: str, user_id: str = Depends(current_user)):
    try:
        return library.preview_url(item_id)
    except library.LibraryError as exc:
        _raise(exc)


@router.get("/items/{item_id}/versions/{version}/preview", operation_id="previewLibraryItem")
async def preview_library_item(item_id: str, version: int, expires: int, signature: str):
    """Short-lived signed link (like the asset preview links): usable by an <img> tag, valid for the item's current version only."""
    try:
        content, media_type = library.preview_bytes(item_id, version, expires, signature)
    except library.LibraryError as exc:
        _raise(exc)
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "private, max-age=60", "X-Content-Type-Options": "nosniff"})


@router.post("/items/{item_id}/import", status_code=201, response_model=AssetRecordResponse, operation_id="importLibraryItem")
async def import_library_item(item_id: str, body: LibraryImportRequest, user_id: str = Depends(current_user)):
    """Copy a published item into the caller's workspace as an ordinary asset (editor role or higher). The item itself is never changed."""
    require_role(body.workspace_id, user_id, {"owner", "admin", "editor"})
    try:
        return library.import_to_workspace(item_id, body.workspace_id, user_id)
    except library.LibraryError as exc:
        _raise(exc)
