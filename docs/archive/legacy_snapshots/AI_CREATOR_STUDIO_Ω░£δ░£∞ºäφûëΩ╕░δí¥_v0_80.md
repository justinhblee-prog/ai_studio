# 개발 진행 기록 v0.80

## 감사 결과

Provider 성공 handoff에서 URL을 DB에 저장한 뒤 Output Worker가 다운로드 시 URL 정책을 검사하는 구조였습니다. 다운로드 단계의 HTTPS/host allowlist 검사는 유지하되, malformed URL이 Job을 `post_processing` 상태로 전환하거나 durable event payload에 기록되는 일을 줄이기 위해 handoff 진입점에 형식 검증을 추가했습니다.

Output 성공 확정 Repository는 내부 private route 및 Output metadata를 전달받아 DB 상태를 확정하므로, Repository 경계에서도 저장 파일명, MIME/확장자, 크기, Job별 private route의 일관성을 확인하도록 강화했습니다.

## 구현

- `SQLitePollRepository._validate_provider_output_reference` 추가:
  - 문자열/길이 제한(4096)
  - 공백 및 제어문자 거부
  - HTTPS, hostname, credential-free URL 요구
- `SQLiteOutputRepository._validate_final_output` 추가:
  - PNG/JPEG/WebP MIME allowlist
  - storage key의 plain filename 여부
  - MIME과 확장자 일치
  - 양수 크기 및 `MAX_OUTPUT_BYTES` 상한
  - 현재 Job에 대응하는 authenticated private output route만 허용
- 검증은 DB 트랜잭션 및 성공 상태 변경 이전에 수행.
- 기존 다운로드 단계의 `FASHN_OUTPUT_HOSTS` allowlist, redirect 차단, content-type/signature 검증은 유지.

## 회귀 테스트

- 잘못된 Provider URL 5종이 Job 상태를 변경하지 않고 거부되는지 확인.
- 잘못된 final output metadata/route 7종이 Output/Job 상태를 변경하지 않고 거부되는지 확인.

## 검증 결과

- Backend pytest: 248 passed
- Python compileall: passed
- Viewer structural validation: 19/19 passed
- ZIP integrity: passed

## 제한

SQLite 단일 호스트 범위입니다. PostgreSQL 및 다중 인스턴스 동시성은 검증하지 않았습니다. Provider URL 형식 검증은 allowlist 검증이나 원격 이미지의 신뢰성 검증을 대체하지 않습니다. 원격 URL의 실제 host allowlist 및 파일 콘텐츠 검증은 기존 Output Store 다운로드 단계에서 수행됩니다.
