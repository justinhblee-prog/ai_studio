"""Fail-closed evidence gate for app/repository_registry.py (needs no database).

A status may only be raised together with live tests that justify it. This module checks the
registry against tests/test_postgres_live_repositories.py mechanically.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from app import repository_registry as reg

ROOT = Path(__file__).resolve().parents[1]
LIVE = (ROOT / "tests" / "test_postgres_live_repositories.py").read_text(encoding="utf-8")
LIVE_TESTS = {n.name for n in ast.parse(LIVE).body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}

# Public repository methods that no live test references directly. They are reached only through the
# route ports (SQLite<->PostgreSQL parity tests), so they are NOT directly verified. This list must match
# reality exactly: a new gap fails the test, and so does an entry that has since been covered.
KNOWN_INDIRECT = {
    "project_products": {"project_workspace"},
    "photos": {"get_run", "check_access", "output_review", "decide_output_review", "create_export_manifest", "record_output_export"},
    "lookbooks": {"check_access", "prepare_package", "get_package_export"},
}


def _public_methods(entry):
    tree = ast.parse((ROOT / (entry.module.replace(".", "/") + ".py")).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == entry.cls)
    return {f.name for f in cls.body if isinstance(f, ast.FunctionDef) and not f.name.startswith("_") and f.name != "initialize"}


def _live_entries():
    return [a for a in reg.AGGREGATES if a.status == reg.LIVE_VERIFIED]


def test_every_live_verified_aggregate_names_existing_live_tests():
    for entry in _live_entries():
        assert entry.module and entry.cls, entry.name
        assert entry.evidence, f"{entry.name} is live_verified without evidence tests"
        unknown = [name for name in entry.evidence if name not in LIVE_TESTS]
        assert not unknown, f"{entry.name}: evidence tests do not exist: {unknown}"


def test_evidence_is_only_claimed_for_live_verified_aggregates():
    for entry in reg.AGGREGATES:
        if entry.status != reg.LIVE_VERIFIED:
            assert not entry.evidence, f"{entry.name} is {entry.status} but lists evidence; raise the status or drop the evidence"


def test_live_verified_aggregates_have_every_public_method_referenced_by_live_tests():
    unexpected, stale = {}, {}
    for entry in _live_entries():
        missing = {m for m in _public_methods(entry) if not re.search(r"\." + re.escape(m) + r"\b", LIVE)}
        allowed = KNOWN_INDIRECT.get(entry.name, set())
        if missing - allowed:
            unexpected[entry.name] = sorted(missing - allowed)
        if allowed - missing:
            stale[entry.name] = sorted(allowed - missing)
    assert not unexpected, f"public methods without any live test reference: {unexpected}"
    assert not stale, f"KNOWN_INDIRECT entries that are now covered (remove them): {stale}"


def test_missing_and_partial_aggregates_stay_in_the_gate():
    status = reg.coverage()
    assert status["output_asset_link"] == reg.MISSING, "output_asset_link has no PostgreSQL implementation"
    assert status["credits_ledger"] == reg.MISSING and status["file_storage_lifecycle"] == reg.MISSING
    assert status["workspace_and_asset_metadata"] == reg.PARTIAL
    assert {"output_asset_link", "credits_ledger", "file_storage_lifecycle", "workspace_and_asset_metadata"} <= set(reg.pending_aggregates())


def test_output_asset_link_really_has_no_postgresql_implementation():
    import pytest

    from app.repositories.output_asset_link import build_output_asset_link_repository
    with pytest.raises(RuntimeError, match="not implemented"):
        build_output_asset_link_repository("postgresql")
