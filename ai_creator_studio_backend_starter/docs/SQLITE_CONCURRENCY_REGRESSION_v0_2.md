
## v0.76 addition

Added a 12-worker concurrent job creation race using the same workspace-scoped idempotency key. The assertion requires one canonical Job ID, exactly one `created=True` result, one Job row, and one idempotency row. This is SQLite single-host evidence only and does not establish PostgreSQL/multi-host behavior.
