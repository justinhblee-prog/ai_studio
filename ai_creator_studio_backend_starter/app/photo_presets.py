"""R-044 A (item 19): brand presets = a named, validated list of local photo steps, saved per workspace and re-applied with one click.
A preset holds only step names and parameters (no image, no secret). Max 50 per workspace; names are unique inside a workspace."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import photo_steps
from app.assets import store
from app.assets.routes import current_user, require_role

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/photo-presets", tags=["photo-presets"])
MAX_PRESETS = 50


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS photo_presets (
        preset_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner_id TEXT NOT NULL, name TEXT NOT NULL,
        steps_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(workspace_id, name))""")


class PresetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=photo_steps.MAX_STEPS)


class PresetResponse(BaseModel):
    preset_id: str
    workspace_id: str
    owner_id: str
    name: str
    steps: list[dict[str, Any]]
    created_at: str


class PresetListResponse(BaseModel):
    items: list[PresetResponse]


def _public(row) -> dict[str, Any]:
    return {"preset_id": row["preset_id"], "workspace_id": row["workspace_id"], "owner_id": row["owner_id"], "name": row["name"],
            "steps": json.loads(row["steps_json"]), "created_at": row["created_at"]}


@router.get("", response_model=PresetListResponse, operation_id="listPhotoPresets")
async def list_presets(workspace_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    with store._connect() as db:
        _init(db)
        rows = db.execute("SELECT * FROM photo_presets WHERE workspace_id=? ORDER BY created_at, name", (workspace_id,)).fetchall()
    return {"items": [_public(r) for r in rows]}


@router.post("", status_code=201, response_model=PresetResponse, operation_id="createPhotoPreset")
async def create_preset(workspace_id: str, body: PresetInput, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    try:
        steps = photo_steps.validate_steps(body.steps)
    except photo_steps.StepError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail={"code": "PRESET_NAME_REQUIRED", "message": "name must not be blank"})
    preset_id = "pst_" + uuid.uuid4().hex
    with store._connect() as db:
        _init(db)
        if db.execute("SELECT COUNT(*) AS n FROM photo_presets WHERE workspace_id=?", (workspace_id,)).fetchone()["n"] >= MAX_PRESETS:
            raise HTTPException(status_code=409, detail={"code": "PRESET_LIMIT", "message": f"at most {MAX_PRESETS} presets per workspace"})
        if db.execute("SELECT 1 FROM photo_presets WHERE workspace_id=? AND name=?", (workspace_id, name)).fetchone():
            raise HTTPException(status_code=409, detail={"code": "PRESET_NAME_TAKEN", "message": "a preset with this name exists"})
        now = datetime.now(timezone.utc).isoformat()
        db.execute("INSERT INTO photo_presets(preset_id, workspace_id, owner_id, name, steps_json, created_at) VALUES (?,?,?,?,?,?)",
                   (preset_id, workspace_id, user_id, name, json.dumps(steps, ensure_ascii=False), now))
        row = db.execute("SELECT * FROM photo_presets WHERE preset_id=?", (preset_id,)).fetchone()
    return _public(row)


@router.delete("/{preset_id}", status_code=204, operation_id="deletePhotoPreset")
async def delete_preset(workspace_id: str, preset_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    with store._connect() as db:
        _init(db)
        cur = db.execute("DELETE FROM photo_presets WHERE preset_id=? AND workspace_id=?", (preset_id, workspace_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Preset not found")
    return None
