"""B-01: the launch checklist is consistent with LAUNCH_STATUS and the repository (and the checker really catches the ways it can drift)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_launch_evidence as chk  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def make_repo(tmp_path, checklist, status="PR #7 PR #8"):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "LAUNCH_CHECKLIST.md").write_text(checklist, encoding="utf-8")
    (tmp_path / "docs" / "LAUNCH_STATUS.md").write_text(status, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_real.py").write_text("x = 1", encoding="utf-8")
    return tmp_path


def table(rows, counts):
    head = "## 요약\n| 상태 | 개수 |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in counts.items()) + "\n## A. x\n| # | 항목 | 상태 | 증거 | 공백 |\n|---|---|---|---|---|\n"
    return head + "".join(f"| {n} | item {n} | {st} | {ev} | gap |\n" for n, st, ev in rows)


def test_the_real_checklist_matches_the_repository():
    result = chk.check(REPO)
    assert result["errors"] == [], result["errors"]
    assert result["rows"] == sum(result["counts"].values()) >= 43


def test_a_consistent_small_repo_passes(tmp_path):
    root = make_repo(tmp_path, table([(1, "완료", "`tests/test_real.py`, PR #7"), (2, "미완료", "—")], {"완료": 1, "부분": 0, "미완료": 1, "차단": 0}))
    assert chk.check(root)["errors"] == []


def test_each_kind_of_drift_is_caught(tmp_path):
    counts = {"완료": 1, "부분": 0, "미완료": 0, "차단": 0}
    cases = {
        "summary does not equal rows": table([(1, "완료", "tests/test_real.py"), (2, "부분", "tests/test_real.py")], counts),
        "unknown status": table([(1, "끝남", "tests/test_real.py")], {"완료": 0, "부분": 0, "미완료": 0, "차단": 0}),
        "completed with no evidence": table([(1, "완료", "—")], counts),
        "file that is not in the repository": table([(1, "완료", "`tests/test_missing.py`")], counts),
        "PR that LAUNCH_STATUS never mentions": table([(1, "완료", "tests/test_real.py PR #999")], counts),
    }
    for index, (expected, text) in enumerate(cases.items()):
        sub = tmp_path / f"r{index}"
        sub.mkdir()
        errors = chk.check(make_repo(sub, text))["errors"]
        assert errors, expected
    # and the messages name the problem
    sub = tmp_path / "msg"
    sub.mkdir()
    errors = chk.check(make_repo(sub, cases["PR that LAUNCH_STATUS never mentions"]))["errors"]
    assert "PR #999" in errors[0]
    sub = tmp_path / "msg2"
    sub.mkdir()
    errors = chk.check(make_repo(sub, cases["file that is not in the repository"]))["errors"]
    assert "test_missing.py" in errors[0]


def test_main_exit_codes(tmp_path, capsys):
    ok = tmp_path / "ok"
    ok.mkdir()
    make_repo(ok, table([(1, "완료", "tests/test_real.py")], {"완료": 1, "부분": 0, "미완료": 0, "차단": 0}))
    assert chk.main(["--root", str(ok)]) == 0
    bad = tmp_path / "bad"
    bad.mkdir()
    make_repo(bad, table([(1, "완료", "—")], {"완료": 1, "부분": 0, "미완료": 0, "차단": 0}))
    assert chk.main(["--root", str(bad), "--json"]) == 1
