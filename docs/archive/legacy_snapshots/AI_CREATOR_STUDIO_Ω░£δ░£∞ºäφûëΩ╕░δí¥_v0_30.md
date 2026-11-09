# AI CREATOR STUDIO 개발 진행 기록 v0.30

## 목표
v0.29에서 확립한 Output 최종 확정 트랜잭션을 독립 Aggregate Repository로 분리합니다.

## 구현
- `app/repositories/output.py`: OutputRepository Protocol 추가
- `app/repositories/sqlite_output.py`: SQLiteOutputRepository 구현
  - Output 조회/기록
  - Poll Task lease 소유권 확인
  - Output upsert + Job succeeded + Execution succeeded + Event append + Poll Task complete 단일 transaction
- `job_repository.py`의 Output 메서드는 하위 호환 facade로 변경
- `SQLitePollRepository`는 전용 OutputRepository adapter를 구성(composition)하여 사용
- 미구현 PostgreSQL Output adapter 선택 시 SQLite로 폴백하지 않고 오류 발생
- Protocol composition 및 PostgreSQL fail-closed 테스트 추가

## 검증
- `python -m pytest -q`: 136 passed
- `python -m compileall -q app scripts tests`: passed
- Viewer `scripts/validate_source.py`: 19/19 passed

## 제한 / 다음 단계
- SQLite only. PostgreSQL 구현 및 실제 서버 검증은 아직 없습니다.
- 바이너리 Output file 저장과 DB commit은 분산 트랜잭션이 아닙니다. 실패 시 Job은 post_processing으로 유지되어 poll task 재시도합니다.
- 다음은 Generation Job/Event 저장소를 같은 방식으로 분리하고, 서비스/API/Worker에서 repository injection을 명시화합니다.
- Credit Quote/Ledger, FASHN 권리·보존·상업적 사용 검증, QA T-01~T-14 미해결 게이트 유지.
