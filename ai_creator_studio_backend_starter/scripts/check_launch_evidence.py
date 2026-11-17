"""B-01: LAUNCH_CHECKLIST.md <-> LAUNCH_STATUS.md <-> repository evidence check.
   python scripts/check_launch_evidence.py [--root <repo>] [--json]
Fails (exit 1) when: the summary counts do not equal the table rows; a row has an unknown status; a 'completed' row has no evidence; a file named in the evidence
column does not exist in the repository; a PR number named in the evidence column never appears in LAUNCH_STATUS.md. It proves the DOCUMENT is consistent with the repo,
not that the product works: it never runs a test and never marks anything completed."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

DONE, PART, TODO, BLOCK = "완료", "부분", "미완료", "차단"
STATUSES = (DONE, PART, TODO, BLOCK)
FILE_RE = re.compile(r"`?([\w./-]+\.(?:py|mjs|md|json|yml|yaml|sh))`?")
GENERATED = {"manifest.json"}      # produced inside export ZIPs, not a repository file
PR_RE = re.compile(r"PR\s*#(\d+)|#(\d+)\b")


def parse_rows(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and cells[0].isdigit():
            rows.append({"n": int(cells[0]), "item": cells[1], "status": cells[2], "evidence": cells[3], "gap": cells[4]})
    return rows


def parse_summary(text: str) -> dict[str, int]:
    out = {}
    block = text.split("## 요약", 1)[-1].split("\n## ", 1)[0]
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and cells[0] in STATUSES and cells[1].isdigit():
            out[cells[0]] = int(cells[1])
    return out


def check(root: Path) -> dict:
    docs = root / "docs"
    checklist = (docs / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    status_doc = (docs / "LAUNCH_STATUS.md").read_text(encoding="utf-8")
    known_files = {p.name for p in root.rglob("*") if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts}
    known_paths = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts}
    status_prs = {int(m) for m in re.findall(r"PR\s*#(\d+)", status_doc)} | {int(m) for m in re.findall(r"#(\d+)", status_doc)}
    rows, errors = parse_rows(checklist), []
    counted = Counter(r["status"] for r in rows)
    summary = parse_summary(checklist)
    for status in STATUSES:
        if summary.get(status) != counted.get(status, 0):
            errors.append(f"summary says {status}={summary.get(status)} but the table has {counted.get(status, 0)}")
    for r in rows:
        tag = f"#{r['n']} {r['item'][:40]}"
        if r["status"] not in STATUSES:
            errors.append(f"{tag}: unknown status {r['status']!r}")
        has_evidence = r["evidence"] not in ("", "—", "-")
        if r["status"] == DONE and not has_evidence:
            errors.append(f"{tag}: marked {DONE} with no evidence")
        for name in set(FILE_RE.findall(r["evidence"])) - GENERATED:
            if name not in known_paths and Path(name).name not in known_files:
                errors.append(f"{tag}: evidence names a file that is not in the repository: {name}")
        for a, b in PR_RE.findall(r["evidence"]):
            number = int(a or b)
            if number not in status_prs:
                errors.append(f"{tag}: evidence names PR #{number}, which LAUNCH_STATUS.md never mentions")
    return {"rows": len(rows), "counts": dict(counted), "summary": summary, "errors": errors}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = check(Path(args.root))
    if args.json:
        sys.stdout.buffer.write((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    else:
        out = [f"rows {result['rows']}  counts {result['counts']}  summary {result['summary']}"] + [f"ERROR {e}" for e in result["errors"]]
        sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
