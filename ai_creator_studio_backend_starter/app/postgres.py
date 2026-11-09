"""PostgreSQL connection and transactional migration primitives.

This module deliberately does not select PostgreSQL as the runtime repository.
It provides a controlled foundation for schema installation and diagnostics;
application repositories remain SQLite-only until their aggregate adapters
pass live parity and concurrency tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from app import config

MIGRATION_DIR = Path(__file__).parent / "sql" / "postgres" / "migrations"
_LOCK_KEY = 0x414353504F535447  # "ACSPOSTG"


class PostgreSQLNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class MigrationResult:
    applied: tuple[str, ...]
    already_applied: tuple[str, ...]


def _connect_factory() -> Callable[..., Any]:
    if not config.DATABASE_URL:
        raise PostgreSQLNotConfigured("DATABASE_URL is required for PostgreSQL operations")
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required; install project requirements") from exc
    return psycopg.connect


def connect(*, connect_factory: Callable[..., Any] | None = None):
    """Open a PostgreSQL connection without logging or exposing the DSN."""
    factory = connect_factory or _connect_factory()
    dsn = config.DATABASE_URL
    if not dsn:
        raise PostgreSQLNotConfigured("DATABASE_URL is required for PostgreSQL operations")
    try:
        from psycopg.rows import dict_row
        return factory(dsn, connect_timeout=5, application_name="ai-creator-studio", row_factory=dict_row)
    except ImportError:
        return factory(dsn, connect_timeout=5, application_name="ai-creator-studio")


def migration_files(directory: Path = MIGRATION_DIR) -> list[Path]:
    files = sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    versions = [p.name.split("_", 1)[0] for p in files]
    if len(versions) != len(set(versions)):
        raise ValueError("Duplicate PostgreSQL migration version")
    return files


def apply_migrations(*, connect_factory: Callable[..., Any] | None = None,
                     directory: Path = MIGRATION_DIR) -> MigrationResult:
    """Apply ordered SQL migrations atomically with an advisory transaction lock."""
    files = migration_files(directory)
    conn = connect(connect_factory=connect_factory)
    applied: list[str] = []
    already: list[str] = []
    try:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
            conn.execute("""CREATE TABLE IF NOT EXISTS acs_schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                checksum_sha256 TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
            rows = conn.execute("SELECT version, checksum_sha256 FROM acs_schema_migrations").fetchall()
            known = {str(row["version"]): str(row["checksum_sha256"]) for row in rows}
            import hashlib
            for path in files:
                version = path.name.split("_", 1)[0]
                raw = path.read_bytes()
                checksum = hashlib.sha256(raw).hexdigest()
                if version in known:
                    if known[version] != checksum:
                        raise RuntimeError(f"Applied migration checksum mismatch: {path.name}")
                    already.append(path.name)
                    continue
                conn.execute(raw.decode("utf-8"), prepare=False)
                conn.execute(
                    "INSERT INTO acs_schema_migrations(version,name,checksum_sha256) VALUES (%s,%s,%s)",
                    (version, path.name, checksum),
                )
                applied.append(path.name)
        return MigrationResult(tuple(applied), tuple(already))
    finally:
        conn.close()


def migration_status(*, connect_factory: Callable[..., Any] | None = None) -> list[dict[str, str]]:
    """Read migration ledger; does not apply schema changes."""
    conn = connect(connect_factory=connect_factory)
    try:
        with conn.transaction():
            exists_row = conn.execute("""SELECT to_regclass('public.acs_schema_migrations') AS relation""").fetchone()
            exists = exists_row["relation"] if isinstance(exists_row, dict) else exists_row[0]
            if not exists:
                return []
            rows = conn.execute(
                "SELECT version,name,checksum_sha256,applied_at::text FROM acs_schema_migrations ORDER BY version"
            ).fetchall()
            return [{"version": str(r["version"]), "name": str(r["name"]), "checksum_sha256": str(r["checksum_sha256"]), "applied_at": str(r["applied_at"])} for r in rows]
    finally:
        conn.close()
