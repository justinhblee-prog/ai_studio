# 개발 진행 기록 v0.40

## 목표
Outbox의 Worker-facing Repository 계약을 전용 모듈로 분리합니다.

## 구현
- `app/repositories/outbox.py`에 Protocol 및 SQLite Adapter를 추가했습니다.
- Worker Composition Root에서 전용 Adapter를 생성하도록 변경했습니다.
- 기존 worker_repositories 이름과 API를 호환 계층으로 유지했습니다.
- PostgreSQL backend 요청은 명시적으로 실패하며 SQLite fallback을 금지합니다.

## 검증
- `python -m pytest -q`: 158 passed
- `python -m compileall -q app scripts tests`: passed
- Viewer `validate_source.py`: 19/19 passed

## 제한
이번 버전은 Repository 경계 추출입니다. Outbox SQL 자체는 아직 `job_repository`의 검증된 트랜잭션 구현을 위임 호출합니다. SQL 이동 및 PostgreSQL 런타임 구현은 완료되지 않았습니다.
