#!/usr/bin/env python3
"""Dry-run-first cleanup of expired private Lookbook ZIP packages; audit rows are retained.

The cleanup is deliberately file-only: immutable database audit rows are never changed.
Each candidate is handled independently so one filesystem error does not abort the batch.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
from pathlib import Path
from typing import Iterable, Mapping, Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.lookbook import _connect, _lookbook_package_dir, initialize


def _safe_storage_key(value: Any) -> bool:
    """Accept only a single ordinary filename; reject traversal and platform separators."""
    if not isinstance(value, str) or not value or value in {".", ".."}:
        return False
    if "/" in value or "\\" in value or "\x00" in value:
        return False
    return Path(value).name == value


def cleanup_candidates(rows: Iterable[Mapping[str, Any]], package_dir: Path, *, apply: bool) -> dict[str, int]:
    """Inspect/delete expired package files without following symlinks.

    A directory file descriptor anchors operations to the already-resolved private export
    directory. unlink(dir_fd=...) removes a directory entry (including a raced-in symlink)
    rather than following its target. Only regular files are eligible.
    """
    counts = {"inspected": 0, "would_remove": 0, "removed": 0,
              "missing": 0, "invalid_paths": 0, "non_regular": 0, "failed": 0}
    package_dir = package_dir.resolve()
    fd = os.open(package_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        for row in rows:
            counts["inspected"] += 1
            key = row["storage_key"]
            if not _safe_storage_key(key):
                counts["invalid_paths"] += 1
                continue
            try:
                info = os.stat(key, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                counts["missing"] += 1
                continue
            except OSError:
                counts["failed"] += 1
                continue
            if not stat.S_ISREG(info.st_mode):
                counts["non_regular"] += 1
                continue
            counts["would_remove"] += 1
            if not apply:
                continue
            try:
                # dir_fd prevents path redirection outside package_dir. unlink never follows
                # a symlink if an attacker races the prior lstat/stat check.
                os.unlink(key, dir_fd=fd)
                counts["removed"] += 1
            except FileNotFoundError:
                counts["missing"] += 1
                counts["would_remove"] -= 1
            except OSError:
                counts["failed"] += 1
                counts["would_remove"] -= 1
    finally:
        os.close(fd)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Delete expired package files; audit records remain")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 10000:
        parser.error("--limit must be between 1 and 10000")
    started = time.monotonic()
    initialize()
    package_dir = _lookbook_package_dir().resolve()
    now = int(time.time())
    db = _connect()
    try:
        rows = db.execute(
            "SELECT export_id,storage_key FROM lookbook_output_package_exports "
            "WHERE expires_at<? ORDER BY expires_at LIMIT ?", (now, args.limit)
        ).fetchall()
    finally:
        db.close()
    counts = cleanup_candidates(rows, package_dir, apply=args.apply)
    result = {"mode": "apply" if args.apply else "dry_run", "limit": args.limit,
              "candidate_count": counts["inspected"], **counts,
              "partial_failure": counts["failed"] > 0,
              "audit_rows_retained": True,
              "duration_ms": round((time.monotonic() - started) * 1000, 2),
              "completed_at": int(time.time())}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    # Non-zero signals partial operational failure; successfully handled candidates remain handled.
    return 2 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
