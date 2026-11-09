# AI CREATOR STUDIO Handoff v3.5 — 2026-11-02

## 현재 기준
v0.22 Storage Port Extraction

## 산출물
- `AI_CREATOR_STUDIO_v0_22_storage_port_extraction.zip`
- `README_v0_22.md`
- `AI_CREATOR_STUDIO_개발진행기록_v0_22.md`
- `ai_creator_studio_backend_starter/app/repository_contract.py`
- `ai_creator_studio_backend_starter/app/storage.py`
- `ai_creator_studio_backend_starter/docs/REPOSITORY_CONTRACT_v0_1.md`

## 완료
- GenerationJobRepository Protocol 및 SQLiteRepository 호환 어댑터 (v0.21)
- StorageBackend Protocol 및 SQLiteStorage (v0.22)
- SQLite 연결 PRAGMA/WAL/timeout 및 BEGIN IMMEDIATE를 Storage Port로 추출
- PostgreSQL backend는 명시적으로 거부, SQLite fallback 금지
- Idempotency workspace isolation/replay 및 create transaction rollback 회귀 테스트

## 검증
- Backend pytest: 114 passed
- Python compileall: passed
- 3D Viewer structural checks: 19/19 passed

## 경계/위험
- SQL/DDL은 여전히 SQLite 전용이며, Storage Port만으로 SQL portability가 생기지 않는다.
- Repository Protocol이 API/Worker 전부에 DI로 적용된 것은 아니다.
- PostgreSQL adapter/server/driver 없음, PostgreSQL integration/concurrency evidence 없음.
- 무중단 DB migration/cutover/rollback rehearsal 미완료.
- SQLite는 single-host PoC이며 multi-host shared filesystem worker에 부적합.

## 다음 작업
1. schema migration runner 및 dialect 분리
2. Job/Outbox/Poll/Alert repository aggregate 추출
3. API 및 Worker의 repository DI 적용
4. PostgreSQL adapter 및 실서버 통합 테스트
5. multi-instance race/lease/recovery 검증
6. 운영 cutover 및 rollback 리허설

## 미해결
- Credit Quote / append-only Credit Ledger
- FASHN live contract/rights/retention/commercial use
- DB 외 private asset/output 복제 및 checksum
- TypeScript/browser/WebGL/Android E2E, production deployment
- QA T-01~T-14 traceability 유지
