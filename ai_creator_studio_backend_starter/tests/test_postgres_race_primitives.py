"""B-05 (D-66c, step 1): the race protections of the SQLite-only modules, rebuilt on real PostgreSQL BEFORE any of those modules gets an adapter.

Each SQLite module protects a "check, then write" with ``BEGIN IMMEDIATE`` (export cap #184, market report cap #190), a partial unique index (review #171), triggers that raise
(append-only history) or ``INSERT OR IGNORE``. None of these work unchanged on PostgreSQL, where the default is READ COMMITTED and readers do not block. This file proves, with real
concurrent connections, (a) that the unprotected pattern really overshoots on PostgreSQL (a barrier makes the race deterministic) and (b) that the replacement construct holds:
  advisory lock / ``SELECT .. FOR UPDATE``  <- ``BEGIN IMMEDIATE``;   partial unique index  <- same;   ``ON CONFLICT DO NOTHING``  <- ``INSERT OR IGNORE``;
  ``ADD COLUMN IF NOT EXISTS`` + migration advisory lock  <- ``add_column`` (#196);   function trigger raising an exception  <- ``RAISE(ABORT, ..)``;   ``IDENTITY``  <- ``AUTOINCREMENT``.
The last test runs the REAL ``app.postgres.apply_migrations`` from 8 threads on a first run. Everything lives in a scratch schema that is dropped afterwards; nothing of the application's schema is touched.

Skipped unless ACS_TEST_DATABASE_URL points at a disposable database (never a shared, TEST Supabase or Production database). Opening PostgreSQL for the application stays forbidden:
these tests do not select the PostgreSQL backend.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

DSN = os.environ.get("ACS_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DSN, reason="ACS_TEST_DATABASE_URL not set")


def _dsn_with_schema(schema: str) -> str:
    return DSN + ("&" if "?" in DSN else "?") + f"options=-c%20search_path%3D{schema}"


@pytest.fixture
def schema():
    import psycopg
    name = "race_" + uuid.uuid4().hex[:10]
    with psycopg.connect(DSN, autocommit=True, connect_timeout=10) as admin:
        admin.execute(f"CREATE SCHEMA {name}")
    try:
        yield name
    finally:
        with psycopg.connect(DSN, autocommit=True, connect_timeout=10) as admin:
            admin.execute(f"DROP SCHEMA {name} CASCADE")


def connect(schema: str):
    import psycopg
    return psycopg.connect(_dsn_with_schema(schema), connect_timeout=10)


def setup(schema: str, *statements: str) -> None:
    with connect(schema) as conn:
        for statement in statements:
            conn.execute(statement)


def scalar(schema: str, sql: str, args=()):
    with connect(schema) as conn:
        return conn.execute(sql, args).fetchone()[0]


def run_all(count: int, work) -> list:
    """Run ``work(i)`` in ``count`` threads and return the results; an exception is returned as the result (so a test can count the losers)."""
    def guarded(i):
        try:
            return work(i)
        except Exception as exc:  # noqa: BLE001
            return exc
    with ThreadPoolExecutor(count) as pool:
        return list(pool.map(guarded, range(count)))


# ------------------------------------------------------------------------------------------ check-then-insert with a cap
CAP_TABLE = "CREATE TABLE exports (ws TEXT NOT NULL, n INTEGER NOT NULL)"


def test_without_a_lock_a_capped_insert_overshoots_on_postgresql(schema):
    """The WHY: under READ COMMITTED every transaction counts 0 before any of them commits, so all of them insert. (SQLite's BEGIN IMMEDIATE made this impossible.)"""
    setup(schema, CAP_TABLE)
    barrier, cap = threading.Barrier(6), 3

    def work(i):
        with connect(schema) as conn:
            seen = conn.execute("SELECT count(*) FROM exports WHERE ws='w'").fetchone()[0]
            barrier.wait(timeout=20)                       # everybody has counted before anybody writes
            if seen < cap:
                conn.execute("INSERT INTO exports VALUES ('w', %s)", (i,))
            conn.commit()
    assert not [r for r in run_all(6, work) if isinstance(r, Exception)]
    assert scalar(schema, "SELECT count(*) FROM exports") == 6 > cap, "the cap was exceeded: the race is real"


def test_an_advisory_lock_per_workspace_keeps_the_cap_exact(schema):
    """The REPLACEMENT for BEGIN IMMEDIATE on a per-workspace cap (export #184, market report #190): serialise the check+insert of one key, other keys stay parallel."""
    setup(schema, CAP_TABLE)
    cap = 3

    def work(i):
        with connect(schema) as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("ws:w",))
            seen = conn.execute("SELECT count(*) FROM exports WHERE ws='w'").fetchone()[0]
            time.sleep(0.05)                               # widen the window the lock has to protect
            allowed = seen < cap
            if allowed:
                conn.execute("INSERT INTO exports VALUES ('w', %s)", (i,))
            conn.commit()
            return allowed
    results = run_all(12, work)
    assert not [r for r in results if isinstance(r, Exception)]
    assert sum(1 for r in results if r is True) == cap and scalar(schema, "SELECT count(*) FROM exports") == cap


def test_the_advisory_lock_of_one_workspace_does_not_block_another(schema):
    setup(schema, CAP_TABLE)
    holder, release, started = None, threading.Event(), threading.Event()

    def hold():
        with connect(schema) as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("ws:a",))
            started.set()
            release.wait(timeout=20)
            conn.commit()
    thread = threading.Thread(target=hold)
    thread.start()
    assert started.wait(timeout=20)
    begun = time.monotonic()
    with connect(schema) as conn:                           # another workspace: must not wait for "ws:a"
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("ws:b",))
        conn.execute("INSERT INTO exports VALUES ('b', 1)")
        conn.commit()
    assert time.monotonic() - begun < 5
    release.set()
    thread.join(timeout=20)


# ------------------------------------------------------------------------------------------ read-modify-write
def test_a_plain_read_modify_write_loses_updates_and_for_update_does_not(schema):
    setup(schema, "CREATE TABLE counters (id INTEGER PRIMARY KEY, n INTEGER NOT NULL)", "INSERT INTO counters VALUES (1, 0)")
    barrier = threading.Barrier(6)

    def lossy(i):
        with connect(schema) as conn:
            n = conn.execute("SELECT n FROM counters WHERE id=1").fetchone()[0]
            barrier.wait(timeout=20)
            conn.execute("UPDATE counters SET n=%s WHERE id=1", (n + 1,))
            conn.commit()
    assert not [r for r in run_all(6, lossy) if isinstance(r, Exception)]
    assert scalar(schema, "SELECT n FROM counters WHERE id=1") == 1, "six increments, one survived: the WHY"
    setup(schema, "UPDATE counters SET n=0 WHERE id=1")

    def safe(i):
        with connect(schema) as conn:
            n = conn.execute("SELECT n FROM counters WHERE id=1 FOR UPDATE").fetchone()[0]
            time.sleep(0.02)
            conn.execute("UPDATE counters SET n=%s WHERE id=1", (n + 1,))
            conn.commit()
    assert not [r for r in run_all(12, safe) if isinstance(r, Exception)]
    assert scalar(schema, "SELECT n FROM counters WHERE id=1") == 12, "SELECT .. FOR UPDATE is the replacement for BEGIN IMMEDIATE on one row"


# ------------------------------------------------------------------------------------------ partial unique index (review #171)
def test_a_partial_unique_index_lets_exactly_one_open_review_exist(schema):
    setup(schema, "CREATE TABLE reviews (id SERIAL PRIMARY KEY, item TEXT NOT NULL, status TEXT NOT NULL)",
          "CREATE UNIQUE INDEX one_open_review ON reviews(item) WHERE status IN ('requested', 'in_review')")
    barrier = threading.Barrier(10)

    def work(i):
        with connect(schema) as conn:
            barrier.wait(timeout=20)
            conn.execute("INSERT INTO reviews(item, status) VALUES ('x', 'requested')")
            conn.commit()
    import psycopg
    results = run_all(10, work)
    assert sum(1 for r in results if r is None) == 1 and all(isinstance(r, psycopg.errors.UniqueViolation) for r in results if r is not None)
    setup(schema, "UPDATE reviews SET status='approved' WHERE item='x'", "INSERT INTO reviews(item, status) VALUES ('x', 'requested')")
    assert scalar(schema, "SELECT count(*) FROM reviews WHERE item='x'") == 2, "once the first is decided a new request is allowed"


# ------------------------------------------------------------------------------------------ INSERT OR IGNORE
def test_on_conflict_do_nothing_is_idempotent_under_concurrency(schema):
    setup(schema, "CREATE TABLE kv (k TEXT PRIMARY KEY, v INTEGER NOT NULL)")
    barrier = threading.Barrier(10)

    def work(i):
        with connect(schema) as conn:
            barrier.wait(timeout=20)
            inserted = conn.execute("INSERT INTO kv VALUES ('same', %s) ON CONFLICT (k) DO NOTHING", (i,)).rowcount
            conn.commit()
            return inserted
    results = run_all(10, work)
    assert not [r for r in results if isinstance(r, Exception)] and sum(results) == 1 and scalar(schema, "SELECT count(*) FROM kv") == 1


# ------------------------------------------------------------------------------------------ AUTOINCREMENT
def test_identity_columns_give_unique_increasing_ids_under_concurrency(schema):
    setup(schema, "CREATE TABLE events (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, note TEXT NOT NULL)")

    def work(i):
        with connect(schema) as conn:
            row = conn.execute("INSERT INTO events(note) VALUES (%s) RETURNING id", (f"n{i}",)).fetchone()
            conn.commit()
            return row[0]
    ids = run_all(20, work)
    assert not [r for r in ids if isinstance(r, Exception)] and len(set(ids)) == 20


# ------------------------------------------------------------------------------------------ append-only history (RAISE(ABORT))
def test_a_function_trigger_makes_a_history_table_append_only(schema):
    setup(schema, "CREATE TABLE member_events (id SERIAL PRIMARY KEY, event TEXT NOT NULL)",
          """CREATE FUNCTION no_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'member_events is append-only'; END $$""",
          "CREATE TRIGGER member_events_no_update BEFORE UPDATE ON member_events FOR EACH ROW EXECUTE FUNCTION no_change()",
          "CREATE TRIGGER member_events_no_delete BEFORE DELETE ON member_events FOR EACH ROW EXECUTE FUNCTION no_change()",
          "INSERT INTO member_events(event) VALUES ('added')")
    import psycopg
    for statement in ("UPDATE member_events SET event='x'", "DELETE FROM member_events"):
        with connect(schema) as conn:
            with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                conn.execute(statement)
    assert scalar(schema, "SELECT count(*) FROM member_events") == 1 and scalar(schema, "SELECT event FROM member_events") == "added"


# ------------------------------------------------------------------------------------------ schema creation races (#196)
def test_add_column_if_not_exists_is_safe_when_many_start_at_once(schema):
    """PostgreSQL's own construct replaces ``app/schema_util.add_column`` (which reads the SQLite error text)."""
    setup(schema, "CREATE TABLE things (id INTEGER PRIMARY KEY)")
    barrier = threading.Barrier(8)

    def work(i):
        with connect(schema) as conn:
            barrier.wait(timeout=20)
            conn.execute("ALTER TABLE things ADD COLUMN IF NOT EXISTS extra TEXT")
            conn.commit()
    assert not [r for r in run_all(8, work) if isinstance(r, Exception)]
    assert scalar(schema, "SELECT count(*) FROM information_schema.columns WHERE table_schema=%s AND table_name='things' AND column_name='extra'", (schema,)) == 1


def test_the_real_apply_migrations_survives_eight_first_runs_at_once(schema, tmp_path, monkeypatch):
    """The REAL code (``app.postgres.apply_migrations``, one advisory lock for the whole migration transaction) on a true first-run race: each migration is applied by exactly one caller."""
    from app import config, postgres
    (tmp_path / "0001_first.sql").write_text("CREATE TABLE first_t (id INTEGER PRIMARY KEY);", encoding="utf-8")
    (tmp_path / "0002_second.sql").write_text("CREATE TABLE second_t (id INTEGER PRIMARY KEY, first_id INTEGER REFERENCES first_t(id));", encoding="utf-8")
    (tmp_path / "0003_third.sql").write_text("CREATE INDEX second_by_first ON second_t(first_id);", encoding="utf-8")
    monkeypatch.setattr(config, "DATABASE_URL", _dsn_with_schema(schema))      # the migration table and the new tables are created in the scratch schema
    barrier = threading.Barrier(8)

    def work(i):
        barrier.wait(timeout=20)
        return postgres.apply_migrations(directory=tmp_path)
    results = run_all(8, work)
    assert not [r for r in results if isinstance(r, Exception)], results
    assert sorted(name for r in results for name in r.applied) == ["0001_first.sql", "0002_second.sql", "0003_third.sql"], "every migration applied exactly once"
    assert scalar(schema, "SELECT count(*) FROM acs_schema_migrations") == 3
    again = postgres.apply_migrations(directory=tmp_path)
    assert again.applied == () and len(again.already_applied) == 3
