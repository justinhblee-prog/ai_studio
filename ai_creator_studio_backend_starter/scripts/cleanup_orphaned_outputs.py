"""Explicit dry-run-first cleanup for unreferenced attempt-scoped output files."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import job_repository
from app.output_store import cleanup_orphaned_attempt_outputs, output_storage_lock


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--older-than-hours", type=int, default=24)
    parser.add_argument("--apply", action="store_true", help="Actually delete files; default is dry-run.")
    args = parser.parse_args()
    if args.older_than_hours < 1:
        parser.error("--older-than-hours must be at least 1")
    # Exclusive same-host lock waits for in-flight output attempts and prevents
    # new ones from entering until the reference snapshot and cleanup are complete.
    with output_storage_lock(exclusive=True):
        referenced = job_repository.list_output_storage_keys()
        candidates = cleanup_orphaned_attempt_outputs(
            referenced, older_than_seconds=args.older_than_hours * 3600, apply=args.apply
        )
    mode = "deleted" if args.apply else "dry-run candidate"
    for name in candidates:
        print(f"{mode}: {name}")
    print(f"{len(candidates)} candidate(s); {len(referenced)} committed reference(s) protected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
