# AI CREATOR STUDIO Handoff v3.4 — 2026-11-02

## 현재 기준 버전
v0.21 Repository Contract Foundation

## 기준 파일
- `AI_CREATOR_STUDIO_v0_21_postgres_repository_contract.zip`
- `README_v0_21.md`
- `AI_CREATOR_STUDIO_개발진행기록_v0_21.md`
- `ai_creator_studio_backend_starter/app/repository_contract.py`
- `ai_creator_studio_backend_starter/docs/POSTGRESQL_MULTI_INSTANCE_MIGRATION_v0_1.md`

## 완료 사항
- Generation Job 저장소용 `GenerationJobRepository` Protocol 정의
- 기존 SQLite 구현을 감싸는 `SQLiteRepository` 어댑터 추가
- backend 선택 설정 명시화 및 PostgreSQL fail-closed
- workspace scoped idempotency replay 및 Outbox insert failure rollback 테스트 추가
- 검증: pytest 111 passed, compileall passed, 3D Viewer 19/19 passed

## 현재 구현 경계와 주의점
- Adapter는 현재 legacy SQLite module을 감싸는 단계이며 API/Worker 전반에 DI를 적용한 상태가 아니다.
- `job_repository.py`의 SQL/DDL/transaction은 SQLite 전용이다.
- PostgreSQL runtime adapter 없음. PostgreSQL live server/driver 검증 없음.
- 따라서 PostgreSQL 운영 전환 또는 무중단 전환 완료가 아니다. PostgreSQL backend는 fail-closed.
- SQLite는 여전히 단일 호스트 PoC이며 공유 NFS/다중 호스트 worker 용도로 사용하지 않는다.

## 다음 실행 순서
1. SQL Connection/Transaction Port 분리
2. Job/Outbox/Poll/Alert repository를 aggregate 단위로 분리
3. API/Worker에 repository DI 적용
4. PostgreSQL adapter 및 실제 PostgreSQL 통합 테스트
5. 다중 인스턴스 claim/idempotency/recovery 검증
6. cutover 및 rollback runbook 완성

## 계속 열려 있는 항목
- Credit Quote 및 append-only Credit Ledger 미구현
- FASHN live contract, rights, retention, commercial use 검증 필요
- asset/output 파일은 DB migration bundle과 별도 복제 및 checksum 검증 필요
- TypeScript/browser/WebGL/Android E2E 및 production deployment 미검증
- QA T-01~T-14는 추적 유지, 미검증 Gate를 완료 처리하지 않음

## 이어서 작업할 때
v0.21 ZIP을 기준으로 진행한다. SQLite 기존 동작을 유지하면서 Port/DI를 단계적으로 도입한다. PostgreSQL로 DSN만 바꾸는 식의 가짜 전환을 하지 말고, 실서버 통합 테스트가 없으면 미검증으로 명시한다.
