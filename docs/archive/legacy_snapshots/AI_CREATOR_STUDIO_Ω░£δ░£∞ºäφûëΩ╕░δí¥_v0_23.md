# AI CREATOR STUDIO 개발 진행 기록 v0.23

## 목표
v0.22에서 분리한 Storage Port를 Generation Job 영역에만 한정하지 않고 Asset/Workspace 메타데이터 연결 경로에도 적용한다.

## 변경
- `app/assets/store.py`의 직접 `sqlite3.connect` 호출 제거
- `app.storage.get_storage()`를 통해 Asset DB 연결 생성
- SQLite foreign key / busy timeout / WAL 설정을 공통 어댑터에 위임
- PostgreSQL 선택 시 Asset 저장소도 SQLite로 폴백하지 않고 명시적 RuntimeError 발생
- Storage Port 통합 테스트 2개 추가
- SQL dialect 분리 전 현재 SQLite 전용 구문과 비목표를 문서화

## 검증 증거
- `python -m pytest -q`: 116 passed
- `python -m compileall -q app scripts tests`: passed
- 3D Viewer `validate_source.py`: 19 structural checks passed

## 미완료 / 차단
- PostgreSQL 드라이버 및 런타임 Repository Adapter 미구현
- 실제 PostgreSQL 서버 기반 트랜잭션/동시성/장애 복구 검증 미실시
- SQL placeholder, `INSERT OR IGNORE`, SQLite 예외 처리 및 claim 쿼리 방언 분리 미완료
- Credit Quote / append-only Credit Ledger 미구현
- FASHN 실계약, 권리, 보존기간, 상업적 사용 조건 검증 미완료
- TypeScript 빌드, 브라우저/WebGL, Android E2E 및 운영 배포 검증 미완료
- QA T-01~T-14의 기존 미해결 상태 유지

## 다음 단계
1. Asset/Workspace Repository 경계를 추출하고 SQL dialect/placeholder 정책을 분리한다.
2. Generation Job, Outbox, Poll Task, Alert Delivery의 저장소별 쿼리를 집계 단위로 분리한다.
3. PostgreSQL 서비스 환경이 확보되면 동일 계약 테스트를 SQLite/PostgreSQL 양쪽에 실행한다.
4. 다중 인스턴스 claim, idempotency, 롤백, 재시작/lease 회복을 실제 PostgreSQL에서 검증한다.
5. Dual-write/CDC/컷오버/롤백 설계를 별도 승인 게이트로 다룬다.
