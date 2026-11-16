"""R-044 A-2: run the local photo steps on one of the workspace's own image assets and store the result as a NEW asset.
The source asset is only read. Nothing leaves the server: no provider, no AI (``is_ai_generated`` is false, mode is local)."""
from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from app import photo_steps
from app.assets import store
from app.assets.routes import current_user, require_role
from app.assets.validation import AssetValidationError, validate_image_upload
from app.config import ASSET_MAX_UPLOAD_BYTES
from app.viewer_responses import AssetRecordResponse

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/photo-steps", tags=["photo-steps"])
EVENT = "asset.photo_steps"


class PhotoStepsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=3, max_length=80)
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=photo_steps.MAX_STEPS)


class PhotoStepsResponse(BaseModel):
    asset: AssetRecordResponse
    steps: list[dict[str, Any]]


@router.post("", status_code=201, response_model=PhotoStepsResponse, operation_id="runPhotoSteps")
async def run_photo_steps(workspace_id: str, body: PhotoStepsRequest, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    source = store.get_asset(body.asset_id, workspace_id)
    if source is None or source.get("asset_kind") != "image":
        raise HTTPException(status_code=404, detail="Image asset not found")
    path = store.storage_path(body.asset_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Image asset not found")
    try:
        photo_steps.validate_steps(body.steps)
        with Image.open(path) as opened:
            opened.load()
            result, records = photo_steps.run_steps(opened, body.steps)
    except photo_steps.StepError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    except (OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=422, detail={"code": "IMAGE_UNREADABLE", "message": "The source image could not be processed."}) from exc
    buffer = io.BytesIO()
    result.save(buffer, format="PNG")
    content = buffer.getvalue()
    filename = f"{str(source['original_filename']).rsplit('.', 1)[0]}-edited.png"
    try:
        validated = validate_image_upload(filename, content, max_bytes=ASSET_MAX_UPLOAD_BYTES)
    except AssetValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    saved = store.save_asset(
        owner_id=user_id, workspace_id=workspace_id, filename=filename, content=content, validated=validated, provenance_event=EVENT,
        provenance_extra={"source_asset_id": body.asset_id, "mode": "local", "is_ai_generated": False,
                          "steps": [{k: r[k] for k in ("op", "size_in", "size_out")} for r in records]})
    return {"asset": saved, "steps": records}
