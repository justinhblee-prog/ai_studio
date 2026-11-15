"""Add, change or take down default-library items from a manifest CSV and an image folder (R-034).

  python scripts/library_import.py MANIFEST.csv IMAGE_DIR              check only (dry run, the default); changes nothing
  python scripts/library_import.py MANIFEST.csv IMAGE_DIR --apply      write the items (all rows must be valid, otherwise nothing is written)
  python scripts/library_import.py --retire top-01 top-02 [--apply]    take items down (status retired); they disappear for users at once

Manifest columns (see docs/LIBRARY_OPERATIONS.md): id, category, subcategory, name_ko, name_en, tags, file, source, tool_and_date,
rights_ok, likeness_check, note, status, is_placeholder, and for category "model": skin_tone, hair, body_type, age_range, region_style.
Rules: every problem is reported with its manifest line number; a row without rights_ok=yes, with a missing/oversized/unsupported
image, an unknown category/source or (models) an attribute outside the allowed list is rejected. The same id twice is rejected.
The same id with the same file is a no-op; the same id with a different file becomes a NEW VERSION (the old file is kept).
Items marked is_placeholder (SAMPLE images) are refused when --production is given or ACS_ENVIRONMENT=production.
Exit code: 0 = no rejected row, 1 = at least one rejected row (nothing is written), 2 = bad command line / unreadable manifest.
This tool never calls a network service and never deletes files or database rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MAX_IMAGE_BYTES = 15 * 1024 * 1024
REQUIRED_COLUMNS = ("id", "category", "name_ko", "file", "source", "tool_and_date", "rights_ok")
OPTIONAL_COLUMNS = ("subcategory", "name_en", "tags", "likeness_check", "note", "status", "is_placeholder")
YES = {"yes", "y", "true", "1"}


def _read_manifest(path: Path):
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            header = [h.strip() for h in (reader.fieldnames or [])]
            rows = [(i, {(k or "").strip(): (v or "").strip() for k, v in row.items()}) for i, row in enumerate(reader, start=2)]
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise SystemExit(f"cannot read the manifest: {exc}") from exc
    return header, rows


def _existing(db_path: Path):
    """item_id -> (version, current checksum) from the database, read-only; empty when nothing has been imported yet."""
    if not db_path.is_file():
        return {}
    try:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        found = {r[0]: (r[1], r[2]) for r in db.execute(
            "SELECT i.item_id, i.version, v.checksum_sha256 FROM library_items i JOIN library_item_versions v ON v.item_id=i.item_id AND v.version=i.version")}
        db.close()
        return found
    except sqlite3.Error:
        return {}


def check_manifest(manifest: Path, image_dir: Path, *, production: bool, existing: dict):
    """Returns (valid, rejected, fatal). valid: list of dicts {line, fields, content, filename, action}; rejected: list of (line, id, reason)."""
    from app import library

    header, rows = _read_manifest(manifest)
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        return [], [], f"line 1: the manifest has no column(s): {', '.join(missing)}"
    valid, rejected, seen = [], [], {}
    image_root = image_dir.resolve()
    for line, row in rows:
        item_id = row.get("id", "")
        if not any(row.values()):
            continue
        def reject(reason):
            rejected.append((line, item_id or "(no id)", reason))
        if item_id in seen:
            reject(f"duplicate id (first used on line {seen[item_id]})")
            continue
        seen[item_id] = line
        blanks = [c for c in REQUIRED_COLUMNS if not row.get(c)]
        if blanks:
            reject("required value(s) missing: " + ", ".join(blanks))
            continue
        if row["rights_ok"].lower() not in YES:
            reject("rights_ok is not 'yes' (the right to provide this image must be confirmed)")
            continue
        placeholder = row.get("is_placeholder", "").lower() in YES
        if placeholder and (production or os.environ.get("ACS_ENVIRONMENT", "").strip().lower() == "production"):
            reject("a SAMPLE (placeholder) item cannot be imported into a production environment")
            continue
        name = row["file"]
        if name != Path(name).name or name in {".", ".."}:
            reject("file must be a plain file name inside the image folder")
            continue
        path = (image_root / name).resolve()
        if path.parent != image_root or not path.is_file():
            reject(f"image file not found: {name}")
            continue
        if path.stat().st_size > MAX_IMAGE_BYTES:
            reject(f"image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB: {name}")
            continue
        content = path.read_bytes()
        fields = {
            "item_id": item_id, "category": row["category"], "subcategory": row.get("subcategory"), "name_ko": row["name_ko"],
            "name_en": row.get("name_en"), "tags": [t.strip() for t in row.get("tags", "").split(",") if t.strip()],
            "attributes": {k: row.get(k, "") for k in library.MODEL_ATTRIBUTES} if row["category"] == "model" else {},
            "source": row["source"], "tool_and_date": row["tool_and_date"], "rights_confirmed": True,
            "status": row.get("status") or "published", "is_placeholder": placeholder, "note": row.get("note"),
        }
        try:
            library.validate_item_fields(fields)
            from app.assets.validation import AssetValidationError, validate_image_upload
            try:
                validate_image_upload(name, content)
            except AssetValidationError as exc:
                raise library.LibraryError(exc.code, str(exc)) from exc
        except library.LibraryError as exc:
            reject(f"{exc.code}: {exc}")
            continue
        warning = ""
        if row["category"] == "model" and row.get("likeness_check", "").lower() not in YES:
            warning = "likeness_check is not 'yes' (a person has not confirmed that the model resembles no real person)"
        current = existing.get(item_id)
        digest = hashlib.sha256(content).hexdigest()
        action = "create" if current is None else ("unchanged-or-update" if current[1] == digest else "new_version")
        valid.append({"line": line, "id": item_id, "fields": fields, "content": content, "filename": name, "action": action, "warning": warning})
    return valid, rejected, None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path)
    parser.add_argument("image_dir", nargs="?", type=Path)
    parser.add_argument("--apply", action="store_true", help="write the changes (default: only check)")
    parser.add_argument("--production", action="store_true", help="refuse SAMPLE (placeholder) items")
    parser.add_argument("--retire", nargs="+", metavar="ID", help="take these items down instead of importing")
    parser.add_argument("--db", type=Path, help="asset database (default: ASSET_DATABASE_PATH)")
    parser.add_argument("--library-dir", type=Path, help="library file folder (default: LIBRARY_STORAGE_DIR)")
    args = parser.parse_args(argv)

    from app import config, library
    if args.db:
        config.ASSET_DATABASE_PATH = args.db.resolve()
    if args.library_dir:
        config.LIBRARY_STORAGE_DIR = args.library_dir.resolve()

    if args.retire:
        known = _existing(Path(config.ASSET_DATABASE_PATH))
        unknown = [i for i in args.retire if i not in known]
        for item_id in args.retire:
            print(f"{'RETIRE' if item_id in known else 'REJECT'} {item_id}" + ("" if item_id in known else "  (no such item)"))
        if unknown:
            return 1
        if args.apply:
            for item_id in args.retire:
                library.set_status(item_id, "retired")
            print(f"retired {len(args.retire)} item(s)")
        else:
            print("dry run: nothing changed (add --apply)")
        return 0

    if not args.manifest or not args.image_dir:
        parser.error("give MANIFEST.csv and IMAGE_DIR (or use --retire)")
    if not args.manifest.is_file() or not args.image_dir.is_dir():
        print("manifest file or image folder not found", file=sys.stderr)
        return 2
    valid, rejected, fatal = check_manifest(args.manifest, args.image_dir, production=args.production or False,
                                            existing=_existing(Path(config.ASSET_DATABASE_PATH)))
    if fatal:
        print("REJECT " + fatal)
        return 1
    for item in valid:
        print(f"OK     line {item['line']}: {item['id']} ({item['action']})" + (f"  WARNING: {item['warning']}" if item["warning"] else ""))
    for line, item_id, reason in rejected:
        print(f"REJECT line {line}: {item_id}: {reason}")
    if rejected:
        print(f"{len(valid)} row(s) fine, {len(rejected)} rejected: nothing was written. Fix the rejected rows and run again.")
        return 1
    if not args.apply:
        print(f"dry run: {len(valid)} row(s) fine, nothing changed (add --apply to write them)")
        return 0
    counts: dict[str, int] = {}
    for item in valid:
        result = library.upsert_item(item["fields"], item["content"], item["filename"])
        counts[result["action"]] = counts.get(result["action"], 0) + 1
    print("applied: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
