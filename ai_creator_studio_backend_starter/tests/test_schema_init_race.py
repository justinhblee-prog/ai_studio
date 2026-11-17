"""B-11: first use of a fresh database by many requests at once. The schema code checks "is the column there?" and then adds it; two callers could both add it and the second
used to fail with "duplicate column name" (a 500 on the very first requests). add_column swallows exactly that error and nothing else."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.schema_sqlite import initialize_schema
from app.schema_util import add_column


def test_add_column_ignores_a_column_that_is_already_there_and_nothing_else():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE t (a TEXT)")
    add_column(db, "ALTER TABLE t ADD COLUMN b TEXT")
    add_column(db, "ALTER TABLE t ADD COLUMN b TEXT")      # the second one is the lost race: no error
    assert [r[1] for r in db.execute("PRAGMA table_info(t)")] == ["a", "b"]
    with pytest.raises(sqlite3.OperationalError):
        add_column(db, "ALTER TABLE missing_table ADD COLUMN c TEXT")
    with pytest.raises(sqlite3.OperationalError):
        add_column(db, "ALTER TABLE t ADD COLUMN ;")


def test_many_connections_initialising_a_fresh_database_at_once_all_succeed(tmp_path):
    path = tmp_path / "fresh.sqlite3"

    def init(_):
        con = sqlite3.connect(path, timeout=30)
        try:
            initialize_schema(con)
            con.commit()
        finally:
            con.close()
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(init, range(8)))          # any exception in a worker is raised here
    con = sqlite3.connect(path)
    columns = {r[1] for r in con.execute("PRAGMA table_info(generation_ops_alert_deliveries)")}
    con.close()
    assert {"claimed_by", "lease_expires_at"} <= columns
