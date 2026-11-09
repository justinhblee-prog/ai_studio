# AI CREATOR STUDIO 개발 진행 기록 v0.21

## 목표
v0.20 PostgreSQL Migration Bridge 다음 단계로, 실제 저장소 엔진 전환 전에 애플리케이션 저장소 계약을 명시하고 기존 SQLite 동작의 안전성을 보강한다.

## 변경 사항
- `app/repository_contract.py` 추가
  - `GenerationJobRepository` Protocol: Job 생성/조회/상태전이, Outbox/Poll/Alert claim, Worker heartbeat/health, 진단/운영 스냅샷 경계 정의
  - `SQLiteRepository`: 현재 `job_repository` 구현을 감싸는 호환 어댑터
  - `build_repository`: SQLite 선택, PostgreSQL 미지원 명시적 오류, 알 수 없는 backend 거부
- `app/config.py`: `DATABASE_BACKEND` 및 `DATABASE_URL` 환경 설정 추가. 기본 backend는 sqlite.
- `tests/test_repository_contract.py`: Protocol 적합성, PostgreSQL fail-closed, 잘못된 backend 거부
- `tests/test_concurrent_claims.py`: workspace 범위 Idempotency replay 및 Job/Execution/Event/Idempotency/Outbox 원자성 롤백 테스트 추가

## 검증 결과
- `python -m pytest -q`: 111 passed
- `python -m compileall -q app scripts tests`: passed
- `python ai_creator_studio_3d_viewer/scripts/validate_source.py`: 19 structural checks passed

## 설계상 주의
- Protocol/Adapter는 저장소 경계를 정한 기반 단계다. 아직 API/Worker가 Adapter를 통한 의존성 주입으로 완전히 전환된 것은 아니다.
- SQLite `job_repository.py`는 여전히 SQLite 전용 DDL/PRAGMA/placeholder/transaction 문법을 직접 사용한다.
- PostgreSQL 드라이버/서버 실통합, `FOR UPDATE SKIP LOCKED`, 다중 인스턴스 경쟁, 장애 복구 검증은 미실시.
- PostgreSQL backend 요청은 SQLite로 폴백하지 않고 오류를 발생시킨다.
- 이 마일스톤을 무중단 DB 전환 완료로 표현하지 않는다.

## 미해결 / 다음 단계
1. Connection/Transaction Port와 단위별 Repository 분리
2. API 및 Worker의 명시적 Repository DI
3. PostgreSQL adapter + 실제 PostgreSQL 통합 테스트
4. dual-write/CDC 또는 정지-복제-검증-전환/롤백 전략 중 운영 조건에 맞는 cutover 선택
5. Credit Quote / append-only Ledger 구현
6. FASHN live contract/rights/retention/commercial-use 확인
7. Browser/WebGL/Android E2E 및 production deployment 검증

QA T-01~T-14 매핑은 유지하며, 이 작업만으로 기존 QA Gate를 닫지 않는다.
