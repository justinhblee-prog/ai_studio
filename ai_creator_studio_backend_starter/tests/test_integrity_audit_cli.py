"""B-22: the file / command-line side of the read-only integrity audit (audit_database, main): it opens a copy read-only, refuses a missing file, writes the report when asked,
and cannot change the database even if a query tried to."""
import json
import sqlite3
import sys

import pytest

from app import integrity_audit
from tests.test_integrity_audit import _db


def _file(tmp_path):
    path = tmp_path / "meta.sqlite3"
    src = _db()
    dst = sqlite3.connect(path)
    src.backup(dst)
    dst.close()
    return path


def test_audit_database_reads_a_file_and_reports_the_same_findings_as_the_connection(tmp_path):
    path = _file(tmp_path)
    report = integrity_audit.audit_database(path)
    assert report["mode"] == "read-only" and report["finding_count"] == len(report["findings"]) > 0
    assert report["counts_by_code"] == integrity_audit.audit_connection(_db())["counts_by_code"]


def test_a_missing_database_file_is_an_error_not_an_empty_report(tmp_path):
    with pytest.raises(FileNotFoundError):
        integrity_audit.audit_database(tmp_path / "nope.sqlite3")


def test_the_audit_leaves_the_database_file_unchanged(tmp_path):
    path = _file(tmp_path)
    before = path.read_bytes()
    integrity_audit.audit_database(path)
    assert path.read_bytes() == before


def test_the_command_line_prints_the_report_and_writes_it_when_asked(tmp_path, monkeypatch, capsys):
    path = _file(tmp_path)
    out = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["integrity_audit", str(path), "--output", str(out)])
    integrity_audit.main()
    printed = json.loads(capsys.readouterr().out)
    assert printed["audit"] == "workspace-reference-integrity"
    assert json.loads(out.read_text(encoding="utf-8")) == printed
    monkeypatch.setattr(sys, "argv", ["integrity_audit", str(path)])
    integrity_audit.main()
    assert json.loads(capsys.readouterr().out)["finding_count"] == printed["finding_count"]
