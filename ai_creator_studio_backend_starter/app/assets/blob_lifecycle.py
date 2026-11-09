"""Backend-aware private blob operations for the Asset lifecycle.

This module is the single boundary for Asset binary I/O. It deliberately does
not own metadata transactions: callers must commit Asset/AssetVersion metadata
and compensate a successful put if that transaction fails. Local storage keeps
its historical on-disk layout for backwards compatibility.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app import config
from app.blob_storage import (
    BlobStore,
    LocalFileBlobStore,
    SupabaseStorageBlobStore,
    tenant_object_key,
    validate_object_key,
)

ASSET_BUCKET = "acs-assets"


@dataclass(frozen=True)
class AssetBlobRef:
    backend: str
    bucket: str
    key: str

    @classmethod
    def from_record(cls, value: dict[str, Any]) -> "AssetBlobRef":
        backend = str(value.get("backend") or "")
        bucket = str(value.get("bucket") or "")
        key = validate_object_key(str(value.get("key") or ""))
        if backend not in {"local", "supabase_storage"}:
            raise ValueError("Asset storage backend is invalid")
        if backend == "local" and bucket != Path(config.ASSET_STORAGE_DIR).name:
            raise ValueError("Local Asset storage bucket is invalid")
        if backend == "supabase_storage" and bucket != ASSET_BUCKET:
            raise ValueError("Supabase Asset storage bucket is invalid")
        return cls(backend=backend, bucket=bucket, key=key)

    def to_record(self) -> dict[str, str]:
        return asdict(self)


def _backend_name(backend: str | None = None) -> str:
    selected = (backend or os.getenv("BLOB_STORAGE_BACKEND", "local")).strip().lower()
    if selected in {"supabase", "supabase_storage"}:
        return "supabase_storage"
    if selected == "local":
        return "local"
    raise ValueError(f"Unsupported BLOB_STORAGE_BACKEND: {selected}")


def build_asset_blob_store(backend: str | None = None) -> tuple[str, str, BlobStore]:
    """Return (backend, bucket, adapter), preserving the legacy local layout."""
    selected = _backend_name(backend)
    if selected == "local":
        bucket = Path(config.ASSET_STORAGE_DIR).name
        # LocalFileBlobStore appends bucket/key; choosing the parent preserves
        # existing assets stored directly under ASSET_STORAGE_DIR.
        return selected, bucket, LocalFileBlobStore(root=Path(config.ASSET_STORAGE_DIR).parent)
    return selected, ASSET_BUCKET, SupabaseStorageBlobStore()


def make_asset_blob_ref(*, workspace_id: str, asset_id: str, filename: str,
                        backend: str | None = None) -> AssetBlobRef:
    selected = _backend_name(backend)
    if selected == "local":
        bucket = Path(config.ASSET_STORAGE_DIR).name
        # Keep the pre-gateway flat key format for old route and worker readers.
        suffix = Path(filename).suffix.lower()
        key = f"{asset_id}{suffix}" if suffix else asset_id
    else:
        bucket = ASSET_BUCKET
        from app.assets.validation import storage_suffix
        suffix = storage_suffix_from_filename(filename)
        key = tenant_object_key(workspace_id, asset_id, f"{asset_id}{suffix}")
    return AssetBlobRef(backend=selected, bucket=bucket, key=validate_object_key(key))


def storage_suffix_from_filename(filename: str) -> str:
    # The filename is already generated from validated media type by callers;
    # keep only a conservative extension rather than trusting path components.
    suffix = Path(filename).suffix.lower()
    if suffix not in {".glb", ".gltf", ".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("Asset filename extension is not supported")
    return suffix


def _store_for_ref(ref: AssetBlobRef) -> BlobStore:
    if ref.backend == "local":
        return LocalFileBlobStore(root=Path(config.ASSET_STORAGE_DIR).parent)
    if ref.backend == "supabase_storage":
        return SupabaseStorageBlobStore()
    raise ValueError("Asset storage backend is invalid")


def put_asset_blob(ref: AssetBlobRef, content: bytes, media_type: str) -> dict[str, Any]:
    """Write bytes once; metadata persistence remains the caller's transaction."""
    return _store_for_ref(ref).put(ref.bucket, ref.key, content, media_type)


def get_asset_blob(ref: AssetBlobRef) -> bytes:
    return _store_for_ref(ref).get(ref.bucket, ref.key)


def delete_asset_blob(ref: AssetBlobRef) -> bool:
    return _store_for_ref(ref).delete(ref.bucket, ref.key)
