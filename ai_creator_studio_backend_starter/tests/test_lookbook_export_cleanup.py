import os
import sqlite3
from pathlib import Path

import pytest

from scripts import cleanup_expired_lookbook_exports as cleanup


def row(key):
    return {"export_id": "exp_test", "storage_key": key}


def test_cleanup_dry_run_and_apply_preserve_audit_file(tmp_path):
    package = tmp_path / "exports"
    package.mkdir()
    archive = package / "expired.zip"
    archive.write_bytes(b"zip")
    dry = cleanup.cleanup_candidates([row(archive.name)], package, apply=False)
    assert dry["would_remove"] == 1 and dry["removed"] == 0
    assert archive.exists()
    applied = cleanup.cleanup_candidates([row(archive.name)], package, apply=True)
    assert applied["removed"] == 1 and not archive.exists()


def test_cleanup_rejects_traversal_and_symlink_without_touching_target(tmp_path):
    package = tmp_path / "exports"
    package.mkdir()
    outside = tmp_path / "outside.zip"
    outside.write_bytes(b"keep")
    (package / "link.zip").symlink_to(outside)
    result = cleanup.cleanup_candidates(
        [row("../outside.zip"), row("..\\outside.zip"), row("link.zip")], package, apply=True
    )
    assert result["invalid_paths"] == 2
    assert result["non_regular"] == 1
    assert outside.read_bytes() == b"keep"
    assert (package / "link.zip").is_symlink()


def test_cleanup_continues_after_one_unlink_failure(tmp_path, monkeypatch):
    package = tmp_path / "exports"
    package.mkdir()
    blocked = package / "blocked.zip"
    good = package / "good.zip"
    blocked.write_bytes(b"blocked")
    good.write_bytes(b"good")
    real_unlink = cleanup.os.unlink

    def injected_unlink(path, *, dir_fd=None):
        if path == "blocked.zip":
            raise PermissionError("injected deletion failure")
        return real_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(cleanup.os, "unlink", injected_unlink)
    result = cleanup.cleanup_candidates([row("blocked.zip"), row("good.zip")], package, apply=True)
    assert result["failed"] == 1
    assert result["removed"] == 1
    assert blocked.exists()
    assert not good.exists()


def test_cleanup_handles_missing_file_and_non_regular_directory(tmp_path):
    package = tmp_path / "exports"
    package.mkdir()
    (package / "nested").mkdir()
    result = cleanup.cleanup_candidates(
        [row("missing.zip"), row("nested")], package, apply=True
    )
    assert result["missing"] == 1
    assert result["non_regular"] == 1
    assert (package / "nested").is_dir()


def test_audit_table_remains_immutable_after_cleanup(tmp_path):
    db = sqlite3.connect(tmp_path / "audit.sqlite")
    db.execute("CREATE TABLE exports (export_id TEXT PRIMARY KEY, storage_key TEXT NOT NULL)")
    db.execute("INSERT INTO exports VALUES ('exp_test','expired.zip')")
    db.execute("CREATE TRIGGER no_delete BEFORE DELETE ON exports BEGIN SELECT RAISE(ABORT,'append only'); END")
    db.commit()
    package = tmp_path / "exports"
    package.mkdir()
    (package / "expired.zip").write_bytes(b"zip")
    cleanup.cleanup_candidates([row("expired.zip")], package, apply=True)
    assert db.execute("SELECT COUNT(*) FROM exports").fetchone()[0] == 1
    db.close()


def test_cleanup_main_emits_machine_readable_dry_run_observability(tmp_path, monkeypatch, capsys):
    class FakeCursor:
        def fetchall(self):
            return [row("expired.zip")]

    class FakeDB:
        def execute(self, *_args):
            return FakeCursor()
        def close(self):
            pass

    package = tmp_path / "exports"
    package.mkdir()
    (package / "expired.zip").write_bytes(b"zip")
    monkeypatch.setattr(cleanup, "initialize", lambda: None)
    monkeypatch.setattr(cleanup, "_lookbook_package_dir", lambda: package)
    monkeypatch.setattr(cleanup, "_connect", lambda: FakeDB())
    monkeypatch.setattr("sys.argv", ["cleanup_expired_lookbook_exports.py", "--limit", "7"])
    assert cleanup.main() == 0
    import json
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "dry_run"
    assert result["limit"] == 7 and result["candidate_count"] == 1
    assert result["would_remove"] == 1 and result["removed"] == 0
    assert result["partial_failure"] is False
    assert result["audit_rows_retained"] is True
    assert isinstance(result["duration_ms"], (int, float))
    assert isinstance(result["completed_at"], int)
    assert (package / "expired.zip").exists()


def test_cleanup_main_reports_partial_failure_and_nonzero_exit(tmp_path, monkeypatch, capsys):
    class FakeCursor:
        def fetchall(self):
            return [row("blocked.zip")]

    class FakeDB:
        def execute(self, *_args):
            return FakeCursor()
        def close(self):
            pass

    package = tmp_path / "exports"
    package.mkdir()
    monkeypatch.setattr(cleanup, "initialize", lambda: None)
    monkeypatch.setattr(cleanup, "_lookbook_package_dir", lambda: package)
    monkeypatch.setattr(cleanup, "_connect", lambda: FakeDB())
    monkeypatch.setattr(cleanup, "cleanup_candidates", lambda *_args, **_kwargs: {
        "inspected": 1, "would_remove": 0, "removed": 0, "missing": 0,
        "invalid_paths": 0, "non_regular": 0, "failed": 1,
    })
    monkeypatch.setattr("sys.argv", ["cleanup_expired_lookbook_exports.py", "--apply"])
    assert cleanup.main() == 2
    import json
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "apply"
    assert result["partial_failure"] is True
    assert result["failed"] == 1 and result["audit_rows_retained"] is True
