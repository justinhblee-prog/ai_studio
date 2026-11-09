# AI CREATOR STUDIO 개발 진행 기록 v0.29

## 목표
Generation Job이 `succeeded`가 되기 전에 Output 메타데이터와 API 참조가 DB에 확정되어야 한다는 핵심 상태 불변식을 실제 Worker 경로에서 보장합니다.

## 구현
1. `job_repository.finalize_output_success()` 추가
   - Poll Task의 `processing`, `claimed_by`, `persist_output` 소유권 확인
   - Output upsert
   - Job `post_processing -> succeeded` 및 `output_url` 기록
   - 최신 Execution `succeeded` / `finished_at` 기록
   - `OUTPUT_PERSISTED` Event 기록
   - 동일 트랜잭션에서 Poll Task 완료 처리
2. `poll_worker._process_output()`에서 기존 3개 독립 commit 호출을 원자적 단일 메서드로 교체
3. Poll Repository Protocol 및 SQLite adapter에 메서드 계약 추가
4. SQLite SQL 문장을 `app/sql/sqlite_worker.py`에 명시적으로 분리
5. 성공 및 중간 DB 쓰기 실패를 주입한 롤백 테스트 추가

## 검증
- `python -m pytest -q`: 134 passed
- `python -m compileall -q app scripts tests`: passed
- Viewer `scripts/validate_source.py`: 19/19 passed

## 제한 / 다음 작업
- DB 트랜잭션만 원자적입니다. 바이너리 Output 파일 저장은 DB transaction 이전에 수행됩니다. DB commit 실패 시 Job은 `post_processing`에 남고 durable poll task가 재시도합니다. 재시도는 같은 job output 파일을 덮어쓸 수 있습니다.
- PostgreSQL 실서버 및 다중 인스턴스 검증은 아직 수행하지 않았습니다.
- 다음은 Job/Event/Output Repository 경계 분리 및 PostgreSQL용 동일 불변식 통합 테스트입니다.
- Credit Quote/Ledger, FASHN 권리·보존·상업적 사용 확인, QA T-01~T-14의 미해결 게이트는 유지합니다.
