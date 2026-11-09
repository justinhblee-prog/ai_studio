# AI CREATOR STUDIO v0.20 — PostgreSQL Migration Bridge

v0.20은 v0.19 SQLite 단일 호스트 PoC의 데이터를 PostgreSQL 신규 DB로 옮기기 위한 오프라인 Migration Bridge를 추가합니다.

## 신규 항목

- `ai_creator_studio_backend_starter/scripts/sqlite_to_postgres.py`
  - SQLite snapshot export
  - PostgreSQL DDL 변환
  - FK 순서 기반 JSONL 데이터 export
  - SHA-256 및 row count 검증
  - psycopg 3 기반 empty-schema import
  - AUTOINCREMENT sequence 복구
- `ai_creator_studio_backend_starter/requirements-migration.txt`
- `ai_creator_studio_backend_starter/tests/test_sqlite_to_postgres_migration.py`
- `ai_creator_studio_backend_starter/tests/test_concurrent_claims.py` (SQLite 단일 호스트 동시 claim 회귀 테스트)
- `ai_creator_studio_backend_starter/docs/POSTGRESQL_MULTI_INSTANCE_MIGRATION_v0_1.md`

## 중요한 범위 제한

**API와 Worker는 아직 PostgreSQL을 사용하지 않습니다.** 기존 SQLite 런타임과 v0.19의 API/Worker 프로세스 토폴로지를 유지합니다. 이 릴리스는 데이터 이전 준비 단계이며 PostgreSQL 런타임 Adapter나 무중단 cutover를 구현한 릴리스가 아닙니다.

## 테스트

- Backend pytest: 106 passed
- 동시 claim 회귀: Outbox / Poll Task / Alert Delivery 각각 12개 경쟁 호출에서 단일 claim 확인 (SQLite only)
- Python compileall (`app`, `scripts`, `tests`): passed
- SQLite 실제 DB export: 14 tables / 5 rows 추출 확인
- PostgreSQL live import/concurrency: 환경 부재로 미실행
- 3D Viewer 구조 검증: 19/19 (v0.19와 동일 소스; 새 Viewer 변경 없음)

## 기준 버전

- v0.19 ZIP SHA-256: `3c9b755990da6b65f0d2621c36f68fde34a839efcae4592dd4f9ebd00f78c9de`
- API version: 0.7.0 (변경 없음)
