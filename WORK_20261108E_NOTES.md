# WORK-20261108-E (BUILD-00231 기준선에서 재시작)

기준: BUILD-00231 패키지 (11-08 A~D 작업물은 이전 환경에서 유실되어 포함되지 않음)

## 직접 실행한 검증
- 백엔드 전체 pytest: 596 passed / 0 failed (fastapi 0.115.14, pydantic 2.14.3, starlette 0.46.2, psycopg 3.3.8)
- 프런트 tsc --noEmit: 오류 0 (수정 전 10건)
- npm run test:source: 통과
- vite build: 성공 (68 modules, JS 880KB — 500KB 초과 경고, 코드 분할 미적용)

## 수정 내용
1. requirements.txt: fastapi>=0.115,<1.0 -> fastapi==0.115.14 (fastapi 0.162에서 include_router가 _IncludedRouter로 감싸져 보안 표면 테스트가 라우트를 못 봄, OpenAPI 스냅샷도 달라짐)
2. docs/api/openapi.runtime.v1.json 재생성 (차이는 ValidationError 스키마의 ctx/input 필드 7줄뿐, 앱 API 계약 변경 없음)
3. src/reportGltfParseError.d.mts, src/resourceRollback.d.mts 추가 (tsc TS7016/7031/7006 해소)
4. src/app/main.tsx: 로컬 AuthSession 타입 제거, supabaseAuth.d.mts의 정식 타입 사용 (token_type 누락 불일치 해소)

## 미검증
저장소 코드의 실제 PostgreSQL 실행, TEST Supabase 접속, 브라우저 E2E, CI 실제 실행

## 추가 (ㄱㄱ 이후): 실제 PostgreSQL 16에서 저장소 코드 실행
- 마이그레이션 0001–0010을 로컬 PostgreSQL 16.15에 적용: 오류 0, 테이블 28개 (Supabase 역할 anon/authenticated/service_role과 auth.uid()를 흉내 낸 스텁 사용)
- 신규 tests/test_postgres_live_repositories.py (ACS_TEST_DATABASE_URL 설정 시에만 실행, 일회용 DB 전용): 5건 통과
  마이그레이션 멱등성, 소유자 역할 보호, Project CRUD·역할·타 워크스페이스 차단, Product/Variant SKU 규칙, Project-Product 연결·워크스페이스 간 거부
- 전체 pytest: 601 passed (live 5건 포함)

## 실DB에서 처음 드러난 결함 2건 (가짜 DB 시험은 통과했던 것)
1. postgres_assets.add_workspace_member: ON CONFLICT DO UPDATE 때문에 소유자/관리자가 워크스페이스 소유자의 역할을 덮어쓸 수 있었음 -> 소유자 대상 변경 거부 (PermissionError)
2. postgres_products(3곳)·postgres_project_products(1곳): psycopg 3 Connection에는 executemany가 없음 -> conn.cursor().executemany로 수정. 이 결함 때문에 Product 생성·Variant 생성/수정·Project-Product 연결이 실DB에서 전부 실패했을 것

## 재현
pg_ctl로 로컬 서버 기동 -> 역할/auth 스텁 생성 -> 빈 DB 생성 ->
ACS_TEST_DATABASE_URL=postgresql://postgres@/DB?host=/소켓경로&port=포트 python -m pytest

## 추가 2 (자율 연속 개발): Character·Photo·Lookbook PostgreSQL 재구현
- 마이그레이션 0011·0012·0013 신규 작성, 저장소 3종 신규, 실DB 시험 13건(누적), 전체 pytest 609 통과
- 상세는 CURRENT_HANDOFF_WORK-E.md

## 추가 3: 공통 오류 모듈·선택 레지스트리
- app/repo_errors.py, app/repository_registry.py, tests/test_repo_errors_and_registry.py(25건, 변이 4종 적발)
- 전체: 일반 621 + 실DB 13 = 634 통과

## 추가 4: CI 초안
- .github/workflows/ci.yml (GitHub 미실행, 명령은 로컬 검증), package-lock.json 신규 생성

## 라우트 어댑터 1단계 — Assets 분석 결과 (코드 변경 없음)
- `app/assets/routes.py`(387줄)·`app/assets/store.py`(710줄)는 **바이트 저장(로컬 파일)과 메타데이터가 한 함수 안에 섞여 있음**: `save_asset`이 파일을 쓰고 행을 넣고, `_verified_version_path`가 로컬 경로를 열어 SHA-256·크기를 재계산하며, 서명 URL/미리보기 스트리밍도 `config.ASSET_STORAGE_DIR` 경로에 직접 의존.
- 따라서 Character/Project/Product처럼 "포트 한 겹"으로는 안 되고, **(1) 메타데이터 포트 + (2) 바이트 저장 포트(`app/storage.py`의 `get_storage`와 정합) + (3) 파일↔행 원자성/정리 규칙**을 먼저 설계해야 함. 설계 없이 PG 저장소만 연결하면 파일이 남거나(고아) 행만 남는 상태가 생길 수 있음.
- 알려진 PG 쪽 공백: `create_asset_version` 실패 시 정리, AssetVersion 파일 해시 검증(어댑터 몫), `restore_asset_version`·`audit_workspace_assets`·`workspace_for_asset`·`get_asset_version_record`에 대응하는 PG 메서드 부재(확인 필요), 미리보기 서명 경로.
- 권장 순서: Assets는 설계 문서(`ASSET_STORAGE_PORT_DESIGN.md`) 작성 → 메타데이터 PG 메서드 보강 + 동등성 시험 → 바이트 저장 포트 → 라우트 전환. Photo(950줄)·Lookbook(1321줄)은 Assets 포트에 의존하는 부분(자산 검증·승인된 출력)이 있어 **Assets 이후**가 안전.
- 사용자 승인이 필요한 항목은 없음(내부 설계·구현 작업).

## 라우트 어댑터 — Photo 범위 조사 (2026-11-09, 코드 변경 없음)
- `app/photo_engine.py` 950줄, 라우트 14개(초안 생성/목록/조회/수정/보관 5, 초안 이벤트 1, `process-local` 1, 실행 목록·이벤트 2, 검수 조회·승인·변경요청·반려 4, 매니페스트 내보내기 1).
- PG 저장소(`postgres_photos.py`)에는 초안 CRUD, `claim_local_run`/`complete_local_run`/`fail_local_run`, 실행·이벤트 조회, 검수·내보내기 기록이 이미 있음. **없는 것**: 처리 결과 이미지를 저장하는 `save_derived_image_asset`의 PG 구현(멱등 재시도, 결정적 키, 계보 관계·출처 이벤트 5종 생성).
- 권장 쪼개기: (a) 초안 CRUD·이벤트·실행 목록 7개 라우트 포트 → (b) 검수·내보내기 5개 → (c) `save_derived_image_asset` PG 구현 후 `process-local`. 각 단계마다 SQLite↔PG 동등성 + 변이 시험.
- `process-local`은 클레임(리스) → 이미지 처리 → 파생 자산 저장 → 완료/실패 기록으로 이어져 **중간 실패 시 파일/행/클레임 상태 일관성**이 핵심 위험. 이 단계는 실패 주입 시험이 필수.
- 승인이 필요한 항목 없음(로컬 처리만; 외부 Provider 호출 없음).
