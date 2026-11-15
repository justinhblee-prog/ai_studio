"""One-page release evidence (Markdown) from the CI logs, for readers who cannot open GitHub (R-031).

Usage: python scripts/release_evidence.py --logs-dir DIR [--commit SHA] [--out FILE]
DIR may hold: pytest.txt (pytest output), frontend.txt (npm run test:source output), e2e*.txt (the e2e step logs, each ending in a
"SUMMARY n/m ... passed" line). Anything missing is written as "미확인" (never as a pass). Secret-like environment variables are listed by
NAME only (set / unset); any secret value that still shows up in the text is replaced by [REDACTED] before output.
This script reads logs and environment variables only: it calls no service and changes no data.
"""
from __future__ import annotations
import argparse, os, re, subprocess, sys
from pathlib import Path

UNKNOWN = "미확인"
SECRET_NAME = re.compile(r"(SECRET|TOKEN|KEY|PASSWORD|PASSWD|DSN|DATABASE_URL|CREDENTIAL)", re.I)
# Flags and settings a launch review cares about: (name, default shown when unset, kind). Defaults must match app/config.py (tested).
SETTINGS = [
    ("LEGAL_REQUIRE_ACCEPTANCE", "off", "flag_off"),               # server-side consent enforcement: stays OFF until the owner decides
    ("ASSET_REQUIRE_RIGHTS_CONFIRMATION", "on", "flag_on"),          # upload rights declaration: ON by default
    ("DATABASE_BACKEND", "sqlite", "text"),                          # postgresql must not be switched on yet
    ("PROVIDER_MODE", "mock", "text"),                               # the generation provider (there is no GENERATION_PROVIDER variable)
    ("PROVIDER_ROUTING_MODE", "MANUAL", "upper"),
]
FALSE_WORDS = {"0", "false", "no", "off"}
TRUE_WORDS = {"1", "true", "yes", "on"}


def effective(name, default, kind, env):
    raw = env.get(name)
    if raw is None:
        return default, "기본값"
    text = raw.strip()
    if kind == "flag_off":
        return ("on" if text.lower() in TRUE_WORDS else "off"), "환경 변수로 지정"
    if kind == "flag_on":
        return ("off" if text.lower() in FALSE_WORDS else "on"), "환경 변수로 지정"
    return (text.upper() if kind == "upper" else text.lower()), "환경 변수로 지정"


def secret_names(env):
    return sorted(n for n in env if SECRET_NAME.search(n))


def secret_values(env):
    return sorted({env[n].strip() for n in secret_names(env) if len(env[n].strip()) >= 4}, key=len, reverse=True)


def redact(text, env):
    for value in secret_values(env):
        text = text.replace(value, "[REDACTED]")
    return text


def parse_pytest(text):
    """Counts from every pytest summary line ('903 passed, 1 warning in 85s'); several runs are summed and listed."""
    runs = []
    for line in text.splitlines():
        if " in " in line and re.search(r"\b\d+ (passed|failed|skipped|errors?)\b", line):
            runs.append({k: 0 for k in ("passed", "failed", "skipped", "error")})
            for n, word in re.findall(r"(\d+) (passed|failed|skipped|errors?)", line):
                runs[-1]["error" if word.startswith("error") else word] += int(n)
    return runs


def parse_node_tests(text):
    """node --test prints '# pass N' / '# fail N' / '# skipped N' per test file; sum them."""
    totals, files = {"pass": 0, "fail": 0, "skipped": 0}, 0
    for key in totals:
        for n in re.findall(rf"^# {key} (\d+)\s*$", text, re.M):
            totals[key] += int(n)
    files = len(re.findall(r"^# pass \d+\s*$", text, re.M))
    return totals, files


def parse_e2e(text):
    m = re.search(r"SUMMARY (\d+)/(\d+) (.+?) passed", text)
    return (int(m.group(1)), int(m.group(2)), m.group(3)) if m else None


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def commit_hash(given):
    if given:
        return given
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip() or UNKNOWN
    except Exception:
        return UNKNOWN


def render(logs_dir, commit, env):
    d = Path(logs_dir) if logs_dir else None
    out = ["# 출시 근거 한 장 (CI 증거 요약)", "", f"- 커밋: `{commit_hash(commit)}`",
           "- 만든 곳: `scripts/release_evidence.py` (로그와 환경 변수 이름만 읽음, 서비스 호출·데이터 변경 없음)",
           "- 이 문서는 로그에 적힌 숫자를 옮긴 것이다. 로그가 없는 항목은 \"미확인\"이며 통과로 세지 않는다.", ""]
    out += ["## 백엔드 pytest", ""]
    pytest_text = read(d / "pytest.txt") if d else None
    runs = parse_pytest(pytest_text) if pytest_text else []
    if not runs:
        out.append(f"- {UNKNOWN} (pytest.txt 없음 또는 요약 줄 없음)")
    else:
        for i, r in enumerate(runs, 1):
            out.append(f"- 실행 {i}: passed {r['passed']}, failed {r['failed']}, skipped {r['skipped']}, error {r['error']}")
        out.append(f"- 합계: passed {sum(r['passed'] for r in runs)}, failed {sum(r['failed'] for r in runs)}, skipped {sum(r['skipped'] for r in runs)}")
    out += ["", "## 프런트 시험 (`npm run test:source`)", ""]
    front = read(d / "frontend.txt") if d else None
    if front is None:
        out.append(f"- {UNKNOWN} (frontend.txt 없음)")
    else:
        totals, files = parse_node_tests(front)
        out.append(f"- node 시험 파일 {files}개: pass {totals['pass']}, fail {totals['fail']}, skipped {totals['skipped']}")
    out += ["", "## e2e 단계별", "", "| 로그 | 통과/전체 | 내용 | 판정 |", "|---|---|---|---|"]
    files = sorted(d.glob("e2e*.txt")) if d and d.is_dir() else []
    if not files:
        out.append(f"| (없음) | {UNKNOWN} | | {UNKNOWN} |")
    for f in files:
        got = parse_e2e(read(f) or "")
        if got is None:
            out.append(f"| {f.name} | {UNKNOWN} | SUMMARY 줄 없음 | 실패 또는 미완료 |")
        else:
            out.append(f"| {f.name} | {got[0]}/{got[1]} | {got[2]} | {'통과' if got[0] == got[1] else '실패'} |")
    out += ["", "## 운영 플래그·기본값 (이 환경에서 읽은 유효값)", "", "| 이름 | 값 | 출처 |", "|---|---|---|"]
    for name, default, kind in SETTINGS:
        value, source = effective(name, default, kind, env)
        out.append(f"| `{name}` | `{value}` | {source} |")
    out += ["", "## 비밀값 (이름만, 값은 쓰지 않음)", ""]
    names = secret_names(env)
    out += [f"- `{n}`: {'설정됨' if env[n].strip() else '비어 있음'}" for n in names] or ["- (비밀로 보이는 환경 변수 없음)"]
    out += ["", "## 이 문서가 말해 주지 않는 것", "", "- GitHub의 실제 run 번호·실서버·실제 Provider·법무 빈칸 확정은 포함하지 않는다(미확인).", ""]
    return redact("\n".join(out), env)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--logs-dir"); p.add_argument("--commit"); p.add_argument("--out")
    a = p.parse_args(argv)
    text = render(a.logs_dir, a.commit, dict(os.environ))
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
