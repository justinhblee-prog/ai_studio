# AI CREATOR STUDIO — 최신 인수인계 (WORK-20261108-E)

> 이 문서가 최신입니다. 프로젝트의 기존 `CURRENT_HANDOFF.md`(BUILD-00231 + WORK A~D)는 **소스가 유실된 작업**을 기술하고 있어 현재 코드와 일치하지 않습니다(아래 §2). 설계·조사 문서(PRD, 시장조사, 라우트 어댑터 설계서)는 유효합니다.

## 1. 기준선과 위치
- 소스 기준선: `AI_CREATOR_STUDIO_FINAL_PACKAGE_BUILD-00231.zip` (사용자 폴더 `1. AI Studio/discern/`)
- 이번 결과: `AI_CREATOR_STUDIO_WORK_20261108E.zip` (사용자 폴더 `1. AI Studio/`)
- 백엔드: `src/ai_creator_studio_backend_starter`, 프런트: `src/ai_creator_studio_3d_viewer`

## 2. 유실 사실 (정직한 보고)
11-08에 이전 작업 환경에서 만든 A~D 산출물(랜딩 재구현·KO/EN·토큰, 공통 오류 모듈, 저장소 선택 레지스트리, Asset 버전 보강, CI 초안, 이전 마이그레이션 0011–0013 소스 등)은 사용자 폴더에 저장되지 않아 복구할 수 없습니다. 마이그레이션 0011–0013과 저장소는 **이번에 처음부터 다시 구현**했습니다. 나머지는 `tasks.json`에서 진행예정으로 되돌렸습니다.

## 3. 이번에 직접 실행해 확인한 것
| 항목 | 결과 |
|---|---|
| 백엔드 전체 pytest | **634 passed / 0 failed** (일반 621 + 실DB 13) |
| compileall | OK |
| 실제 PostgreSQL 16.15에 마이그레이션 0001–0013 적용 | 오류 0, 테이블 45개, 전부 RLS 활성, anon/authenticated 권한 0 |
| 실DB 저장소 시험 | 13건 통과 (Project·Product·Variant·Assignment·Character·Photo·Lookbook) |
| 동시성 | 8스레드 동시 claim에서 단일 승자(변이 시험으로 잠금 제거 시 실패 확인) |
| 프런트 `tsc --noEmit` | 오류 0 (수정 전 10건) |
| `npm run test:source` / `vite build` | 통과 / 성공 (JS 880KB, 500KB 경고) |

## 4. 수정·추가 내용
1. `requirements.txt`: `fastapi==0.115.14` 고정. FastAPI 0.162에서는 `include_router`가 `_IncludedRouter`로 감싸져 보안 표면 시험이 라우트를 못 보고 OpenAPI 스냅샷도 달라짐. 스냅샷은 고정 버전에서 재생성(차이 7줄, 전부 프레임워크 생성 ValidationError 스키마).
2. 보안: `postgres_assets.add_workspace_member`가 `ON CONFLICT DO UPDATE`로 소유자 역할을 덮어쓸 수 있던 결함 수정.
3. psycopg 3 호환: `Connection.executemany` 부재로 Product·Variant·Project-Product 쓰기 경로 4곳이 실DB에서 실패할 코드였음 → `conn.cursor().executemany`.
4. 프런트: `reportGltfParseError.d.mts`·`resourceRollback.d.mts` 추가, `main.tsx`가 정식 `AuthSession` 타입 사용.
5. 신규 마이그레이션: `0011_characters`, `0012_photo`, `0013_lookbook`. 설계 포인트 — 워크스페이스 일치는 DB 트리거와 복합 FK로 강제, 이벤트·산출물은 append-only 트리거, "최신 결정"은 SQLite `rowid` 대신 `seq` 식별 컬럼.
6. 신규 저장소: `postgres_characters.py`, `postgres_photos.py`, `postgres_lookbooks.py`.
7. 신규 시험·러너: `tests/test_postgres_live_repositories.py`, `scripts/run_live_pg_tests.sh`.
8. 공통 오류 모듈 `app/repo_errors.py`: 멤버 아님→404, 권한 부족→403, 충돌→409, 검증→422, DB 오류는 SQLSTATE로만 분류하고 드라이버 문구는 노출하지 않음. 신규 저장소 3종은 이를 사용하고, 충돌 오류는 `RepositoryConflictError` 하나로 단일 출처화.
9. 선택 레지스트리 `app/repository_registry.py`: 집계별 상태(live_verified/unverified/partial/missing)를 기록하고, 모든 집계가 live_verified가 되기 전에는 `postgresql` 선택을 거부(SQLite 대체 금지). 라우트·DI에는 아직 연결하지 않음. 시험: `tests/test_repo_errors_and_registry.py` 25건, 변이 4종 모두 적발.

10. CI 초안 `.github/workflows/ci.yml`: 백엔드(Python 3.13, `postgres:16` 서비스, 실DB 시험이 건너뛰어지면 실패) + 프런트(`npm ci`, `tsc`, `test:source`, `build`). 안에 든 명령은 모두 로컬에서 실행해 통과했지만 **GitHub에서는 실행하지 않았음**. 저장소 루트는 이 패키지의 `src/`를 가정.
11. `ai_creator_studio_3d_viewer/package-lock.json` 신규 생성(원본 패키지에는 없었음, `package.json`은 변경 없음). 현재 npm 레지스트리 기준으로 만든 잠금 파일이므로 처음 한 번 검토 후 유지 여부를 결정.

## 5. 재현
```
cd src/ai_creator_studio_backend_starter
pip install -r requirements.txt
python -m pytest -q                                  # 전체 (실DB 시험은 건너뜀)
PYTHON=python bash scripts/run_live_pg_tests.sh      # 임시 PG 클러스터에서 실DB 시험 13건 (PG 16 바이너리 필요)
cd ../ai_creator_studio_3d_viewer && npm install && npx tsc --noEmit && npm run test:source && npm run build
```

## 6. 아직 하지 않은 것 (완료로 보고 금지)
- API 런타임은 여전히 SQLite. PG 저장소는 어느 라우트에도 연결되지 않음. `DATABASE_BACKEND=postgresql` 활성화 금지.
- 마이그레이션 0011–0013은 **로컬 PG에만** 적용. Supabase TEST 적용은 접속 정보·승인 필요.
- 파일 수준 무결성 검증(AssetVersion 파일 해시)과 패키지 생성은 어댑터 몫이라 PG 저장소에 없음.
- 랜딩 재구현, 브라우저 E2E, 실 Provider, 3D·가상 피팅, GitHub에서의 CI 실제 실행.

## 7. 다음 작업 순서
1. 라우트 어댑터 1단계 진행: 완료 = Workspace 권한 포트, Character, Project, Project↔Product, Products(라우트 10개), Workspaces(라우트 3개), Assets 메타데이터 라우트와 **바이트 라우트**, **Photo 14개 라우트 전부(`app/ports/photos.py`: 초안·이벤트·실행 목록 8개, 검수·내보내기 5개, process-local 1개)**(업로드·새 버전·복원·무결성 감사·삭제 시 파일 제거·미리보기 경로 조회)(각각 SQLite↔PG 동등성 시험 + 변이 시험). 남음 = `save_derived_image_asset`(Photo 엔진이 사용), Photo, Lookbook
2. (위 1에 포함: 레지스트리를 DI에 연결하되 런타임은 SQLite 유지)
3. Workspace·Asset PG 저장소 보강(`create_asset_version` 정리 등) 및 실DB 시험
4. Job·Worker·Output 경합 시험
5. 랜딩 재구현(시안 ①), CI 초안
6. (승인 후) TEST Supabase에 0011–0013 적용, 2인 격리 시험

## 8. 승인 경계 (불변)
Production Supabase/Vercel 변경 금지, 유료 Provider 호출 금지, `DATABASE_BACKEND=postgresql` 활성화 금지, 비밀정보·키 요구 시 사용자 확인.

## 9. 동작 변경 기록 (라우트 어댑터 1단계에서 의도적으로 바뀐 것)
- Products 라우트: 권한 확인을 상품 조회보다 먼저 수행. 비멤버가 없는 상품을 조회하면 이전 "Product not found" 대신 "Workspace not found"(둘 다 404). 상태 코드는 동일.
- PG 상품 저장소: 보관된 상품의 변형 목록은 SQLite와 같이 404(이전엔 200). 이 차이는 동등성 시험이 찾아냄.
- PG 상품 저장소에 `update`·`archive`·`list_events` 신규 구현(이전엔 SQLite에만 있었음). `archive`는 활성 Lookbook 초안/활성 Project 배정이 있으면 409, 활성 변형을 함께 보관.
- 구조화된 422 본문(`{code, message}`)은 `DetailedValueError`로 보존.
- 검증되지 않은 것: `archive`/`update`의 행 잠금(FOR UPDATE)은 동시성 시험이 없음(변이로 확인 안 됨). Lookbook 생성과 상품 보관 사이의 경합도 미시험.
- Workspaces: PG 저장소를 레거시 계약에 맞춤 — 멤버 재추가·소유자 재추가는 409(이전 PG는 역할을 덮어씀), 목록은 최신순(이전 PG는 오래된 순), 생성 응답에 `role` 포함, 비멤버/없는 워크스페이스는 404 "Workspace not found", 낮은 역할은 403, 중복 ID는 409 "Workspace ID already exists".
- SQLite 전용 배포는 psycopg 없이 import 되어야 함: 포트는 PG 모듈을 지연 import 해야 하며 이를 회귀 시험으로 고정(변이로 확인).
- Assets 메타데이터(PG 저장소 수정 — 동등성 시험이 찾은 것): `list_assets(kind=image|model)`가 PG에서 500(LIKE의 `%` 미이스케이프), **`soft_delete_asset`에 참조 보호가 전혀 없었음**(활성 상품·변형·Photo/Lookbook 초안·생성 출력물이 쓰는 자산도 삭제 가능) → 레거시와 같은 5종 보호 + 409로 정렬, 관계 생성에 `derived_from` 순환 검사·중복 409·양쪽 출처 이벤트 추가, 출처 이벤트명 `asset.uploaded`/`asset.deleted`로 정렬, 관계 목록 최신순, `kind=model`은 `model/*`만.
- 아직 PG에서 미검증/미구현: 자산 삭제 시 **파일 바이트 삭제는 하지 않음**(메타데이터만; B 단위), 상품 생성과 자산 삭제 사이의 경합(트리거가 자산 행을 잠그지 않음) 미시험, Supabase Storage 구현 없음.
- 알려진 불일치: 레지스트리의 `workspace_and_asset_metadata`는 여전히 PARTIAL(바이트 포트 전까지 유지).
- Assets 바이트 포트(`app/ports/asset_bytes.py`, `app/assets/blob_store.py`): 규칙 = ① 객체를 배타적으로 쓰고 ② 메타데이터 트랜잭션을 커밋하고 ③ ②가 실패하면 ①의 객체를 삭제. 삭제는 행 변경 커밋 **후** 파일 제거. PG 쪽 `create_asset_version`이 `original_filename/gltf_version/embedded_binary` 갱신과 `previous_version` 기록을 하지 않던 것을 레거시와 맞춤.
- 라우트 권한 확인(`app.assets.routes.require_role`)이 이제 워크스페이스 포트를 통함 → Photo/Lookbook/Main이 이 함수를 import하므로 해당 권한 확인도 같은 백엔드를 봄(SQLite 동작은 동일).
- **기존 테스트 1건 수정**: `test_authenticated_asset_version_preview_content_rechecks_membership`가 내부 지점 `asset_routes.workspace_role`을 덮어써 "멤버십 취소 → 404"를 확인했음. 그 지점이 포트로 이동해서 `SQLiteWorkspacePort.role`을 덮어쓰도록 변경(검증 의도는 동일).
- 미검증/미구현: Supabase Storage 구현 없음(TEST 환경 없음), 서명 미리보기의 검증된 경로 조회(`_verified_version_path`)는 로컬 디스크 전용 코드가 라우트에 남아 있음, `save_derived_image_asset` PG 구현 없음, 자산 삭제와 상품/초안 생성 사이의 경합 미시험, 파일 삭제 실패 시 남는 고아 파일을 정리하는 작업 없음.
- **Photo (a)단계** (`app/ports/photos.py`, 8개 라우트): 권한 확인을 초안 조회보다 먼저 수행(비멤버 → 404 "Workspace not found", 읽기 전용 역할의 쓰기 → 403; 이전에는 없는 초안이면 역할과 무관하게 404 "Photo Draft not found"). PG 저장소를 레거시 계약에 맞춤: 이벤트 페이지 상한 200→500(라우트와 동일, 이전엔 PG만 422), 실행 이벤트 정렬 최신순(이전 PG는 오래된 순 — 기존 실DB 시험 기대값을 뒤집음), 실행 목록에 `review_status` 추가 및 `run_id DESC` 동률 정렬, 자산 검증 실패는 구조화 422 `PHOTO_IMAGE_ASSET_REQUIRED`. 검증: SQLite↔PG 동등성 49단계(출력 확인) + 변이 5종(정렬·상한·존재 확인·review_status·오류 형식) 모두 검출(상한 변이는 처음엔 시험이 놓쳐 `run-events-max-limit` 단계를 추가).
- Photo 남음: (b) 검수 조회·승인·변경요청·반려·매니페스트 내보내기 5개 라우트, (c) `process-local`(파생 자산 저장 `save_derived_image_asset` PG 구현 + 실패 주입 시험). 아직 SQLite 코드 경로(`photo_engine`의 검수·처리 함수)를 그대로 사용.
- **Photo (b)단계** (검수·내보내기 5개 라우트, 같은 `app/ports/photos.py`): PG 저장소에 `output_review`/`decide_output_review`/`create_export_manifest` 신규 구현(레거시와 같은 규칙: 성공한 실행만, 출력 파일 바이트·출력 버전·출처 기록 무결성 재확인, 승인/반려는 종결, 같은 결정 반복 금지, 승인 스냅샷이 현재 출력과 같아야 내보내기, 검수 결정은 owner/admin만, 내보내기는 editor 이상). 레거시 계약대로 **상태·검증 거절은 모두 409**(빈 코멘트 포함). 파일 검증은 `LocalBlobStore.audit_status` 사용(레거시와 같은 기준: 루트 안 경로·크기·SHA-256). 행 잠금(`FOR UPDATE`)으로 동시 결정 직렬화.
- **`save_derived_image_asset` PG 구현** (`PostgreSQLAssetBytesPort.save_derived` + `save_derived_image_metadata`): 결정적 ID(`av_photo_`/`ap_photo_`/`ar_photo_*`), 같은 바이트 재시도는 재사용, 다른 바이트는 거절(잔여 파일 덮어쓰지 않음), 메타데이터 커밋 실패 시 방금 만든 파일 삭제, 출처 기록 3종·`derived_from` 관계 생성. `process-local` 라우트는 아직 SQLite 경로 사용(이 구현은 시험에서만 호출됨).
- 검증: 검수·내보내기 동등성 42단계(SQLite는 실제 파일 변조 포함) + 변이 시험 10종 중 처음 3종은 시험 코드가 잘못되어(문법 오류=무효) 재실행, 1종은 시험이 놓쳐 추가(잔여 파일 거절, 출처 변경 후 내보내기). 시험 ID 정규화 누락(무작위 `av_` 접두)도 한 건 수정(결함 아님). 동시 승인 8스레드 → 승리 1·거절 7·검수 이벤트 1건(잠금 제거 시 실패 확인).
- 알려진 미검증: 승인 스냅샷 불일치는 DB 직접 조작 시험으로만 확인(API 경로로는 재현 불가), 파일 시스템 장애(쓰기 도중 디스크 가득 등) 주입 시험 없음, Supabase Storage 없음.
- 테스트 수: 일반 625 passed / 32 skipped(실DB 시험은 PG 없으면 건너뜀), 실DB 32 passed.
- **Photo (c)단계 — `process-local`** (같은 포트의 `process_local`): 라우트 14개 전부 포트 경유. PG 쪽은 클레임(리스·멱등 키) → 원본 바이트를 `LocalBlobStore.read_verified`로 검증 → 백엔드 독립 렌더 함수(`render_local_image_bytes`; SQLite 경로도 같은 함수 사용) → `save_derived`(파일 선 기록·메타데이터 커밋·실패 시 파일 삭제) → 완료/실패 기록. 레거시 오류 계약 유지: 클레임 거절은 409, 초안 없음 404, 그 이후 실패는 422 `PHOTO_LOCAL_PROCESSING_FAILED`(고정 문구 "Source image integrity validation failed"/"Local image processing failed").
- 검증: 동등성 시나리오(권한 순서, 지원 안 되는 작업·프롬프트·참조 이미지·출력 수 거절, 성공, 같은 키 재시도(파일 추가 없음), 다른 초안에 같은 키 409, 검수→승인→내보내기까지 이어짐, 원본 변조 시 422·실패 기록·파생 파일 없음·재시도 시 attempts 2). **두 백엔드의 출력 이미지 SHA-256이 동일**(결정적 렌더). PG 전용: 메타데이터 저장 실패 주입 → 파일 원복·실행 failed·같은 키 재시도 성공(attempts 2, 이벤트 순서 확인), 동일 키 6스레드 동시 호출 → 실행 1건·파생 파일 1개. 변이 6종(실패 미기록, 원본 무결성 미검증, 재생 분기 제거, 권한 순서, 409→422 매핑, 행 잠금 제거) 모두 검출 — 단 행 잠금 변이는 새 시험이 아니라 기존 `claims_have_single_winner` 시험이 잡음(새 동시성 시험은 잠금 없이도 통과: 이후 단계가 직렬화됨).
- 미검증/미구현: 처리 중 프로세스가 죽는 경우(리스 만료 후 재클레임은 기존 시험이 다룸, 파일만 남은 상태는 `save_derived` 시험이 다룸), 디스크 가득/권한 오류 같은 파일 시스템 오류 주입, Photo 초안 갱신과 처리 클레임 사이의 경합, Supabase Storage.
- Photo 라우트 14개 포트화 완료. 다음: **Lookbook**(lookbook.py 1321줄)과 `_photo_output_base`/`_verify_photo_output_version` 직접 import 제거(현재 Lookbook이 SQLite 경로로 직접 호출).
- 테스트 수: 일반 625 passed / 35 skipped(실DB 시험은 PG 없으면 건너뜀), 실DB 35 passed.
- **Lookbook (a)단계** (`app/ports/lookbooks.py`, 25개 중 10개: 초안 생성·목록·조회·수정·제출·승인·변경요청·보관·이벤트·계획 매니페스트): 권한 확인을 초안 조회보다 먼저(Photo와 동일: 비멤버 404 "Workspace not found", 낮은 역할 403 — 이전엔 없는 초안이면 역할과 무관하게 404). PG 저장소는 대부분 레거시와 이미 같았고 두 가지만 고침: 이벤트 페이지 상한 200→500, 자산 검증 실패를 구조화 422 `LOOKBOOK_IMAGE_ASSET_REQUIRED`로. 검증: SQLite↔PG 동등성 70여 단계(출력 확인) + 변이 7종(검수 역할, 상한, 오류 형식, 상태 전이 검사, 역할/조회 순서, ACTIVE 프로젝트 검사, 보관된 초안 매니페스트) 모두 검출 + 동시 승인 8스레드(승리 1·거절 7·승인 이벤트 1건; 행 잠금 제거 시 실패 확인). 시험 코드 한계 두 가지 정정: JSONB는 키 순서를 보존하지 않아 이벤트 `details`는 정렬해 비교, 이미지 없는 상품은 상품 생성 단계에서 거절되어 해당 시나리오는 제외.
- **Lookbook (b)단계** (`app/ports/lookbooks.py`, 25개 중 6개 추가: 산출물 목록·첨부·조립 검수 조회·제출·승인/반려·출력 매니페스트; 누적 16개): 권한 먼저·조회 나중 순서 동일 적용, PG 저장소의 상태 거절을 전부 409로(레거시와 동일). 검증: SQLite↔PG 동등성 60단계(실제 Photo process-local 산출물 사용, 출력 확인) — 첨부 거절 11종·동결 후 첨부·재제출·반려 사유 필수·승인 후 재승인 409·매니페스트 해시 일치·파일 변조 시 `integrity_error`/409 포함. 변이 8종 모두 검출(Photo 파일 검증 첨부 시·조립 검증 시, 동결 검사, 기획 승인 검사, 제출 상태 검사, 결정 시/매니페스트 시 스냅샷 해시 검사). 처음엔 변이 3종이 살아남아(첨부 시 파일 변조, 결정/매니페스트 시 스냅샷 해시) 시험을 추가해 막았다: 변조된 산출물 첨부 시험, 직접 SQL로 페이지 순서를 바꾼 뒤 결정/매니페스트가 409인지(이 경로는 API로 도달 불가라 동등성 단계가 아니라 PG 전용 시험). 동시성: 같은 페이지 6스레드 첨부(승 1), 같은 산출물 다른 페이지 6스레드(승 1), 동시 제출(1), 동시 승인/반려(1건만 기록). 기존 저장소 수준 시험은 실제 Photo 산출물(실제 바이트·버전·출처)과 실제 검증기를 쓰도록 바꾸고 상태 거절 예외 타입을 ValueError→LookbookStateError(409)로 갱신. 결과: 전체 pytest 625 passed/39 skipped, live PG 39 passed.
- **Lookbook (c)단계** (`app/ports/lookbooks.py`, 패키지 내보내기 3개: 목록·생성·서명 다운로드; Lookbook 라우트 전부 포트 경유): 레거시 zip 쓰기·목록 모양을 공용 함수(`write_lookbook_package`, `package_export_list`)로 뽑아 두 백엔드가 같은 코드를 쓴다(다운로드도 `fetch_row`/`authorize` 주입). PG 쪽 추가: `prepare_package`(승인·스냅샷·100쪽·250MiB 재검증), `record_package_export`(같은 트랜잭션에서 승인/순서 재검증, `export_id` 지정), `get_package_export`; 목록 정렬은 레거시와 같게 `created_at DESC, export_id DESC`. 검증: SQLite↔PG 동등성 27단계(생성 거절 8종·역할 순서·목록 상태·서명/만료/변조/파일 없음 다운로드·zip 내용과 manifest 비교·기록된 해시와 실제 해시 일치), PG 전용 시험(zip 쓰는 동안 순서가 바뀌면 409·파일 삭제·감사 행 없음, 쪽수 한도), 변이 8종 모두 검출(쪽수 한도는 처음에 살아남아 시험 추가), 동시 생성 6스레드(서로 다른 6개·파일 6개·임시 파일 0·감사 행 삭제 불가). 결과: 전체 pytest 625 passed/41 skipped, live PG 41 passed. 동작 변경(§9 참고): 목록·생성 라우트도 권한 확인이 초안 조회보다 먼저, 생성 중 상태 거절은 409 유지. 남은 한계: 파일 쓰기 중 디스크 부족/권한 오류 주입 시험 없음, 다운로드 응답은 zip 내용·기록 해시 일치로 비교(전송 중단·부분 읽기 시험 없음).
- **동시성 점검 1차 (결함 발견·수정)**: 저장소의 "참조 대상이 활성인지" 확인이 잠금 없이 읽기만 해서, 삭제/보관과 참조 생성이 겹치면 삭제된 자산·보관된 상품·삭제된 캐릭터를 가리키는 활성 항목이 남았다(DB 트리거는 일부만 막고 오류가 그대로 노출). 수정: 확인 쿼리에 `FOR SHARE`(자산은 `ORDER BY asset_id`로 잠금 순서 고정; Photo 원본 조회는 `FOR SHARE OF a`) — Product 생성/수정/변형 생성·수정, Character, Photo 초안, Lookbook 초안(자산·Product·Variant·Character). 시험: 20~25회 반복 경합으로 불변식 검사 — 수정 전: 상품 생성 vs 자산 삭제 25회 중 18회 위반(+원시 트리거 오류 7건), Photo·Lookbook 초안 생성 vs 자산 삭제 위반, 상품 보관 vs Lookbook 초안 생성 거의 매회 위반, 캐릭터 삭제 vs Lookbook 초안 생성 위반; 수정 후 전부 0회. 시험 한계: 변형 생성 vs 자산 삭제는 수정 전에도 통과해(20회) 이 경로가 실제로 위험했다는 증거가 못 된다; Character 생성/수정의 자산 잠금과 Project 활성 검사에는 경합 시험이 없다; 경합 시험은 타이밍에 의존하는 확률적 시험이다. live PG 47 passed(4회 연속 안정), 전체 pytest 625 passed. 아직 운영 경로(SQLite)에는 영향 없음(PG 저장소는 런타임에서 도달 불가).
- **동시성 점검 2차 (Job/Worker/Output; 결함 2건 발견·수정)**: 이 영역의 PG 저장소는 실제 DB 시험이 없고 모의(mock) 시험뿐이었다. 실제 DB 시험 추가: 같은 키 동시 멱등 생성 8스레드(작업·멱등 행·outbox·execution 각 1개, 다른 payload는 전부 거절), 동시 전이 8스레드(승자 1·이벤트 [queued, running]·version 2), 취소 대 발송 완료 25회 경합, Output 확정 3개 + 소진 1개 동시 15회(승자 1명만, 산출물·링크·이벤트 정확히 1건 또는 0건 — 확정 7회·소진 8회로 양쪽 결과 모두 발생), 리스 만료 후 오래된 워커의 확정/완료/갱신/소진 거절과 새 워커 인계. 결함 1: `cancel_queued`가 job→outbox 순으로, `complete_outbox_submission`이 outbox→job 순으로 잠가 교착(DeadlockDetected) 발생 → 취소도 outbox→job 순으로 변경(오류 메시지 우선순위는 그대로). 결함 2: `reschedule_poll_task`가 `phase`를 줄 때 실제 PG에서 "could not determine data type of parameter" 오류로 항상 실패(모의 시험은 못 잡음) → `%s::text` 형변환. 수정 되돌리면 시험 3개가 실패함을 확인. 공유 시험 DB의 다른 대기 작업이 끼어들지 않도록 시험 시작 시 다른 대기 행을 먼 미래로 보류(`_isolate_queue`). 한계: Job→Output 연결(output_asset_link)·알림 전달(operations)·Outbox 소진 경합·Job 목록/페이지는 경합 시험 없음; 확률적 시험. live PG 52 passed(3회 연속 안정), 전체 pytest 625 passed.
- **동시성 점검 3차 (Outbox·알림 전달; 새 결함 없음)**: 알림 전달 — 6워커가 10건을 경쟁 청구해 모두 정확히 1번씩만 청구, 소유자·리스 펜싱(다른 워커/만료 후/오래된 소유자의 완료 거절, 만료 후 재청구는 attempts=2), 소유자 동시 완료 4스레드 중 1건만 적용. Outbox — 발송 완료 vs 미확정 표시 vs 리스 만료 청구 20회 경합(승자 정확히 1명, 완료 쪽이면 outbox processed·job running·execution running·이벤트 [JOB_CREATED, PROVIDER_SUBMITTED], 미확정 쪽이면 needs_reconciliation·queued·execution unknown·이벤트 [JOB_CREATED, PROVIDER_START_UNKNOWN]; 양쪽 결과 모두 발생 확인), 만료 리스는 다음 청구 때 격리되고 오래된 워커의 완료(RuntimeError)·미확정 표시(False)는 거절. 잠금 순서(outbox→job, 폴링 작업→job)는 서로 일관됨을 코드로 확인. 시험 한계: 이 시험들은 모두 현재 코드에서 통과했으므로 시험이 결함을 잡는다는 변이 증거는 없다(작업 취소 교착과 reschedule 형변환 시험만 되돌려서 실패를 확인함); 확률적 시험; Job→Output 자산 연결(output_asset_link)의 PG 구현은 확인 못 함. live PG 56 passed(3회 연속 안정), 전체 pytest 625 passed.
- Lookbook 남음: (b) 산출물 목록·첨부·조립 검수 조회·제출·승인·반려·출력 매니페스트(8개), (c) 패키지 내보내기 목록·생성·서명 다운로드(3개, 파일 생성·서명 URL 포함). 이 둘은 `_photo_output_base`/`_verify_photo_output_version`(SQLite)을 직접 호출 중이라 Photo 포트의 `verify_output_base`로 교체 필요.
- 테스트 수: 일반 625 passed / 37 skipped, 실DB 37 passed.
- **동시성 점검 4차 (2026-11-09 세션; 결함 2건 발견·수정, 시험 공백 보강)**
  - CI 확인(직접 조회): main run #4 backend 잡 `681 passed, 1 warning`(skipped 0), 실DB 시험 단독 `56 passed`. 실DB 시험은 건너뛰어지지 않음.
  - 결함 1 (Project 활성 검사): `postgres_lookbooks`가 Project 상태를 잠금 없이 읽어, Project 보관과 Lookbook 초안 생성이 겹치면 보관된 Project를 가리키는 활성 초안이 남음(수정 전 25회 중 20회 위반, 3/3 시험 실패). 수정: `FOR SHARE`. 수정 후 3/3 통과, 잠금 제거 변이는 시험이 적발.
  - 결함 2 (Character 자산 참조, **동작 변경**): 활성 Character가 쓰는 자산을 삭제할 수 있었음(PG·SQLite 레거시 모두; `integrity_audit`의 `CHARACTER_ASSET_DELETED`가 위반으로 보는 상태). 양쪽 `soft_delete_asset`에 "활성 Character 참조 시 409" 보호 추가. 시험: PG 순차 1 + 경합 2(Character 생성·수정 vs 자산 삭제 25회), SQLite API 1. 변이: 보호 제거(순차·생성 경합 적발), Character `_check_assets`의 `FOR SHARE` 제거(생성·수정 경합 적발), SQLite 보호 제거(적발). 한계: Character 수정 경합은 보호 제거 변이로는 안 잡힘(생성 경합이 잡음).
  - Job 목록·페이지: `list_for_workspace` 시험 추가(created_at 동률 시 job_id 내림차순, 페이지 이어붙이면 전체와 동일, 워크스페이스 격리, 한도 검증). 변이 3종(타이브레이크 ASC, offset 무시, 워크스페이스 필터 제거) 적발. 미시험: `list_executions` 커서 페이지, 동시 삽입 중 offset 페이지의 이동(OFFSET 방식의 본질적 한계).
  - Outbox·알림 변이 증거: 기존 시험이 `status='processing'` 검사에 가려 소유자·만료 방어를 확인하지 못했음(두 겹 제거 변이가 살아남음) → 시험 2종 추가(다른 워커의 완료·미확정 표시 거절, 재청구 전 만료 리스의 완료·미확정 표시 거절). 변이 결과: 적발 = Job 전이 행 잠금, 멱등 생성 advisory lock, Output 확정 소유자·만료 방어, Outbox 완료의 소유자·만료 방어(검사+UPDATE 두 겹 제거), Outbox 미확정 표시 소유자·만료, 알림 완료 소유자·만료(두 겹 제거). **적발 못 함(동치로 판단)**: `FOR UPDATE SKIP LOCKED`→`FOR UPDATE`(배타성은 유지되고 대기 방식만 바뀜), Outbox 완료의 Job 행 잠금 제거, 알림 완료의 `FOR UPDATE` 제거(이후 `UPDATE ... WHERE`와 `status` 조건이 같은 보호를 제공). 한 겹만 제거하는 변이(`O2`/`O3`)는 이중 방어 때문에 결과가 같음.
  - `output_asset_link`: **PG 구현 없음** — `build_output_asset_link_repository("postgresql")`은 `RuntimeError`로 거부(SQLite 대체 금지). 구현·경합 시험은 남은 작업.
  - 시험 취약점 수정: 새 시험이 남긴 대기 poll 행이 반복 실행 시 `_job_at_persist_output`의 두 번째 claim을 가로채 시험이 간헐 실패했음(새 DB 한 번 실행에서는 안 보임). 새 시험이 자기 행을 정리하고 헬퍼에 재격리 추가. dirty DB 4회 연속 + 새 클러스터 1회 통과.
  - 결과: 전체 pytest 626 passed / 63 skipped, 실DB(새 클러스터) 63 passed, compileall OK. 실행하지 않음: 프런트(`tsc`/`test:source`/`build`) — 이번 변경은 백엔드만.
