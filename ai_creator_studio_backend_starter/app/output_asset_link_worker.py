"""Idempotent cross-database linker from persisted Generation Outputs to Asset/AssetVersion.

Run independently: python -m app.output_asset_link_worker
The Generation DB outbox is authoritative. Asset DB writes use deterministic IDs;
if the Asset transaction commits but the outbox acknowledgement is lost, retry
verifies and reuses the same Asset rather than creating duplicates.
"""
from __future__ import annotations
import hashlib
import json
import os
import socket
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.output_store import get_stored_output
from app.assets.validation import validate_image_upload, storage_suffix
from app.assets.store import _connect as asset_connect, initialize as initialize_asset_store
from app.repositories.output_asset_link import build_output_asset_link_repository

WORKER_ID = os.getenv("OUTPUT_ASSET_LINK_WORKER_ID", f"asset-link-{socket.gethostname()}-{uuid.uuid4().hex[:8]}")
LEASE_SECONDS = max(30, int(os.getenv("OUTPUT_ASSET_LINK_LEASE_SECONDS", "120")))
POLL_SECONDS = max(0.25, float(os.getenv("OUTPUT_ASSET_LINK_POLL_SECONDS", "2")))
MAX_ATTEMPTS = max(1, int(os.getenv("OUTPUT_ASSET_LINK_MAX_ATTEMPTS", "5")))


def _stable_id(prefix: str, output_id: str) -> str:
    return prefix + hashlib.sha256(output_id.encode("utf-8")).hexdigest()[:32]


def _write_asset_file(destination: Path, data: bytes, expected_checksum: str) -> None:
    root = config.ASSET_STORAGE_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    resolved = destination.resolve()
    if resolved.parent != root:
        raise ValueError("Output Asset destination escaped the private Asset storage root")
    if resolved.exists():
        actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual != expected_checksum:
            raise ValueError("A deterministic Output Asset storage key already contains different bytes")
        return
    temporary = root / f".{resolved.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
        if resolved.exists():
            actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if actual != expected_checksum:
                raise ValueError("Concurrent Output Asset import produced a checksum conflict")
            temporary.unlink(missing_ok=True)
        else:
            os.replace(temporary, resolved)
    finally:
        temporary.unlink(missing_ok=True)


def import_output_asset(task: dict) -> dict[str, str]:
    """Create or verify the deterministic Asset/Version/Provenance for one Output."""
    path = get_stored_output(task["job_id"], task["storage_key"])
    if path is None:
        raise FileNotFoundError("Persisted private Output file is missing")
    data = path.read_bytes()
    if len(data) != int(task["size_bytes"]):
        raise ValueError("Persisted Output byte size does not match its database record")
    validated = validate_image_upload(path.name, data, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
    if validated.media_type != task["media_type"]:
        raise ValueError("Persisted Output MIME type does not match decoded image content")
    checksum = hashlib.sha256(data).hexdigest()
    if task.get("output_checksum_sha256") and task["output_checksum_sha256"] != checksum:
        raise ValueError("Persisted Output checksum does not match its database record")

    asset_id = _stable_id("ast_out_", task["output_id"])
    version_id = _stable_id("av_out_", task["output_id"])
    provenance_id = _stable_id("ap_out_", task["output_id"])
    asset_storage_key = asset_id + storage_suffix(validated.media_type)
    destination = config.ASSET_STORAGE_DIR.resolve() / asset_storage_key

    initialize_asset_store()
    with asset_connect() as db:
        # Autocommit connection: without BEGIN a failure between the three INSERTs would leave a half-imported asset, which this
        # function then refuses forever ("failed integrity verification") on every retry.
        db.execute("BEGIN IMMEDIATE")
        workspace = db.execute("SELECT 1 FROM workspaces WHERE workspace_id=?", (task["workspace_id"],)).fetchone()
        if not workspace:
            raise ValueError("Output Workspace no longer exists in the Asset database")
        existing = db.execute("SELECT * FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
        if existing:
            if existing["deleted_at"] is not None:
                raise ValueError("The deterministic Output Asset was previously deleted; retention review is required")
            expected = (task["owner_id"], task["workspace_id"], asset_storage_key,
                        validated.media_type, len(data), checksum)
            actual = (existing["owner_id"], existing["workspace_id"], existing["storage_key"],
                      existing["media_type"], existing["size_bytes"], existing["checksum_sha256"])
            if actual != expected:
                raise ValueError("Existing deterministic Output Asset owner, workspace, or content metadata conflicts with this Output")
            version = db.execute("SELECT * FROM asset_versions WHERE version_id=? AND asset_id=?", (version_id, asset_id)).fetchone()
            provenance = db.execute("SELECT * FROM asset_provenance WHERE provenance_id=? AND asset_id=?", (provenance_id, asset_id)).fetchone()
            version_expected = (task["workspace_id"], 1, asset_storage_key, validated.media_type,
                                len(data), checksum, task["owner_id"])
            version_actual = ((version["workspace_id"], version["version_number"], version["storage_key"],
                               version["media_type"], version["size_bytes"], version["checksum_sha256"],
                               version["created_by"]) if version else None)
            try:
                provenance_details = json.loads(provenance["details_json"]) if provenance else None
            except (TypeError, ValueError):
                provenance_details = None
            provenance_valid = bool(
                provenance
                and provenance["workspace_id"] == task["workspace_id"]
                and provenance["version_number"] == 1
                and provenance["event_type"] == "asset.generated_output_imported"
                and provenance["actor_id"] in {task["owner_id"], "system:output_asset_link_worker"}
                and isinstance(provenance_details, dict)
                and provenance_details.get("source") == "generation_output"
                and provenance_details.get("job_id") == task["job_id"]
                and provenance_details.get("output_id") == task["output_id"]
            )
            if version_actual != version_expected or not provenance_valid:
                raise ValueError("Existing Output Asset immutable Version or Provenance metadata failed integrity verification")
            _write_asset_file(destination, data, checksum)
        else:
            _write_asset_file(destination, data, checksum)
            now = datetime.now(timezone.utc).isoformat()
            db.execute("""INSERT INTO assets(asset_id,owner_id,workspace_id,original_filename,storage_key,media_type,
                size_bytes,checksum_sha256,gltf_version,embedded_binary,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (asset_id, task["owner_id"], task["workspace_id"], f"generated-{task['job_id']}{storage_suffix(validated.media_type)}"[:255],
                 asset_storage_key, validated.media_type, len(data), checksum, "", 0, now))
            db.execute("""INSERT INTO asset_versions(version_id,asset_id,workspace_id,version_number,storage_key,media_type,
                size_bytes,checksum_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (version_id, asset_id, task["workspace_id"], 1, asset_storage_key, validated.media_type, len(data), checksum, task["owner_id"], now))
            details = json.dumps({"source": "generation_output", "job_id": task["job_id"],
                                 "output_id": task["output_id"], "initiated_by": task["owner_id"],
                                 "worker_id": task.get("claimed_by") or WORKER_ID}, separators=(",", ":"))
            db.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,event_type,actor_id,details_json,created_at)
                VALUES(?,?,?,?,?,?,?,?)""", (provenance_id, task["workspace_id"], asset_id, 1,
                "asset.generated_output_imported", "system:output_asset_link_worker", details, now))
    # Asset metadata transaction is committed before the Generation DB outbox acknowledgement.
    # A crash in between is safe: the deterministic Asset IDs make the retry idempotent.
    return {"asset_id": asset_id, "asset_version_id": version_id, "provenance_id": provenance_id, "checksum_sha256": checksum}


def process_one(worker_id: str | None = None, repository=None) -> bool:
    from app.repositories.operations import build_worker_heartbeat_repository
    heartbeat_worker = build_worker_heartbeat_repository().heartbeat
    repo = repository or build_output_asset_link_repository()
    selected_worker = worker_id or WORKER_ID
    try:
        heartbeat_worker(selected_worker, "idle", {"worker_type": "output_asset_link"})
    except Exception:
        pass
    task = repo.claim_one(selected_worker, LEASE_SECONDS)
    if task is None:
        return False
    try:
        heartbeat_worker(selected_worker, "working", {"worker_type": "output_asset_link", "link_id": task["link_id"]})
    except Exception:
        pass
    try:
        linked = import_output_asset(task)
    except Exception as exc:
        attempts = 1 if isinstance(exc, ValueError) else MAX_ATTEMPTS
        repo.record_failure(task["link_id"], selected_worker, error=f"{type(exc).__name__}: {exc}", max_attempts=attempts)
        try: heartbeat_worker(selected_worker, "idle", {"worker_type": "output_asset_link"})
        except Exception: pass
        return True
    repo.mark_linked(task["link_id"], selected_worker, **linked)
    try: heartbeat_worker(selected_worker, "idle", {"worker_type": "output_asset_link"})
    except Exception: pass
    return True


def run_forever() -> None:
    while True:
        try:
            if not process_one(): time.sleep(POLL_SECONDS)
        except Exception:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run_forever()
