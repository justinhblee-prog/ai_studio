"""Private object bytes on local disk: exclusive writes, verified reads, path-escape rejection.

This is the only module the PostgreSQL bytes port uses to touch files. A Supabase Storage
implementation of the same surface does not exist and is untested (no TEST environment).
"""
from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from app import config


class BlobIntegrityError(ValueError):
    """Stored bytes are missing or no longer match their recorded metadata (HTTP 409)."""


class LocalBlobStore:
    @staticmethod
    def root(create: bool = False) -> Path:
        root = config.ASSET_STORAGE_DIR.resolve()
        if create:
            root.mkdir(parents=True, exist_ok=True)
        return root

    def path_for(self, key: str) -> Path:
        root = self.root()
        path = (root / key).resolve()
        if Path(key).name != key or path.parent != root:
            raise RuntimeError("Invalid private storage path")
        return path

    def write_new(self, key: str, content: bytes) -> Path:
        """Create the object exclusively; an existing key is never overwritten."""
        self.root(create=True)
        path = self.path_for(key)
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
        return path

    def delete(self, key: str) -> None:
        try:
            self.path_for(key).unlink(missing_ok=True)
        except RuntimeError:
            return  # an unsafe key can never name a file inside the private root

    def read_verified(self, key: str, size_bytes: int, checksum_sha256: str) -> bytes:
        if not key or Path(key).name != key:
            raise BlobIntegrityError("Historical version storage reference is invalid")
        path = (self.root() / key).resolve()
        if path.parent != self.root() or not path.is_file():
            raise BlobIntegrityError("Historical version file is missing")
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise BlobIntegrityError("Historical version file cannot be read") from exc
        if len(content) != int(size_bytes):
            raise BlobIntegrityError("Historical version size does not match its recorded metadata")
        if not hmac.compare_digest(hashlib.sha256(content).hexdigest(), checksum_sha256):
            raise BlobIntegrityError("Historical version checksum does not match its recorded metadata")
        return content

    def audit_status(self, key: str, size_bytes: int, checksum_sha256: str) -> str:
        root = self.root()
        path = (root / key).resolve()
        if path.parent != root or not path.is_file():
            return "missing"
        digest, actual = hashlib.sha256(), 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                actual += len(chunk)
                digest.update(chunk)
        if actual != size_bytes:
            return "size_mismatch"
        if not hmac.compare_digest(digest.hexdigest(), checksum_sha256):
            return "checksum_mismatch"
        return "ok"

    def current_file(self, key: str) -> Path | None:
        root = self.root()
        path = (root / key).resolve()
        return path if path.parent == root and path.is_file() else None
