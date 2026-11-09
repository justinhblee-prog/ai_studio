"""Private binary storage adapters for Asset and Output bytes.

Local filesystem remains the default. Supabase Storage is explicit opt-in and
uses only private buckets; it never creates buckets or public URLs at runtime.
"""
from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath
from typing import Protocol
from urllib.parse import quote

import httpx
from app import config


class BlobStorageError(RuntimeError):
    pass


class BlobStore(Protocol):
    def put(self, bucket: str, key: str, content: bytes, media_type: str) -> dict: ...
    def get(self, bucket: str, key: str) -> bytes: ...
    def delete(self, bucket: str, key: str) -> bool: ...


_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def validate_object_key(key: str) -> str:
    if not isinstance(key, str) or not key or "\\" in key:
        raise ValueError("Storage object key is invalid")
    raw_parts = key.split("/")
    path = PurePosixPath(key)
    if path.is_absolute() or any(part in {"", ".", ".."} or not _SAFE_SEGMENT.fullmatch(part)
                                 for part in raw_parts):
        raise ValueError("Storage object key contains an unsafe path segment")
    return str(path)


def tenant_object_key(workspace_id: str, asset_id: str, filename: str) -> str:
    """Construct the canonical workspace-scoped object key after caller authorization."""
    for value, label in ((workspace_id, "workspace_id"), (asset_id, "asset_id"), (filename, "filename")):
        if not isinstance(value, str) or not _SAFE_SEGMENT.fullmatch(value):
            raise ValueError(f"{label} is not a safe storage path segment")
    return validate_object_key(f"{workspace_id}/{asset_id}/{filename}")


class LocalFileBlobStore:
    backend = "local"

    def __init__(self, root: Path | None = None):
        self.root = Path(root or config.ASSET_STORAGE_DIR).resolve()

    def _path(self, bucket: str, key: str) -> Path:
        safe_key = validate_object_key(key)
        if not _SAFE_SEGMENT.fullmatch(bucket):
            raise ValueError("Storage bucket name is invalid")
        destination = (self.root / bucket / safe_key).resolve()
        if not destination.is_relative_to(self.root):
            raise ValueError("Storage path escaped its private root")
        return destination

    def put(self, bucket: str, key: str, content: bytes, media_type: str) -> dict:
        if not isinstance(content, bytes) or not content:
            raise ValueError("Storage content must be non-empty bytes")
        path = self._path(bucket, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(content)
        return {"bucket": bucket, "key": key, "size_bytes": len(content), "media_type": media_type}

    def get(self, bucket: str, key: str) -> bytes:
        path = self._path(bucket, key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise KeyError(key) from exc

    def delete(self, bucket: str, key: str) -> bool:
        path = self._path(bucket, key)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False


class SupabaseStorageBlobStore:
    backend = "supabase_storage"
    DEFAULT_LIMITS = {"acs-assets": 100 * 1024 * 1024,
                      "acs-gallery": 20 * 1024 * 1024,
                      "acs-outputs": 25 * 1024 * 1024}
    DEFAULT_MIME = {
        "acs-assets": {"model/gltf-binary", "model/gltf+json", "application/octet-stream"},
        "acs-gallery": {"image/jpeg", "image/png", "image/webp"},
        "acs-outputs": {"image/jpeg", "image/png", "image/webp"},
    }

    def __init__(self, *, project_url: str | None = None, service_key: str | None = None,
                 timeout: float = 20.0, transport: httpx.BaseTransport | None = None):
        self.project_url = (project_url or os.getenv("SUPABASE_URL") or "").rstrip("/")
        self.service_key = service_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not self.project_url or not self.service_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for Supabase Storage")
        if not self.project_url.startswith("https://"):
            raise ValueError("Supabase project URL must use HTTPS")
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def _request(self, method: str, bucket: str, key: str, **kwargs):
        if bucket not in self.DEFAULT_LIMITS:
            raise ValueError("Storage bucket is not in the approved private bucket allowlist")
        safe_key = validate_object_key(key)
        encoded = "/".join(quote(part, safe="") for part in safe_key.split("/"))
        url = f"{self.project_url}/storage/v1/object/{quote(bucket, safe='')}/{encoded}"
        headers = {"apikey": self.service_key, "Authorization": f"Bearer {self.service_key}"}
        headers.update(kwargs.pop("headers", {}))
        try:
            response = self._client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise BlobStorageError("Supabase Storage request failed") from exc
        if response.status_code >= 400:
            # Do not include response body: it can contain provider diagnostics or user data.
            raise BlobStorageError(f"Supabase Storage returned HTTP {response.status_code}")
        return response

    def put(self, bucket: str, key: str, content: bytes, media_type: str) -> dict:
        if bucket not in self.DEFAULT_LIMITS:
            raise ValueError("Storage bucket is not in the approved private bucket allowlist")
        if not isinstance(content, bytes) or not content:
            raise ValueError("Storage content must be non-empty bytes")
        if len(content) > self.DEFAULT_LIMITS[bucket]:
            raise ValueError("Storage object exceeds the configured bucket limit")
        if media_type not in self.DEFAULT_MIME[bucket]:
            raise ValueError("Storage media type is not allowed for this bucket")
        response = self._request("POST", bucket, key, content=content,
                                 headers={"Content-Type": media_type, "x-upsert": "false"})
        return {"bucket": bucket, "key": validate_object_key(key),
                "size_bytes": len(content), "media_type": media_type,
                "etag": response.headers.get("etag")}

    def get(self, bucket: str, key: str) -> bytes:
        """Download a private object with a hard response-size and MIME boundary.

        Do not use ``Client.request`` here: it eagerly buffers the complete body
        before the caller can enforce the bucket limit. Stream chunks and stop
        as soon as the configured maximum is crossed.
        """
        if bucket not in self.DEFAULT_LIMITS:
            raise ValueError("Storage bucket is not in the approved private bucket allowlist")
        safe_key = validate_object_key(key)
        encoded = "/".join(quote(part, safe="") for part in safe_key.split("/"))
        url = f"{self.project_url}/storage/v1/object/{quote(bucket, safe='')}/{encoded}"
        headers = {"apikey": self.service_key, "Authorization": f"Bearer {self.service_key}"}
        limit = self.DEFAULT_LIMITS[bucket]
        try:
            with self._client.stream("GET", url, headers=headers) as response:
                if response.status_code >= 400:
                    raise BlobStorageError(f"Supabase Storage returned HTTP {response.status_code}")
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if content_type not in self.DEFAULT_MIME[bucket]:
                    raise BlobStorageError("Supabase Storage returned an unsupported media type")
                declared_length = response.headers.get("content-length")
                if declared_length:
                    try:
                        if int(declared_length) < 0 or int(declared_length) > limit:
                            raise BlobStorageError("Supabase Storage object exceeds the configured bucket limit")
                    except ValueError as exc:
                        raise BlobStorageError("Supabase Storage returned an invalid content length") from exc
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    if len(chunks) + len(chunk) > limit:
                        raise BlobStorageError("Supabase Storage object exceeds the configured bucket limit")
                    chunks.extend(chunk)
                if not chunks:
                    raise BlobStorageError("Supabase Storage returned an empty object")
                return bytes(chunks)
        except httpx.HTTPError as exc:
            raise BlobStorageError("Supabase Storage request failed") from exc

    def delete(self, bucket: str, key: str) -> bool:
        self._request("DELETE", bucket, key)
        return True

    def close(self) -> None:
        self._client.close()


def build_blob_store(backend: str | None = None) -> BlobStore:
    selected = (backend or os.getenv("BLOB_STORAGE_BACKEND", "local")).strip().lower()
    if selected == "local":
        return LocalFileBlobStore()
    if selected in {"supabase", "supabase_storage"}:
        return SupabaseStorageBlobStore()
    raise ValueError(f"Unsupported BLOB_STORAGE_BACKEND: {selected}")
