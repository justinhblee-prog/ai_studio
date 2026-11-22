"""B-22: the PostgreSQL connection and migration primitives' own guard rails and the migration ledger reader, with a fake connection (no database).
The behaviour on a real PostgreSQL is covered by test_postgres_live_repositories.py and test_postgres_race_primitives.py."""
import hashlib
import sys
from contextlib import contextmanager

import pytest

from app import config, postgres


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConn:
    def __init__(self, script):
        self.script, self.executed, self.closed = script, [], False

    @contextmanager
    def transaction(self):
        yield

    def execute(self, sql, params=None, prepare=None):
        self.executed.append(sql.split()[0] + " " + (sql.split()[1] if len(sql.split()) > 1 else ""))
        for prefix, rows in self.script:
            if sql.lstrip().startswith(prefix):
                return FakeResult(rows)
        return FakeResult([])

    def close(self):
        self.closed = True


def factory_for(conn, seen=None):
    def factory(dsn, **kwargs):
        if seen is not None:
            seen.append((dsn, kwargs))
        return conn
    return factory


def test_without_a_url_nothing_connects(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "")
    with pytest.raises(postgres.PostgreSQLNotConfigured):
        postgres.connect()
    with pytest.raises(postgres.PostgreSQLNotConfigured):
        postgres.connect(connect_factory=lambda *a, **k: None)
    with pytest.raises(postgres.PostgreSQLNotConfigured):
        postgres._connect_factory()


def test_a_missing_driver_says_so_without_exposing_the_address(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setitem(sys.modules, "psycopg", None)
    with pytest.raises(RuntimeError, match="psycopg is required") as exc:
        postgres._connect_factory()
    assert "secret" not in str(exc.value)


def test_connect_passes_the_timeout_and_name_and_falls_back_when_the_row_factory_is_missing(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://u@h/db")
    seen = []
    postgres.connect(connect_factory=factory_for(object(), seen))
    assert seen[0][0] == "postgresql://u@h/db" and seen[0][1]["connect_timeout"] == 5 and seen[0][1]["application_name"] == "ai-creator-studio" and "row_factory" in seen[0][1]
    monkeypatch.setitem(sys.modules, "psycopg.rows", None)                  # the rows module cannot be imported: connect without a row factory
    seen.clear()
    postgres.connect(connect_factory=factory_for(object(), seen))
    assert "row_factory" not in seen[0][1] and seen[0][1]["connect_timeout"] == 5


def test_migration_files_are_ordered_and_a_duplicate_version_is_refused(tmp_path):
    (tmp_path / "0002_b.sql").write_text("select 2;", encoding="utf-8")
    (tmp_path / "0001_a.sql").write_text("select 1;", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not a migration", encoding="utf-8")
    assert [p.name for p in postgres.migration_files(tmp_path)] == ["0001_a.sql", "0002_b.sql"]
    (tmp_path / "0001_other.sql").write_text("select 3;", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        postgres.migration_files(tmp_path)


def test_a_recorded_migration_whose_file_changed_is_refused_and_the_connection_is_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://u@h/db")
    (tmp_path / "0001_a.sql").write_text("select 1;", encoding="utf-8")
    conn = FakeConn([("SELECT version, checksum_sha256", [{"version": "0001", "checksum_sha256": "0" * 64}])])
    with pytest.raises(RuntimeError, match="checksum mismatch: 0001_a.sql"):
        postgres.apply_migrations(connect_factory=factory_for(conn), directory=tmp_path)
    assert conn.closed is True


def test_an_unchanged_recorded_migration_is_reported_as_already_applied_and_a_new_one_as_applied(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://u@h/db")
    first = tmp_path / "0001_a.sql"
    first.write_text("select 1;", encoding="utf-8")
    (tmp_path / "0002_b.sql").write_text("select 2;", encoding="utf-8")
    conn = FakeConn([("SELECT version, checksum_sha256", [{"version": "0001", "checksum_sha256": hashlib.sha256(first.read_bytes()).hexdigest()}])])
    result = postgres.apply_migrations(connect_factory=factory_for(conn), directory=tmp_path)
    assert result.already_applied == ("0001_a.sql",) and result.applied == ("0002_b.sql",) and conn.closed is True


def test_the_ledger_reader_returns_nothing_when_there_is_no_ledger_and_the_rows_when_there_is(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://u@h/db")
    assert postgres.migration_status(connect_factory=factory_for(FakeConn([("SELECT to_regclass", [{"relation": None}])]))) == []
    rows = [{"version": "0001", "name": "0001_a.sql", "checksum_sha256": "abc", "applied_at": "2026-11-22 10:00:00+00"}]
    as_dict = FakeConn([("SELECT to_regclass", [{"relation": "acs_schema_migrations"}]), ("SELECT version,name", rows)])
    assert postgres.migration_status(connect_factory=factory_for(as_dict)) == rows and as_dict.closed is True
    as_tuple = FakeConn([("SELECT to_regclass", [("acs_schema_migrations",)]), ("SELECT version,name", rows)])
    assert postgres.migration_status(connect_factory=factory_for(as_tuple))[0]["name"] == "0001_a.sql"
    empty_tuple = FakeConn([("SELECT to_regclass", [(None,)])])
    assert postgres.migration_status(connect_factory=factory_for(empty_tuple)) == [] and empty_tuple.closed is True
