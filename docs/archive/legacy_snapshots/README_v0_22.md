# AI CREATOR STUDIO v0.22 — Storage Port Extraction

## 이번 마일스톤
- v0.21의 GenerationJobRepository Protocol / SQLiteRepository 경계를 유지했습니다.
- `app/storage.py`에 저수준 `StorageBackend` Port를 추가했습니다.
- SQLite 연결 생성(PRAGMA, WAL, busy timeout, foreign keys)과 쓰기 트랜잭션 시작(`BEGIN IMMEDIATE`)을 `SQLiteStorage`로 격리했습니다.
- `job_repository._connect()`와 모든 쓰기 트랜잭션 시작을 Storage Port를 통해 수행하도록 변경했습니다.
- PostgreSQL 선택은 계속 fail-closed이며 SQLite 자동 폴백은 없습니다.

## 검증
- Backend pytest: **114 passed**
- Python compileall: 통과
- 3D Viewer 구조 검사: **19/19 통과**

## 한계
SQL 스키마/쿼리 자체는 아직 SQLite 전용입니다. `executescript`, `INSERT OR IGNORE`, qmark placeholder, SQLite DDL 및 row 타입 의존성이 남아 있습니다. API/Worker의 전체 Repository DI도 아직 완료되지 않았습니다. 따라서 PostgreSQL 런타임/무중단 전환이 아닙니다.

## 다음 단계
1. SQL dialect 및 schema migration runner 분리
2. Job / Outbox / Poll / Alert aggregate repository 분리
3. API/Worker에 명시적 Repository DI 적용
4. PostgreSQL adapter 구현 및 실서버 테스트
5. 다중 인스턴스 경쟁·복구 및 cutover rehearsal
