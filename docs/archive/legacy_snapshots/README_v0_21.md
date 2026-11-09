# AI CREATOR STUDIO v0.21 — Repository Contract Foundation

## 이번 마일스톤
- Generation Job 저장소의 애플리케이션 경계인 `GenerationJobRepository` Protocol을 정의했습니다.
- 기존 SQLite 구현을 `SQLiteRepository` 어댑터로 감싸 기존 SQL/트랜잭션 동작을 변경하지 않았습니다.
- `DATABASE_BACKEND` 선택을 명시화했습니다. `sqlite`만 활성화되어 있으며 `postgresql`은 준비되지 않은 상태에서 즉시 실패합니다. SQLite로 자동 폴백하지 않습니다.
- workspace 범위 Idempotency 재생/분리와 Job 생성 중 Outbox 쓰기 실패 시 전체 롤백 회귀 테스트를 추가했습니다.

## 검증
- Backend pytest: **111 passed**
- Python compileall: 통과
- 3D Viewer 구조 검사: **19/19 통과**

## 중요한 한계
이 마일스톤은 PostgreSQL Repository Adapter가 아닙니다. 현재 핵심 저장소는 SQLite 전용 SQL(`BEGIN IMMEDIATE`, `INSERT OR IGNORE`, `?` placeholder, SQLite DDL/PRAGMA)을 사용합니다. API 및 Worker가 아직 이 Protocol을 통해 저장소를 주입받도록 전환되지 않았고, PostgreSQL 실서버/드라이버 통합 검증도 수행하지 않았습니다. `DATABASE_BACKEND=postgresql`은 의도적으로 fail-closed 처리됩니다.

## 다음 작업
1. Job Repository의 SQL/트랜잭션 사용처를 단위별로 분리하고 Connection/Transaction Port를 설계합니다.
2. SQLite 구현을 Port 뒤로 이동하면서 API/Worker 의존성을 주입 방식으로 전환합니다.
3. PostgreSQL DDL 및 SQL dialect를 별도 구현하고 실제 PostgreSQL 서비스에서 idempotency, rollback, SKIP LOCKED lease claim, multi-instance race를 검증합니다.
4. 그 이후에만 PostgreSQL 운영 전환 및 무중단 cutover 설계를 실행합니다.

기존 QA T-01~T-14의 통과 상태를 새로 선언하지 않았습니다. FASHN 계약/권리/보존기간 검증, Credit Quote/Ledger, TypeScript/browser/WebGL/Android E2E 및 운영 배포 검증은 미해결입니다.
