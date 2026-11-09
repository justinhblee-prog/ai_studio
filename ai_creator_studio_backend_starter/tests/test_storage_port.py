from __future__ import annotations

import sqlite3

import pytest

from app.storage import SQLiteStorage, get_storage


def test_sqlite_storage_connection_applies_required_pragmas(tmp_path):
    connection = get_storage("sqlite").connect(tmp_path / "storage.sqlite3")
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert isinstance(connection, sqlite3.Connection)
    finally:
        connection.close()


def test_sqlite_storage_begin_write_uses_immediate_transaction(tmp_path):
    storage = SQLiteStorage()
    connection = storage.connect(tmp_path / "transaction.sqlite3")
    try:
        storage.begin_write(connection)
        assert connection.in_transaction is True
        connection.rollback()
    finally:
        connection.close()


def test_storage_rejects_postgresql_without_fallback():
    with pytest.raises(RuntimeError, match="not implemented"):
        get_storage("postgresql")


def test_asset_store_uses_selected_storage_port(monkeypatch, tmp_path):
    from app import config
    from app.assets import store

    database = tmp_path / "assets-through-port.sqlite3"
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", database)
    store.initialize()
    connection = get_storage("sqlite").connect(database)
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"workspaces", "workspace_members", "assets"}.issubset(names)
    finally:
        connection.close()


def test_asset_store_does_not_fallback_when_postgresql_selected(monkeypatch):
    from app import config
    from app.assets import store

    monkeypatch.setattr(config, "DATABASE_BACKEND", "postgresql")
    with pytest.raises(RuntimeError, match="PostgreSQL storage driver is not implemented"):
        store.initialize()


def test_storage_transaction_commits_and_closes_connection(tmp_path):
    storage = SQLiteStorage()
    database = tmp_path / "unit-of-work.sqlite3"
    with storage.transaction(database) as connection:
        storage.begin_write(connection)
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample(value) VALUES('committed')")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    with storage.transaction(database) as verify:
        assert verify.execute("SELECT value FROM sample").fetchone()[0] == "committed"


def test_storage_transaction_rolls_back_on_exception(tmp_path):
    storage = SQLiteStorage()
    database = tmp_path / "unit-of-work-rollback.sqlite3"
    with storage.transaction(database) as connection:
        storage.begin_write(connection)
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
    with pytest.raises(RuntimeError, match="abort unit of work"):
        with storage.transaction(database) as connection:
            storage.begin_write(connection)
            connection.execute("INSERT INTO sample(value) VALUES('not-committed')")
            raise RuntimeError("abort unit of work")
    with storage.transaction(database) as verify:
        assert verify.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 0
