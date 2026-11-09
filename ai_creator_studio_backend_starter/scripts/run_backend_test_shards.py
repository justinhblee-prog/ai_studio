#!/usr/bin/env python3
"""Run backend pytest files in isolated subprocesses and retain per-file logs.

The full backend suite contains API tests with shared process-level fixtures and
can exceed constrained single-command execution windows. Running each test file
in a fresh process gives deterministic isolation and makes slow/failing shards
identifiable without changing application code or test semantics.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-dir", type=Path,
        default=Path("build_backend_test_shards"),
        help="directory for per-file stdout/stderr logs",
    )
    parser.add_argument(
        "--timeout-seconds", type=int, default=120,
        help="maximum runtime for each test-file subprocess (default: 120)",
    )
    parser.add_argument(
        "--file", action="append", default=[], metavar="TEST_FILE",
        help="run only this test filename (repeatable); defaults to all test files",
    )
    parser.add_argument(
        "--stop-on-failure", action="store_true",
        help="stop after the first failed or timed-out shard",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    tests_dir = root / "tests"
    test_files = sorted(tests_dir.glob("test_*.py"))
    if args.file:
        requested = set(args.file)
        test_files = [path for path in test_files if path.name in requested]
        missing = requested - {path.name for path in test_files}
        if missing:
            print("Unknown test file(s): " + ", ".join(sorted(missing)), file=sys.stderr)
            return 2
    if not test_files:
        print(f"No test files found under {tests_dir}", file=sys.stderr)
        return 2
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")

    log_dir = args.log_dir.resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")

    passed_files = failed_files = timed_out_files = passed_tests = 0
    started = time.monotonic()
    summary_lines: list[str] = []

    for index, test_file in enumerate(test_files, start=1):
        relative = test_file.relative_to(root)
        log_path = log_dir / f"{test_file.stem}.log"
        command = [sys.executable, "-m", "pytest", "-q", str(relative)]
        shard_started = time.monotonic()
        try:
            # Write directly to disk rather than buffering the entire pytest
            # stream in memory. This preserves partial progress when a shard
            # times out and makes long-running failures diagnosable.
            with log_path.open("w", encoding="utf-8") as log_file:
                result = subprocess.run(
                    command, cwd=root, env=env, text=True,
                    stdout=log_file, stderr=subprocess.STDOUT,
                    timeout=args.timeout_seconds, check=False,
                )
            output = log_path.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"(\d+) passed(?:,| in )", output)
            count = int(match.group(1)) if match else 0
            elapsed = time.monotonic() - shard_started
            if result.returncode == 0:
                passed_files += 1
                passed_tests += count
                status = f"PASS ({count} tests, {elapsed:.2f}s)"
            else:
                failed_files += 1
                status = f"FAIL (exit {result.returncode}, {elapsed:.2f}s)"
        except subprocess.TimeoutExpired:
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(f"\nTIMED OUT after {args.timeout_seconds}s\n")
            timed_out_files += 1
            status = f"TIMEOUT ({args.timeout_seconds}s)"

        line = f"[{index}/{len(test_files)}] {relative}: {status}"
        print(line, flush=True)
        summary_lines.append(line)
        if args.stop_on_failure and ("FAIL" in status or "TIMEOUT" in status):
            break

    elapsed = time.monotonic() - started
    summary = [
        "Backend pytest shard summary",
        f"Test files selected: {len(test_files)}",
        f"Test files passed: {passed_files}",
        f"Test files failed: {failed_files}",
        f"Test files timed out: {timed_out_files}",
        f"Individual tests passed: {passed_tests}",
        f"Elapsed: {elapsed:.2f}s",
        "",
        *summary_lines,
    ]
    (log_dir / "SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary[:7]))
    return 0 if failed_files == 0 and timed_out_files == 0 and passed_files == len(test_files) else 1


if __name__ == "__main__":
    raise SystemExit(main())
