"""Asset *bytes* port: uploads, versions, restore, integrity audit and file lookup.

SQLite delegates to the legacy store (file write + row insert + cleanup on failure, unchanged).
PostgreSQL applies the same rules with LocalBlobStore + repository calls:
  1. write the object exclusively; 2. commit the metadata transaction;
  3. if (2) fails, delete the object written in (1).
Supabase Storage is NOT implemented here.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any, Protocol

from app.ports.assets import _public_asset
from app.ports.workspace import WorkspacePort, get_workspace_port, require_role
from app.repository_registry import require_runtime_backend

ASSET_NOT_FOUND = "Asset not found"
VERSION_NOT_FOUND = "Asset version not found"


class AssetBytesPort(Protocol):
    def workspace_of(self, asset_id: str) -> str | None: ...
    def version_record(self, asset_id: str, workspace_id: str, version_id: str) -> dict[str, Any] | None: ...
    def current_file(self, asset_id: str) -> Path | None: ...
    def save(self, workspace_id: str, user_id: str, filename: str, content: bytes, validated: Any) -> dict[str, Any]: ...
    def save_version(self, asset_id: str, user_id: str, filename: str, content: bytes, validated: Any) -> dict[str, Any]: ...
    def restore(self, asset_id: str, user_id: str, version_id: str) -> dict[str, Any]: ...
    def audit(self, workspace_id: str, user_id: str, limit: int, offset: int) -> dict[str, Any]: ...
    def save_derived(self, **kw: Any) -> dict[str, Any]: ...


class SQLiteAssetBytesPort:
    def __init__(self, workspaces: WorkspacePort | None = None):
        self._workspaces = workspaces or get_workspace_port()

    def workspace_of(self, asset_id):
        from app.assets import store
        return store.workspace_for_asset(asset_id)

    def version_record(self, asset_id, workspace_id, version_id):
        from app.assets import store
        return store.get_asset_version_record(asset_id, workspace_id, version_id)

    def current_file(self, asset_id):
        from app.assets import store
        return store.storage_path(asset_id)

    def _asset_workspace(self, asset_id, user_id, write):
        workspace_id = self.workspace_of(asset_id)
        if not workspace_id:
            raise LookupError(ASSET_NOT_FOUND)
        require_role(self._workspaces, workspace_id, user_id, write=write)
        return workspace_id

    def save(self, workspace_id, user_id, filename, content, validated):
        from app.assets import store
        require_role(self._workspaces, workspace_id, user_id, write=True)
        return store.save_asset(owner_id=user_id, workspace_id=workspace_id, filename=filename,
                                content=content, validated=validated)

    def save_version(self, asset_id, user_id, filename, content, validated):
        from app.assets import store
        workspace_id = self._asset_workspace(asset_id, user_id, True)
        try:
            return store.create_asset_version(asset_id=asset_id, workspace_id=workspace_id, actor_id=user_id,
                                              filename=filename, content=content, validated=validated)
        except LookupError as exc:
            raise LookupError(ASSET_NOT_FOUND) from exc

    def restore(self, asset_id, user_id, version_id):
        from app.assets import store
        workspace_id = self._asset_workspace(asset_id, user_id, True)
        try:
            return store.restore_asset_version(asset_id=asset_id, workspace_id=workspace_id,
                                               version_id=version_id, actor_id=user_id)
        except LookupError as exc:
            raise LookupError(VERSION_NOT_FOUND) from exc

    def audit(self, workspace_id, user_id, limit, offset):
        from app.assets import store
        require_role(self._workspaces, workspace_id, user_id)
        return store.audit_workspace_assets(workspace_id, limit=limit, offset=offset)


    def save_derived(self, **kw):
        from app.assets.store import save_derived_image_asset
        return save_derived_image_asset(**kw)


class PostgreSQLAssetBytesPort:
    def __init__(self, repository=None, workspaces: WorkspacePort | None = None, blobs=None):
        if repository is None:
            from app.repository_registry import build_postgres_repository
            repository = build_postgres_repository("workspace_and_asset_metadata", allow_unverified=True)
        from app.assets.blob_store import LocalBlobStore
        from app.ports.workspace import PostgreSQLWorkspacePort
        self._repo = repository
        self._workspaces = workspaces or PostgreSQLWorkspacePort(repository)
        self._blobs = blobs or LocalBlobStore()

    def workspace_of(self, asset_id):
        return self._repo.workspace_for_asset(asset_id)

    def version_record(self, asset_id, workspace_id, version_id):
        return self._repo.get_asset_version_record(asset_id, workspace_id, version_id)

    def current_file(self, asset_id):
        workspace_id = self._repo.workspace_for_asset(asset_id)
        row = self._repo.get_asset(asset_id, workspace_id) if workspace_id else None
        return self._blobs.current_file(row["storage_key"]) if row else None

    def _asset_workspace(self, asset_id, user_id, write):
        workspace_id = self.workspace_of(asset_id)
        if not workspace_id:
            raise LookupError(ASSET_NOT_FOUND)
        require_role(self._workspaces, workspace_id, user_id, write=write)
        return workspace_id

    def _reload(self, asset_id, workspace_id):
        row = self._repo.get_asset(asset_id, workspace_id)
        if row is None:
            raise RuntimeError("Asset metadata could not be reloaded")
        return _public_asset(row)

    def save(self, workspace_id, user_id, filename, content, validated):
        from app.assets.validation import storage_suffix
        require_role(self._workspaces, workspace_id, user_id, write=True)
        asset_id = "ast_" + uuid.uuid4().hex
        key = f"{asset_id}{storage_suffix(validated.media_type)}"
        self._blobs.write_new(key, content)
        try:
            self._repo.register_asset(
                asset_id=asset_id, owner_id=user_id, workspace_id=workspace_id,
                original_filename=Path(filename).name, storage_key=key, media_type=validated.media_type,
                size_bytes=validated.size_bytes, checksum_sha256=hashlib.sha256(content).hexdigest(),
                gltf_version=validated.gltf_version or "", embedded_binary=bool(validated.embedded_binary))
        except Exception:
            self._blobs.delete(key)
            raise
        return self._reload(asset_id, workspace_id)

    def save_version(self, asset_id, user_id, filename, content, validated):
        from app.assets.validation import storage_suffix
        workspace_id = self._asset_workspace(asset_id, user_id, True)
        version_id = "av_" + uuid.uuid4().hex
        key = f"{asset_id}_{version_id}{storage_suffix(validated.media_type)}"
        self._blobs.write_new(key, content)
        try:
            created = self._repo.create_asset_version(
                asset_id=asset_id, workspace_id=workspace_id, actor_id=user_id, storage_key=key,
                media_type=validated.media_type, size_bytes=validated.size_bytes,
                checksum_sha256=hashlib.sha256(content).hexdigest(), version_id=version_id,
                original_filename=Path(filename).name, gltf_version=validated.gltf_version or "",
                embedded_binary=bool(validated.embedded_binary))
        except LookupError as exc:
            self._blobs.delete(key)
            raise LookupError(ASSET_NOT_FOUND) from exc
        except Exception:
            self._blobs.delete(key)
            raise
        return self._reload(asset_id, workspace_id) | {"version_number": created["version_number"], "version_id": version_id}

    def restore(self, asset_id, user_id, version_id):
        from app.assets import store
        from app.assets.blob_store import BlobIntegrityError
        from app.assets.validation import (AssetValidationError, storage_suffix, validate_gltf_upload,
                                           validate_image_upload)
        from app import config
        workspace_id = self._asset_workspace(asset_id, user_id, True)
        source = self._repo.get_asset_version_record(asset_id, workspace_id, version_id)
        if not source:
            raise LookupError(VERSION_NOT_FOUND)
        try:
            content = self._blobs.read_verified(source["storage_key"], source["size_bytes"], source["checksum_sha256"])
        except BlobIntegrityError as exc:
            raise store.AssetVersionIntegrityError(str(exc)) from exc
        suffix = storage_suffix(source["media_type"])
        filename = Path(str(source["original_filename"] or "restored.glb")).stem + suffix
        try:
            check = validate_image_upload if str(source["media_type"]).startswith("image/") else validate_gltf_upload
            validated = check(filename, content, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
        except AssetValidationError as exc:
            raise store.AssetVersionIntegrityError("Historical version no longer passes its media validation") from exc
        new_version_id = "av_" + uuid.uuid4().hex
        key = f"{asset_id}_{new_version_id}{suffix}"
        self._blobs.write_new(key, content)
        try:
            created = self._repo.restore_asset_version(
                asset_id=asset_id, workspace_id=workspace_id, actor_id=user_id, source_version_id=version_id,
                new_version_id=new_version_id, storage_key=key, media_type=validated.media_type,
                size_bytes=validated.size_bytes, checksum_sha256=hashlib.sha256(content).hexdigest(),
                original_filename=filename, gltf_version=validated.gltf_version or "",
                embedded_binary=bool(validated.embedded_binary))
        except LookupError as exc:
            self._blobs.delete(key)
            raise LookupError(VERSION_NOT_FOUND) from exc
        except Exception:
            self._blobs.delete(key)
            raise
        return self._reload(asset_id, workspace_id) | {
            "version_number": created["version_number"], "version_id": new_version_id,
            "restored_from_version_id": version_id}

    def audit(self, workspace_id, user_id, limit, offset):
        require_role(self._workspaces, workspace_id, user_id)
        total, rows = self._repo.audit_page(workspace_id, limit=limit, offset=offset)
        items = [{"asset_id": r["asset_id"],
                  "status": self._blobs.audit_status(r["storage_key"], int(r["size_bytes"]), r["checksum_sha256"])}
                 for r in rows]
        counts = {k: sum(1 for i in items if i["status"] == k) for k in ("ok", "missing", "size_mismatch", "checksum_mismatch")}
        return {"workspace_id": workspace_id, "total": total, "limit": limit, "offset": offset,
                "checked": len(items), "counts": counts, "items": items}


    def save_derived(self, *, asset_id, owner_id, workspace_id, source_asset_id, source_version_id,
                     source_checksum_sha256, filename, content, validated, run_id, operation, processor_version):
        """Deterministic, retry-safe derived image: reuse identical bytes, refuse different bytes,
        and never leave a file behind when the metadata transaction does not commit."""
        import hmac

        from app.assets.validation import storage_suffix
        if not asset_id.startswith("ast_") or not content:
            raise ValueError("A deterministic asset ID and non-empty image are required")
        key = f"{asset_id}{storage_suffix(validated.media_type)}"
        checksum = hashlib.sha256(content).hexdigest()
        created = False
        existing = self._blobs.current_file(key)
        if existing is not None:
            if not hmac.compare_digest(hashlib.sha256(existing.read_bytes()).hexdigest(), checksum):
                raise ValueError("A deterministic output storage key already contains different bytes")
        else:
            try:
                self._blobs.write_new(key, content)
                created = True
            except FileExistsError:
                current = self._blobs.current_file(key)
                if current is None or not hmac.compare_digest(hashlib.sha256(current.read_bytes()).hexdigest(), checksum):
                    raise ValueError("A deterministic output storage key already contains different bytes")
        try:
            info = self._repo.save_derived_image_metadata(
                asset_id=asset_id, owner_id=owner_id, workspace_id=workspace_id, source_asset_id=source_asset_id,
                source_version_id=source_version_id, source_checksum_sha256=source_checksum_sha256,
                filename=Path(filename).name, media_type=validated.media_type, size_bytes=len(content),
                checksum_sha256=checksum, storage_key=key, run_id=run_id, operation=operation,
                processor_version=processor_version)
        except Exception:
            if created and self._repo.get_asset(asset_id, workspace_id) is None:
                self._blobs.delete(key)
            raise
        return self._reload(asset_id, workspace_id) | info


def get_asset_bytes_port() -> AssetBytesPort:
    return SQLiteAssetBytesPort() if require_runtime_backend() == "sqlite" else PostgreSQLAssetBytesPort()
