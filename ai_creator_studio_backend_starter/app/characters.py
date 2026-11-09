"""Workspace-scoped persistent character catalog and asset associations."""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from app.viewer_responses import CharacterListResponse, CharacterResponse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.assets.routes import current_user
from app.assets.store import _connect
from app.ports.characters import get_character_port
from app.repo_errors import raise_http

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/characters", tags=["characters"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _initialize() -> None:
    with _connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS characters (
            character_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
            owner_id TEXT NOT NULL,
            name TEXT NOT NULL,
            character_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_characters_workspace ON characters(workspace_id, deleted_at, updated_at)")
        db.execute("""CREATE TABLE IF NOT EXISTS character_assets (
            character_id TEXT NOT NULL REFERENCES characters(character_id) ON DELETE CASCADE,
            asset_id TEXT NOT NULL REFERENCES assets(asset_id),
            relation TEXT NOT NULL DEFAULT 'model',
            created_at TEXT NOT NULL,
            PRIMARY KEY(character_id, asset_id, relation)
        )""")
        db.executescript("""
        CREATE TRIGGER IF NOT EXISTS trg_character_assets_workspace_insert
        BEFORE INSERT ON character_assets BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM characters c JOIN assets a ON a.asset_id=NEW.asset_id
                WHERE c.character_id=NEW.character_id AND c.workspace_id=a.workspace_id
            ) THEN RAISE(ABORT, 'character asset workspace mismatch') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_character_assets_workspace_update
        BEFORE UPDATE OF character_id,asset_id ON character_assets BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM characters c JOIN assets a ON a.asset_id=NEW.asset_id
                WHERE c.character_id=NEW.character_id AND c.workspace_id=a.workspace_id
            ) THEN RAISE(ABORT, 'character asset workspace mismatch') END;
        END;
        """)


class Identity(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = Field(min_length=1, max_length=120)
    gender: str = Field(default="unspecified", max_length=32)
    age_range: str = Field(default="adult", max_length=32)
    face_shape: str = Field(default="unspecified", max_length=64)
    eye_shape: str = Field(default="unspecified", max_length=64)
    nose_shape: str = Field(default="unspecified", max_length=64)
    lip_shape: str = Field(default="unspecified", max_length=64)
    hairstyle: str = Field(default="unspecified", max_length=100)
    hair_color: str = Field(default="unspecified", max_length=64)
    body_type: str = Field(default="unspecified", max_length=64)
    skin_tone: str = Field(default="unspecified", max_length=64)
    skin_texture: str = Field(default="natural", max_length=100)
    distinguishing_features: list[str] = Field(default_factory=list, max_length=30)


class Outfit(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="custom", max_length=40)
    top: str = Field(default="", max_length=300)
    bottom: str = Field(default="", max_length=300)
    shoes: str = Field(default="", max_length=300)
    accessories: list[str] = Field(default_factory=list, max_length=50)
    description: str = Field(default="", max_length=2000)


class CharacterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity: Identity
    outfits: list[Outfit] = Field(default_factory=list, max_length=100)
    active_outfit_id: str | None = Field(default=None, max_length=80)
    asset_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def active_outfit_exists(self):
        ids = {o.id for o in self.outfits if o.id}
        if self.active_outfit_id and self.active_outfit_id not in ids:
            raise ValueError("active_outfit_id must reference an outfit in this character")
        if len(self.asset_ids) != len(set(self.asset_ids)):
            raise ValueError("asset_ids must be unique")
        return self


class CharacterPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity: Identity
    outfits: list[Outfit] = Field(default_factory=list, max_length=100)
    active_outfit_id: str | None = Field(default=None, max_length=80)
    asset_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def active_outfit_exists(self):
        ids = {o.id for o in self.outfits if o.id}
        if self.active_outfit_id and self.active_outfit_id not in ids:
            raise ValueError("active_outfit_id must reference an outfit in this character")
        if len(self.asset_ids) != len(set(self.asset_ids)):
            raise ValueError("asset_ids must be unique")
        return self


def _read(row: sqlite3.Row) -> dict[str, Any]:
    value = json.loads(row["character_json"])
    with _connect() as db:
        links = db.execute("SELECT asset_id, relation FROM character_assets WHERE character_id=? ORDER BY created_at", (row["character_id"],)).fetchall()
    return {
        "character_id": row["character_id"], "workspace_id": row["workspace_id"],
        "owner_id": row["owner_id"], "identity": value["identity"], "outfits": value["outfits"],
        "active_outfit_id": value["active_outfit_id"],
        "asset_ids": [link["asset_id"] for link in links],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def _get(character_id: str, workspace_id: str):
    _initialize()
    with _connect() as db:
        return db.execute("SELECT * FROM characters WHERE character_id=? AND workspace_id=? AND deleted_at IS NULL", (character_id, workspace_id)).fetchone()


@router.post("", status_code=201, response_model=CharacterResponse)
async def create_character(workspace_id: str, body: CharacterInput, user_id: str = Depends(current_user)):
    try:
        return get_character_port().create(workspace_id, user_id, body.model_dump(mode="json", exclude={"asset_ids"}), body.asset_ids)
    except Exception as exc:
        raise_http(exc)


@router.get("", response_model=CharacterListResponse)
async def list_characters(workspace_id: str, user_id: str = Depends(current_user)):
    try:
        return get_character_port().list(workspace_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(workspace_id: str, character_id: str, user_id: str = Depends(current_user)):
    try:
        return get_character_port().get(workspace_id, character_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(workspace_id: str, character_id: str, body: CharacterPatch, user_id: str = Depends(current_user)):
    try:
        return get_character_port().update(workspace_id, character_id, user_id,
                                           body.model_dump(mode="json", exclude={"asset_ids"}), body.asset_ids)
    except Exception as exc:
        raise_http(exc)


@router.delete("/{character_id}", status_code=204)
async def delete_character(workspace_id: str, character_id: str, user_id: str = Depends(current_user)):
    try:
        get_character_port().delete(workspace_id, character_id, user_id)
    except Exception as exc:
        raise_http(exc)
    return None
