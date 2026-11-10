"""Multi-statement writes on the asset database must be all-or-nothing.

The connection runs in autocommit mode (isolation_level=None), so a block with several INSERTs is atomic only if it starts with an
explicit BEGIN. These tests inject a failure on the last INSERT and check nothing is left behind and a retry works.
"""
import sqlite3

import pytest

from test_output_asset_link_worker import linked_output_env  # noqa: F401  (reuse the generation-output fixture)
from app.output_asset_link_worker import build_output_asset_link_repository, import_output_asset


def _raw(path):
    return sqlite3.connect(path, isolation_level=None)


@pytest.fixture
def plain_env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "atomic.sqlite3")
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    from app.assets.store import initialize
    initialize()
    return tmp_path / "atomic.sqlite3"


def test_create_workspace_leaves_no_ownerless_workspace_when_the_member_insert_fails(plain_env):
    from app.assets.store import create_workspace
    db = _raw(plain_env)
    db.execute("CREATE TRIGGER inject_member_failure BEFORE INSERT ON workspace_members BEGIN SELECT RAISE(ABORT, 'injected'); END")
    with pytest.raises(sqlite3.DatabaseError):
        create_workspace("ws-atomic", "user-a")
    assert db.execute("SELECT COUNT(*) FROM workspaces WHERE workspace_id='ws-atomic'").fetchone()[0] == 0
    db.execute("DROP TRIGGER inject_member_failure")
    assert create_workspace("ws-atomic", "user-a")["role"] == "owner"          # the same id can still be created
    assert db.execute("SELECT COUNT(*) FROM workspace_members WHERE workspace_id='ws-atomic'").fetchone()[0] == 1
    db.close()


def test_a_failed_generated_output_import_leaves_nothing_and_the_retry_succeeds(linked_output_env):
    from app.assets.store import _connect
    repository = build_output_asset_link_repository()
    claimed = repository.claim_one("atomicity-test", lease_seconds=60)
    assert claimed is not None
    with _connect() as db:
        db.execute("CREATE TRIGGER inject_provenance_failure BEFORE INSERT ON asset_provenance "
                   "WHEN NEW.event_type='asset.generated_output_imported' BEGIN SELECT RAISE(ABORT, 'injected'); END")
    with pytest.raises(sqlite3.DatabaseError):
        import_output_asset(claimed)
    with _connect() as db:
        assert db.execute("SELECT COUNT(*) FROM assets WHERE asset_id LIKE 'ast_out_%'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM asset_versions WHERE version_id LIKE 'av_out_%'").fetchone()[0] == 0
        db.execute("DROP TRIGGER inject_provenance_failure")
    imported = import_output_asset(claimed)                                      # without the fix this raised "failed integrity verification"
    assert imported["asset_id"].startswith("ast_out_")
