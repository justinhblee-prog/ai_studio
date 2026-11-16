"""Lane 5: picture -> 3D model jobs (MOCK ONLY, like the video jobs). The input is one picture from the workspace's own library; the mock provider (``MockImageTo3D``) returns a tiny VALID
.glb that records the picture's hash and says it is no reconstruction; the result is stored as a normal 3D asset, goes through the normal .glb validation and is filed in the library as a
``3d`` item. A real provider is NOT connected: ``PROVIDER_MODE`` other than mock fails closed (409) so no picture can leave the service by this route. The job contract (queued / running /
succeeded / failed read through GET) is the one a real provider will need; the mock simply finishes inside the request.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import config, takedown
from app.assets import store
from app.assets.routes import current_user, require_role
from app.assets.validation import AssetValidationError, validate_gltf_upload

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/three-d-jobs", tags=["three-d-jobs"])
EVENT = "asset.three_d_output"
MAX_INPUT_BYTES = 25 * 1024 * 1024


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS three_d_jobs (
        job_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner_id TEXT NOT NULL, status TEXT NOT NULL, provider TEXT NOT NULL, input_item_id TEXT NOT NULL,
        input_asset_id TEXT NOT NULL, instruction TEXT, output_asset_id TEXT, library_item_id TEXT, error_code TEXT, created_at TEXT NOT NULL, finished_at TEXT)""")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_item_id: str = Field(min_length=4, max_length=80)
    prompt: str | None = Field(default=None, max_length=500)


class JobOut(BaseModel):
    job_id: str
    workspace_id: str
    owner_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    provider: str
    input_item_id: str
    input_asset_id: str
    prompt: str | None
    output_asset_id: str | None
    library_item_id: str | None
    error_code: str | None
    created_at: str
    finished_at: str | None


class JobListOut(BaseModel):
    items: list[JobOut]


def _public(row) -> dict[str, Any]:
    return {"job_id": row["job_id"], "workspace_id": row["workspace_id"], "owner_id": row["owner_id"], "status": row["status"], "provider": row["provider"],
            "input_item_id": row["input_item_id"], "input_asset_id": row["input_asset_id"], "prompt": row["instruction"], "output_asset_id": row["output_asset_id"],
            "library_item_id": row["library_item_id"], "error_code": row["error_code"], "created_at": row["created_at"], "finished_at": row["finished_at"]}


@router.post("", status_code=201, response_model=JobOut, operation_id="createThreeDJob")
async def create_job(workspace_id: str, body: JobIn, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    from app import rate_limit
    rate_limit.check("generate", user_id, workspace_id)
    if config.PROVIDER_MODE != "mock":
        raise HTTPException(status_code=409, detail={"code": "THREED_PROVIDER_NOT_CONNECTED", "message": "3D generation by an external AI service is not connected yet."})
    from app.tryon_inputs import _item
    row = _item(workspace_id, body.input_item_id)
    if row is None or not takedown.visible_to(row["asset_id"], user_id):
        raise HTTPException(status_code=404, detail={"code": "THREED_INPUT_NOT_FOUND", "message": "library item not found"})
    if row["kind"] == "3d" or not str(row["media_type"]).startswith("image/"):
        raise HTTPException(status_code=422, detail={"code": "THREED_INPUT_KIND", "message": "the input must be a picture item"})
    path = store.storage_path(row["asset_id"])
    if path is None or not path.is_file():
        raise HTTPException(status_code=409, detail={"code": "THREED_INPUT_GONE", "message": "the item's file is missing"})
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with store._connect() as db:
        _init(db)
        used = db.execute("SELECT COUNT(*) AS n FROM three_d_jobs WHERE workspace_id=? AND created_at>=?", (workspace_id, since)).fetchone()["n"]
    if used >= config.THREED_DAILY_LIMIT:
        raise rate_limit.too_many("THREED_DAILY_LIMIT", "today's 3D limit is used up", 3600, estimated=True, limit=config.THREED_DAILY_LIMIT, used=used)
    data = path.read_bytes()
    if len(data) > MAX_INPUT_BYTES:
        raise HTTPException(status_code=422, detail={"code": "THREED_INPUT_KIND", "message": "the picture is too large for 3D conversion"})
    from app.providers.mock3d import MockImageTo3D
    provider = MockImageTo3D()
    job_id, now, status, error, output_asset_id, item_id = "t3d_" + uuid.uuid4().hex, _now(), "failed", "GLB_INVALID", None, None
    glb = await provider.convert(data)
    try:                                       # the result is checked exactly like an uploaded model before it is delivered
        validated = validate_gltf_upload(f"{job_id[-6:]}.glb", glb, max_bytes=config.WORKSPACE_LIBRARY_MAX_3D_BYTES)
    except AssetValidationError:
        validated = None
    if validated is not None:
        saved = store.save_asset(owner_id=user_id, workspace_id=workspace_id, filename=f"model-{job_id[-6:]}.glb", content=glb, validated=validated, provenance_event=EVENT,
                                 provenance_extra={"job_id": job_id, "mode": "mock", "is_ai_generated": False, "source_asset_id": row["asset_id"], "is_reconstruction": False})
        output_asset_id, status, error = saved["asset_id"], "succeeded", None
        from app import workspace_library
        outcome = workspace_library.file_item(workspace_id, output_asset_id, user_id, "3d", f"3D {job_id[-6:]}", {"service": "3d", "source_asset_ids": [row["asset_id"]]})
        if outcome == "filed":
            with store._connect() as db:
                found = db.execute("SELECT item_id FROM workspace_library_items WHERE workspace_id=? AND asset_id=?", (workspace_id, output_asset_id)).fetchone()
                item_id = found["item_id"] if found else None
    with store._connect() as db:
        _init(db)
        db.execute("""INSERT INTO three_d_jobs(job_id, workspace_id, owner_id, status, provider, input_item_id, input_asset_id, instruction, output_asset_id, library_item_id, error_code,
            created_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (job_id, workspace_id, user_id, status, "mock3d", body.input_item_id, row["asset_id"], (body.prompt or "").strip() or None,
                                                                         output_asset_id, item_id, error, now, _now()))
        return _public(db.execute("SELECT * FROM three_d_jobs WHERE job_id=?", (job_id,)).fetchone())


@router.get("", response_model=JobListOut, operation_id="listThreeDJobs")
async def list_jobs(workspace_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = db.execute("SELECT * FROM three_d_jobs WHERE workspace_id=? ORDER BY created_at DESC, job_id LIMIT 100", (workspace_id,)).fetchall()
        return {"items": [_public(r) for r in rows]}


@router.get("/{job_id}", response_model=JobOut, operation_id="getThreeDJob")
async def get_job(workspace_id: str, job_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    with store._connect() as db:
        store.initialize()
        _init(db)
        row = db.execute("SELECT * FROM three_d_jobs WHERE job_id=? AND workspace_id=?", (job_id, workspace_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="3D job not found")
        return _public(row)
