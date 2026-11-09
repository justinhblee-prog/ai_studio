# AI CREATOR STUDIO 개발 진행 기록 v0.25

날짜: 2026-11-02

## 목표
v0.24 Worker Repository Port에 이어 SQLite DDL이 Application Repository 내부에 섞여 있는 구조를 분리한다.

## 변경
- `app/schema_sqlite.py` 추가.
- 기존 `job_repository.initialize()` 내부 DDL을 별도 모듈로 이동.
- Core Job / Outbox / Poll Task / Operations(Alert) schema group으로 분리.
- `initialize_schema()`가 의존성 순서대로 schema group 적용.
- 기존 schema migration marker 1~5 및 `CREATE IF NOT EXISTS` 동작 유지.
- `job_repository.initialize()`는 storage connection을 열고 schema module에 위임.

## 검증
- `PYTHONPATH=. pytest -q`: 122 passed.
- `python -m compileall -q app scripts tests`: passed.
- 3D Viewer 구조 검사: 19/19 passed.
- 스키마 2회 초기화, 테이블 존재, migration marker 유지 검증 추가.

## 제한
SQLite 전용 DDL 분리이며 PostgreSQL DDL 변환이나 런타임 구현이 아니다. 쿼리 본문과 트랜잭션은 아직 monolithic repository에 남아 있다. 무중단 cutover는 수행하지 않았다.

## 다음
1. Outbox/Poll/Operations SQL query를 aggregate별 SQLite repository로 추출.
2. transaction/session 경계와 SQL dialect 추상화.
3. PostgreSQL migration runner 및 adapter, 실서버 테스트.
