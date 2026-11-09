"""Asset *metadata* port: SQLite (current behaviour) and PostgreSQL adapter.

Metadata operations only; uploads/versions/restore/audit live in ``asset_bytes``. ``delete`` removes the
asset row state and, after that commit, the object files (SQLite via the legacy store, PostgreSQL via LocalBlobStore).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Protocol

from app.ports.workspace import WorkspacePort, get_workspace_port, require_role
from app.repository_registry import require_runtime_backend
from app.repositories.postgres_assets import AssetConflictError as AssetConflict

ASSET_NOT_FOUND = "Asset not found"
RELATED_NOT_FOUND = "Related asset not found in this workspace"
RELATION_EXISTS = "This asset relation already exists"
_PUBLIC_DROP = {"storage_key"}  # legacy contract hides only the private storage key


class AssetMetadataPort(Protocol):
    def get(self, asset_id: str, user_id: str) -> dict[str, Any]: ...
    def list(self, workspace_id: str, user_id: str, kind: str) -> dict[str, Any]: ...
    def versions(self, asset_id: str, user_id: str) -> dict[str, Any]: ...
    def provenance(self, asset_id: str, user_id: str, limit: int, offset: int) -> dict[str, Any]: ...
    def relations(self, asset_id: str, user_id: str) -> dict[str, Any]: ...
    def add_relation(self, asset_id: str, user_id: str, target_asset_id: str, relation_type: str) -> dict[str, Any]: ...
    def delete(self, asset_id: str, user_id: str) -> None: ...


class SQLiteAssetMetadataPort:
    def __init__(self, workspaces: WorkspacePort | None = None):
        self._workspaces = workspaces or get_workspace_port()

    def _workspace(self, asset_id: str, user_id: str, write: bool = False) -> str:
        from app.assets import store
        workspace_id = store.workspace_for_asset(asset_id)
        if not workspace_id:
            raise LookupError(ASSET_NOT_FOUND)
        require_role(self._workspaces, workspace_id, user_id, write=write)
        return workspace_id

    def get(self, asset_id, user_id):
        from app.assets import store
        value = store.get_asset(asset_id, self._workspace(asset_id, user_id))
        if not value:
            raise LookupError(ASSET_NOT_FOUND)
        return value

    def list(self, workspace_id, user_id, kind):
        from app.assets import store
        require_role(self._workspaces, workspace_id, user_id)
        return {"items": store.list_assets(workspace_id, kind=kind)}

    def versions(self, asset_id, user_id):
        from app.assets import store
        return {"items": store.list_asset_versions(asset_id, self._workspace(asset_id, user_id))}

    def provenance(self, asset_id, user_id, limit, offset):
        from app.assets import store
        return {"items": store.list_asset_provenance(asset_id, self._workspace(asset_id, user_id),
                                                     limit=limit, offset=offset)}

    def relations(self, asset_id, user_id):
        from app.assets import store
        return {"items": store.list_asset_relations(asset_id, self._workspace(asset_id, user_id))}

    def add_relation(self, asset_id, user_id, target_asset_id, relation_type):
        from app.assets import store
        workspace_id = self._workspace(asset_id, user_id, write=True)
        try:
            return store.create_asset_relation(workspace_id=workspace_id, source_asset_id=asset_id,
                                               target_asset_id=target_asset_id, relation_type=relation_type,
                                               actor_id=user_id)
        except ValueError:
            raise
        except LookupError as exc:
            raise LookupError(RELATED_NOT_FOUND) from exc
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise AssetConflict(RELATION_EXISTS) from exc
            raise

    def delete(self, asset_id, user_id):
        from app.assets import store
        workspace_id = self._workspace(asset_id, user_id, write=True)
        try:
            if not store.delete_asset(asset_id, workspace_id, actor_id=user_id):
                raise LookupError(ASSET_NOT_FOUND)
        except ValueError as exc:  # legacy contract: "referenced / retained" refusals are 409
            raise AssetConflict(str(exc)) from exc


def _plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _public_asset(row: dict[str, Any]) -> dict[str, Any]:
    value = {k: v for k, v in row.items() if k not in _PUBLIC_DROP}
    value["embedded_binary"] = bool(value.get("embedded_binary"))
    value["asset_kind"] = "image" if str(value["media_type"]).startswith("image/") else "model"
    if value["asset_kind"] == "image":
        value["gltf_version"] = None
    return _plain(value)


class PostgreSQLAssetMetadataPort:
    def __init__(self, repository=None, workspaces: WorkspacePort | None = None, blobs=None):
        if repository is None:
            from app.repository_registry import build_postgres_repository
            repository = build_postgres_repository("workspace_and_asset_metadata", allow_unverified=True)
        from app.assets.blob_store import LocalBlobStore
        self._blobs = blobs or LocalBlobStore()
        self._repo = repository
        from app.ports.workspace import PostgreSQLWorkspacePort
        self._workspaces = workspaces or PostgreSQLWorkspacePort(repository)

    def _workspace(self, asset_id: str, user_id: str, write: bool = False) -> str:
        workspace_id = self._repo.workspace_for_asset(asset_id)
        if not workspace_id:
            raise LookupError(ASSET_NOT_FOUND)
        require_role(self._workspaces, workspace_id, user_id, write=write)
        return workspace_id

    def get(self, asset_id, user_id):
        value = self._repo.get_asset(asset_id, self._workspace(asset_id, user_id))
        if not value:
            raise LookupError(ASSET_NOT_FOUND)
        return _public_asset(value)

    def list(self, workspace_id, user_id, kind):
        require_role(self._workspaces, workspace_id, user_id)
        return {"items": [_public_asset(r) for r in self._repo.list_assets(workspace_id, kind=kind)]}

    def versions(self, asset_id, user_id):
        workspace_id = self._workspace(asset_id, user_id)
        current_key = (self._repo.get_asset(asset_id, workspace_id) or {}).get("storage_key")
        keep = ("version_id", "asset_id", "workspace_id", "version_number", "media_type", "size_bytes",
                "checksum_sha256", "created_by", "created_at")
        items = [_plain({**{k: row[k] for k in keep}, "is_current": row["storage_key"] == current_key})
                 for row in self._repo.list_asset_versions(asset_id, workspace_id)]
        return {"items": items}

    def provenance(self, asset_id, user_id, limit, offset):
        workspace_id = self._workspace(asset_id, user_id)
        keep = ("provenance_id", "asset_id", "version_number", "event_type", "actor_id", "created_at")
        items = [_plain({**{k: row[k] for k in keep}, "details": row["details_json"]})
                 for row in self._repo.list_asset_provenance(asset_id, workspace_id, limit=limit, offset=offset)]
        return {"items": items}

    def relations(self, asset_id, user_id):
        workspace_id = self._workspace(asset_id, user_id)
        return {"items": _plain(self._repo.list_asset_relations(asset_id, workspace_id))}

    def add_relation(self, asset_id, user_id, target_asset_id, relation_type):
        workspace_id = self._workspace(asset_id, user_id, write=True)
        try:
            return _plain(self._repo.create_asset_relation(
                workspace_id=workspace_id, source_asset_id=asset_id, target_asset_id=target_asset_id,
                relation_type=relation_type, created_by=user_id))
        except LookupError as exc:
            raise LookupError(RELATED_NOT_FOUND) from exc

    def delete(self, asset_id, user_id):
        workspace_id = self._workspace(asset_id, user_id, write=True)
        keys = self._repo.asset_storage_keys(asset_id)
        if not self._repo.soft_delete_asset(asset_id, workspace_id, actor_id=user_id):
            raise LookupError(ASSET_NOT_FOUND)
        for key in keys:  # only after the row change committed; a failure here leaves an orphan, never a dangling row
            self._blobs.delete(key)


def get_asset_metadata_port() -> AssetMetadataPort:
    return SQLiteAssetMetadataPort() if require_runtime_backend() == "sqlite" else PostgreSQLAssetMetadataPort()
