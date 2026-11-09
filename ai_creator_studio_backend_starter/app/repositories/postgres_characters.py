"""PostgreSQL Character aggregate repository; not runtime-selected yet."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.postgres import apply_migrations, connect
from app.repo_errors import InsufficientRoleError, NotAMemberError, RepositoryConflictError


class CharacterConflictError(RepositoryConflictError):
    """Character is referenced by an active Lookbook draft."""


class PostgreSQLCharacterRepository:
    backend = "postgresql"
    WRITABLE_ROLES = {"owner", "admin", "editor"}
    READABLE_ROLES = WRITABLE_ROLES | {"viewer"}

    def initialize(self) -> None:
        apply_migrations()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _jsonb(value: dict[str, Any]):
        from psycopg.types.json import Jsonb
        return Jsonb(value)

    @staticmethod
    def _role(conn: Any, workspace_id: str, actor_id: str) -> str | None:
        row = conn.execute(
            "SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
            (workspace_id, actor_id),
        ).fetchone()
        return str(row["role"]) if row else None

    @classmethod
    def _require(cls, conn: Any, workspace_id: str, actor_id: str, *, write: bool) -> None:
        role = cls._role(conn, workspace_id, actor_id)
        if role is None:
            raise NotAMemberError("User is not a member of this workspace")
        if role not in (cls.WRITABLE_ROLES if write else cls.READABLE_ROLES):
            raise InsufficientRoleError("Workspace role cannot " + ("modify" if write else "read") + " characters")

    @staticmethod
    def _validate(payload: dict[str, Any], asset_ids: list[str]) -> str:
        identity = payload.get("identity") if isinstance(payload, dict) else None
        name = identity.get("name") if isinstance(identity, dict) else None
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise ValueError("Character identity.name must contain 1 to 120 characters")
        outfits = payload.get("outfits", [])
        if not isinstance(outfits, list) or len(outfits) > 100:
            raise ValueError("Character outfits must be a list of at most 100 items")
        active = payload.get("active_outfit_id")
        if active is not None and active not in {o.get("id") for o in outfits if isinstance(o, dict) and o.get("id")}:
            raise ValueError("active_outfit_id must reference an outfit in this character")
        if (not isinstance(asset_ids, list) or len(asset_ids) > 100 or len(asset_ids) != len(set(asset_ids))
                or any(not isinstance(a, str) or not a.strip() for a in asset_ids)):
            raise ValueError("asset_ids must be at most 100 unique non-empty strings")
        return name.strip()

    @staticmethod
    def _check_assets(conn: Any, workspace_id: str, asset_ids: list[str]) -> None:
        if not asset_ids:
            return
        rows = conn.execute(
            "SELECT asset_id FROM assets WHERE workspace_id=%s AND deleted_at IS NULL AND asset_id = ANY(%s) ORDER BY asset_id FOR SHARE",
            (workspace_id, asset_ids),
        ).fetchall()
        if {str(r["asset_id"]) for r in rows} != set(asset_ids):
            raise ValueError("Every linked asset must belong to this workspace and be active")

    @staticmethod
    def _active_lookbook_reference(conn: Any, workspace_id: str, character_id: str) -> bool:
        if conn.execute("SELECT to_regclass('public.lookbook_draft_entities') AS t").fetchone()["t"] is None:
            return False
        return conn.execute(
            """SELECT 1 FROM lookbook_draft_entities e
               JOIN lookbook_drafts d ON d.draft_id=e.draft_id
               WHERE e.entity_type='character' AND e.entity_id=%s AND d.workspace_id=%s
                 AND d.archived_at IS NULL LIMIT 1""",
            (character_id, workspace_id),
        ).fetchone() is not None

    @staticmethod
    def _read(conn: Any, row: Any) -> dict[str, Any]:
        value = dict(row["character_json"])
        links = conn.execute(
            "SELECT asset_id FROM character_assets WHERE character_id=%s ORDER BY sort_order,created_at,asset_id",
            (row["character_id"],),
        ).fetchall()
        return {
            "character_id": row["character_id"], "workspace_id": row["workspace_id"],
            "owner_id": row["owner_id"], "identity": value["identity"],
            "outfits": value.get("outfits", []), "active_outfit_id": value.get("active_outfit_id"),
            "asset_ids": [str(link["asset_id"]) for link in links],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    @staticmethod
    def _replace_links(conn: Any, character_id: str, asset_ids: list[str], now: datetime) -> None:
        conn.execute("DELETE FROM character_assets WHERE character_id=%s", (character_id,))
        if asset_ids:
            conn.cursor().executemany(
                "INSERT INTO character_assets(character_id,asset_id,relation,sort_order,created_at) VALUES(%s,%s,'model',%s,%s)",
                [(character_id, aid, i, now) for i, aid in enumerate(asset_ids)],
            )

    def create(self, *, workspace_id: str, actor_id: str, payload: dict[str, Any],
               asset_ids: list[str] | None = None) -> dict[str, Any]:
        asset_ids = list(asset_ids or [])
        name = self._validate(payload, asset_ids)
        character_id, now = "chr_" + uuid.uuid4().hex, self._now()
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            self._check_assets(conn, workspace_id, asset_ids)
            conn.execute(
                """INSERT INTO characters(character_id,workspace_id,owner_id,name,character_json,created_at,updated_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (character_id, workspace_id, actor_id, name, self._jsonb(payload), now, now),
            )
            self._replace_links(conn, character_id, asset_ids, now)
            row = conn.execute("SELECT * FROM characters WHERE character_id=%s", (character_id,)).fetchone()
            return self._read(conn, row)

    def list_for_workspace(self, workspace_id: str, actor_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=False)
            rows = conn.execute(
                "SELECT * FROM characters WHERE workspace_id=%s AND deleted_at IS NULL ORDER BY updated_at DESC, character_id",
                (workspace_id,),
            ).fetchall()
            return [self._read(conn, r) for r in rows]

    def get(self, character_id: str, workspace_id: str, actor_id: str) -> dict[str, Any] | None:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=False)
            row = conn.execute(
                "SELECT * FROM characters WHERE character_id=%s AND workspace_id=%s AND deleted_at IS NULL",
                (character_id, workspace_id),
            ).fetchone()
            return self._read(conn, row) if row else None

    def update(self, character_id: str, workspace_id: str, actor_id: str, *, payload: dict[str, Any],
               asset_ids: list[str] | None = None) -> dict[str, Any] | None:
        asset_ids = list(asset_ids or [])
        name = self._validate(payload, asset_ids)
        now = self._now()
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            row = conn.execute(
                "SELECT character_id FROM characters WHERE character_id=%s AND workspace_id=%s AND deleted_at IS NULL FOR UPDATE",
                (character_id, workspace_id),
            ).fetchone()
            if row is None:
                return None
            if self._active_lookbook_reference(conn, workspace_id, character_id):
                raise CharacterConflictError("Character is referenced by an active Lookbook Draft; archive the draft before editing the Character")
            self._check_assets(conn, workspace_id, asset_ids)
            conn.execute(
                "UPDATE characters SET name=%s, character_json=%s, updated_at=%s WHERE character_id=%s AND workspace_id=%s",
                (name, self._jsonb(payload), now, character_id, workspace_id),
            )
            self._replace_links(conn, character_id, asset_ids, now)
            return self._read(conn, conn.execute("SELECT * FROM characters WHERE character_id=%s", (character_id,)).fetchone())

    def soft_delete(self, character_id: str, workspace_id: str, actor_id: str) -> bool:
        now = self._now()
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            row = conn.execute(
                "SELECT character_id FROM characters WHERE character_id=%s AND workspace_id=%s AND deleted_at IS NULL FOR UPDATE",
                (character_id, workspace_id),
            ).fetchone()
            if row is None:
                return False
            if self._active_lookbook_reference(conn, workspace_id, character_id):
                raise CharacterConflictError("Character is referenced by an active Lookbook Draft; archive the draft first")
            conn.execute("UPDATE characters SET deleted_at=%s, updated_at=%s WHERE character_id=%s", (now, now, character_id))
            return True
