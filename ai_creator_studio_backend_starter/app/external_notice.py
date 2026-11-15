"""Acknowledgement of the external-transfer notice (R-037): "this job sends your photos to an external AI service (<provider>)".
A member records it once per workspace and provider; a job for a real provider is refused until the creator has done so."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.assets.routes import current_user, require_role
from app.provider_registry import list_capabilities

router = APIRouter(prefix="/v1/external-provider-notices", tags=["external-provider-notices"])


def known_external_providers() -> set[str]:
    return {r["provider_id"] for r in list_capabilities() if r["provider_id"] != "mock"}


def _db():
    from app.assets import store
    store.initialize()
    return store._connect()


def acknowledged(workspace_id: str, actor_id: str, provider: str) -> bool:
    with _db() as db:
        return db.execute("SELECT 1 FROM external_provider_notices WHERE workspace_id=? AND actor_id=? AND provider=?",
                          (workspace_id, actor_id, provider)).fetchone() is not None


class NoticeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]+$")
    provider: str = Field(min_length=2, max_length=40)


class NoticeResponse(BaseModel):
    provider: str
    acknowledged: bool
    acknowledged_at: str


@router.post("", response_model=NoticeResponse, operation_id="acknowledgeExternalProviderNotice")
async def acknowledge(body: NoticeRequest, user_id: str = Depends(current_user)):
    require_role(body.workspace_id, user_id, {"owner", "admin", "editor"})
    provider = body.provider.strip().lower()
    if provider not in known_external_providers():
        raise HTTPException(status_code=422, detail={"code": "UNKNOWN_PROVIDER", "message": "Unknown external provider."})
    now = datetime.now(timezone.utc).isoformat()
    with _db() as db:
        db.execute("INSERT OR IGNORE INTO external_provider_notices(notice_id,workspace_id,actor_id,provider,created_at) VALUES(?,?,?,?,?)",
                   ("epn_" + uuid.uuid4().hex, body.workspace_id, user_id, provider, now))
        at = db.execute("SELECT created_at FROM external_provider_notices WHERE workspace_id=? AND actor_id=? AND provider=?",
                        (body.workspace_id, user_id, provider)).fetchone()["created_at"]
    return {"provider": provider, "acknowledged": True, "acknowledged_at": at}
