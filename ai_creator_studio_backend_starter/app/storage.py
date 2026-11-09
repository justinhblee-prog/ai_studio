"""Low-level storage port for the Generation Job persistence adapters.

Connection lifetime and transaction semantics are backend-owned. SQLite DDL
and SQL dialect statements live in schema and aggregate repository modules;
this abstraction does not imply PostgreSQL runtime support.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator, Protocol
from contextlib import contextmanager


class StorageBackend(Protocol):
    name: str
    def connect(self, database_path: Path) -> sqlite3.Connection: ...
    def begin_write(self, connection: sqlite3.Connection) -> None: ...
    def transaction(self, database_path: Path) -> Iterator[sqlite3.Connection]: ...


class SQLiteStorage:
    name = "sqlite"

    def connect(self, database_path: Path) -> sqlite3.Connection:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def begin_write(self, connection: sqlite3.Connection) -> None:
        # SQLite's reserved write lock serializes read-modify-write claim paths.
        connection.execute("BEGIN IMMEDIATE")

    @contextmanager
    def transaction(self, database_path: Path) -> Iterator[sqlite3.Connection]:
        """Own connection lifetime and commit/rollback behavior for one unit of work."""
        connection = self.connect(database_path)
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


def get_storage(backend: str | None = None) -> StorageBackend:
    from app import config
    selected = (backend or config.DATABASE_BACKEND).strip().lower()
    if selected == "sqlite":
        return SQLiteStorage()
    if selected == "postgresql":
        raise RuntimeError("PostgreSQL storage driver is not implemented; refusing SQLite fallback.")
    raise ValueError(f"Unsupported DATABASE_BACKEND: {selected}")
