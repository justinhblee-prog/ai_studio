import ipaddress
import os
import uuid
import fcntl
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
import httpx
from app import config

IMAGE_SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/webp": (b"RIFF", ".webp"),
}

class OutputStoreError(RuntimeError):
    pass


@contextmanager
def output_storage_lock(*, exclusive: bool = False):
    """Coordinate same-host Output writes and orphan cleanup.

    Workers hold a shared lock across download and DB finalization. Maintenance
    holds an exclusive lock across reference snapshot and deletion, so cleanup
    cannot race an active Output attempt on the supported single-host filesystem.
    """
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = config.OUTPUT_DIR / ".output-maintenance.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

def _validate_output_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise OutputStoreError("Provider output URL must be a credential-free HTTPS URL.")
    host = parsed.hostname.lower().rstrip(".")
    if host not in config.FASHN_OUTPUT_HOSTS:
        raise OutputStoreError("Provider output host is not on the configured allowlist.")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise OutputStoreError("Non-public output hosts are not allowed.")
    except ValueError:
        pass

def _detect_image(content_type: str, data: bytes) -> str:
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in IMAGE_SIGNATURES:
        raise OutputStoreError("Provider output is not a supported image type.")
    signature, extension = IMAGE_SIGNATURES[media_type]
    if not data.startswith(signature):
        raise OutputStoreError("Provider output signature does not match its content type.")
    if media_type == "image/webp" and data[8:12] != b"WEBP":
        raise OutputStoreError("Invalid WEBP image signature.")
    return extension

async def save_provider_output_artifact(url: str, job_id: str, attempt_id: str) -> tuple[str, str]:
    _validate_output_url(url)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chunks = []
    size = 0
    try:
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT_SECONDS, follow_redirects=False) as client:
            async with client.stream("GET", url, headers={"Accept": "image/png,image/jpeg,image/webp"}) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                length = response.headers.get("content-length")
                if length and int(length) > config.MAX_OUTPUT_BYTES:
                    raise OutputStoreError("Provider output exceeds the configured size limit.")
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > config.MAX_OUTPUT_BYTES:
                        raise OutputStoreError("Provider output exceeds the configured size limit.")
                    chunks.append(chunk)
    except OutputStoreError:
        raise
    except httpx.HTTPError as exc:
        raise OutputStoreError("Could not download provider output.") from exc
    data = b"".join(chunks)
    extension = _detect_image(content_type, data)
    safe_id = "".join(c for c in job_id if c.isalnum() or c in "-_" )[:100] or uuid.uuid4().hex
    safe_attempt = "".join(c for c in str(attempt_id) if c.isalnum() or c in "-_")[:120]
    if not safe_attempt:
        raise OutputStoreError("A valid output attempt identifier is required.")
    # Immutable attempt-scoped names prevent a stale Worker from replacing a
    # newer Worker's artifact after its DB lease has expired.
    target = config.OUTPUT_DIR / f"{safe_id}.attempt-{safe_attempt}.{uuid.uuid4().hex}{extension}"
    temporary = config.OUTPUT_DIR / f".{safe_id}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    # Atomic replace prevents readers from observing a partially written output.
    # Outputs remain private; callers receive an authenticated API route, never a static URL.
    return f"/v1/generation-jobs/{safe_id}/output", target.name


async def save_provider_output(url: str, job_id: str) -> str:
    """Backward-compatible wrapper for non-worker callers and older tests."""
    route, _storage_key = await save_provider_output_artifact(url, job_id, "legacy-" + uuid.uuid4().hex)
    return route


def get_stored_output(job_id: str, storage_key: str | None = None) -> Path | None:
    """Resolve only a named private artifact when a DB reference is available.

    The legacy deterministic lookup remains for older local data, but new
    finalizations always persist an immutable attempt-scoped storage_key.
    """
    safe_id = "".join(c for c in job_id if c.isalnum() or c in "-_")[:100]
    if not safe_id:
        return None
    root = config.OUTPUT_DIR.resolve()
    if storage_key is not None:
        if not isinstance(storage_key, str) or Path(storage_key).name != storage_key:
            return None
        if not storage_key.startswith(safe_id + ".attempt-"):
            return None
        candidate = (root / storage_key).resolve()
        return candidate if candidate.parent == root and candidate.is_file() else None
    for suffix in (".png", ".jpg", ".webp"):
        candidate = (root / f"{safe_id}{suffix}").resolve()
        if candidate.parent == root and candidate.is_file():
            return candidate
    return None


def cleanup_orphaned_attempt_outputs(referenced_storage_keys: set[str], *, older_than_seconds: int = 86400,
                                     now: float | None = None, apply: bool = False) -> list[str]:
    """Delete old attempt artifacts not referenced by committed Output rows.

    This is an explicit maintenance operation; it is not run automatically by
    a Worker because DB and filesystem do not share an atomic transaction.
    By default it is a dry-run; pass apply=True to remove the listed files.
    """
    import time
    if older_than_seconds < 0:
        raise ValueError("older_than_seconds must be non-negative")
    root = config.OUTPUT_DIR.resolve()
    cutoff = (time.time() if now is None else now) - older_than_seconds
    removed: list[str] = []
    if not root.exists():
        return removed
    # A hard process exit after fsync but before os.replace leaves a hidden
    # attempt temp file. It can never be referenced by a committed Output row,
    # so stale temp files are safe to collect under the caller's exclusive lock.
    def is_generated_temp(candidate: Path) -> bool:
        parts = candidate.name.split(".")
        return (
            len(parts) == 4 and parts[0] == "" and bool(parts[1])
            and len(parts[2]) == 32
            and all(ch in "0123456789abcdef" for ch in parts[2])
            and parts[3] == "tmp"
        )

    candidates = list(root.glob("*.attempt-*.*"))
    candidates.extend(candidate for candidate in root.glob(".*.tmp") if is_generated_temp(candidate))
    for candidate in candidates:
        if candidate.name in referenced_storage_keys or not candidate.is_file():
            continue
        try:
            resolved = candidate.resolve()
            if resolved.parent != root or candidate.stat().st_mtime > cutoff:
                continue
            if apply:
                candidate.unlink()
            removed.append(candidate.name)
        except FileNotFoundError:
            continue
    return removed
