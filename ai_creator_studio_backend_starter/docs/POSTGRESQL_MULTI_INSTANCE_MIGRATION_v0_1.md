# PostgreSQL / Multi-instance 전환 준비 v0.1

- 기준 소스: AI CREATOR STUDIO v0.19
- 범위: SQLite 데이터 스냅샷 추출 및 PostgreSQL 신규 DB 적재 도구, 스키마 변환 검증, 다중 Worker 잠금 설계
- 상태: **Migration bridge 구현 / PostgreSQL 런타임 Adapter 미구현**

## 1. 현재 구현 범위

`../scripts/sqlite_to_postgres.py`는 SQLite DB의 일관된 읽기 트랜잭션에서 사용자 테이블, 인덱스, FK 의존 순서, 행 데이터, 행 수 및 SHA-256을 추출합니다. PostgreSQL DDL 변환은 현재 프로젝트 스키마에서 사용 중인 SQLite 타입 범위(TEXT/INTEGER/REAL/BLOB 및 AUTOINCREMENT)를 대상으로 합니다.

- `export`: Python 표준 라이브러리만 사용
- `import`: `requirements-migration.txt`의 psycopg 3 필요
- 현재 프로젝트에서 사용하는 `BEFORE UPDATE/DELETE ... BEGIN SELECT RAISE(ABORT, 'literal message'); END` 형태의 append-only/immutable trigger는 공통 PostgreSQL trigger function과 row trigger로 변환합니다. 변환된 trigger 이름은 manifest에 기록합니다.
- 위의 제한된 형태가 아닌 trigger, view, virtual table은 export를 fail-closed로 거부합니다. 변환기를 구현하지 않은 객체를 조용히 생략하지 않습니다.
- PostgreSQL DDL importer는 dollar-quoted PL/pgSQL 함수 본문 안의 세미콜론을 보존하는 SQL statement splitter를 사용합니다.
- BUILD-00193부터 migration bundle v2를 사용합니다. Import는 DB 연결 전에 manifest 구조, table/column 식별자, 파일 경로(절대경로·상위 경로·역슬래시·심볼릭 링크 차단), schema/data SHA-256, JSONL 컬럼 집합 및 행 수를 전부 사전 검증합니다. schema SQL과 각 JSONL payload는 검증 후 메모리에 고정해 검증과 사용 사이 파일 교체(TOCTOU)를 방지합니다.
- `schema.postgresql.sql`도 manifest의 `schema_sha256`으로 검증합니다. 이 digest는 bundle 내부 무결성 확인이며 서명된 출처 인증은 아닙니다. 신뢰할 수 없는 bundle은 별도 검토 없이 import하지 않아야 합니다. 기존 bundle v1은 자동 수용하지 않으며 v2로 다시 export해야 합니다.
- JSONL 레코드 구분은 LF(`\n`)만 사용합니다. U+2028/U+2029, NEL, vertical tab 등 JSON 문자열에 유효한 Unicode 구분 문자를 레코드 경계로 오인하지 않습니다.
- Export 대상 디렉터리가 이미 존재하고 비어 있지 않으면 거부합니다. 이전 export의 잔여 파일이 새 bundle에 섞이는 것을 방지하려면 새 빈 디렉터리를 사용해야 합니다. 실제 파일은 동일 파일시스템의 임시 staging 디렉터리에 모두 작성·검증한 뒤 마지막에 rename으로 게시하며, 실패 시 staging을 제거해 부분 bundle을 남기지 않습니다. 대상 경로 자체가 symlink이면 거부합니다.
- Import는 대상 PostgreSQL 현재 schema에 일반/분할 테이블, 뷰, 구체화 뷰, 외부 테이블 또는 sequence가 하나라도 있으면 거부합니다.
- 모든 DDL 및 데이터 적재는 단일 PostgreSQL 트랜잭션 안에서 실행됩니다.
- 각 JSONL 파일의 SHA-256과 테이블별 행 수를 확인한 후 커밋합니다.
- SQLite AUTOINCREMENT 컬럼의 PostgreSQL sequence 값을 데이터 적재 후 복구합니다.
- FK 참조 순서에 따라 부모 테이블부터 적재합니다. FK 순환 구조는 현재 도구가 명시적으로 거부합니다.

## 2. 실행 방법

```bash
# SQLite DB별로 별도 번들 생성
python scripts/sqlite_to_postgres.py export \
  --sqlite ./assets.sqlite3 \
  --out ./migration_bundle/assets

# PostgreSQL import 전용 의존성 설치
pip install -r requirements-migration.txt

# 새로 만든 빈 PostgreSQL DB에 적재
python scripts/sqlite_to_postgres.py import \
  --bundle ./migration_bundle/assets \
  --database-url 'postgresql://USER:PASSWORD@HOST:5432/DATABASE'
```

`GENERATION_DATABASE_PATH`를 `ASSET_DATABASE_PATH`와 분리해 사용했다면 두 SQLite DB를 각각 export하고 각 PostgreSQL 대상에 import해야 합니다. 현재 기본 구성은 두 저장소가 같은 SQLite 파일을 사용할 수 있습니다. 별도 DB로 운영할 때 워크스페이스/멤버십과 Generation Job 간 참조가 분산될 수 있으므로, 런타임 전환 설계에서 DB 경계를 다시 확정해야 합니다.

## 3. PostgreSQL Worker claim 규칙

PostgreSQL 런타임 Repository Adapter를 구현할 때 다음 규칙을 지켜야 합니다.

1. Outbox / Poll Task / Alert Delivery claim은 `SELECT ... FOR UPDATE SKIP LOCKED`와 `UPDATE ... RETURNING`을 하나의 트랜잭션으로 묶습니다.
2. Outbox lease 만료는 Provider가 요청을 수락했을 수 있으므로 `needs_reconciliation`으로 전환하고 자동 재전송하지 않습니다.
3. Poll Task lease 만료는 안전한 상태 조회/출력 저장 작업이므로 정책상 재예약할 수 있습니다. Output 저장은 동일 storage key 기준으로 멱등이어야 합니다.
4. Alert Delivery는 만료 claim을 회수하고 재시도 횟수 상한을 유지합니다.
5. `(workspace_id, idempotency_key)` 고유 제약은 DB에서 최종 보장합니다. 동시 요청은 unique conflict 이후 기존 Job을 다시 읽고 payload hash를 비교해야 합니다.
6. Job 상태 변경은 행 잠금 또는 `version` 조건부 UPDATE를 사용하고, Job / Execution / Event / Outbox / Poll Task의 원자적 경계를 유지합니다.
7. Job이 `SUCCEEDED`가 되는 트랜잭션에는 Output 메타데이터 및 Output 파일의 영속화 확인이 선행되어야 합니다.

권장 Outbox claim 형태(실제 Adapter 구현 시 컬럼/반환 DTO와 통합 검증 필요):

```sql
WITH candidate AS (
    SELECT event_id
    FROM generation_outbox
    WHERE status = 'pending' AND available_at <= CURRENT_TIMESTAMP
    ORDER BY created_at, event_id
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
UPDATE generation_outbox AS task
SET status = 'processing',
    attempts = attempts + 1,
    claimed_by = %(worker_id)s,
    claimed_at = CURRENT_TIMESTAMP,
    lease_expires_at = CURRENT_TIMESTAMP + (%(lease_seconds)s * INTERVAL '1 second')
FROM candidate
WHERE task.event_id = candidate.event_id
RETURNING task.*;
```

## 4. 전환 절차와 무중단 여부

현재 코드에는 PostgreSQL Repository Adapter, 양방향 Dual Write, CDC, 트래픽 전환기, PostgreSQL 통합 테스트 환경이 없습니다. 따라서 **이 버전만으로 무중단 전환을 보장하지 않습니다.** 안전한 1차 이전은 다음 순서의 점검된 유지보수 창이 필요합니다.

1. API와 모든 Worker의 쓰기 중단 및 drain
2. SQLite 최종 스냅샷 export
3. Private asset/output 파일 볼륨 복사 및 파일별 checksum 검증
4. 빈 PostgreSQL DB에 import
5. 테이블별 행 수, FK, 인덱스, sequence, 샘플 Job/Event/Output 교차 검증
6. PostgreSQL Repository Adapter를 적용한 별도 배포본에서 통합/경합 테스트
7. 운영자 승인 후 DB 연결과 Worker를 함께 전환

진정한 무중단 전환은 Adapter 구현 이후 별도 단계에서 Dual Write 또는 CDC 기반 동기화, 최종 cutover barrier, rollback 전략을 구현하고 검증해야 합니다. 현 단계에서 이를 구현했다고 표시하지 않습니다.

## 5. 현재 확인된 한계

- 개발 실행 환경에 Docker, `psql`, PostgreSQL 서버 및 psycopg 3가 설치되어 있지 않아 실제 PostgreSQL 접속/DDL/Import/경합 테스트는 수행하지 못했습니다.
- SQLite export와 PostgreSQL DDL 변환, FK 순서, serial column 식별, 체크섬 및 데이터 행 추출은 자동 테스트했습니다.
- BUILD-00191에서 지원하지 않는 trigger/view/virtual table을 조용히 누락하지 않도록 fail-closed 검사를 추가했습니다.
- BUILD-00192에서 현재 프로젝트의 append-only/immutable `RAISE(ABORT)` trigger subset을 PostgreSQL trigger function으로 변환합니다. `assets.sqlite3`의 44개 테이블/18개 trigger와 별도 `../assets.sqlite3`의 15개 테이블/4개 trigger가 모두 export되었고 각 table JSONL SHA-256이 확인되었습니다. 이는 DDL 생성/번들 검증이며 실제 PostgreSQL import 성공을 의미하지 않습니다.
- BUILD-00193에서 bundle v2 사전검증을 추가하고 경로 조작, symlink, schema/data 변조, JSONL 컬럼 불일치 및 행 수 불일치를 DB 연결 전에 차단합니다.
- BUILD-00196에서 JSONL 파서가 Python `str.splitlines()`의 광범위한 Unicode 분리 규칙을 사용하지 않고 LF만 기준으로 레코드를 분리하도록 수정했습니다. 비ASCII 줄/문단 구분 문자가 포함된 유효한 데이터의 false rejection을 방지합니다. 또한 비어 있지 않은 export 대상 디렉터리를 거부해 stale payload가 번들에 잔류하는 문제를 차단합니다.
- BUILD-00197에서 bundle 생성 전체를 sibling staging 디렉터리에서 수행하고 완료 후 원자적 rename으로 게시하도록 변경했습니다. export 중 오류가 발생해도 불완전한 bundle이 최종 경로에 남지 않으며, destination symlink도 거부합니다.
- SQLite schema migration 버전은 현재 1~5를 데이터로 보존합니다. PostgreSQL용 schema migration runner는 별도 구현 대상입니다.
- 파일 시스템의 private assets/output은 DB bundle에 포함되지 않습니다. 별도 파일 복사와 checksum 검증이 필수입니다.
- 앱의 모든 SQL은 여전히 SQLite 전용이며 API/Worker 런타임은 계속 SQLite를 사용합니다.
- PostgreSQL에서 여러 Worker가 동시에 claim하는 동작은 아직 실행 검증되지 않았습니다.

## 6. 다음 구현 순서

1. Repository Protocol과 DB transaction abstraction 정의
2. Generation Repository PostgreSQL Adapter 구현(placeholder/row mapping 포함)
3. PostgreSQL 전용 schema migration runner 구현
4. PostgreSQL test service 확보 후 두 Worker 이상의 동시 claim 테스트
5. Idempotency, Job transition, Outbox lease, Poll lease, Alert Delivery 경합/rollback 통합 테스트
6. Asset/workspace DB 경계와 파일 저장소 이전 절차 확정
7. Dual Write/CDC 및 cutover/rollback 설계는 별도 승인 게이트로 유지

Credit Quote 및 append-only Credit Ledger는 이 범위에 포함되지 않았으며 미구현 상태를 유지합니다.
