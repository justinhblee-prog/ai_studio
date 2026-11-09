# AI CREATOR STUDIO v0.51 개발 진행 기록

## 변경 사항
- Added `OperationsAlertReadRepository` and a dedicated SQLite read adapter for workspace-independent, bounded alert listing.
- Alert listing SQL and details JSON decoding moved out of `job_repository.py`.
- Existing status filter and 1–200 row limit are preserved.

## 검증
- Backend pytest: 176 passed
- Python compileall: passed
- Viewer structural validation: 19/19 passed

## 잔여 작업
- Operational snapshot 및 alert evaluation 집계 SQL 이전
- PostgreSQL 런타임 및 실제 DB 통합 테스트 미완료
- Credit Quote/Ledger 미구현
- FASHN 권리·계약·보존기간 검증 미완료
- Frontend E2E/운영 배포 미검증
