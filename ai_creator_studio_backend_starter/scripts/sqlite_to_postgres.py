#!/usr/bin/env python3
"""Portable, offline SQLite -> PostgreSQL migration bundle utility.

Export is dependency-free. Import requires psycopg 3 and a NEW/EMPTY target DB.
This utility migrates relational schema/data only; private asset/output files must
be copied separately and verified against their storage keys/checksums.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
import re
import binascii
import os
import shutil
import tempfile
import sqlite3
import sys
from pathlib import Path
from typing import Any

BUNDLE_VERSION = 2


def _quote_ident(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsupported SQL identifier in source schema: {value!r}")
    return '"' + value.replace('"', '""') + '"'


def _topological_tables(conn: sqlite3.Connection, names: list[str]) -> list[str]:
    dependencies: dict[str, set[str]] = {}
    for name in names:
        dependencies[name] = {
            row[2] for row in conn.execute(f"PRAGMA foreign_key_list({_quote_ident(name)})")
            if row[2] in names and row[2] != name
        }
    ordered: list[str] = []
    remaining = set(names)
    while remaining:
        ready = sorted(name for name in remaining if not (dependencies[name] & remaining))
        if not ready:
            # Cyclic FK graphs are legal in PostgreSQL when constraints are deferred;
            # the current application schema is expected to be acyclic.
            raise ValueError(f"Foreign-key cycle detected among tables: {sorted(remaining)}")
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered


def _json_safe(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"__acs_bytes_b64__": base64.b64encode(bytes(value)).decode("ascii")}
    return value


def _json_restore(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"__acs_bytes_b64__"}:
        encoded = value["__acs_bytes_b64__"]
        if not isinstance(encoded, str):
            raise ValueError("Binary payload must contain a base64 string")
        try:
            return base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Binary payload contains invalid base64") from exc
    return value


def _json_object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON numeric constant is not allowed: {value}")


def _load_strict_json(value: str) -> Any:
    return json.loads(value, object_pairs_hook=_json_object_no_duplicates,
                      parse_constant=_reject_json_constant)


def _schema_trigger_names(schema: str) -> list[str]:
    """Read trigger declarations only at SQL statement boundaries, never inside bodies/literals."""
    names: list[str] = []
    trigger_start = re.compile(
        r'^\s*CREATE\s+TRIGGER\s+'
        r'"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"', re.IGNORECASE
    )
    for statement in _split_sql_statements(schema):
        match = trigger_start.match(statement)
        if match:
            names.append(match.group("name"))
    return names


def _pg_ddl(sql: str) -> str:
    """Translate the SQLite DDL subset used by this project to PostgreSQL."""
    value = sql.strip().rstrip(";")
    value = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "BIGSERIAL PRIMARY KEY", value, flags=re.I)
    value = re.sub(r"\bAUTOINCREMENT\b", "", value, flags=re.I)
    value = re.sub(r"\bREAL\b", "DOUBLE PRECISION", value, flags=re.I)
    value = re.sub(r"\bBLOB\b", "BYTEA", value, flags=re.I)
    # SQLite's untyped/affinity columns are not used in the app's current schema.
    return value + ";"



def _translate_append_only_trigger(sql: str) -> str | None:
    """Translate the project's narrow BEFORE UPDATE/DELETE RAISE(ABORT) trigger form."""
    pattern = re.compile(
        r"\s*CREATE\s+TRIGGER\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+"
        r"BEFORE\s+(?P<event>UPDATE|DELETE)\s+ON\s+"
        r"(?P<table>[A-Za-z_][A-Za-z0-9_]*)\s+"
        r"BEGIN\s+SELECT\s+RAISE\s*\(\s*ABORT\s*,\s*"
        r"'(?P<message>(?:''|[^'])*)'\s*\)\s*;\s*END\s*;?\s*",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.fullmatch(sql)
    if not match:
        return None
    name = _quote_ident(match.group("name"))
    table = _quote_ident(match.group("table"))
    event = match.group("event").upper()
    message = match.group("message").replace("''", "'").replace("'", "''")
    return (
        f"CREATE TRIGGER {name} BEFORE {event} ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION acs_raise_append_only_error('"
        + message + "');"
    )


def _split_sql_statements(source: str) -> list[str]:
    """Split PostgreSQL SQL while respecting strings, dollar bodies and comments."""
    statements: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    escape_string = False
    dollar_tag: str | None = None
    line_comment = False
    block_comment_depth = 0
    index = 0
    while index < len(source):
        if line_comment:
            if source[index] in "\r\n":
                line_comment = False
                buffer.append(source[index])
            index += 1
            continue
        if block_comment_depth:
            if source.startswith("/*", index):
                block_comment_depth += 1
                index += 2
            elif source.startswith("*/", index):
                block_comment_depth -= 1
                index += 2
            else:
                index += 1
            continue
        if dollar_tag is not None:
            if source.startswith(dollar_tag, index):
                buffer.append(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
                continue
            buffer.append(source[index])
            index += 1
            continue
        if quote is not None:
            char = source[index]
            buffer.append(char)
            if escape_string and char == "\\" and index + 1 < len(source):
                buffer.append(source[index + 1])
                index += 2
                continue
            if char == quote:
                if index + 1 < len(source) and source[index + 1] == quote:
                    buffer.append(source[index + 1])
                    index += 2
                    continue
                quote = None
                escape_string = False
            index += 1
            continue
        if source.startswith("--", index):
            line_comment = True
            index += 2
            buffer.append(" ")
            continue
        if source.startswith("/*", index):
            block_comment_depth = 1
            index += 2
            buffer.append(" ")
            continue
        if source[index] in "'\"":
            quote = source[index]
            # PostgreSQL E'...' strings allow backslash-escaped quote characters.
            escape_string = quote == "'" and index > 0 and source[index - 1] in "eE" and (
                index < 2 or not (source[index - 2].isalnum() or source[index - 2] in "_$")
            )
            buffer.append(source[index])
            index += 1
            continue
        if source[index] == "$":
            tag_match = re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", source[index:])
            if tag_match:
                dollar_tag = tag_match.group(0)
                buffer.append(dollar_tag)
                index += len(dollar_tag)
                continue
        if source[index] == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer.clear()
            index += 1
            continue
        buffer.append(source[index])
        index += 1
    if quote is not None or dollar_tag is not None:
        raise ValueError("Unterminated quoted value in PostgreSQL schema bundle")
    if block_comment_depth:
        raise ValueError("Unterminated block comment in PostgreSQL schema bundle")
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements

def export_bundle(database: Path, destination: Path) -> dict[str, Any]:
    database = database.resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    conn = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        objects = conn.execute("""SELECT type, name, tbl_name, sql FROM sqlite_master
            WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
            AND type IN ('table','index','trigger','view')
            ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1
                WHEN 'trigger' THEN 2 ELSE 3 END, name""").fetchall()
        trigger_rows = [row for row in objects if row["type"] == "trigger"]
        unsupported = [
            f"{row['type']} {row['name']}"
            for row in objects
            if row["type"] == "view"
            or (row["type"] == "table" and re.match(r"\s*CREATE\s+VIRTUAL\s+TABLE\b", row["sql"], re.I))
        ]
        unsupported.extend(
            f"trigger {row['name']} (unsupported trigger body)"
            for row in trigger_rows if _translate_append_only_trigger(row["sql"]) is None
        )
        if unsupported:
            details = ", ".join(unsupported[:20])
            suffix = f" (and {len(unsupported) - 20} more)" if len(unsupported) > 20 else ""
            raise ValueError(
                "SQLite export refused: PostgreSQL migration does not yet translate "
                f"these database objects: {details}{suffix}. "
                "Convert and verify these objects explicitly before exporting."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            raise ValueError(f"Migration bundle destination must not be a symlink: {destination}")
        if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
            raise ValueError(
                f"Migration bundle destination is not empty or is not a directory: {destination}. "
                "Use a fresh directory so stale or unrelated files cannot enter the bundle."
            )
        # Build off to the side and publish with one same-filesystem rename. A failed
        # export must never leave a partial bundle that blocks a safe retry.
        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
        data_dir = staging / "data"
        data_dir.mkdir()
        tables = [row["name"] for row in objects if row["type"] == "table"]
        ordered = _topological_tables(conn, tables)
        table_defs = {row["name"]: row["sql"] for row in objects if row["type"] == "table"}
        index_defs = [row["sql"] for row in objects if row["type"] == "index" and row["sql"]]
        trigger_defs = [_translate_append_only_trigger(row["sql"]) for row in trigger_rows]
        schema_parts = [_pg_ddl(table_defs[name]) for name in ordered]
        schema_parts.extend(_pg_ddl(sql) for sql in index_defs)
        if trigger_defs:
            schema_parts.append("""CREATE FUNCTION acs_raise_append_only_error()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION USING MESSAGE = TG_ARGV[0], ERRCODE = 'integrity_constraint_violation';
END;
$$;""")
            schema_parts.extend(trigger_defs)
        (staging / "schema.postgresql.sql").write_text("\n\n".join(schema_parts) + "\n", encoding="utf-8")

        table_manifest = []
        total_rows = 0
        for name in ordered:
            columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({_quote_ident(name)})")]
            serial_match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", table_defs[name], re.I)
            serial_columns = [serial_match.group(1)] if serial_match else []
            path = data_dir / f"{name}.jsonl"
            count = 0
            digest = hashlib.sha256()
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                cursor = conn.execute(f"SELECT * FROM {_quote_ident(name)}")
                for row in cursor:
                    payload = {column: _json_safe(row[column]) for column in columns}
                    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                    handle.write(line + "\n")
                    digest.update((line + "\n").encode("utf-8"))
                    count += 1
            table_manifest.append({"name": name, "columns": columns, "serial_columns": serial_columns,
                                   "rows": count, "file": f"data/{name}.jsonl", "sha256": digest.hexdigest()})
            total_rows += count
        schema_path = staging / "schema.postgresql.sql"
        manifest = {"bundle_version": BUNDLE_VERSION, "source_database": database.name,
                    "schema_sha256": hashlib.sha256(schema_path.read_bytes()).hexdigest(),
                    "tables": table_manifest, "table_count": len(ordered), "row_count": total_rows,
                    "triggers": [row["name"] for row in trigger_rows], "trigger_count": len(trigger_rows)}
        (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        conn.commit()
        if destination.exists():
            # The earlier check permits an existing empty directory for convenience.
            destination.rmdir()
        os.replace(staging, destination)
        return manifest
    finally:
        if "staging" in locals() and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        conn.close()


def _bundle_file(bundle: Path, relative: str, label: str) -> Path:
    """Resolve a manifest path without permitting traversal or symlink escapes."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError(f"Invalid {label} path in migration manifest")
    candidate = Path(relative)
    if candidate.is_absolute() or any(part in ("", ".", "..") for part in candidate.parts):
        raise ValueError(f"Unsafe {label} path in migration manifest: {relative!r}")
    root = bundle.resolve(strict=True)
    current = root
    for part in candidate.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Symlink is not allowed in migration bundle: {relative!r}")
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"{label} file is missing or outside migration bundle: {relative!r}")
    return resolved


def _validate_bundle(bundle: Path) -> tuple[dict[str, Any], str, dict[str, bytes]]:
    """Validate every manifest-controlled path, digest, JSONL row and schema before DB access."""
    if bundle.is_symlink():
        raise ValueError("Migration bundle must not be a symlink")
    root = bundle.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Migration bundle must be a directory")
    manifest_path = _bundle_file(root, "manifest.json", "manifest")
    try:
        manifest = _load_strict_json(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Migration manifest is not valid UTF-8 JSON") from exc
    bundle_version = manifest.get("bundle_version") if isinstance(manifest, dict) else None
    if (not isinstance(bundle_version, int) or isinstance(bundle_version, bool)
            or bundle_version != BUNDLE_VERSION):
        raise ValueError(f"Unsupported migration bundle version; expected {BUNDLE_VERSION} as an integer")
    tables = manifest.get("tables")
    if not isinstance(tables, list) or not tables:
        raise ValueError("Migration manifest tables must be a non-empty list")
    table_count = manifest.get("table_count")
    if not isinstance(table_count, int) or isinstance(table_count, bool) or table_count != len(tables):
        raise ValueError("Migration manifest table_count does not match tables")
    row_count = manifest.get("row_count")
    if not isinstance(row_count, int) or isinstance(row_count, bool) or row_count < 0:
        raise ValueError("Migration manifest row_count is invalid")
    source_database = manifest.get("source_database")
    if not isinstance(source_database, str) or not source_database.strip():
        raise ValueError("Migration manifest source_database is invalid")
    trigger_names = manifest.get("triggers")
    trigger_count = manifest.get("trigger_count")
    if not isinstance(trigger_names, list) or not isinstance(trigger_count, int) or isinstance(trigger_count, bool):
        raise ValueError("Migration manifest trigger inventory is invalid")
    if trigger_count != len(trigger_names) or any(
        not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
        for name in trigger_names
    ) or len(set(trigger_names)) != len(trigger_names):
        raise ValueError("Migration manifest trigger inventory is inconsistent")
    schema_path = _bundle_file(root, "schema.postgresql.sql", "schema")
    schema_bytes = schema_path.read_bytes()
    schema_digest = manifest.get("schema_sha256")
    if not isinstance(schema_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", schema_digest):
        raise ValueError("Migration manifest schema_sha256 is invalid")
    if hashlib.sha256(schema_bytes).hexdigest() != schema_digest:
        raise ValueError("Checksum mismatch for schema.postgresql.sql")
    try:
        schema = schema_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("PostgreSQL schema is not valid UTF-8") from exc
    schema_trigger_names = _schema_trigger_names(schema)
    if len(schema_trigger_names) != len(set(schema_trigger_names)) or sorted(schema_trigger_names) != sorted(trigger_names):
        raise ValueError("Migration manifest trigger inventory does not match PostgreSQL schema")
    seen_names: set[str] = set()
    seen_files: set[str] = set()
    data_payloads: dict[str, bytes] = {}
    total_rows = 0
    for table in tables:
        if not isinstance(table, dict):
            raise ValueError("Migration table entry must be an object")
        name, columns, serial_columns = table.get("name"), table.get("columns"), table.get("serial_columns")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or name in seen_names:
            raise ValueError(f"Invalid or duplicate table name in migration manifest: {name!r}")
        seen_names.add(name)
        if not isinstance(columns, list) or not columns or any(
            not isinstance(column, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", column)
            for column in columns
        ) or len(set(columns)) != len(columns):
            raise ValueError(f"Invalid columns for migration table {name}")
        if not isinstance(serial_columns, list) or any(
            not isinstance(column, str) or column not in columns for column in serial_columns
        ) or len(set(serial_columns)) != len(serial_columns):
            raise ValueError(f"Invalid serial_columns for migration table {name}")
        rows = table.get("rows")
        if not isinstance(rows, int) or isinstance(rows, bool) or rows < 0:
            raise ValueError(f"Invalid row count for migration table {name}")
        relative = table.get("file")
        if not isinstance(relative, str) or relative != f"data/{name}.jsonl":
            raise ValueError(f"Unexpected data file path for migration table {name}")
        if relative in seen_files:
            raise ValueError(f"Duplicate data file in migration manifest: {relative!r}")
        seen_files.add(relative)
        data_path = _bundle_file(root, relative, f"data for {name}")
        digest = table.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Invalid checksum for {name}")
        data_bytes = data_path.read_bytes()
        if hashlib.sha256(data_bytes).hexdigest() != digest:
            raise ValueError(f"Checksum mismatch for {name}")
        data_payloads[name] = data_bytes
        try:
            text = data_bytes.decode("utf-8")
            actual_rows = 0
            # JSONL records are separated by the literal LF byte only. str.splitlines()
            # is broader and treats valid Unicode characters such as U+2028/U+2029,
            # NEL and vertical tab inside JSON strings as record boundaries.
            lines = text.split("\n")
            if lines and lines[-1] == "":
                lines.pop()  # exporter emits one final LF, not an extra empty record
            for line_number, line in enumerate(lines, 1):
                if not line:
                    raise ValueError(f"Blank JSONL record in {name} at line {line_number}")
                record = _load_strict_json(line)
                if not isinstance(record, dict) or set(record) != set(columns):
                    raise ValueError(f"Column mismatch in {name} at line {line_number}")
                for value in record.values():
                    _json_restore(value)
                actual_rows += 1
        except (UnicodeError, json.JSONDecodeError, TypeError, binascii.Error) as exc:
            raise ValueError(f"Invalid JSONL data for {name}") from exc
        if actual_rows != rows:
            raise ValueError(f"Row count mismatch for {name}: {actual_rows} != {rows}")
        total_rows += actual_rows
    # A bundle is a closed artifact: reject hidden/unreferenced files rather than
    # silently accepting payloads that the manifest does not account for.
    expected_files = {"manifest.json", "schema.postgresql.sql", *seen_files}
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for current, directories, filenames in __import__("os").walk(root, followlinks=False):
        current_path = Path(current)
        for directory in directories:
            directory_path = current_path / directory
            if directory_path.is_symlink():
                raise ValueError(f"Symlink is not allowed in migration bundle: {directory!r}")
            actual_directories.add(directory_path.relative_to(root).as_posix())
        for filename in filenames:
            file_path = current_path / filename
            if file_path.is_symlink():
                raise ValueError(f"Symlink is not allowed in migration bundle: {file_path.relative_to(root)!s}")
            actual_files.add(file_path.relative_to(root).as_posix())
    if actual_files != expected_files or actual_directories != {"data"}:
        unexpected = sorted(actual_files - expected_files)
        missing = sorted(expected_files - actual_files)
        unexpected_dirs = sorted(actual_directories - {"data"})
        missing_dirs = sorted({"data"} - actual_directories)
        raise ValueError(
            "Migration bundle file set mismatch; "
            f"unexpected={unexpected}, missing={missing}, "
            f"unexpected_directories={unexpected_dirs}, missing_directories={missing_dirs}"
        )
    if total_rows != manifest["row_count"]:
        raise ValueError(f"Migration total row count mismatch: {total_rows} != {manifest['row_count']}")
    return manifest, schema, data_payloads


def import_bundle(bundle: Path, database_url: str) -> dict[str, int]:
    manifest, schema, data_payloads = _validate_bundle(bundle)
    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:
        raise RuntimeError("PostgreSQL import requires psycopg 3; install requirements-migration.txt") from exc

    inserted: dict[str, int] = {}
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_schema()")
            schema_name = cur.fetchone()[0]
            cur.execute("""SELECT count(*) FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = %s AND relation.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')""",
                (schema_name,))
            if cur.fetchone()[0]:
                raise RuntimeError(
                    "Target PostgreSQL schema is not empty (tables, views, foreign tables, or sequences exist); "
                    "import is refused to prevent data overwrite"
                )
            for statement in _split_sql_statements(schema):
                cur.execute(statement)
            for table in manifest["tables"]:
                columns = table["columns"]
                statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table["name"]),
                    sql.SQL(",").join(sql.Identifier(column) for column in columns),
                    sql.SQL(",").join(sql.Placeholder() for _ in columns),
                )
                count = 0
                with io.StringIO(data_payloads[table["name"]].decode("utf-8")) as handle:
                    batch = []
                    for line in handle:
                        record = json.loads(line)
                        batch.append(tuple(_json_restore(record[column]) for column in columns))
                        if len(batch) >= 500:
                            cur.executemany(statement, batch)
                            count += len(batch)
                            batch.clear()
                    if batch:
                        cur.executemany(statement, batch)
                        count += len(batch)
                if count != table["rows"]:
                    raise RuntimeError(f"Row count mismatch for {table['name']}: {count} != {table['rows']}")
                inserted[table["name"]] = count
            # Restore sequences for every SQLite AUTOINCREMENT column.
            for table in manifest["tables"]:
                for column in table.get("serial_columns", []):
                    cur.execute("SELECT pg_get_serial_sequence(%s, %s)", (table["name"], column))
                    sequence = cur.fetchone()[0]
                    if sequence:
                        cur.execute(sql.SQL("SELECT setval(%s, COALESCE(MAX({}), 1), MAX({}) IS NOT NULL) FROM {}").format(
                            sql.Identifier(column), sql.Identifier(column), sql.Identifier(table["name"])), (sequence,))
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export_parser = sub.add_parser("export", help="Export a consistent SQLite snapshot bundle")
    export_parser.add_argument("--sqlite", required=True, type=Path)
    export_parser.add_argument("--out", required=True, type=Path)
    import_parser = sub.add_parser("import", help="Import a bundle into a NEW/EMPTY PostgreSQL schema")
    import_parser.add_argument("--bundle", required=True, type=Path)
    import_parser.add_argument("--database-url", required=True, help="PostgreSQL DSN; avoid shell history in production")
    args = parser.parse_args()
    if args.command == "export":
        result = export_bundle(args.sqlite, args.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = import_bundle(args.bundle, args.database_url)
        print(json.dumps({"inserted_rows": result, "total_rows": sum(result.values())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"migration failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
