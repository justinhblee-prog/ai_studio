# PostgreSQL 전환: 경합 보호 대체표 (B-05 · D-66c 1단계)

SQLite 전용 모듈 43개가 "확인 후 쓰기"를 지키는 방식과, PostgreSQL(기본 READ COMMITTED, 읽기는 막지 않음)에서 그것을 대체할 구성. **모든 행은 `tests/test_postgres_race_primitives.py`가 진짜 PostgreSQL(CI의 `postgres:16`)에서 동시 연결로 증명**한다(로컬에서는 `ACS_TEST_DATABASE_URL`이 없어 건너뜀). 이 시험은 격리된 임시 스키마만 쓰며 애플리케이션의 DB 백엔드를 PostgreSQL로 열지 않는다(금지선 유지).

| SQLite 쪽(지금) | 쓰는 곳 | PostgreSQL 대체 | 증명하는 시험 |
|---|---|---|---|
| `BEGIN IMMEDIATE` + 개수 확인 후 삽입 | 내보내기 #184, 마켓 신고 한도 #190 | `pg_advisory_xact_lock(hashtextextended(키, 0))` 로 **키별** 직렬화(다른 작업공간은 병렬) | `test_without_a_lock_…`(잠금 없으면 상한 초과가 **결정적으로** 재현) / `test_an_advisory_lock_per_workspace_keeps_the_cap_exact` / `test_the_advisory_lock_of_one_workspace_does_not_block_another` |
| `BEGIN IMMEDIATE` + 읽고 고쳐 쓰기 | 카운터·상태 전이 | `SELECT … FOR UPDATE` | `test_a_plain_read_modify_write_loses_updates_and_for_update_does_not` |
| 부분 유일 인덱스 | 열린 검수 1개 #171 | 같은 문법(`CREATE UNIQUE INDEX … WHERE …`) 그대로 유효 | `test_a_partial_unique_index_lets_exactly_one_open_review_exist` |
| `INSERT OR IGNORE` | 멱등 삽입 21곳 | `INSERT … ON CONFLICT (키) DO NOTHING` (영향 행 수로 승자 판별) | `test_on_conflict_do_nothing_is_idempotent_under_concurrency` |
| `AUTOINCREMENT`·`rowid` | 이력 표 10·23곳 | `GENERATED ALWAYS AS IDENTITY` | `test_identity_columns_give_unique_increasing_ids_under_concurrency` |
| 트리거 `RAISE(ABORT, …)` (추가만 가능 이력) 35곳 | 멤버·설정·검수 이력 | 함수 트리거 `RAISE EXCEPTION` | `test_a_function_trigger_makes_a_history_table_append_only` |
| `add_column`(오류 문자열 의존, #196) | 스키마 초기화 11곳 | `ALTER TABLE … ADD COLUMN IF NOT EXISTS` | `test_add_column_if_not_exists_is_safe_when_many_start_at_once` |
| 새 DB 첫 요청 동시 초기화 | 전부 | 마이그레이션 전체를 한 어드바이저리 락 트랜잭션으로(`app/postgres.py::apply_migrations`, **이미 있음**) | `test_the_real_apply_migrations_survives_eight_first_runs_at_once` (실제 코드, 마이그레이션마다 정확히 1번 적용) |

**아직 없는 것**: 이 표는 *대체 구성이 PostgreSQL에서 성립한다*는 증명일 뿐, 43개 모듈의 어댑터가 아니다. 어댑터가 생기면 각 모듈의 동시성 시험이 위 구성을 쓰도록 하고, SQLite↔PG 동일성 시험(`test_postgres_live_repositories.py` 방식)을 모듈별로 붙인다. 순서는 D-66c: **권한·삭제 묶음**(members·data_export·moderation·legal …) 먼저, 마켓·결제 근접 묶음은 법무 결정 뒤.
