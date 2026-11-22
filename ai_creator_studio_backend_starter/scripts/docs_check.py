"""B-20: the index of docs/ and a monthly check for documents that went stale.

   python scripts/docs_check.py --check        the default (CI runs it): every docs/*.md is listed in docs/INDEX.md and nothing listed is missing -> exit 1 otherwise
   python scripts/docs_check.py --write        regenerate docs/INDEX.md (title and first line of every document)
   python scripts/docs_check.py --stale 90     list documents whose last git change is older than 90 days (the monthly look; never fails)
   python scripts/docs_check.py --refs         list `path/like/this.py` mentions in the documents whose file no longer exists (never fails)

The index lists only the top-level docs/*.md; the sub-folders (api, archive, development, handoff, releases, ...) have their own roles described in docs/README.md.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
INDEX = DOCS / "INDEX.md"
HEADER = "# 문서 색인 (docs/*.md)\n\n자동 생성: `python ai_creator_studio_backend_starter/scripts/docs_check.py --write`. 새 문서를 `docs/`에 추가하면 이 표도 갱신해야 CI가 통과한다(`--check`).\n오래된 문서 점검은 `--stale 90`(월 1회), 사라진 파일을 가리키는 언급은 `--refs`. 하위 폴더의 역할은 `README.md`.\n\n| 문서 | 제목 | 첫 줄 |\n|---|---|---|\n"
CODE_SUFFIXES = (".py", ".md", ".mjs", ".yml", ".json", ".sql", ".ts", ".tsx", ".txt", ".sh")


def documents() -> list[Path]:
    return sorted(p for p in DOCS.glob("*.md") if p.name != INDEX.name)


def describe(path: Path) -> tuple[str, str]:
    title, first = path.stem, ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if title == path.stem:
                title = line.lstrip("# ").strip()
            continue
        first = line
        break
    return title.replace("|", "/"), (first[:110] + ("…" if len(first) > 110 else "")).replace("|", "/")


def render() -> str:
    rows = [f"| `{p.name}` | {t} | {f} |" for p in documents() for t, f in [describe(p)]]
    return HEADER + "\n".join(rows) + "\n"


def listed() -> set[str]:
    if not INDEX.is_file():
        return set()
    return set(re.findall(r"^\| `([^`]+\.md)` \|", INDEX.read_text(encoding="utf-8"), re.M))


def check() -> int:
    actual, in_index = {p.name for p in documents()}, listed()
    missing, dead = sorted(actual - in_index), sorted(in_index - actual)
    for name in missing:
        print(f"NOT IN THE INDEX: docs/{name}  (run --write)")
    for name in dead:
        print(f"LISTED BUT GONE: docs/{name}  (run --write)")
    if not INDEX.is_file():
        print("docs/INDEX.md does not exist (run --write)")
        return 1
    print(f"docs index: {len(actual)} documents, {len(missing)} missing from the index, {len(dead)} listed but gone")
    return 1 if missing or dead else 0


def last_change(path: Path) -> date | None:
    out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return date.fromisoformat(out) if out else None


def stale(days: int) -> int:
    today, rows = date.today(), []
    for p in documents():
        changed = last_change(p)
        if changed is not None and (today - changed).days > days:
            rows.append(((today - changed).days, p.name, changed))
    for age, name, changed in sorted(rows, reverse=True):
        print(f"{age:4d} days  docs/{name}  (last change {changed})")
    print(f"{len(rows)} of {len(documents())} documents unchanged for more than {days} days (the date is from git: a shallow clone shows one date for everything)")
    return 0


def refs() -> int:
    candidates = [ROOT, ROOT / "ai_creator_studio_backend_starter", ROOT / "ai_creator_studio_3d_viewer", DOCS, ROOT / "ai_creator_studio_backend_starter" / "app"]
    found = 0
    for p in documents():
        for ref in sorted(set(re.findall(r"`([\w./-]+/[\w.-]+)`", p.read_text(encoding="utf-8")))):
            if not ref.endswith(CODE_SUFFIXES) or ref.startswith(("http", "/")) or "*" in ref or "<" in ref:
                continue
            if not any((base / ref).exists() for base in candidates):
                print(f"docs/{p.name}: `{ref}` does not exist")
                found += 1
    print(f"{found} mention(s) of files that no longer exist")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--stale", type=int, metavar="DAYS")
    parser.add_argument("--refs", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        INDEX.write_text(render(), encoding="utf-8", newline="\n")
        print(f"wrote {INDEX.relative_to(ROOT)} ({len(documents())} documents)")
        return 0
    if args.stale is not None:
        return stale(args.stale)
    if args.refs:
        return refs()
    return check()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
