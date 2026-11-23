"""D-2 API: ``POST /v1/workspaces/{id}/photo-body`` {asset_id, sex, height_cm?} -> the ESTIMATED own3d measurements of the person in one of the workspace's own full-body photos
(``app/photo_body.py``), ready to be given to a 3D render (``render3d-jobs``) as ``measurements``. Editor or above, behind the own3d flag (RENDER3D_ENABLED, default OFF -> 409), nothing is stored,
no AI, no network. The picture is only read."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import config, photo_body
from app.assets import store
from app.assets.routes import current_user, require_role

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/photo-body", tags=["photo-body"])


class PhotoBodyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=3, max_length=80)
    sex: Literal["male", "female"]
    height_cm: float | None = Field(default=None, ge=120, le=220)


@router.post("", operation_id="estimatePhotoBody")
async def estimate_body(workspace_id: str, body: PhotoBodyIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    if not getattr(config, "RENDER3D_ENABLED", False):
        raise HTTPException(status_code=409, detail={"code": "RENDER3D_CLOSED", "message": "The 3D render job is not open yet."})
    source = store.get_asset(body.asset_id, workspace_id)
    path = store.storage_path(body.asset_id) if source else None
    if source is None or path is None or source.get("asset_kind") != "image":
        raise HTTPException(status_code=404, detail="Image asset not found")
    try:
        return photo_body.estimate(path.read_bytes(), sex=body.sex, height_cm=body.height_cm)
    except photo_body.PhotoBodyError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
