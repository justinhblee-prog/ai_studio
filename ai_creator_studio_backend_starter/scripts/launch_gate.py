"""Pre-launch gate: runs the automatable checks and prints pass / fail / not-run counts.

Usage: python scripts/launch_gate.py [--skip NAME ...] [--json]
Exit 0 = every step that ran passed and nothing required was skipped; 1 = a step failed; 2 = a required step did not run.
Steps: tests (pytest), audit (pip-audit on the installed environment), backup_drill (backup -> verify -> restore into a new folder, on a throwaway database).
Not covered (needs people or real services, always reported as NOT_RUN): real provider verification, legal blanks,
real deployment smoke, GitHub CI, real-data purge approval. This script never touches real data or paid services.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASS, FAIL, SKIP = "PASS", "FAIL", "NOT_RUN"
MANUAL = [
    ("provider_verification", "실제 Provider 품질 검증(예산 승인·테스트 키 필요)"),
    ("legal_blanks", "약관·방침의 법률 빈칸 확정과 법률 검토"),
    ("deploy_smoke", "실제 배포 환경 스모크(배포 후)"),
    ("github_ci", "GitHub CI 결과 확인(개발 창 보고)"),
    ("purge_approval", "첫 실데이터 삭제 승인"),
]


def parse_pytest(text: str) -> dict:
    """Read counts from pytest's last summary line, e.g. '684 passed, 59 skipped in 25s'."""
    counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    last = ""
    for line in text.splitlines():
        if re.search(r"\b(passed|failed|error|errors|skipped)\b", line) and " in " in line:
            last = line
    for n, word in re.findall(r"(\d+) (passed|failed|skipped|errors?)", last):
        counts["error" if word.startswith("error") else word] += int(n)
    return counts


def _run(cmd, timeout, env=None):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env)


def step_tests():
    r = _run([sys.executable, "-m", "pytest", "-q", "-W", "ignore"], 1800)
    c = parse_pytest(r.stdout + r.stderr)
    ok = r.returncode == 0 and c["failed"] == 0 and c["error"] == 0 and c["passed"] > 0
    return (PASS if ok else FAIL), f"passed={c['passed']} failed={c['failed']} errors={c['error']} skipped={c['skipped']}"


def step_audit():
    # Audits the installed environment (requirements.txt uses ranges, which pip-audit cannot resolve offline).
    r = _run([sys.executable, "-m", "pip_audit", "--skip-editable"], 600)
    text = (r.stdout + r.stderr).strip().splitlines()
    if r.returncode == 0:
        return PASS, "no known vulnerabilities"
    if "No module named" in " ".join(text):
        return SKIP, "pip-audit is not installed"
    return FAIL, " | ".join(text[-3:])[:300]


def step_backup_drill():
    """Backup -> verify -> restore into a new folder, on a throwaway database created in a temp directory.
    Main's `scripts/backup_restore.py` backs up the *configured* database; the drill points it at temp paths so it
    never reads or writes real data and also works on a checkout that has no database yet."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        env = dict(os.environ, ASSET_DATABASE_PATH=str(tmp / "live" / "assets.sqlite3"), ASSET_STORAGE_DIR=str(tmp / "live" / "private"),
                   OUTPUT_DIR=str(tmp / "live" / "outputs"), GENERATION_DATABASE_PATH="", ASSET_SIGNING_SECRET="d" * 48)
        (tmp / "live").mkdir()
        seed = _run([sys.executable, "-c", "from app.assets.store import create_workspace; create_workspace('drill-ws', 'drill-user')"], 120, env)
        if seed.returncode != 0:
            return FAIL, "could not create the throwaway database: " + (seed.stdout + seed.stderr)[-200:]
        script = "scripts/backup_restore.py"
        r = _run([sys.executable, script, "backup", "--dest", str(tmp / "backups")], 300, env)
        if r.returncode != 0:
            return FAIL, "backup failed: " + (r.stdout + r.stderr)[-200:]
        found = sorted((tmp / "backups").glob("backup-*/manifest.json"))
        if not found:
            return FAIL, "backup produced no manifest"
        backup_dir = found[0].parent
        r = _run([sys.executable, script, "verify", str(backup_dir)], 300, env)
        if r.returncode != 0:
            return FAIL, "verify failed: " + (r.stdout + r.stderr)[-200:]
        r = _run([sys.executable, script, "restore", str(backup_dir), "--target", str(tmp / "restored")], 300, env)
        if r.returncode != 0:
            return FAIL, "restore failed: " + (r.stdout + r.stderr)[-200:]
        return PASS, f"backup, verify and restore into a new folder passed on a throwaway database ({backup_dir.name})"


STEPS = {"tests": step_tests, "audit": step_audit, "backup_drill": step_backup_drill}


def run(skip=()):
    results = []
    for name, fn in STEPS.items():
        if name in skip:
            results.append({"step": name, "status": SKIP, "detail": "skipped by flag"})
            continue
        try:
            status, detail = fn()
        except subprocess.TimeoutExpired:
            status, detail = FAIL, "timed out"
        results.append({"step": name, "status": status, "detail": detail})
    for name, detail in MANUAL:
        results.append({"step": name, "status": SKIP, "detail": detail, "manual": True})
    return results


def exit_code(results):
    if any(r["status"] == FAIL for r in results):
        return 1
    if any(r["status"] == SKIP and not r.get("manual") for r in results):
        return 2
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", nargs="*", default=[])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    results = run(set(a.skip))
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    else:
        for r in results:
            print(f"[{r['status']:7}] {r['step']}: {r['detail']}")
        n = lambda s: sum(1 for r in results if r["status"] == s)
        print(f"summary: pass={n(PASS)} fail={n(FAIL)} not_run={n(SKIP)} (manual items stay NOT_RUN: launch is not approved by this script)")
    return exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())
