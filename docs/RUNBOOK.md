# 운영 런북 (제한된 B2B 파일럿, SQLite 단일 인스턴스)

> **상태**: 이 문서의 명령과 설정은 코드에서 확인했고, 점검·백업·복구 절차는 시험으로 검증했다. 그러나 **실제 배포 환경에서 실행해 본 적은 없다**(배포 대상 정보 없음 — `docs/LAUNCH_STATUS.md` 차단 표 참조). 아래 "cron 예시"처럼 이 문서가 제안하는 운영 절차는 시험하지 않았다.
> 전제: 영속 디스크가 있는 단일 서버. **서버리스 전용 배포라면 SQLite·로컬 파일 저장소 전제가 깨지므로 이 런북은 적용되지 않는다.** Production Supabase/Vercel, 유료 Provider, `DATABASE_BACKEND=postgresql`은 이 파일럿 범위 밖이다.

## 1. 프로세스 (모두 `ai_creator_studio_backend_starter`에서 같은 환경변수로 실행)
| 프로세스 | 명령 | 없으면 |
|---|---|---|
| API | `uvicorn app.main:app` | 서비스 중단 |
| 제출(outbox) 워커 | `python -m app.worker` | 생성 작업이 `queued`에 머묾 |
| Provider 폴링·출력 워커 | `python -m app.poll_worker` | 작업이 `running`에서 끝나지 않음 |
| 출력→자산 연결 워커 | `python -m app.output_asset_link_worker` | 출력이 자산으로 연결되지 않아 검수 불가 |
| 모니터 | `python -m app.monitor_worker` | 알림이 평가되지 않음 |
파일럿은 **단일 인스턴스**다: API를 여러 대로 늘려도 SQLite·로컬 디스크는 공유되지 않는다.

## 2. 주요 설정 (환경변수)
| 변수 | 의미 | 기본값 / 비고 |
|---|---|---|
| `ASSET_DATABASE_PATH` | SQLite DB 파일 | `./assets.sqlite3` — **영속 디스크 위에 둘 것** |
| `GENERATION_DATABASE_PATH` | 생성 작업 DB를 따로 둘 때 | 미설정이면 위 DB 사용 |
| `ASSET_STORAGE_DIR` / `OUTPUT_DIR` | 자산·룩북 ZIP / Provider 출력 폴더 | `./private_assets` / `./outputs` — 백업 대상 |
| `ASSET_SIGNING_SECRET` | 서명 URL 비밀 | **비밀. 저장소·로그에 넣지 말 것** |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | 사용자 토큰 검증 | 둘 다 설정하면 Supabase로 검증. 둘 다 비면 정적 토큰(`ASSET_API_TOKENS`, 개발·시험용) |
| `APP_CORS_ORIGINS` | 허용할 웹 출처 | 쉼표 구분 |
| `PROVIDER_MODE` | `mock`(이미지를 만들지 않음) 또는 실제 Provider | 기본 `mock` |
| `FASHN_API_KEY` | 실제 Provider 키 | **비밀, 유료 호출 발생** |
| `OPS_ADMIN_USER_IDS` | `/internal/ops/*` 접근 사용자 ID | 쉼표 구분. 비어 있으면 아무도 접근 못 함 |
| `REQUIRED_WORKER_TYPES` | 필수 워커 유형 | `outbox,provider_poll,output_asset_link` |
| `WORKER_STALE_AFTER_SECONDS` | 하트비트가 이보다 오래되면 죽은 워커 | 30 |
| `GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE` | 워크스페이스·UTC 하루 생성 작업 상한 | 0 = 무제한. 잘못된 값은 시작 시 오류 |
| `ASSET_REQUIRE_RIGHTS_CONFIRMATION` | 이미지 업로드 시 권리 확인(`rights_confirmed=true`) 강제. **명시적으로 0/false/no/off일 때만 꺼짐**(옛 클라이언트용), 그 외에는 켜짐 | **true** (D2) |
| `LEGAL_REQUIRE_ACCEPTANCE` | 1이면 현재 법률 문서 버전에 동의하지 않은 사용자의 API 호출을 403으로 거절(동의·철회·삭제 요청 경로 제외; 재시작 필요) | 꺼짐 |
| `AI_JOBS_DISABLED` | 킬 스위치(1이면 유료 Provider 새 작업 거부·워커 호출 중단, mock 제외; 재시작 필요) | 미설정 |
| `AI_JOB_LIMIT_PER_WORKSPACE_MONTH` / `AI_JOB_LIMIT_GLOBAL_MONTH` | 유료 Provider 월간 작업 수 상한(0=끔) | 200 / 0 |
| `BACKUP_DIR` | 백업 스크립트의 저장 위치(점검이 최신 백업 나이를 봄) | 미설정이면 점검이 경고 |
| `HEALTH_DISK_WARN_FREE_PERCENT` / `HEALTH_DISK_FAIL_FREE_PERCENT` / `HEALTH_BACKUP_MAX_AGE_HOURS` | 점검 임계값 | 15 / 5 / 26 |
| `ACCESS_LOG_ENABLED` / `ACCESS_LOG_DIR` / `ACCESS_LOG_RETENTION_DAYS` / `ACCESS_LOG_ACTOR` / `ACCESS_LOG_CLIENT_IP` | 접근 로그(3-1절) | true / 표준 출력 / 30(임시) / hash / false |
| `OPS_ALERT_WEBHOOK_URL`, `OPS_ALERT_WEBHOOK_TOKEN` | 알림 웹훅(HTTPS) | 미설정이면 전달 안 함 |

## 3. 상태 점검
- `GET /health` — 공개 생존 확인(`{"ok":true,"version":...}`). **운영 구조·큐 정보는 일부러 안 줌.**
- `GET /internal/ops/health` — **심층 점검**(운영자 전용). 전체 `status`는 `ok` < `warn` < `fail` 중 가장 나쁜 값이고 **`fail`이면 HTTP 503**이라 업타임 모니터에 바로 쓸 수 있다. 확인 항목: DB 파일 존재·읽기·`PRAGMA quick_check`, 저장 폴더 쓰기(1바이트 임시 파일), 디스크 여유 비율, 필수 워커의 신선한 하트비트(+ 수동 조정이 필요한 제출 수), 최신 백업 나이. 파일 경로·비밀은 응답에 없다. 이 점검은 DB가 없을 때 새로 만들지 않는다.
- `GET /internal/ops/workers`, `/internal/ops/alerts`, `/internal/ops/metrics`(Prometheus 형식).
- 워커는 상태 `running`/`idle`/`working`이고 하트비트가 신선하면 "살아 있음"이다(`error`·`stopped`는 아님).

## 3-1. 접근 로그 (L-05)
- 앱이 요청마다 JSON 한 줄을 남긴다(`acs.access` 로거). 항목: UTC 시각, `request_id`(응답 헤더 `X-Request-ID`로도 반환), 메서드, **라우트 템플릿**(원본 경로가 아님), 상태 코드, 소요 시간(ms), `workspace_id`(ID 형식일 때만), `actor`. **쿼리 문자열·헤더·본문·토큰·서명·일치하지 않는 경로는 기록하지 않는다.**
- `actor`는 기본이 **가명 해시**(`h_` + SHA-256 16자리)이고 `ACCESS_LOG_ACTOR=plain|none`으로 바꾼다. 클라이언트 IP는 기본 미기록(`ACCESS_LOG_CLIENT_IP=true`일 때만).
- `ACCESS_LOG_DIR`를 지정하면 `access.log`를 **UTC 자정마다 회전**하고 `ACCESS_LOG_RETENTION_DAYS`개(기본 30, 0은 거부)만 남긴다. 지정하지 않으면 표준 출력.
- **uvicorn의 기본 접근 로그는 쿼리 문자열을 그대로 남긴다**(서명 미리보기·다운로드 URL의 `signature` 포함). 운영에서는 `uvicorn app.main:app --no-access-log`로 끄고 이 로그만 쓴다.
- **보관 기간 30일은 근거 있는 값이 아니라 임시 기본값이다.** 법적 보관 기간·접근 통제·삭제 요청 시의 처리는 정해지지 않았다(`docs/LAUNCH_STATUS.md`). 로그 파일은 백업 대상이 아니다.

## 4. 백업과 복구 (`scripts/backup_restore.py`, 시험으로 검증)
```bash
python scripts/backup_restore.py backup --dest "$BACKUP_DIR"              # 백업 (DB는 온라인 백업 API, 쓰는 중에도 안전)
python scripts/backup_restore.py verify "$BACKUP_DIR/backup-<타임스탬프>"      # 해시 검증
python scripts/backup_restore.py restore "$BACKUP_DIR/backup-<타임스탬프>" --target /srv/acs-restored   # 새 빈 폴더로만 복구
```
- 복구는 **기존 데이터를 절대 덮어쓰지 않는다**(대상이 비어 있지 않으면 거절). 복구 후 출력된 경로를 `ASSET_DATABASE_PATH`·`ASSET_STORAGE_DIR`·`OUTPUT_DIR`로 지정하고 API·워커를 다시 시작한다.
- 파일 영역의 **심볼릭 링크는 따라가지도 복사하지도 않는다**(링크 대상은 백업에 들어가지 않으니, 링크로 연결한 저장소가 있다면 그 실제 위치를 따로 백업해야 한다). `verify`는 매니페스트에 없는 파일이 백업 폴더에 있으면 실패로 보고한다.
- 합성 데이터 기준 소요 시간: 1 GB에서 백업 2.2초·복구 2.7초(로컬 디스크; 실제 서버는 다를 수 있음).
- **자동 스케줄·외부 보관·암호화·보존 기간은 아직 없다.** 하루 한 번 백업을 돌리고 결과를 서버 밖으로 복사하는 것은 운영자가 정해야 한다. 예시(시험하지 않음): `17 3 * * * cd /srv/acs/backend && python scripts/backup_restore.py backup --dest "$BACKUP_DIR"`
- **복구 훈련**: 분기마다 새 폴더로 복구해 `GET /internal/ops/health`와 자산 하나의 미리보기가 정상인지 확인한다(아직 실제 환경에서 해 본 적 없음).

### 점검 스크립트 (`scripts/ops_check.py`, cron·모니터용)
```bash
python scripts/ops_check.py --db "$ASSET_DATABASE_PATH" --backup-dir "$BACKUP_DIR"   # 종료 코드 0 정상 / 1 경고 / 2 치명, --json 가능
```
읽기 전용이다. 하트비트·막힌 작업·월 유료 작업 수(상한의 80%에서 경고, 도달하면 치명)·유예기간 지난 삭제 요청·최신 백업 나이(36시간)를 본다. 알림은 보내지 않으니 종료 코드를 보고 알리는 것은 운영자가 정한다(시험하지 않은 제안).

### 삭제 요청 처리 (`scripts/purge_requests.py`)
```bash
python scripts/purge_requests.py                                   # 유예기간(7일)이 지난 pending 요청의 계획만 출력(dry-run)
python scripts/purge_requests.py --apply --confirm <request_id>    # 요청 하나를 실제 처리 (되돌릴 수 없음)
```
- **실데이터 첫 실행은 사용자 승인이 필요하다.** 먼저 백업(위)을 만들고 dry-run 출력을 확인한다.
- `blocked=`에 `LAST_OWNER`·`JOB_IN_PROGRESS`·`UNMAPPED_TABLE`이 나오면 처리하지 않는다(알 수 없는 표가 생기면 일부러 멈춘다).
- 백업에 남은 사본은 지워지지 않는다. 백업은 30일 뒤 폐기하는 것이 결정이다.

## 5. 장애 대응
| 증상 (심층 점검의 항목) | 원인 후보 | 조치 |
|---|---|---|
| `database_*` fail "missing" | DB 파일 삭제·경로 설정 오류 | 경로 확인 → 없으면 **최신 백업 복구**. 프로세스를 재시작하지 말 것(빈 DB가 새로 생길 수 있음) |
| `database_*` fail "quick_check"/"cannot be read" | 디스크 오류·손상 | API 중지 → 손상 파일 보관(삭제 금지) → 백업에서 복구 |
| `storage_*` fail | 폴더 없음·권한·디스크 가득 | 경로·권한·`disk_space` 확인 |
| `disk_space` warn/fail | 디스크 부족 | 오래된 백업·`cleanup_orphaned_outputs.py`·`cleanup_expired_lookbook_exports.py`로 정리, 용량 증설 |
| `workers` fail "no fresh heartbeat: X" | 워커 X가 죽었거나 DB를 못 읽음 | 해당 프로세스 재시작(`python -m app.<worker>`), 로그 확인 |
| `workers` warn "reconciliation" | 제공자 접수 여부가 불명확한 제출(자동 재전송 안 함) | 제공자 콘솔에서 해당 요청을 확인한 뒤 수동 조정(자동 재시도는 중복 과금 위험) |
| 생성이 429 `DAILY_JOB_LIMIT_EXCEEDED` | 일일 상한 도달 | 의도한 동작. 필요하면 `GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE` 조정 후 API 재시작 |
| 이미지 업로드가 422 `RIGHTS_CONFIRMATION_REQUIRED` | 권리 확인 강제 설정 | 의도한 동작(화면의 체크박스) |
| `backup` warn | 백업이 없거나 오래됨 | 백업 실행, 스케줄 확인 |

## 6. 배포·롤백
1. 먼저 백업하고 `verify`한다. 2. 새 코드를 배포하고 API·워커를 재시작한다(SQLite 스키마는 시작 시 자동 보강된다). 3. `GET /internal/ops/health`가 `ok`(또는 의도한 `warn`)인지 확인한다. 4. 문제가 있으면 코드를 되돌리고, 데이터 문제면 1번의 백업을 새 폴더로 복구한다. **스키마 되돌리기(다운 마이그레이션)는 지원하지 않는다.**

## 7. 이 런북이 다루지 않는 것
실제 Provider 장애 대응(파일럿은 `mock` 또는 소수 사용 전제), PostgreSQL 전환, 개인정보 삭제 요청·침해 신고 절차(L-01, L-08은 미구현 — `docs/LAUNCH_STATUS.md`), 로그의 중앙 수집·법적 보관 정책, 사고 시 연락 체계, 다중 인스턴스.
