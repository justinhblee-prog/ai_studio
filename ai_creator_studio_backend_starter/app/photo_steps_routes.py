"""R-044 A-2: run the local photo steps on one of the workspace's own image assets and store the result as a NEW asset.
The source asset is only read. Nothing leaves the server: no provider, no AI (``is_ai_generated`` is false, mode is local)."""
from __future__ import annotations

import io
import json
import uuid
from typing import Any, Literal

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


def _process_one(workspace_id: str, user_id: str, asset_id: str, steps: list[dict[str, Any]], extra: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run the steps on one image asset and store the result as a NEW asset. Raises HTTPException (404 / 422) exactly as the single-image route always did."""
    source = store.get_asset(asset_id, workspace_id)
    if source is None or source.get("asset_kind") != "image":
        raise HTTPException(status_code=404, detail="Image asset not found")
    path = store.storage_path(asset_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Image asset not found")
    try:
        photo_steps.validate_steps(steps)
        with Image.open(path) as opened:
            opened.load()
            result, records = photo_steps.run_steps(opened, steps)
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
        provenance_extra={"source_asset_id": asset_id, "mode": "local", "is_ai_generated": False,
                          "steps": [{k: r[k] for k in ("op", "size_in", "size_out")} for r in records], **(extra or {})})
    return saved, records


@router.post("", status_code=201, response_model=PhotoStepsResponse, operation_id="runPhotoSteps")
async def run_photo_steps(workspace_id: str, body: PhotoStepsRequest, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    from app import rate_limit    # R-067
    rate_limit.check("generate", user_id, workspace_id)
    saved, records = _process_one(workspace_id, user_id, body.asset_id, body.steps)
    return {"asset": saved, "steps": records}


# ------------------------------------------------------------------------------------------------------------- E-09e: one recipe, many images
MAX_BATCH = 20


class PhotoStepsBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_ids: list[str] = Field(min_length=1, max_length=MAX_BATCH)
    steps: list[dict[str, Any]] | None = Field(default=None, min_length=1, max_length=photo_steps.MAX_STEPS)
    preset_id: str | None = Field(default=None, min_length=3, max_length=80)


class BatchItem(BaseModel):
    asset_id: str
    status: Literal["ok", "failed", "not_run"]
    asset: AssetRecordResponse | None = None
    steps: list[dict[str, Any]] | None = None
    error_code: str | None = None
    message: str | None = None


class PhotoStepsBatchResponse(BaseModel):
    batch_id: str
    preset_id: str | None
    total: int
    succeeded: int
    failed: int
    not_run: int
    items: list[BatchItem]


def _preset_steps(workspace_id: str, preset_id: str) -> list[dict[str, Any]]:
    from app import photo_presets
    with store._connect() as db:
        photo_presets._init(db)
        row = db.execute("SELECT steps_json FROM photo_presets WHERE preset_id=? AND workspace_id=?", (preset_id, workspace_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    return json.loads(row["steps_json"])


@router.post("/batch", status_code=201, response_model=PhotoStepsBatchResponse, operation_id="runPhotoStepsBatch")
async def run_photo_steps_batch(workspace_id: str, body: PhotoStepsBatchRequest, user_id: str = Depends(current_user)):
    """Apply ONE recipe (the given steps, or a saved preset of this workspace) to up to 20 of the workspace's images. The recipe is checked once before anything runs (a bad recipe changes nothing);
    then each image is processed on its own: one that fails (missing, not an image, too large after enlarging) is reported and the others still go ahead. Every image counts against the
    generation rate limit; when the limit is reached the remaining images are reported as ``not_run`` (nothing is queued). Each result is a NEW asset; the sources are never changed."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    if (body.steps is None) == (body.preset_id is None):
        raise HTTPException(status_code=422, detail={"code": "BATCH_RECIPE_REQUIRED", "message": "give either steps or preset_id, not both and not neither"})
    if len(set(body.asset_ids)) != len(body.asset_ids):
        raise HTTPException(status_code=422, detail={"code": "BATCH_DUPLICATE_ASSET", "message": "each image may be listed once"})
    steps = body.steps if body.steps is not None else _preset_steps(workspace_id, body.preset_id or "")
    try:
        plan = photo_steps.validate_steps(steps)
    except photo_steps.StepError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    from app import rate_limit    # R-067
    batch_id, items, stopped = "pbt_" + uuid.uuid4().hex, [], False
    for asset_id in body.asset_ids:
        if stopped:
            items.append({"asset_id": asset_id, "status": "not_run", "error_code": "RATE_LIMITED", "message": "the generation limit was reached; run this image later"})
            continue
        try:
            rate_limit.check("generate", user_id, workspace_id)
        except HTTPException as exc:
            if exc.status_code != 429:
                raise
            stopped = True
            items.append({"asset_id": asset_id, "status": "not_run", "error_code": "RATE_LIMITED", "message": "the generation limit was reached; run this image later"})
            continue
        try:
            saved, records = _process_one(workspace_id, user_id, asset_id, plan, {"batch_id": batch_id, **({"preset_id": body.preset_id} if body.preset_id else {})})
            items.append({"asset_id": asset_id, "status": "ok", "asset": saved, "steps": records})
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"code": "ASSET_NOT_FOUND" if exc.status_code == 404 else "STEP_FAILED", "message": str(exc.detail)}
            items.append({"asset_id": asset_id, "status": "failed", "error_code": detail.get("code"), "message": detail.get("message")})
    count = lambda status: sum(1 for i in items if i["status"] == status)  # noqa: E731
    return {"batch_id": batch_id, "preset_id": body.preset_id, "total": len(items), "succeeded": count("ok"), "failed": count("failed"), "not_run": count("not_run"), "items": items}
