"""R-072: writes docs/ERROR_CODES.md from app/error_catalog.py (``--check`` only compares). The document is generated, never edited by hand."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import error_catalog as ec  # noqa: E402

DOC = Path(__file__).resolve().parents[2] / "docs" / "ERROR_CODES.md"


def render() -> str:
    lines = ["# 오류 코드 → 안내 문구 표 (자동 생성 — 직접 고치지 않음)", "",
             f"버전 `{ec.VERSION}`. 원본은 `ai_creator_studio_backend_starter/app/error_catalog.py`, 같은 내용을 `GET /v1/error-catalog?lang=ko|en`(로그인 불필요)이 JSON으로 줍니다. "
             "`python scripts/generate_error_codes_doc.py`로 다시 만들고, 시험이 이 문서가 최신인지와 **서버가 보내는 모든 코드가 표에 있는지**를 확인합니다.", "",
             "- **종류**: `limit` = 한도·속도 제한·용량(429 또는 그에 준함, 응답에 `retry_after_seconds`·`retry_at`이 있을 수 있음), `error` = 그 밖의 오류.",
             f"- **법무성 문구는 비어 있음**(`[결정 필요: 법무]`): {', '.join('`' + c + '`' for c in ec.NEEDS_DECISION)}. 이 코드들은 `message: null`, `needs_decision: true`이며 홈페이지는 **HTTP 상태별 기본 문구**를 대신 보여 주세요.",
             "- 코드가 **없는** 응답(예: 권한 없음 403의 글자 한 줄)은 아래 \"HTTP 상태별 기본 문구\"를 쓰세요.", "",
             "## 코드별 문구", "", "| 코드 | 영역 | 종류 | 한국어 | English |", "|---|---|---|---|---|"]
    for code in sorted(ec.CODES):
        text = ec.CODES[code]
        ko, en = ("**[결정 필요: 법무]**", "**[decision needed: legal]**") if text is None else text
        lines.append(f"| `{code}` | {ec.area_of(code)} | {'limit' if code in ec.LIMIT_CODES else 'error'} | {ko} | {en} |")
    lines += ["", "## HTTP 상태별 기본 문구", "", "| 상태 | 한국어 | English |", "|---|---|---|"]
    for status, (ko, en) in ec.HTTP.items():
        lines.append(f"| {status} | {ko} | {en} |")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    text = render()
    if "--check" in args:
        return 0 if DOC.exists() and DOC.read_text(encoding="utf-8") == text else 1
    DOC.write_bytes(text.encode("utf-8"))      # LF line endings on every platform
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
