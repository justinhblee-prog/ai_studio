"""Character port: one interface, a SQLite implementation (current behaviour) and a PostgreSQL one."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from app.ports.workspace import WorkspacePort, get_workspace_port, require_role
from app.repository_registry import require_runtime_backend


from app.repositories.postgres_characters import CharacterConflictError as CharacterConflict  # noqa: E402  single source


class CharacterPort(Protocol):
    def create(self, workspace_id: str, user_id: str, payload: dict[str, Any], asset_ids: list[str]) -> dict[str, Any]: ...
    def list(self, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def get(self, workspace_id: str, character_id: str, user_id: str) -> dict[str, Any]: ...
    def update(self, workspace_id: str, character_id: str, user_id: str, payload: dict[str, Any], asset_ids: list[str]) -> dict[str, Any]: ...
    def delete(self, workspace_id: str, character_id: str, user_id: str) -> None: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteCharacterPort:
    """Preserves the pre-port SQLite behaviour exactly; only the error carriers changed."""

    def __init__(self, workspaces: WorkspacePort | None = None):
        self._workspaces = workspaces or get_workspace_port()

    def _role(self, workspace_id: str, user_id: str, write: bool = False) -> None:
        require_role(self._workspaces, workspace_id, user_id, write=write)

    @staticmethod
    def _assets_belong_to_workspace(workspace_id: str, asset_ids: list[str]) -> None:
        if not asset_ids:
            return
        from app.assets.store import _connect
        from app.characters import _initialize
        _initialize()
        placeholders = ",".join("?" for _ in asset_ids)
        with _connect() as db:
            rows = db.execute(
                f"SELECT asset_id FROM assets WHERE workspace_id=? AND deleted_at IS NULL AND asset_id IN ({placeholders})",
                [workspace_id, *asset_ids]).fetchall()
        if {r["asset_id"] for r in rows} != set(asset_ids):
            raise ValueError("Every linked asset must belong to this workspace and be active")

    @staticmethod
    def _referenced_by_active_lookbook(db, workspace_id: str, character_id: str) -> bool:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='lookbook_draft_entities'").fetchone():
            return False
        return db.execute("""SELECT 1 FROM lookbook_draft_entities e
            JOIN lookbook_drafts d ON d.draft_id=e.draft_id
            WHERE e.entity_type='character' AND e.entity_id=? AND d.workspace_id=?
              AND d.archived_at IS NULL LIMIT 1""", (character_id, workspace_id)).fetchone() is not None

    def create(self, workspace_id, user_id, payload, asset_ids):
        from app.assets.store import _connect
        from app.characters import _get, _initialize, _read
        self._role(workspace_id, user_id, True)
        self._assets_belong_to_workspace(workspace_id, asset_ids)
        _initialize()
        character_id, now = "chr_" + uuid.uuid4().hex, _now()
        with _connect() as db:
            db.execute("INSERT INTO characters VALUES(?,?,?,?,?,?,?,NULL)",
                       (character_id, workspace_id, user_id, payload["identity"]["name"],
                        json.dumps(payload, ensure_ascii=False), now, now))
            db.executemany("INSERT INTO character_assets(character_id,asset_id,relation,created_at) VALUES(?,?,?,?)",
                           [(character_id, aid, "model", now) for aid in asset_ids])
        return _read(_get(character_id, workspace_id))

    def list(self, workspace_id, user_id):
        from app.assets.store import _connect
        from app.characters import _initialize, _read
        self._role(workspace_id, user_id)
        _initialize()
        with _connect() as db:
            rows = db.execute("SELECT * FROM characters WHERE workspace_id=? AND deleted_at IS NULL ORDER BY updated_at DESC",
                              (workspace_id,)).fetchall()
        return {"items": [_read(row) for row in rows]}

    def get(self, workspace_id, character_id, user_id):
        from app.characters import _get, _read
        self._role(workspace_id, user_id)
        row = _get(character_id, workspace_id)
        if not row:
            raise LookupError("Character not found")
        return _read(row)

    def update(self, workspace_id, character_id, user_id, payload, asset_ids):
        from app.assets.store import _connect
        from app.characters import _get, _read
        self._role(workspace_id, user_id, True)
        if not _get(character_id, workspace_id):
            raise LookupError("Character not found")
        with _connect() as probe:
            if self._referenced_by_active_lookbook(probe, workspace_id, character_id):
                raise CharacterConflict("Character is referenced by an active Lookbook Draft; archive the draft before editing the Character")
        self._assets_belong_to_workspace(workspace_id, asset_ids)
        now = _now()
        with _connect() as db:
            db.execute("UPDATE characters SET name=?, character_json=?, updated_at=? WHERE character_id=? AND workspace_id=?",
                       (payload["identity"]["name"], json.dumps(payload, ensure_ascii=False), now, character_id, workspace_id))
            db.execute("DELETE FROM character_assets WHERE character_id=?", (character_id,))
            db.executemany("INSERT INTO character_assets(character_id,asset_id,relation,created_at) VALUES(?,?,?,?)",
                           [(character_id, aid, "model", now) for aid in asset_ids])
        return _read(_get(character_id, workspace_id))

    def delete(self, workspace_id, character_id, user_id):
        from app.assets.store import _connect
        from app.characters import _get
        self._role(workspace_id, user_id, True)
        if not _get(character_id, workspace_id):
            raise LookupError("Character not found")
        with _connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._referenced_by_active_lookbook(db, workspace_id, character_id):
                raise CharacterConflict("Character is referenced by an active Lookbook Draft; archive the draft first")
            db.execute("UPDATE characters SET deleted_at=?, updated_at=? WHERE character_id=?", (_now(), _now(), character_id))


def _iso(value: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in value.items()}


class PostgreSQLCharacterPort:
    """Adapts PostgreSQLCharacterRepository (which performs its own membership/role checks)."""

    def __init__(self, repository=None):
        if repository is None:
            from app.repository_registry import build_postgres_repository
            repository = build_postgres_repository("characters")
        self._repo = repository

    def create(self, workspace_id, user_id, payload, asset_ids):
        return _iso(self._repo.create(workspace_id=workspace_id, actor_id=user_id, payload=payload, asset_ids=asset_ids))

    def list(self, workspace_id, user_id):
        return {"items": [_iso(i) for i in self._repo.list_for_workspace(workspace_id, user_id)]}

    def get(self, workspace_id, character_id, user_id):
        row = self._repo.get(character_id, workspace_id, user_id)
        if row is None:
            raise LookupError("Character not found")
        return _iso(row)

    def update(self, workspace_id, character_id, user_id, payload, asset_ids):
        row = self._repo.update(character_id, workspace_id, user_id, payload=payload, asset_ids=asset_ids)
        if row is None:
            raise LookupError("Character not found")
        return _iso(row)

    def delete(self, workspace_id, character_id, user_id):
        if not self._repo.soft_delete(character_id, workspace_id, user_id):
            raise LookupError("Character not found")


def get_character_port() -> CharacterPort:
    return SQLiteCharacterPort() if require_runtime_backend() == "sqlite" else PostgreSQLCharacterPort()
