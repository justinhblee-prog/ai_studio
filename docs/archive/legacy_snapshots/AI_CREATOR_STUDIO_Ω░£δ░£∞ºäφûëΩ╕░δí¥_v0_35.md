# AI CREATOR STUDIO 개발 진행 기록 v0.35

## 목표
수동 Provider submission reconciliation도 Job/Event 원자적 애플리케이션 서비스 경계로 통합한다.

## 변경
- `JobEventUnitOfWork`에 `reconcile_unknown_submission` 명령 추가.
- `JobLifecycleService`가 reconciliation 명령을 UoW에 위임.
- `dependencies.py`에 캐시된 `get_job_event_uow` 및 `get_job_lifecycle_service` 추가.
- `POST /v1/generation-jobs/{job_id}/reconciliation`이 legacy JobRepository 메서드 대신 lifecycle service를 사용하도록 변경.
- 기존 owner/admin 권한, action/payload validation, conflict 응답 및 JobResponse 계약 유지.
- SQLite 구현의 기존 단일 transaction 안에서 Job 상태/attempt 변경과 audit Event가 함께 기록되는 구조 유지.

## 검증
- Backend pytest: 148 passed.
- Python compileall: 통과.
- Viewer structural validation: 19/19 통과.
- 기존 수동 reconciliation API 테스트 전체 통과.

## 제한 및 미완료
- SQL 및 transaction 소유권은 SQLite legacy 구현에 남아 있으며 UoW adapter는 이를 호출한다.
- PostgreSQL runtime adapter 및 실제 서버 통합 검증 미완료. PostgreSQL 선택은 fail-closed.
- Credit Quote 및 append-only Credit Ledger 미구현.
- FASHN 실계약/권리/보존/상업 이용 검증 미완료.
- Browser/WebGL/Android E2E 및 Production 배포 검증 미완료.
- QA T-01~T-14 추적성 유지.

## 다음 단계
1. Job/Event의 SQL 구현을 별도 adapter로 이동하고, legacy compatibility facade를 점진적으로 축소한다.
2. reconciliation 및 lifecycle command에 대한 rollback/동시성 테스트를 계속 확장한다.
3. PostgreSQL 서버/드라이버 확보 시 실제 transaction, row lock, lease, idempotency 및 multi-instance 검증을 수행한다.
