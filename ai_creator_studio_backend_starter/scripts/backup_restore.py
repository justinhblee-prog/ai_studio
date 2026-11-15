#!/usr/bin/env python3
"""Backup and restore for the single-instance (SQLite + local files) deployment.

backup   consistent snapshot of the SQLite database(s) with the SQLite online-backup API (the database runs in WAL
         mode, so copying the file would not be safe) plus a copy of the file storage, with a manifest of SHA-256
         hashes, row counts, integrity checks and timings.
verify   re-check a backup against its manifest without restoring it.
restore  verify first, then copy into a NEW, EMPTY target directory. It never overwrites or deletes existing data;
         point the application at the printed paths to use the restored copy.

Nothing here reads secrets or contacts a network service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MANIFEST = "manifest.json"
FORMAT_VERSION = 1


class BackupError(RuntimeError):
    pass


class BackupVerificationError(BackupError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tables(db: sqlite3.Connection) -> dict[str, int]:
    names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {name: db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in names}


def _integrity(path: Path) -> tuple[str, dict[str, int]]:
    """Return (integrity_check result, row counts). A file SQLite cannot even read reports its error text."""
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        try:
            result = db.execute("PRAGMA integrity_check").fetchone()[0]
            return result, _tables(db)
        except sqlite3.DatabaseError as exc:
            return f"unreadable: {exc}", {}
    finally:
        db.close()


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _regular_files(root: Path):
    """Regular files under root, sorted. Symlinks (to files or directories) are never followed or copied,
    so a link cannot pull data from outside the file area into a backup."""
    found = []
    for current, _dirs, names in os.walk(root, followlinks=False):
        found.extend(Path(current) / n for n in names if not (Path(current) / n).is_symlink() and (Path(current) / n).is_file())
    return sorted(found)


def backup(databases: dict[str, Path], file_areas: dict[str, Path], destination_root: Path, *, label: str | None = None) -> Path:
    """Create destination_root/backup-<UTC timestamp>/ and return it."""
    started = time.perf_counter()
    for name, path in databases.items():
        if not Path(path).is_file():
            raise BackupError(f"database '{name}' not found: {path}")
    for name, area in file_areas.items():
        if _inside(destination_root, area) or _inside(area, destination_root):
            raise BackupError(f"backup destination and file area '{name}' must not contain each other")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = Path(destination_root) / f"backup-{stamp}{('-' + label) if label else ''}"
    (out / "db").mkdir(parents=True)
    manifest: dict = {"format": FORMAT_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "databases": [], "files": []}

    t_db = time.perf_counter()
    seen: dict[Path, str] = {}
    for name, path in databases.items():
        resolved = Path(path).resolve()
        if resolved in seen:  # asset and generation database may be the same file
            manifest["databases"].append({"name": name, "same_as": seen[resolved]})
            continue
        seen[resolved] = name
        target = out / "db" / f"{name}.sqlite3"
        source = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
        copy = sqlite3.connect(target)
        try:
            source.backup(copy)  # consistent snapshot even while other connections write
            copy.execute("PRAGMA journal_mode=DELETE")  # the snapshot is one self-contained file, no -wal/-shm side files
        finally:
            copy.close()
            source.close()
        check, tables = _integrity(target)
        if check != "ok":
            raise BackupError(f"snapshot of '{name}' failed the integrity check: {check}")
        manifest["databases"].append({"name": name, "file": f"db/{name}.sqlite3", "size": target.stat().st_size,
                                      "sha256": _sha256(target), "integrity_check": check, "tables": tables})
    db_seconds = time.perf_counter() - t_db

    t_files = time.perf_counter()
    for area, root in file_areas.items():
        root = Path(root)
        if not root.is_dir():
            manifest["files"].append({"area": area, "missing_source": True})
            continue
        for source in _regular_files(root):
            rel = source.relative_to(root).as_posix()
            target = out / "files" / area / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            manifest["files"].append({"area": area, "path": rel, "size": target.stat().st_size, "sha256": _sha256(target)})
    files_seconds = time.perf_counter() - t_files

    manifest["totals"] = {
        "database_bytes": sum(d.get("size", 0) for d in manifest["databases"]),
        "file_count": sum(1 for f in manifest["files"] if "path" in f),
        "file_bytes": sum(f.get("size", 0) for f in manifest["files"]),
        "rows": sum(sum(d.get("tables", {}).values()) for d in manifest["databases"]),
    }
    manifest["seconds"] = {"databases": round(db_seconds, 3), "files": round(files_seconds, 3), "total": round(time.perf_counter() - started, 3)}
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return out


def verify(backup_dir: Path) -> dict:
    """Check every file of a backup against its manifest; raise BackupVerificationError listing all problems."""
    backup_dir = Path(backup_dir)
    manifest_path = backup_dir / MANIFEST
    if not manifest_path.is_file():
        raise BackupVerificationError(f"no {MANIFEST} in {backup_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT_VERSION:
        raise BackupVerificationError(f"unsupported backup format: {manifest.get('format')}")
    problems: list[str] = []
    for entry in manifest["databases"]:
        if "same_as" in entry:
            continue
        path = backup_dir / entry["file"]
        if not path.is_file():
            problems.append(f"missing database file: {entry['file']}")
        elif _sha256(path) != entry["sha256"]:
            problems.append(f"database file changed: {entry['file']}")
    for entry in manifest["files"]:
        if "path" not in entry:
            continue
        path = backup_dir / "files" / entry["area"] / entry["path"]
        if not path.is_file():
            problems.append(f"missing file: {entry['area']}/{entry['path']}")
        elif path.stat().st_size != entry["size"] or _sha256(path) != entry["sha256"]:
            problems.append(f"file changed: {entry['area']}/{entry['path']}")
    expected = {MANIFEST}
    expected |= {e["file"] for e in manifest["databases"] if "file" in e}
    expected |= {f"files/{e['area']}/{e['path']}" for e in manifest["files"] if "path" in e}
    for found in _regular_files(backup_dir):
        rel = found.relative_to(backup_dir).as_posix()
        if rel not in expected:
            problems.append(f"unlisted file in backup: {rel}")
    if problems:
        raise BackupVerificationError("; ".join(problems[:20]) + (f" (+{len(problems) - 20} more)" if len(problems) > 20 else ""))
    return manifest


def restore(backup_dir: Path, target_root: Path) -> dict:
    """Verify the backup, then copy it into an empty target. Returns the paths and what was checked."""
    started = time.perf_counter()
    backup_dir, target_root = Path(backup_dir), Path(target_root)
    manifest = verify(backup_dir)  # nothing is written if this fails
    if target_root.exists() and any(target_root.iterdir()):
        raise BackupError(f"restore target is not empty: {target_root}")
    target_root.mkdir(parents=True, exist_ok=True)
    result: dict = {"databases": {}, "areas": {}}
    names_to_files: dict[str, Path] = {}
    for entry in manifest["databases"]:
        if "same_as" in entry:
            result["databases"][entry["name"]] = str(names_to_files[entry["same_as"]])
            continue
        destination = target_root / "db" / f"{entry['name']}.sqlite3"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_dir / entry["file"], destination)
        check, tables = _integrity(destination)
        if check != "ok" or tables != entry["tables"] or _sha256(destination) != entry["sha256"]:
            raise BackupVerificationError(f"restored database '{entry['name']}' does not match the backup (integrity={check})")
        names_to_files[entry["name"]] = destination
        result["databases"][entry["name"]] = str(destination)
    for entry in manifest["files"]:
        area_root = target_root / "files" / entry["area"]
        area_root.mkdir(parents=True, exist_ok=True)
        result["areas"][entry["area"]] = str(area_root)
        if "path" not in entry:
            continue
        destination = area_root / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_dir / "files" / entry["area"] / entry["path"], destination)
        if _sha256(destination) != entry["sha256"]:
            raise BackupVerificationError(f"restored file changed: {entry['area']}/{entry['path']}")
    result["totals"] = manifest["totals"]
    result["seconds"] = round(time.perf_counter() - started, 3)
    return result


def _runtime_sources() -> tuple[dict[str, Path], dict[str, Path]]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import config
    databases = {"assets": Path(config.ASSET_DATABASE_PATH)}
    if config.GENERATION_DATABASE_PATH:
        databases["generation"] = Path(config.GENERATION_DATABASE_PATH)
    return databases, {"private_assets": Path(config.ASSET_STORAGE_DIR), "outputs": Path(config.OUTPUT_DIR),
                             "library": Path(config.LIBRARY_STORAGE_DIR)}  # R-032: the default library files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backup", help="back up the databases and file storage configured for the app")
    b.add_argument("--dest", required=True, type=Path, help="directory that will contain backup-<timestamp>/")
    v = sub.add_parser("verify", help="check a backup against its manifest")
    v.add_argument("backup_dir", type=Path)
    r = sub.add_parser("restore", help="verify, then restore into a NEW empty directory")
    r.add_argument("backup_dir", type=Path)
    r.add_argument("--target", required=True, type=Path, help="empty (or new) directory to restore into")
    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            databases, areas = _runtime_sources()
            out = backup(databases, areas, args.dest)
            print(json.dumps({"backup": str(out), **json.loads((out / MANIFEST).read_text())["totals"],
                              "seconds": json.loads((out / MANIFEST).read_text())["seconds"]}, indent=2))
        elif args.command == "verify":
            manifest = verify(args.backup_dir)
            print(json.dumps({"ok": True, "totals": manifest["totals"]}, indent=2))
        else:
            print(json.dumps(restore(args.backup_dir, args.target), indent=2))
            print("To use the restored copy set ASSET_DATABASE_PATH, ASSET_STORAGE_DIR, OUTPUT_DIR and LIBRARY_STORAGE_DIR to the paths above.", file=sys.stderr)
    except BackupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
