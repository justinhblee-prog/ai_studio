# AI CREATOR STUDIO — CURRENT HANDOFF BUILD-00213

- 작성일: 2026-11-06
- 기준 소스: BUILD-00209 full handoff source, BUILD-00212 readiness implementation plus BUILD-00213 PostgreSQL fail-closed coverage
- Engineering build: **BUILD-00213**
- 상태: 내부 preflight 기능 구현 및 로컬 회귀 검증 완료. Supabase/Vercel 실환경 통합은 다음 배치 검증 대상으로 유지.

## 1. 이번 빌드 변경 사항

- `ai_creator_studio_backend_starter/app/platform_readiness.py` 추가
  - 네트워크 연결이나 DB 변경 없이 현재 통합 준비 상태를 읽기 전용으로 반환.
  - DB backend, Supabase PostgreSQL, Supabase Storage, Worker, AI provider, Vercel Preview를 각각 구분.
  - DATABASE_URL 및 API 키 값은 노출하지 않고 설정 유무만 표시.
- `GET /internal/ops/runtime-readiness` 추가
  - 플랫폼 운영자 전용 (`OPS_ADMIN_USER_IDS` 검사).
  - 인증 누락은 401, 운영자 아닌 사용자는 403.
  - 외부 리소스 변경, 데이터베이스 접속, Storage 업로드를 수행하지 않음.
- `docs/api/openapi.runtime.v1.json` 갱신.
- readiness unit/API 보안 테스트 4개 추가.
- PostgreSQL Repository factory 15개와 Storage selector가 SQLite로 조용히 fallback하지 않도록 fail-closed 회귀 테스트 추가.
- PostgreSQL adapter coverage matrix 작성; 애플리케이션 Python 소스에서 SQLite 전용 참조 106개를 정적 검색으로 확인.

## 2. 로컬 검증 결과

- Backend pytest: **495 passed / 0 failed** (BUILD-00213).
- Python compileall (`app`, `tests`): PASS.
- Runtime OpenAPI snapshot check: PASS.
- requirements manifest: 7개 독립 항목 확인 PASS.
- Readiness API 인증 경계: 401 / 403 / 200 검증 PASS.
- Secret redaction: DATABASE_URL password 및 provider key 문자열 미노출 확인 PASS.

이 결과는 로컬 테스트 증거이며 Supabase 또는 Vercel 실환경 통합 성공을 의미하지 않음.

## 3. Supabase 환경

### 기존 운영 프로젝트 — 변경 금지
- `AI Characters STUDIO`
- project ID: `lmdhgqfqvfyymfrovaty`
- Seoul (`ap-northeast-2`), PostgreSQL 17.11
- 기존 public 앱 테이블 8개, RLS 활성화.
- Security Advisor 0 lints로 확인된 이전 감사 기록이 있음.
- 광범위한 `anon`/`authenticated` 테이블 권한은 별도 보안 검토 대상이며 변경하지 않음.

### 신규 테스트 프로젝트
- `AI-CREATOR-STUDIO-TEST`
- project ID: `niktytizbtvxypwswbcc`
- Seoul (`ap-northeast-2`), PostgreSQL 17.11, 상태 `ACTIVE_HEALTHY`로 확인.
- 마이그레이션 `acs_private_storage_buckets` 1개 적용.
- 비공개 버킷 3개: `acs-assets`, `acs-gallery`, `acs-outputs`.
- 앱 public 테이블, Storage object policies, 테스트 사용자, Storage 객체는 아직 없음.
- 운영 데이터 복사 없음.
- Vercel 환경변수/런타임 연결 없음.

**주의:** 버킷 생성은 애플리케이션 업로드/다운로드 통합 테스트 완료가 아님. PostgreSQL Repository Adapter 및 Supabase Storage Adapter가 구현되기 전까지 `DATABASE_BACKEND=postgresql`을 활성화하지 말 것.

## 4. Vercel 상태

- Project: `ai-creator-studio`
- Project ID: `prj_YLMaRJ9qTE1ZJh4FNr7pgj6mZAfW`
- Framework: FastAPI
- 기존 배포: `dpl_FJHKKrgj3WG69sEhLyiyYrqWNF8X`, target `production`, state `READY`.
- URL: `https://ai-creator-studio-edhu46qt9-justinhblee-9540.vercel.app`
- Alias: `https://ai-creator-studio-topaz.vercel.app`
- 기존 `/` 및 `/health`는 HTTP 200이나 응답은 `bootstrap-preview` smoke-test임.
- 전체 AI CREATOR STUDIO 모듈은 배포되지 않았음.
- Git repository 연결 및 소스 기반 Preview 배포는 미확인/미수행.
- Production 재배포 또는 alias 변경 금지. 다음 실환경 배치는 별도 Preview target만 사용.

## 5. 다음 개발 및 통합 순서

1. PostgreSQL adapter 범위 확정: Job, Event, Execution, Outbox, Poll, Output, Output Review, Asset/Workspace, Operations/Alert 등 전체 aggregate.
2. PostgreSQL schema migration runner와 test DB disposable migration 검증.
3. Job/Outbox/Poll lease의 transaction 및 `FOR UPDATE SKIP LOCKED` 경쟁 테스트.
4. Asset metadata 및 workspace RBAC의 DB 경계 통합.
5. Supabase Storage adapter: tenant-safe key, private bucket, MIME/size/checksum, signed URL, rollback/delete lifecycle.
6. API와 Worker 프로세스 분리 배포 및 durable worker topology 확정.
7. Source-backed Vercel Preview 배포와 health/API contract smoke test.
8. Supabase + Vercel 통합 배치에서 인증, DB, Storage, Worker, API 로그를 한 번에 검증.
9. 유료 AI provider 실생성은 별도 비용 승인 전까지 수행하지 않음.

## 6. 운영 원칙

- 로컬 설계·개발·회귀 검증을 충분히 누적한 뒤 실환경 테스트를 배치 실행.
- Supabase/Vercel 실환경 검증 결과는 로컬 mock 테스트와 구분.
- 운영 Supabase 및 Vercel Production은 승인 없이 변경하지 않음.
- 미검증 기능을 완료로 표시하지 않음.
- 테스트 계정·API secret은 소스/문서/로그/채팅에 기록하지 않음.

## 7. 시작 명령

```bash
cd ai_creator_studio_backend_starter
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/export_runtime_openapi.py --check
```

## 8. 주의할 미완료 사항

- PostgreSQL runtime adapter: NOT IMPLEMENTED.
- Supabase Storage application adapter: NOT IMPLEMENTED.
- Supabase live app integration: NOT RUN.
- Vercel source-backed Preview: NOT DEPLOYED.
- Browser-based React/Three.js end-to-end and visible GLB render: NOT VERIFIED.
- Real AI image generation: NOT RUN; default provider remains mock.
- Marketplace, billing, full video pipeline and production operations: NOT READY.


## 9. BUILD-00213 추가 산출물

- `ai_creator_studio_backend_starter/docs/POSTGRESQL_ADAPTER_COVERAGE_MATRIX_BUILD-00213.md`
- `ai_creator_studio_backend_starter/tests/test_postgresql_fail_closed.py`
- PostgreSQL 선택 시 15개 Repository factory와 storage selector가 모두 fail-closed 하는 테스트 16개 통과.
