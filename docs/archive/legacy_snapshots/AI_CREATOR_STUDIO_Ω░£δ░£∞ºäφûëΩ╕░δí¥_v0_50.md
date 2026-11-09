# AI CREATOR STUDIO v0.50 개발 진행 기록

## 목표
Worker Health and Queue Count Repository Extraction

## 변경 사항
- Added WorkerHealthRepository with dedicated SQLite reads for worker heartbeat health, Outbox counts, and Poll Task counts.
- `job_repository.worker_health`, `outbox_counts`, and Poll Task count helper now act as compatibility facades.
- Operational snapshot/alert evaluation still owns additional aggregate SQL and is explicitly left for a later extraction.
- Added tests proving health reads and counts bypass the legacy facade.

## 검증 증거
- Backend pytest: 174 passed
- Python compileall: passed
- Viewer structural validation: 19/19 passed

## 미완료 위험
- Operational snapshot/alert evaluation의 집계 SQL은 Legacy 경로에 일부 잔존
- PostgreSQL 런타임 Adapter 및 실제 DB 통합 테스트 미완료
- 프로덕션 무중단 전환 증거 없음
- Credit Quote/Ledger 미구현
- FASHN 계약·권리·보존기간·상업적 이용 검증 미완료
- 프런트엔드 E2E 및 운영 배포 미검증

## 다음 단계
1. Operational snapshot 및 alert evaluation SQL을 전용 Repository로 이전
2. 운영 알림 조회 SQL과 메트릭 집계 SQL 분리
3. 트랜잭션 실패 주입·동시성 테스트 강화
4. PostgreSQL 실제 런타임 테스트 환경 확보 및 구현
