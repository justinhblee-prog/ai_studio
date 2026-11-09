#!/usr/bin/env python3
"""Report PostgreSQL test-environment capabilities; never connects to a DB."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.postgres_readiness import probe_postgres_runtime


if __name__ == "__main__":
    result = probe_postgres_runtime()
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    raise SystemExit(0 if result.ready_for_local_integration_test else 2)
