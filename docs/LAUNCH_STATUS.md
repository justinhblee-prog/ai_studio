# LAUNCH STATUS

> 이 파일은 2026-11-09 세션에서 **새로 만들었다**. 이전에는 저장소의 어느 브랜치와 로컬 파일시스템에도 `docs/LAUNCH_STATUS.md`가 없었다(검색으로 확인). 따라서 이전 내용을 기준으로 정리한 것이 아니라, 이 세션에서 직접 확인한 사실만 적는다. 이전 버전이 따로 있다면 그 내용은 반영되지 않았다.

## 변경 로그 (최신이 위, PR이 머지될 때마다 추가)

### 2026-11-09 · PR #10 (머지 525ae7d) — 권한별·교차 Workspace·모바일 폭 E2E
- **CI (head db2fbf3, run 42567811198)**: backend success — pytest `725 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10 steps passed`, `SUMMARY 6/6 rights steps passed`, `SUMMARY 6/6 role scenarios passed`. 로그에 `failed` 없음.
- **완료**: 6개 시나리오(뷰어는 업로드·승인 불가, 편집자는 업로드 가능·승인 불가, 소유자 승인, 외부인 API의 모든 읽기·쓰기 거절, 외부인 UI에서 공유 데이터 미노출, 390px 모바일 가로 넘침 없음). 변이 4/4 적발(뷰어 업로드 허용, 편집자 승인 허용, 비멤버를 뷰어로 취급, 폭 강제). 간헐 실패 1건의 원인(시드된 `photo-enhance.png`와 부분 문자열 일치)을 찾아 고침: 수정 후 25회 중 0회 실패(수정 전 3회 반복 중 1회, 20회 시도 중 1회).
- **미검증**: Supabase Auth는 mock; AI Provider 없음; 상품·프로젝트·룩북의 권한 경로는 브라우저에서 시험하지 않음(API 시험만 있음); 태블릿 등 다른 화면 폭.
- **차단**: 없음.

### 2026-11-09 · PR #9 (머지 5082305) — AI 비용 상한
- **CI (head b281220, run 42567035715)**: backend success — pytest `725 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10 steps passed`, `SUMMARY 6/6 rights steps passed`.
- **완료·미검증·한계**: 아래 §7. 변이 10/10 적발.
- **차단**: 설계서 D5와의 일치 여부는 설계서가 없어 확인 못 함.

### 2026-11-09 · PR #8 (머지 56090a7) — L-04 업로드 권리·초상권 확인
- **CI (head 9e2f8e7, run 42566387583)**: backend success — pytest `716 passed, 1 warning`, 실DB 단계 `76 passed, 1 warning`(failed 없음); frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10 steps passed`, `SUMMARY 6/6 rights steps passed`.
- **완료**: 이미지 업로드의 권리·초상권 선언(서버 필드 3개, 설정 `ASSET_REQUIRE_RIGHTS_CONFIRMATION` 기본 꺼짐, `asset_provenance` 기록, UI 체크박스); 기록은 자산 삭제 후에도 유지(SQLite·PG); 기존 자산 소급 차단 없음; OpenAPI 스냅샷 재생성(옵션 필드 3개만 추가). 변이: 백엔드 10/10, 프런트 로직 5/5, 브라우저 3/3, 기록 유지 2/2 적발. 아래 §6에 동작 표.
- **미검증**: 설계서(D2)와의 대조 — 문서 없음. UI 문구는 법무 승인 전 임시 문구. 영구 삭제(L-01) 시 이 기록 처리는 미정. "소급 차단 없음" 시험은 표적 변이 없음.
- **차단**: 설계서 `DESIGN_PACK_20261109.md`, 법률·동의 패치 zip 2개가 세션에 없음(아래 차단 표). D1(AI 학습 동의) 구현이 이 저장소에 없음.

### 2026-11-09 · PR #7 (머지 2c39903) — 브라우저 E2E 1단계
- **CI (head 5dc966a, run 42552138675)**: backend success — pytest `705 passed, 1 warning`, 실DB 단계 `74 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 pass/0 fail + 4 pass/0 fail, `vite build` 통과; **e2e success — GitHub에서 `SUMMARY 10/10 steps passed`**(ZIP에 `manifest.json`과 이미지 포함 확인).
- **완료**: 출시 빌드를 헤드리스 Chromium으로 구동하는 소유자 흐름 10단계(로그인 → Workspace → 이미지 업로드 → 상품 → 포토 초안 → 로컬 이미지 처리 → 검수 승인 → 룩북 기획·조립 승인 → ZIP 다운로드); 변이 3종 적발(주소 입력란 복구는 처음에 놓쳐서 시험을 고친 뒤 적발).
- **미검증**: Supabase Auth는 **mock**(실제 Supabase 로그인 미시험); AI Provider 경로 미시험(이 앱의 "생성"은 결정적 로컬 조정); 모바일 폭·권한별·교차 Workspace 시험은 아직 없음.
- **차단**: 없음.

### 2026-11-09 · PR #6 (머지 46005d4) — 레지스트리 증거 게이트
- **CI (head c9163c6, run 42550454875)**: backend success — pytest `705 passed, 1 warning`, 실DB 단계 `74 passed, 1 warning`(failed 없음); frontend success — `tsc` 통과, `test:source` 8 pass/0 fail + 4 pass/0 fail, `vite build` 통과.
- **완료**: 레지스트리에 집계별 근거 시험명(`evidence`)과 기계 검사(`tests/test_registry_evidence.py`) 추가; 실DB 시험 12종 추가(멱등 조회, Outbox `get_job`, 하트비트 2종, Output `record`/`list_storage_keys`/`get`, Job `update`/`list_outputs`, 풀 리스 갱신) — 변이 20/20 적발, 게이트 변이 8/8 적발; generation_jobs·job_outbox·provider_poll·outputs·operations_and_health를 live_verified로 올림; output_asset_link를 missing으로 추가.
- **미검증**: `photos`(6)·`lookbooks`(3)·`project_products`(1)의 공개 메서드는 실DB 시험이 직접 호출하지 않고 포트 경유 동등성 시험으로만 간접 검증(`KNOWN_INDIRECT`에 명시); "메서드가 참조됨"은 충분한 시험의 증명이 아님. `postgresql` 런타임 선택은 여전히 거부됨(4개 집계 미충족), 런타임은 SQLite.
- **차단**: 아래 표 그대로.

### 2026-11-09 · PR #5 (머지 294b6dd) — L-13, T56, CI 실패 은폐 수정
- **CI (head bf6ed25, run 42548956699)**: backend success — pytest `692 passed, 1 warning`, 실DB 단계 `66 passed, 1 warning`(failed 없음); frontend success — `tsc --noEmit` 통과, `test:source` node 시험 8 pass/0 fail + 4 pass/0 fail, `vite build` 통과.
- **완료**: L-13(출시 빌드는 `VITE_API_BASE_URL`만 사용, 주소 입력란·저장 값·localhost 대체 제거, 개발 빌드는 유지); T56(SQLite↔PG 새 버전 생성 메타데이터 비교 시험, 변이 7/7 적발); CI "Live tests must not be silently skipped" 단계가 실패를 가리던 문제 수정(4가지 경우 시뮬레이션); 간헐 실패 시험(Lookbook 조립 경합) 설계 결함 수정(기존 시험 40회 중 1회·순서 뒤집으면 10회 중 6회 실패 → 수정 후 두 순서 모두 40회 중 0회).
- **미검증**: L-13은 브라우저 설정만 제거한 것이며 서버가 주소를 강제하지 않음; 헤드리스 Chromium 검증은 로컬 1회(CI에는 브라우저 시험 없음). work-20261109 핸드오프의 "원인 불명 1회 실패"가 위 시험인지는 시험 이름 미기록으로 확인 못 함.
- **차단**: 아래 "차단" 섹션 참조.

## 차단 (입력·승인이 없어 하지 못한 것; 다른 작업은 계속 진행)
| 항목 | 이유 | 필요한 것 |
|---|---|---|
| `ai_studio_legal_patch_20261109.zip` 적용(큐 2) | 세션에 파일 없음(업로드 폴더 `.saved-uploads`에 `NEXT_SESSION_START.md`뿐, 파일시스템 검색에도 없음). 2회 확인 | zip을 저장소에 커밋하거나 세션에 업로드 |
| L-02 서버 API(`/v1/legal/documents`, `/v1/me/legal-status`, `/v1/me/legal-acceptances`) | 저장소에 해당 라우트 없음(패치 zip에 들어 있을 것으로 추정 — 미확인). 법률 문서 본문·버전은 빈칸을 임의로 채우지 않음 | 패치 zip 또는 문서 본문 |
| `claude/LEGAL_IMPLEMENTATION_GAPS.md`(L-항목 정의) | 저장소에 없음 | 문서 |
| 배포 환경(영속 디스크 유무) | 파일럿은 SQLite 단일 인스턴스를 전제. 서버리스뿐이면 결론이 바뀜 | 배포 대상 정보 |
| `claude/DESIGN_PACK_20261109.md` 및 폴더 `1. AI Studio`의 사본(D1·D2·D4·D5) | 저장소(모든 원격 브랜치)·로컬 파일시스템·세션 업로드 폴더 어디에도 없음(3회 확인). 설계서 내용을 알 수 없어 D2 대조·D4·D5를 설계서대로 구현하지 못함 | 문서를 저장소에 커밋하거나 세션에 업로드 |
| `ai_studio_legal_patch_20261109.zip`, `ai_studio_consent_patch_20261109.zip`(각 APPLY.md) | 두 파일 모두 세션에 없음(위와 같이 검색). 적용·OpenAPI 재생성·PR을 하지 못함 | 두 zip을 저장소에 커밋하거나 업로드 |
| D1(AI 학습 별도 동의) "이미 구현됨" | **이 저장소에서는 확인되지 않음**: 학습·동의 관련 코드가 없고(`consent`가 들어간 파일은 모두 이번 L-04 작업물), 원격 브랜치 9개 어디에도 D1 구현이 없음. 다른 사본·패치(동의 패치 zip)에 있을 가능성 | 동의 패치 zip 또는 D1이 있는 브랜치 |
| L-01 영구 삭제 스크립트(`scripts/purge_deletion_requests.py`) | 저장소에 "삭제 요청" 테이블·API가 없음(법률·동의 패치에 있을 것으로 추정 — 패치 zip이 없어 확인 못 함). 무엇을 어떤 기준으로 지울지의 명세 없이 만들면 어긋나므로 만들지 않음. 영구 삭제는 L-04 기록(`asset_provenance`)의 처리 정책도 정해야 함 | 법률·동의 패치 zip 또는 L-01 명세 |
| TEST Supabase에 0011–0013 적용 | 금지 항목(접속 정보·승인 필요) | — |
| Production Supabase/Vercel, 유료 Provider, Production `DATABASE_BACKEND=postgresql`, 실데이터 영구 삭제, 비밀·키 | 금지 항목 | — |

## 1. PR #5 머지 전 확인 (head 436792c, CI run 42547697665)

| 확인 | 결과 |
|---|---|
| frontend `npx tsc --noEmit` | success |
| frontend `npm run test:source` | success — node 시험 8건 pass / 0 fail, 4건 pass / 0 fail(`apiBaseUrl.test.mjs`), Public landing contract PASS |
| frontend `npm run build` | success (`tsc -b && vite build`, built in 2.66s) |
| backend 전체 pytest (실DB 포함) | 692 passed, 1 warning (skipped 0) |
| backend "Live tests must not be silently skipped" 단계 | **단계는 success로 표시됐지만 로그는 `1 failed, 65 passed`** (아래 §2) |
| T56 시험의 변이 검증 | 변이 7종 모두 적발(재실행). 이 시험만 잡는 것: `previous_version` 오프바이원, 255자 절단 제거, 포트의 경로 제거 제거 |
| PR #4(merge-20261109) | main에 merged — merge commit `c5baffa`. main push CI run #8: backend 691 passed(skipped 0)·실DB 65 passed, frontend success |
| PR #3(work-20261109) | merged (포함된 커밋이 main에 들어가 GitHub이 merged 처리) |
| 법률 패치 PR | **없음** — `ai_studio_legal_patch_20261109.zip`이 세션에 없어 적용·PR 생성을 하지 못함 |
| PR #1(Add Python CI workflow) | 열린 채로 남아 있음(이번 작업과 무관, 손대지 않음) |

T56은 수정이 아니라 비교 시험 추가였다. "수정을 되돌리면 실패하는가"는 코드 변이로 확인했다: `postgres_assets.create_asset_version`과 `asset_bytes` 포트의 해당 줄을 바꾸면 7/7 실패, 원상복구 후 통과.

## 2. CI에서 발견한 문제 (PR #5 CI에서 드러남)
1. **CI 단계가 실패를 가렸다**: `pytest ... | tee live.txt && ! grep -q skipped live.txt`는 파이프 종료 코드가 `tee`의 것이라 시험이 실패해도 단계가 통과했다. → `set -o pipefail`과 `grep -qE "[0-9]+ (skipped|failed)"`로 수정. 4가지 경우(통과·실패·건너뜀·pytest 비정상 종료)를 로컬에서 시뮬레이션해 확인.
2. **간헐 실패 시험의 원인 확정**: `test_lookbook_assembly_concurrent_attach_and_decide_are_serialised`의 두 번째 경합이 항상 `runs[5]`를 썼는데, 첫 경합에서 6개 중 아무 run이나 이기므로 `runs[5]`가 승자면 두 번째 경합이 전부 "이미 첨부됨" 충돌이 되어 승자가 0이 된다(제품 결함이 아니라 시험 설계 결함). 증거: 기존 시험 로컬 40회 중 1회 실패, 첫 경합에서 `runs[5]`가 먼저 시도되게 순서를 뒤집으면 10회 중 6회 실패. 수정(승자가 아닌 run을 사용): 뒤집은 순서 40회 중 0회, 일반 순서 40회 중 0회 실패.
3. work-20261109 핸드오프의 "전체 실DB 실행 중 1회 실패, 시험 이름 확인 못 함(원인 불명)"이 이 시험인지는 **확인하지 못함**. 같은 증상(드문 1회 실패)이지만 그 실패의 시험 이름이 기록되지 않았다. 앞서 15회 반복에서 15/15 통과한 것도 이 시험이 약 1/40 확률로만 실패하기 때문에 설명된다(15회 반복은 이 결함을 잡기에 충분하지 않았다).

## 3. 큐 (이 파일이 없었으므로 `NEXT_SESSION_START.md`의 큐 기준)
| 항목 | 상태 |
|---|---|
| CI backend pytest 요약 확인 | 완료 |
| 경합 시험 4종·Job/Outbox/알림 변이 증거 | 완료(`output_asset_link` PG 구현 없음 — 미구현으로 확인) |
| T56 | 완료(시험 보강) |
| L-13 출시 빌드 API 주소 고정 | 완료 (PR #5) |
| L-04 인물 사진 업로드 권리·동의 확인 | **구현·머지됨(PR #8)** — 설계서(D2)와 대조 못 함(문서 없음). UI 문구는 법무 승인 전 임시 문구(`src/rightsConfirmationCopy.ts`) |
| L-02 프런트 동의 화면 | **막힘** — 위와 같음 |
| 법률 패치 zip 적용 | **막힘** — 파일 없음 |
| 랜딩 재구현(시안 ①) | 시안 파일이 저장소에 없음 — 확인 필요 |
| 브라우저 E2E | 진행 중 — 1단계(소유자 흐름) 구현, 아래 "E2E" 참조 |
| TEST Supabase에 0011–0013 적용 | 승인·접속 정보 필요 — 하지 않음 |

## 4. 승인 경계 (불변)
Production Supabase/Vercel 변경 금지, 유료 Provider 호출 금지, `DATABASE_BACKEND=postgresql` 활성화 금지, 영구 삭제 실행 금지, 비밀·키 사용 금지.

## 5. E2E (큐 6, 브랜치 e2e-flow)
- `ai_creator_studio_3d_viewer/e2e/pilot_flow.mjs`: 출시 빌드를 헤드리스 Chromium으로 구동 — 로그인 → Workspace 자동 생성 → 이미지 업로드 → 상품 생성 → 포토 초안 → 로컬 이미지 처리 → 검수 승인·manifest → 룩북 초안 → 기획 제출·승인 → 승인된 Photo 결과 연결 → 조립 검토 제출·승인 → 내부 ZIP 생성·다운로드(ZIP 무결성, `manifest.json`과 이미지 포함 확인). 로컬 3회 연속 `SUMMARY 10/10 steps passed`.
- **실제와 mock 구분**: 실제 = 웹 번들, FastAPI, SQLite, 파일 저장소, 결정적 로컬 이미지 처리, ZIP 내보내기. **mock = Supabase Auth**(브라우저에서 요청을 가로챔; 실제 Supabase 로그인은 시험하지 않음). **AI Provider 호출 없음**: 이 앱의 "생성"은 외부 Provider가 아니라 Pillow 기반 결정적 로컬 조정(`ENHANCE`/`LIGHTING`). Provider 경로(`/v1/generation-jobs`, `PROVIDER_MODE=mock`)는 이 E2E가 시험하지 않음.
- 변이 검증: 주소 입력란 복구(처음에는 **적발 못 함** — 입력란 검사를 로그인 이후에만 해서 시험 결함이었음, 로그인 화면·설정 패널 검사를 추가한 뒤 적발), ZIP에서 manifest 제거(적발), 로컬 처리 실패(적발).
- CI: `e2e` 잡 추가(Playwright 1.63.0 고정). **GitHub에서 실행한 결과는 이 PR의 CI로 확인**(아래 PR 항목 참조).

## 6. L-04 업로드 권리·초상권 확인 (D2와의 대조는 문서가 없어 못 함 — 구현의 실제 동작만 기록)
요청하신 3가지 대조 항목에 대한 **이 구현의 실제 동작**(시험으로 확인). 설계서와 비교한 것이 **아니다**.
| 항목 | 이 구현의 동작 | 근거 시험 |
|---|---|---|
| (1) 권리 확인 없는 업로드 거부(422) | `ASSET_REQUIRE_RIGHTS_CONFIRMATION`이 **켜진 때만** 422(`RIGHTS_CONFIRMATION_REQUIRED`; 사람이 나온다고 선언하면 `LIKENESS_CONSENT_REQUIRED`도). **기본값은 꺼짐**이라 확인 없는 업로드도 201(옛 클라이언트 호환). 거절된 업로드는 자산·파일을 남기지 않음. 이미지 업로드만 대상(GLB 모델 업로드는 제외) | `test_rights_confirmation.py` 9건, 실제 브라우저 `rights_flow.mjs` 6/6 |
| (2) 확인 기록 테이블, 자산 삭제 후 기록 유지 | 별도 테이블 없이 기존 `asset_provenance`의 `asset.uploaded` 행 `details.rights`에 `{rights_confirmed, depicts_person, likeness_consent}`를 기록. 자산 soft delete 후에도 행이 남음(`asset.uploaded` + `asset.deleted` 2행). **영구 삭제(L-01 purge)가 이 행을 어떻게 다룰지는 미정·미구현** | SQLite `test_declaration_record_survives_deleting_the_asset`, PG `test_upload_declaration_record_survives_deleting_the_asset_in_postgresql`; 변이(삭제 시 출처 행도 삭제) 2/2 적발 |
| (3) 기존 자산 호환(소급 차단 없음) | 강제는 **새 업로드에만** 적용. 선언 없이 올라간 기존 자산은 강제를 켠 뒤에도 목록·조회·포토 초안 원본으로 계속 사용 가능, provenance는 옛 형식(`{"source":"upload"}`) 그대로 | `test_assets_uploaded_before_enforcement_are_not_blocked_retroactively` (이 시험에 대한 표적 변이는 만들지 못함 — "동작 없음"을 지키는 회귀 시험) |
- **설계서와 달라도 이 구현을 유지하는 이유는 판단할 수 없다**(설계서를 못 봄). 별도 확인 테이블이 설계서의 요구라면 이 구현은 그것을 충족하지 않는다.
- 기록 호환: 선언이 없으면 provenance가 이전과 바이트 단위로 같음(시험).
- 변이 검증: 백엔드 10/10 적발, 프런트 로직 5/5 적발, 브라우저 3/3 적발(선언 미전송, 오류 메시지 매핑 제거, 권리 체크 무시).

## 7. AI 비용 상한 (큐 11, 브랜치 cost-cap; D5와의 일치 여부는 설계서가 없어 확인 못 함)
- 설정 `GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE`(기본 **0 = 무제한**, 호환 유지). 값이 있으면 워크스페이스당 UTC 하루 동안 **생성된 작업 수**가 한도에 도달했을 때 `POST /v1/generation-jobs`를 `429`(`DAILY_JOB_LIMIT_EXCEEDED`, `limit`·`used`, `Retry-After`=다음 UTC 자정까지 초)로 차단하고 작업·outbox를 만들지 않음. 잘못된 값(`abc`, `-1`, `2.5`)은 조용히 무제한이 되지 않고 시작 시 오류, 빈 값은 "미설정".
- 세는 기준: 만든 시점의 **모든 작업**(취소·실패 포함 — 이미 Provider 비용이 났을 수 있어서). 같은 `Idempotency-Key` 재생은 세지도 막지도 않음. 다른 워크스페이스·어제 작업은 세지 않음.
- 경합: SQLite는 `BEGIN IMMEDIATE`, PG는 워크스페이스별 advisory lock 안에서 세므로 동시 생성이 한도를 넘지 못함(PG 시험: 동시 10개 생성 → 정확히 3개 성공·7개 차단·작업 3개·outbox 3개).
- 시험: `tests/test_generation_daily_cap.py` 7건(mock Provider, 외부 호출 없음) + PG 2건. 변이 10/10 적발(점검 제거, 일 경계 제거, 워크스페이스 필터 제거, 경계 오프바이원 2종, 라우트 배선 제거, 429→503, PG 잠금 제거(5회 반복), PG 일 경계 제거, PG 점검 제거).
- **미검증/한계**: 사용자(개별) 단위 상한 없음; 금액이 아니라 작업 **개수** 상한이라 비용이 큰 모델과 작은 모델을 구분하지 않음; 크레딧 원장(`credits_ledger`)과 연동되지 않음; 프런트에 작업 생성 화면이 없어 UI 변경 없음(429는 API 클라이언트가 처리); `_impl` 호환 통로(v0.31)는 상한을 적용하지 않음(런타임은 사용하지 않음); 시간은 서버 시계(UTC) 기준.

## 8. 백업·복구 (큐 9, 브랜치 backup-restore)
- `ai_creator_studio_backend_starter/scripts/backup_restore.py`: `backup`(SQLite 온라인 백업 API로 일관된 스냅샷 + 파일 저장소 복사 + `manifest.json`), `verify`, `restore`. DB가 WAL 모드라 파일 복사는 쓰지 않음.
- 안전 규칙: 복구는 **새 빈 디렉터리에만** 하고 기존 데이터를 덮어쓰거나 지우지 않음(비어 있지 않으면 거절); 복구 전에 모든 파일의 SHA-256을 검증하고 하나라도 다르면 아무것도 쓰지 않음; 복구 후 DB `integrity_check`·행 수·해시를 다시 비교; 백업 대상이 데이터 폴더 안이면 거절. 비밀·키·네트워크 사용 없음.
- 사용: `python scripts/backup_restore.py backup --dest <dir>` → `verify <backup>` → `restore <backup> --target <새 폴더>`; 복구 후 출력된 경로를 `ASSET_DATABASE_PATH`·`ASSET_STORAGE_DIR`·`OUTPUT_DIR`로 지정.
- **시험**: `tests/test_backup_restore.py` 15건(실제 API로 자산·상품·포토 초안과 로컬 처리 결과·생성 작업을 만든 뒤 백업 → 복구 → 같은 API로 조회가 일치하는지, 복구된 파일 바이트가 기록된 체크섬과 같은지, 변조·누락·같은 크기 손상·비어 있지 않은 대상·쓰는 중 백업·WAL에만 있는 커밋 데이터·동일 파일 DB·부산물 없음·CLI).
- **변이 검증**: 시험 보강 전 첫 측정에서는 3종이 살아남았고(`verify()`의 체크섬 생략, 온라인 백업 대신 파일 복사, 복구 후 비교 생략) 그중 둘은 기준이 이미 빨간색이어서 증거가 아니었음 — 기준 통과를 확인하는 방식으로 다시 측정. 최종: 적발 = 복구 전 검증 생략, 비어 있지 않은 대상 허용, `verify()` 체크섬 생략, DB 체크섬 생략, 온라인 백업 대신 파일 복사, 파일 영역 생략, 행 수 오기록, DB 복사 후 비교 생략, 파일 복사 후 비교 생략, 대상이 데이터 안, 동일 파일 중복 스냅샷, WAL 부산물, 소요 시간 미기록. **적발 못 함(동치로 판단)**: 복구 시 `integrity_check` 결과만 무시, 읽을 수 없는 DB를 ok로 보고 — 행 수·해시 비교가 같은 손상을 잡는 이중 방어라서.
- 시험 중 찾은 결함: 스냅샷이 WAL 모드로 복사되어 백업 폴더에 `-wal`·`-shm` 부산물이 남음(→ 스냅샷을 단일 파일로 정리), 손상된 복사본에서 원시 `sqlite3.DatabaseError`가 새어 나옴(→ `BackupVerificationError`로 보고).
- **소요 시간(합성 데이터, 이 샌드박스의 로컬 디스크·웜 캐시, 실제 운영 디스크와 다름)**:

| 데이터 | 백업 | 검증 | 복구 |
|---|---|---|---|
| 5.3 MB (파일 50개, 1천 행) | 0.04 s | 0.01 s | 0.04 s |
| 65.8 MB (파일 300개, 2만 행) | 0.25 s | 0.06 s | 0.27 s |
| 1,046.6 MB (파일 1000개, 10만 행) | 2.21 s | 1.20 s | 2.73 s |
- **미검증/한계**: 운영 서버·네트워크 디스크에서의 소요 시간; 백업 파일의 외부 보관·암호화·보존 기간·자동 스케줄(운영 결정, 아직 없음); 복구 훈련을 실제 배포 환경에서 해 본 적 없음; 백업 중 파일 저장소가 바뀌는 경우의 일관성은 DB만 보장(파일은 복사 시점의 상태, 쓰는 중 파일은 해시가 복사본 기준으로 기록됨); `ASSET_STORAGE_DIR`와 `OUTPUT_DIR`만 대상(다른 경로를 쓰면 지정 필요); PG 백업은 범위 밖(런타임은 SQLite).
