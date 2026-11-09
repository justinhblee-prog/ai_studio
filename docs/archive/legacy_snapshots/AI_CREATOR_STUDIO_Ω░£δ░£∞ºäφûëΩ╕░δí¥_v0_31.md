# AI CREATOR STUDIO 개발 진행 기록 v0.31

## 작업 목표
Generation Job 및 Event 저장소 경계를 분리하고 API 라우트에 의존성 주입을 적용한다.

## 구현
1. `app/repositories/job.py`
   - `JobRepository` Protocol: create/get/get_idempotent/transition/update.
   - `SQLiteJobRepository`: 기존 `job_repository` 구현을 감싸는 호환 어댑터.
2. `app/repositories/event.py`
   - append-only lifecycle Event 조회용 `EventRepository` Protocol.
   - `SQLiteEventRepository` 어댑터.
3. `app/dependencies.py`
   - API composition root에서 Job/Event Repository를 캐시해 제공.
   - `DATABASE_BACKEND=postgresql`은 구현 미완료 오류로 fail-closed.
4. `app/main.py`
   - Job 생성, 조회, 이벤트 조회 경로에 FastAPI `Depends` 적용.
   - 기존 이벤트 API 응답의 execution/output/outbox/poll 진단 필드 유지.
5. Protocol 준수, 어댑터 위임, dependency 캐시 동작 테스트 추가.

## 검증 결과
- Backend pytest: 139 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## 제한 및 미해결
- SQLite 어댑터는 기존 SQLite SQL 구현을 위임 호출한다. SQL 구현 전체가 새 저장소 모듈로 이전된 것은 아니다.
- PostgreSQL Repository 구현 및 실제 PostgreSQL 서버 통합 검증은 아직 수행하지 않았다.
- Multi-instance PostgreSQL claim/lease/transaction 테스트 미완료.
- Zero-downtime Dual Write/CDC/cutover/rollback 미구현.
- Credit Quote/Ledger 미구현.
- FASHN 라이브 권리·계약·보존기간·상업적 이용 검증 미완료.
- Browser/WebGL/Android E2E 및 production 배포 검증 미완료.
- QA T-01~T-14 추적성을 유지하며 미검증 게이트를 완료 처리하지 않는다.

## 다음 단계
- Event append와 Job lifecycle 변경의 쓰기 경계를 추가로 분리하되 append-only/transactional 보장을 유지한다.
- API의 나머지 Job 관련 route와 Worker entrypoint를 composition root로 이전한다.
- PostgreSQL 드라이버/서버 환경을 확보한 뒤 SQL 방언, `FOR UPDATE SKIP LOCKED`, idempotency unique constraint, transaction isolation을 실제 통합 테스트한다.
