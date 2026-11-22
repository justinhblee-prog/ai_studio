"""B-02: turn restore-drill reports (``restore_drill.py --out``) into a Markdown summary and, on failure, an alert text - the glue of the weekly drill workflow.
   python scripts/drill_report.py small.json scale.json [--max-rto 30] [--issue-body]
Exit 0 = every drill passed and (with --max-rto) none was slower than the budget; 1 = something failed or a report is missing/unreadable. Only reads the JSON files; touches nothing else."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"ok": False, "unreadable": f"{type(exc).__name__}", "checks": {}}
    return data if isinstance(data, dict) else {"ok": False, "unreadable": "not an object", "checks": {}}


def judge(report: dict[str, Any], max_rto: float | None) -> tuple[bool, list[str]]:
    problems = []
    if report.get("unreadable"):
        problems.append(f"the report could not be read ({report['unreadable']})")
    failed = [name for name, check in (report.get("checks") or {}).items() if not (check or {}).get("ok")]
    if failed:
        problems.append("failed checks: " + ", ".join(sorted(failed)))
    if not report.get("ok") and not problems:
        problems.append("the drill reported ok=false")
    rto = report.get("rto_seconds")
    if max_rto is not None and isinstance(rto, (int, float)) and rto > max_rto:
        problems.append(f"RTO {rto:.2f} s is over the budget of {max_rto:g} s")
    return not problems, problems


def summarize(paths: list[Path], max_rto: float | None = None) -> tuple[str, bool, dict[str, list[str]]]:
    lines = ["| drill | result | rows | files | backup s | restore s | RTO s | problems |", "|---|---|---|---|---|---|---|---|"]
    everything_ok, by_drill = True, {}
    for path in paths:
        report = load(path)
        ok, problems = judge(report, max_rto)
        everything_ok &= ok
        by_drill[path.stem] = problems
        sizes, seconds = report.get("sizes") or {}, report.get("seconds") or {}
        lines.append(f"| {path.stem} | {'PASS' if ok else 'FAIL'} | {sizes.get('rows', '?')} | {sizes.get('file_count', '?')} | {seconds.get('backup', '?')} | {seconds.get('restore', '?')} | "
                     f"{report.get('rto_seconds', '?')} | {'; '.join(problems) or '-'} |")
    if max_rto is not None:
        lines.append(f"\nRTO budget (a proposal, measured on the CI runner, not on a production server): {max_rto:g} s.")
    return "\n".join(lines) + "\n", everything_ok, by_drill


def issue_body(table: str, run_url: str | None) -> str:
    return ("The scheduled backup / restore drill failed.\n\n" + table +
            "\nWhat to do (docs/RESTORE_DRILL.md): open the run's artifact `restore-drill-reports`, read which check failed, reproduce with "
            "`python scripts/restore_drill.py --demo small`, and fix the backup/restore code before the next release. A failing drill means a backup made today may not be restorable.\n" +
            (f"\nRun: {run_url}\n" if run_url else ""))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--max-rto", type=float)
    parser.add_argument("--issue-body", action="store_true")
    parser.add_argument("--run-url")
    args = parser.parse_args(argv)
    table, ok, _ = summarize(args.reports, args.max_rto)
    print(issue_body(table, args.run_url) if args.issue_body else table)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
