"""B-01 follow-up: keep a PR index in docs/LAUNCH_STATUS.md complete.
   gh pr list --state merged --limit 500 --json number,title,mergedAt,mergeCommit > prs.json
   python scripts/launch_status_pr_index.py prs.json [--apply]      (prints the table; --apply rewrites the block between the markers in LAUNCH_STATUS.md)
The index lists WHAT merged and WHEN. It does not copy CI numbers (those stay in each PR's checks and in the hand-written entries below it): it never claims a PR passed anything."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

START, END = "<!-- PR_INDEX_START -->", "<!-- PR_INDEX_END -->"
DOC = Path(__file__).resolve().parents[2] / "docs" / "LAUNCH_STATUS.md"


def render(prs: list[dict]) -> str:
    rows = sorted(prs, key=lambda p: -int(p["number"]))
    lines = ["| PR | 머지 시각(UTC) | 머지 커밋 | 제목 |", "|---:|---|---|---|"]
    for p in rows:
        sha = ((p.get("mergeCommit") or {}).get("oid") or "")[:7] or "-"
        title = re.sub(r"\s+", " ", str(p["title"])).replace("|", "\\|").strip()
        lines.append(f"| #{int(p['number'])} | {str(p.get('mergedAt') or '')[:16].replace('T', ' ')} | {sha} | {title} |")
    return "\n".join(lines)


def block(prs: list[dict]) -> str:
    return (f"{START}\n### 머지된 PR 색인 (스크립트 생성, {len(prs)}건)\n> 무엇이 언제 머지됐는지만 적는다. **CI 수치는 여기에 없다** — 각 PR의 체크 기록과 아래 손으로 쓴 항목을 본다. "
            f"재생성: `scripts/launch_status_pr_index.py`.\n\n{render(prs)}\n{END}")


def apply(text: str, prs: list[dict]) -> str:
    if START in text and END in text:
        head, rest = text.split(START, 1)
        _, tail = rest.split(END, 1)
        return head + block(prs) + tail
    anchor = "## 변경 로그 (최신이 위, PR이 머지될 때마다 추가)"
    if anchor not in text:
        raise SystemExit("anchor heading not found in LAUNCH_STATUS.md")
    return text.replace(anchor, anchor + "\n\n" + block(prs), 1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--doc", default=str(DOC))
    args = parser.parse_args(argv)
    prs = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    if args.apply:
        doc = Path(args.doc)
        doc.write_text(apply(doc.read_text(encoding="utf-8"), prs), encoding="utf-8")
    else:
        sys.stdout.buffer.write((render(prs) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
