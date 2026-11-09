# AI CREATOR STUDIO 개발 진행 기록 v0.33

## 목표
Worker 실행 모듈의 import 시점 Repository singleton 결합을 제거하고, API에서 적용한 DI 원칙을 Worker 프로세스 경계까지 확장한다.

## 변경
- `app/worker.py`: Outbox Worker의 `process_one()`과 `run_forever()`가 Repository를 명시적으로 받도록 변경. 프로세스 루프 시작 시 한 번 생성한 Repository를 반복 실행에 전달.
- `app/poll_worker.py`: 상태 조회, Output 저장, 재시도/소진, heartbeat, poll task 처리를 명시적 Repository 인자로 전달.
- `app/monitor_worker.py`: Alert 평가, webhook dispatch, heartbeat를 명시적 Repository 인자로 전달.
- 세 Worker 모듈의 module-level `job_repository` singleton 제거.
- `WorkerRepositories` composition bundle 및 `build_worker_repositories()` 추가. backend 검증 이후 Outbox/Poll/Operations 어댑터가 같은 legacy SQLite implementation을 공유하도록 구성.
- 기존 단독 함수 호출 호환성을 위해 Repository 인자가 생략된 경우에만 factory를 호출하는 경로 유지.
- 명시적 Repository 주입 시 factory가 다시 호출되지 않는 테스트 추가.

## 검증
- Backend pytest: 143 passed.
- Python compileall: 통과.
- 3D Viewer structural validation: 19/19 통과.

## 제한 및 미완료
- SQLite Worker adapter의 일부 기능은 아직 legacy `job_repository` 구현에 위임됨.
- PostgreSQL runtime adapter 및 실제 PostgreSQL 통합 검증 미완료. PostgreSQL 선택 시 SQLite fallback 없이 fail-closed.
- Credit Quote 및 append-only Credit Ledger 미구현.
- FASHN 실계약/권리/보존/상업 이용 검증 미완료.
- Browser/WebGL/Android E2E 및 Production 배포 검증 미완료.
- QA T-01~T-14 추적성 유지.

## 다음 단계
1. Job/Event 서비스 계층에서 동일 Unit of Work로 상태 변경과 append-only Event 기록을 묶는 경계 정의.
2. SQLite에서 rollback 및 동시성 테스트를 추가하고 기존 Job/Event API 계약 유지.
3. PostgreSQL 서버/드라이버 확보 시 repository adapter와 migration/runtime integration suite를 별도 검증.
