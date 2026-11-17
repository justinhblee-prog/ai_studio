"""Small helpers for the SQLite schema code that every module carries.

B-08/B-11: ``ALTER TABLE .. ADD COLUMN`` after a "does the column exist?" check is not atomic: when the first requests on a fresh database arrive together
(or two server processes start together), both see the column missing and the second ALTER fails with "duplicate column name", which used to surface as a 500.
``add_column`` treats exactly that error as "someone else just did it" and re-raises everything else.
"""
from __future__ import annotations

import sqlite3
from typing import Any


def add_column(db: Any, ddl: str) -> None:
    try:
        db.execute(ddl)
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise
