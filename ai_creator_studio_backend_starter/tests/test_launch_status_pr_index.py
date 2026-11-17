"""B-01 follow-up: the PR index block in LAUNCH_STATUS.md."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import launch_status_pr_index as idx  # noqa: E402

PRS = [{"number": 7, "title": "old | pipe", "mergedAt": "2026-11-09T01:02:03Z", "mergeCommit": {"oid": "abcdef1234567"}},
       {"number": 142, "title": "새   제목\n두 줄", "mergedAt": "2026-11-17T09:10:11Z", "mergeCommit": {"oid": "1234567890abc"}},
       {"number": 99, "title": "no commit", "mergedAt": None, "mergeCommit": None}]
DOC = "# LAUNCH STATUS\n\n## 변경 로그 (최신이 위, PR이 머지될 때마다 추가)\n\n### 2026-11-10 · PR #43 — 손으로 쓴 항목\n- 내용\n"


def test_render_is_newest_first_escapes_pipes_and_survives_missing_fields():
    table = idx.render(PRS).splitlines()
    assert [row.split("|")[1].strip() for row in table[2:]] == ["#142", "#99", "#7"]
    assert "새 제목 두 줄" in table[2] and "abcdef1" in table[4] and "old \\| pipe" in table[4]
    assert table[3].split("|")[3].strip() == "-", "no merge commit -> a dash, not a crash"


def test_apply_inserts_once_keeps_the_hand_written_entries_and_is_idempotent():
    once = idx.apply(DOC, PRS)
    assert once.count(idx.START) == 1 and once.count(idx.END) == 1 and "### 2026-11-10 · PR #43 — 손으로 쓴 항목" in once and "3건)" in once
    assert idx.apply(once, PRS) == once
    more = idx.apply(once, PRS + [{"number": 200, "title": "newer", "mergedAt": "2026-11-18T00:00:00Z", "mergeCommit": {"oid": "fffffff111"}}])
    assert more.count("| #200 |") == 1 and more.count(idx.START) == 1 and "4건)" in more and "| #142 |" in more


def test_the_index_never_claims_ci_results():
    assert "CI 수치는 여기에 없다" in idx.block(PRS) and "passed" not in idx.block(PRS)


def test_main_writes_the_document_only_with_apply(tmp_path, capsys):
    doc, data = tmp_path / "LAUNCH_STATUS.md", tmp_path / "prs.json"
    doc.write_text(DOC, encoding="utf-8")
    data.write_text(json.dumps(PRS), encoding="utf-8")
    assert idx.main([str(data), "--doc", str(doc)]) == 0 and doc.read_text(encoding="utf-8") == DOC
    assert idx.main([str(data), "--doc", str(doc), "--apply"]) == 0 and idx.START in doc.read_text(encoding="utf-8")


def test_a_document_without_the_anchor_heading_is_refused():
    try:
        idx.apply("# nothing here\n", PRS)
    except SystemExit as exc:
        assert "anchor" in str(exc)
    else:
        raise AssertionError("should refuse")
