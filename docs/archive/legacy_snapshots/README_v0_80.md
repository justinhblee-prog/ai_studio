# AI CREATOR STUDIO v0.80

## 변경 사항

- Provider 성공 응답에서 output reference를 영속화하기 전에 형식을 검증합니다.
- Provider output reference는 비어 있지 않은 최대 4096자 HTTPS URL이어야 하며, 공백/제어문자와 URL 사용자 인증정보를 거부합니다.
- Output 성공 확정 직전 저장 파일명, 확장자와 MIME type 일치, 이미지 MIME allowlist, 파일 크기(1..MAX_OUTPUT_BYTES), Job별 인증된 private output route를 검증합니다.
- 잘못된 Provider URL 또는 Output finalization 입력은 DB 상태 변경 전에 거부됩니다.
- 실제 다운로드 시의 HTTPS host allowlist 및 이미지 서명 검사는 기존 Output Store에서 계속 수행합니다.

## 검증

- Backend: `python -m pytest -q` — 248 passed
- Compile: `python -m compileall -q app scripts tests` — passed
- Viewer: `python scripts/validate_source.py` — 19/19 passed
- ZIP: `unzip -t` — passed

## 범위 및 한계

SQLite 단일 호스트 구현 및 테스트입니다. PostgreSQL, 다중 서버, 분산 Lease 동기화는 검증하지 않았습니다. Provider output host allowlist는 다운로드 단계의 기존 설정을 사용하며, 실제 FASHN 계약/권리/보존/상업적 이용 검증을 대체하지 않습니다. Provider 성공 URL의 형식 검사만으로 원격 서버의 안전성이 보장되는 것은 아니며, 다운로드 시 기존 host allowlist 검사가 필수입니다.
