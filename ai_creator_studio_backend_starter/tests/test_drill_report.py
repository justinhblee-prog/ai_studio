"""B-02: the drill report summary and the alert text: what counts as a failure, what the alert says, and that a missing or broken report is a failure (never a silent pass)."""
import json

import pytest

from scripts import drill_report


def report(ok=True, rto=2.2, failed=None, rows=72):
    checks = {"integrity_check": {"ok": True}, "row_counts": {"ok": True}, "asset_files": {"ok": True}}
    for name in failed or []:
        checks[name] = {"ok": False}
    return {"ok": ok and not failed, "checks": checks, "sizes": {"rows": rows, "file_count": 18}, "seconds": {"backup": 0.06, "restore": 0.04}, "rto_seconds": rto}


def write(tmp_path, name, data):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
    return path


def test_two_passing_drills_make_a_pass_table_and_exit_zero(tmp_path, capsys):
    paths = [write(tmp_path, "small", report()), write(tmp_path, "scale", report(rto=2.24, rows=80044))]
    table, ok, problems = drill_report.summarize(paths)
    assert ok and problems == {"small": [], "scale": []} and table.count("PASS") == 2 and "80044" in table and "FAIL" not in table
    assert drill_report.main([str(p) for p in paths]) == 0 and "| small | PASS |" in capsys.readouterr().out


def test_a_failed_check_is_a_failure_and_the_alert_names_it(tmp_path, capsys):
    paths = [write(tmp_path, "small", report()), write(tmp_path, "scale", report(failed=["row_counts"]))]
    table, ok, problems = drill_report.summarize(paths)
    assert not ok and problems["scale"] == ["failed checks: row_counts"] and "| scale | FAIL |" in table
    assert drill_report.main([str(p) for p in paths]) == 1
    body = drill_report.issue_body(table, "https://example.invalid/run/1")
    assert "failed" in body and "row_counts" in body and "docs/RESTORE_DRILL.md" in body and "https://example.invalid/run/1" in body and "may not be restorable" in body


def test_the_rto_budget_is_a_failure_only_when_given_and_exceeded(tmp_path):
    slow = write(tmp_path, "scale", report(rto=45.0))
    assert drill_report.summarize([slow])[1] is True, "no budget given: only the checks count"
    table, ok, problems = drill_report.summarize([slow], max_rto=30)
    assert not ok and "over the budget of 30 s" in problems["scale"][0] and "RTO budget" in table
    assert drill_report.summarize([write(tmp_path, "fast", report(rto=2.2))], max_rto=30)[1] is True


@pytest.mark.parametrize("content", ["not json at all", "[1, 2]", "", '"a string"'])
def test_a_broken_report_is_a_failure_not_a_pass(tmp_path, content):
    table, ok, problems = drill_report.summarize([write(tmp_path, "small", content)])
    assert not ok and "could not be read" in problems["small"][0] and "FAIL" in table


def test_a_missing_report_is_a_failure(tmp_path):
    _, ok, problems = drill_report.summarize([tmp_path / "nothing.json"])
    assert not ok and "could not be read" in problems["nothing"][0]
    assert drill_report.main([str(tmp_path / "nothing.json")]) == 1


def test_ok_false_without_a_named_check_is_still_a_failure(tmp_path):
    _, ok, problems = drill_report.summarize([write(tmp_path, "small", {"ok": False, "checks": {}})])
    assert not ok and problems["small"] == ["the drill reported ok=false"]


def test_issue_body_mode_prints_the_alert_text(tmp_path, capsys):
    path = write(tmp_path, "small", report(failed=["asset_files"]))
    assert drill_report.main([str(path), "--issue-body", "--run-url", "https://example.invalid/r"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("The scheduled backup / restore drill failed.") and "asset_files" in out and "https://example.invalid/r" in out


def test_the_real_drill_output_shape_is_understood(tmp_path):
    real = {"ok": True, "checks": {"integrity_check": {"ok": True}, "foreign_keys": {"ok": True, "violations": 0}, "row_counts": {"ok": True, "tables": 36, "rows": 72, "differences": {}},
                                    "asset_files": {"ok": True, "checked": 6}, "application_smoke": {"ok": True}},
            "sizes": {"database_bytes": 466944, "file_bytes": 1768, "file_count": 18, "rows": 72}, "seconds": {"backup": 0.06, "verify": 0.01, "restore": 0.04, "checks": 0.01, "smoke": 0.1}, "rto_seconds": 0.16}
    table, ok, _ = drill_report.summarize([write(tmp_path, "small", real)], max_rto=30)
    assert ok and "| small | PASS | 72 | 18 | 0.06 | 0.04 | 0.16 | - |" in table
