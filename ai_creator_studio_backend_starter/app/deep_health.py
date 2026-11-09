"""Deep health report for the single-instance deployment (private; platform operators only).

``/health`` stays a public, minimal liveness probe. This report answers "is the pilot actually healthy": can the
database be read and is it intact, can the storage folders be written, is there disk space, are the required workers
alive, and is there a recent backup. It never returns file system paths or secrets, and it only writes a one-byte
temporary file into each storage folder.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import config

OK, WARN, FAIL = "ok", "warn", "fail"
_ORDER = {OK: 0, WARN: 1, FAIL: 2}


def _check(check_id: str, status: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"id": check_id, "status": status, "detail": detail, **extra}


def check_database(name: str, path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    check_id = f"database_{name}"
    path = Path(path)
    if not path.is_file():
        return _check(check_id, FAIL, "database file is missing")
    try:
        db = sqlite3.connect(f"file:{path}?mode=rw", uri=True, timeout=5)
        try:
            db.execute("SELECT 1").fetchone()
            quick = db.execute("PRAGMA quick_check").fetchone()[0]
            journal = db.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            db.close()
    except sqlite3.Error as exc:
        return _check(check_id, FAIL, f"database cannot be read: {type(exc).__name__}")
    ms = round((time.perf_counter() - started) * 1000, 1)
    wal = Path(str(path) + "-wal")
    extra = {"duration_ms": ms, "size_bytes": path.stat().st_size, "journal_mode": journal,
             "wal_bytes": wal.stat().st_size if wal.exists() else 0}
    if quick != "ok":
        return _check(check_id, FAIL, "database failed PRAGMA quick_check", **extra)
    return _check(check_id, OK, "database readable and intact", **extra)


def check_storage_dir(name: str, path: Path) -> dict[str, Any]:
    check_id = f"storage_{name}"
    path = Path(path)
    if not path.is_dir():
        return _check(check_id, FAIL, "storage folder does not exist")
    probe = path / f".healthcheck-{uuid.uuid4().hex}"
    try:
        probe.write_bytes(b"x")
        probe.unlink()
    except OSError as exc:
        return _check(check_id, FAIL, f"storage folder is not writable: {type(exc).__name__}")
    return _check(check_id, OK, "storage folder writable")


def check_disk(path: Path) -> dict[str, Any]:
    target = Path(path)
    while not target.exists() and target != target.parent:
        target = target.parent
    usage = shutil.disk_usage(target)
    free_percent = round(usage.free * 100 / usage.total, 1) if usage.total else 0.0
    extra = {"free_bytes": usage.free, "total_bytes": usage.total, "free_percent": free_percent,
             "warn_below_percent": config.HEALTH_DISK_WARN_FREE_PERCENT, "fail_below_percent": config.HEALTH_DISK_FAIL_FREE_PERCENT}
    if free_percent < config.HEALTH_DISK_FAIL_FREE_PERCENT:
        return _check("disk_space", FAIL, f"only {free_percent}% of the disk is free", **extra)
    if free_percent < config.HEALTH_DISK_WARN_FREE_PERCENT:
        return _check("disk_space", WARN, f"{free_percent}% of the disk is free", **extra)
    return _check("disk_space", OK, f"{free_percent}% of the disk is free", **extra)


def check_workers() -> dict[str, Any]:
    # The worker repositories initialise the schema, which would create a missing database file. A health check must
    # never hide a lost database by creating an empty one, so look first.
    worker_db = Path(config.GENERATION_DATABASE_PATH or config.ASSET_DATABASE_PATH)
    if not worker_db.is_file():
        return _check("workers", FAIL, "worker status cannot be read: the database file is missing")
    try:
        from app.repositories.operations import build_worker_health_repository
        report = build_worker_health_repository().worker_health(config.WORKER_STALE_AFTER_SECONDS)
    except Exception as exc:  # noqa: BLE001 - a broken database must show up as a failed check, not a 500
        return _check("workers", FAIL, f"worker status cannot be read: {type(exc).__name__}")
    healthy_types = {w["metadata"].get("worker_type") for w in report["workers"] if w["healthy"]}
    required = list(config.REQUIRED_WORKER_TYPES)
    missing = [t for t in required if t not in healthy_types]
    reconcile = int(report["outbox_counts"].get("needs_reconciliation", 0))
    extra = {"required": required, "healthy_types": sorted(t for t in healthy_types if t),
             "outbox_counts": report["outbox_counts"], "poll_task_counts": report["poll_task_counts"],
             "stale_after_seconds": report["stale_after_seconds"]}
    if missing:
        return _check("workers", FAIL, "required workers have no fresh heartbeat: " + ", ".join(missing), **extra)
    if reconcile:
        return _check("workers", WARN, f"{reconcile} submission(s) need manual reconciliation (provider acceptance unknown)", **extra)
    return _check("workers", OK, "all required workers have a fresh heartbeat", **extra)


def check_backup(now: datetime) -> dict[str, Any]:
    directory = config.BACKUP_DIR
    if directory is None:
        return _check("backup", WARN, "no backup directory is configured (BACKUP_DIR)")
    newest: tuple[datetime, dict] | None = None
    if Path(directory).is_dir():
        for manifest_path in Path(directory).glob("backup-*/manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                created = datetime.fromisoformat(manifest["created_at"])
            except (OSError, ValueError, KeyError):
                continue
            if newest is None or created > newest[0]:
                newest = (created, manifest)
    if newest is None:
        return _check("backup", WARN, "no backup found in the backup directory")
    age_hours = round((now - newest[0]).total_seconds() / 3600, 2)
    extra = {"newest_created_at": newest[0].isoformat(), "age_hours": age_hours, "max_age_hours": config.HEALTH_BACKUP_MAX_AGE_HOURS,
             "file_count": newest[1].get("totals", {}).get("file_count"), "rows": newest[1].get("totals", {}).get("rows")}
    if age_hours > config.HEALTH_BACKUP_MAX_AGE_HOURS:
        return _check("backup", WARN, f"the newest backup is {age_hours} hours old", **extra)
    return _check("backup", OK, f"the newest backup is {age_hours} hours old", **extra)


def run_deep_health(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    databases = {"assets": Path(config.ASSET_DATABASE_PATH)}
    if config.GENERATION_DATABASE_PATH and Path(config.GENERATION_DATABASE_PATH).resolve() != databases["assets"].resolve():
        databases["generation"] = Path(config.GENERATION_DATABASE_PATH)
    checks = [check_database(name, path) for name, path in databases.items()]
    checks += [check_storage_dir("private_assets", config.ASSET_STORAGE_DIR), check_storage_dir("outputs", config.OUTPUT_DIR),
               check_disk(config.ASSET_STORAGE_DIR), check_workers(), check_backup(now)]
    status = max((c["status"] for c in checks), key=_ORDER.__getitem__)
    return {"status": status, "checked_at": now.isoformat(), "checks": checks}
