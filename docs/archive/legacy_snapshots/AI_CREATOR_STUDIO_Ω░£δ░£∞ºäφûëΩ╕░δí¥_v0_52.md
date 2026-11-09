# AI CREATOR STUDIO v0.52 개발 진행 기록

## 변경 사항
- Added `OperationsMonitoringRepository` and a dedicated SQLite adapter for bounded operational snapshots and alert evaluation.
- Worker heartbeat, Outbox/Poll aggregate counts, oldest queue age, alert aggregates, and delivery aggregates now live behind the monitoring repository.
- Alert fingerprint create/update/resolve logic now executes in the dedicated repository transaction.
- Legacy `operational_snapshot` and `evaluate_operational_alerts` are compatibility facades.
- Added tests proving the legacy monitoring facade is bypassed and repeated evaluation does not duplicate active fingerprints.

## 검증
- Backend pytest: 178 passed
- Python compileall: passed
- Viewer structural validation: 19/19 passed

## 잔여 작업
- Prometheus 메트릭 출력 경계 점검 및 전용 read model 정리
- PostgreSQL 런타임 Adapter 및 실제 DB 통합 테스트 미완료
- Credit Quote/Ledger 미구현
- FASHN 권리·계약·보존기간 검증 미완료
- Frontend E2E 및 운영 배포 미검증
