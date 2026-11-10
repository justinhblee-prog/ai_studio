# LAUNCH STATUS

> 이 파일은 2026-11-09 세션에서 **새로 만들었다**. 이전에는 저장소의 어느 브랜치와 로컬 파일시스템에도 `docs/LAUNCH_STATUS.md`가 없었다(검색으로 확인). 따라서 이전 내용을 기준으로 정리한 것이 아니라, 이 세션에서 직접 확인한 사실만 적는다. 이전 버전이 따로 있다면 그 내용은 반영되지 않았다.

## 변경 로그 (최신이 위, PR이 머지될 때마다 추가)

### 2026-11-10 · PR #43 (머지 8b3d272) — CLAUDE.md: 설계 창과의 소통 v2 규칙
- **CI (head 89f8fb7, run 42757771977)**: backend success — pytest `902 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — 노드 시험 통과(로그의 `failed` 문자열은 시험 이름뿐); e2e success — 10/10, 6/6 rights, 4/4 disclosure, 6/6 legal, 4/4 account(+layout·roles 단계 success). 로그에 실패 줄 없음.
- **완료**: 폴더 우체통 블록을 v2 블록(붙여 넣기 방식, R-번호별 결과 한 덩어리, 금지선 충돌은 BLOCKED, 사용자 결정은 NEED_USER)으로 교체. 코드 변경 없음.
- **미확인**: PC 쪽 폴더 동기화(클라우드 세션에서 보이지 않음).
- **차단**: 없음.

### 2026-11-10 · PR #46 (머지 6076be7) — L-08 후속: 보류된 자산 위에 새 사진·룩북 작업을 쌓지 못하게 함
- **CI (head 6666308, run 42739460832)**: backend success — pytest `902 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — TypeScript 15개 소스 + 선언 22개 `0 errors`, 패키지 무결성 `0 findings`, `143 structural checks passed`, `vite build` 성공; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `13/13 layout`, `6/6 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: Photo Draft 생성·수정·`process-local`(실행 기록 선점 전 확인 + 렌더링 시점 재확인)과 룩북 attach·내보내기 manifest·패키지가 보류된 자산을 거절, 복구되면 다시 동작. 변이 7종 적발. §24.
- **참고**: PR이 충돌(`dirty`) 상태면 GitHub가 `pull_request` CI를 시작하지 않는다(체크 런 0개). 이번에 그렇게 한 번 기다렸고 main을 합쳐 푸시한 뒤에야 CI가 돌았다.
- **미검증·한계**: 상품·캐릭터가 보류된 자산 ID를 참조로 보여 주는 것, 이미 만든 파생 출력, UI, PostgreSQL.

### 2026-11-10 · PR #45 (머지 0186dd0) — 자동 커밋 연결 위의 다중 쓰기 점검: `create_workspace`·출력 가져오기 수정
- **CI (head 9299ace, run 42732044072)**: backend success — pytest `899 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — TypeScript 15개 소스 + 선언 22개 `0 errors`, 패키지 무결성 `0 findings`, `143 structural checks passed`, `vite build` 성공; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `13/13 layout`, `6/6 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: `app/assets/store.py::create_workspace`(소유자 없는 워크스페이스가 남던 것)와 `app/output_asset_link_worker.py::import_output_asset`(반쯤 들어간 자산이 영구히 재시도 거절되던 것)에 `BEGIN IMMEDIATE`. 실패 주입 시험 2건, 변이 2종 적발. §23.
- **미검증**: 점검은 AST 휴리스틱 + `store.py` 손으로 읽기 기준(다른 모듈은 훑기만 함), PostgreSQL 경로 미점검.

### 2026-11-10 · PR #42 (머지 083a281) — L-08 권리 침해 신고와 임시 비공개 (검수 기준 범위)
- **CI (head 3ba9d13, run 42728659459)**: backend success — pytest `897 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `13/13 layout`, `6/6 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: 신고 API(응답 동일) → 즉시 비공개(소유자만 접근, 서명 링크 무효화) → 운영자 기각/인정/되돌리기, 소유자 상태 조회, 신고자 비노출, 소유자 삭제 차단, 남용 방지, 신고자 계정 purge 익명화. 시험 11건, 변이 12종 적발. §22.
- **미검증·한계**: UI 없음, 보류된 자산을 이미 참조하는 경로(Photo Draft `process-local`, 룩북 패키지 등)는 미차단, PostgreSQL 없음.
- **차단(결정 필요)**: 신고 가능 범위, 처리 기한, 소유자 알림·이의제기, `remove`된 파일의 물리 삭제 시점.

### 2026-11-10 · PR #41 (머지 d4004d6) — L-05 접속 로그: 문서의 항목 목록과 코드 일치, 본문·서명 URL 비기록 고정
- **CI (head 0037b3a, run 42727853148)**: backend success — pytest `886 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `13/13 layout`, `6/6 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: `LOGGED_FIELDS`가 단일 출처, RUNBOOK 키 표와 코드를 시험이 대조, 요청 본문·본문 속 서명 URL이 로그에 없음을 시험, 만료 로그 삭제 방법 문서화. 변이 6종 적발. 표는 §21.
- **미검증**: 정책의 보유 기간과의 일치(정책 없음, 30일은 임시 기본값), RUNBOOK의 수동 삭제 명령은 실행하지 않음, uvicorn 자체 접근 로그는 운영에서 `--no-access-log` 필요.

### 2026-11-10 · PR #40 (머지 4337a43) — L-07 AI 생성물 표시를 검수 기준으로 확인하고 시험으로 고정
- **CI (head 290ab58, run 42727073288)**: backend success — pytest `882 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `13/13 layout`, `6/6 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: 룩북 내보내기 manifest `outputs[*]`와 패키지(ZIP) manifest(최상위·`outputs[*]`)의 표시 필드를 시험으로 고정, "사용자가 끌 수 없음" 시험 3건. 변이 5종 적발. 표는 §20.
- **한계(기준이 요구한 명시)**: 메타데이터와 화면 배지뿐, **이미지 자체에 눈에 보이는 표시는 없음**(법무 검토 사항). 실제 외부 Provider로는 검증하지 않음.

### 2026-11-09 · PR #39 (머지 8bf3718) — D2: 이미지 버전 업로드의 권리 선언, `save_asset` 원자성
- **CI (head d1ba50f, run 42724362735)**: backend success — pytest `879 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `13/13 layout`, `6/6 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료(결함 2건 수정)**: 이미지 자산의 새 버전 업로드가 권리 선언 없이 되던 것(이제 서버가 강제, 선언은 출처 기록에 저장), `save_asset`이 자동 커밋 연결 위에서 한 트랜잭션이 아니었던 것(`BEGIN IMMEDIATE`; 고장 주입 시험). 변이 4종 적발. §19.
- **미검증**: 같은 모양의 다른 쓰기 함수(`app/assets/store.py`) 전수 점검 안 함.
- **차단/결정**: D2는 기본 켜짐 유지(사용자 결정, 2026-11-10). 서버의 동의 강제는 꺼 둠(사용자 결정이 날 때까지 바꾸지 않음).

### 2026-11-09 · PR #38 (머지 8aa0211) — 문서·`tasks.json` 갱신, 차단 표 정리
- **CI (head 922dbf4, run 42717141311)**: backend success — pytest `873 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `13/13 layout`, `6/6 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: 낡은 차단 표를 현재 상태로 다시 씀, `tasks.json`(T19·T60·T61·T66·T69·T77 완료 처리, T78~T82 추가), Supabase TEST 환경 상황 기록. 코드 변경 없음.
- **차단**: 실제 Supabase TEST 로그인(공개 키 주입이 아직 안 됨, 비밀번호는 요청 본문이라 프록시 폼으로 못 넘김).

### 2026-11-09 · PR #37 (머지 951f8d6) — D2 업로드 권리 확인: 기본 필수 + 기록 표 + 보존 규칙
- **CI (head 5039aaf, run 42715972017)**: backend success — pytest `873 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `13/13 layout`, `6/6 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: `ASSET_REQUIRE_RIGHTS_CONFIRMATION` 기본 켜짐, 표 `upload_rights_confirmations`, `GET /v1/assets/{id}/rights-confirmation`, 자산 삭제 시 기록 삭제, 공유 워크스페이스 계정 purge 시 `deleted-user` 익명화. 설계 창의 인수 시험 4건·삭제 연동 2건(3차 패키지)을 내 구현에 돌려 통과(상수 하나만 변경), 내 시험 10건 추가, 변이 8종 적발. 기준 구현과의 차이는 §18.
- **미검증**: PostgreSQL(표 없음, 런타임 미사용), 정책 버전은 문서 초안 버전.
- **차단/결정 필요**: **기본 필수냐 호환 유지(꺼짐)냐** — 설계 창 문서끼리 갈림(`DEV_NONSTOP_PROMPT`는 필수, `W04_D2_ACCEPTANCE`·기준 구현은 기본 꺼짐); 지금은 켜짐.

### 2026-11-09 · PR #35 (머지 a1a3372) — 설계 창 launch_gate (독립 패치)
- **CI (head 3e1a514, run 42714560517)**: backend success — pytest `857 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `13/13 layout`, `6/6 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: 출시 전 게이트 스크립트(시험·의존성 점검·백업 훈련, 수동 5항목은 항상 NOT_RUN). 패치의 백업 훈련이 main에 없는 스크립트를 불러 실패하므로 일회용 DB 위의 `backup_restore.py` 훈련으로 바꿈. 시험 6건, 변이 5종 적발.
- **미검증**: CI에서 이 스크립트를 실행하지 않음, 의존성 점검은 설치된 환경 대상.
- **차단**: 없음.

### 2026-11-09 · PR #36 (머지 52a8bac) — 재동의 브라우저 시험
- **CI (head 922457b, run 42713834168)**: backend success — pytest `851 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `13/13 layout`, **`6/6 legal screen`**, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: 문서 버전이 바뀐 뒤 바뀐 문서만 다시 묻고, 서버도 다시 닫히고, 동의하면 열리며 이력은 옛 수락을 남김. 변이 1종 적발.
- **미검증**: 버전 상승은 DB의 수락 기록을 옛 버전으로 바꿔 흉내 낸 것(실제 환경 변수로 서버를 다시 띄우지 않음).
- **차단**: 없음.

### 2026-11-09 · PR #34 (머지 4b33004) — 설계 창 패치 9: authz_seeded
- **CI (head 8c07d38, run 42626231677)**: backend success — pytest `851 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`, `5/5 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: 실제 객체가 있는 상태의 인가 시험 3건(상품 변형, Lookbook, Photo process-local; 비멤버·뷰어). 패치 README의 변이는 이 경로들이 쓰지 않는 층(`routes.require_role`)을 깨는 것이라 적발되지 않아, 실제로 쓰는 층(`ports/workspace.require_role` 등)에서 4종을 다시 시행해 모두 적발.
- **미검증**: Lookbook 내보내기 다운로드(서명 토큰)와 `POST /v1/workspaces`는 이 시험이 판정하지 못함; Photo 초안 생성의 쓰기 검사 약화는 이 시험이 못 잡음(인가 행렬 몫).
- **차단**: 없음.

### 2026-11-09 · PR #32 (머지 cdc13f3) — 레이아웃 시험에 게이트·계정 패널 추가
- **CI (head e80f65e, run 42626726671)**: backend success — pytest `848 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, **`13/13 layout`**, `5/5 legal screen`, `4/4 account flow`. 로그에 `failed` 없음. (첫 CI 실행에서 e2e가 `pilot_flow`의 시험 경합으로 한 번 실패 → PR #33으로 수정한 뒤 main을 병합해 다시 돌린 결과.)
- **완료**: 설정(계정 패널)과 동의 게이트가 열 개 폭(360~1280 px)에서 가로로 넘치지 않음을 확인(변이 2종 적발).
- **미검증**: 가로 넘침만 봄(시각 품질 아님), 3D 스튜디오·검수 화면은 대상 아님.
- **차단**: 없음.

### 2026-11-09 · PR #33 (머지 032bb2b) — E2E 시험의 경합 하나 수정 (`pilot_flow` 초안 저장)
- **CI (head 7375e00, run 42625907062)**: backend success — pytest `848 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`, `5/5 legal screen`, `4/4 account flow`. 로그에 `failed` 없음.
- **배경**: PR #32의 CI e2e가 이 단계에서 한 번 실패(`0 !== 1`) — 제품 결함이 아니라 시험의 경합(목록 대기 ≠ 저장 요청 완료 대기). POST를 600 ms 지연시켜 재현, 응답을 기다리도록 수정하고 같은 지연으로 통과 확인.
- **미검증**: 같은 모양의 다른 단계는 전수 점검하지 않음(실제로 실패한 한 곳만 수정).
- **차단**: 없음.

### 2026-11-09 · PR #31 (머지 2e8d8a1) — 서버의 동의 강제 (`LEGAL_REQUIRE_ACCEPTANCE`)
- **CI (head 9e872f3, run 42624754322)**: backend success — pytest `848 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`, `5/5 legal screen`(서버를 강제 모드로 띄움), `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: 설정을 켜면 동의 안 한 사용자의 API 호출이 403 `LEGAL_ACCEPTANCE_REQUIRED`(동의·철회·삭제 요청·`/internal/` 제외). 프런트는 동의 확인 뒤에 워크스페이스를 불러오거나 만든다. 변이 7종 적발.
- **미검증**: 운영에서 켤지는 결정 필요(**기본 꺼짐**), 요청당 SQLite 질의 1회의 부하, 켠 상태의 전체 E2E, PostgreSQL.
- **차단**: 없음.

### 2026-11-09 · PR #30 (머지 5300688) — 동의 화면·삭제 요청 화면 (L-02 프런트 / L-01 화면)
- **CI (head 2557512, run 42623611639)**: backend success — pytest `842 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 통과(`legalApi.test.mjs` 5건 포함), `vite build` 통과; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`, **`5/5 legal screen`**, `4/4 account flow`; 의존성 점검 워크플로의 `python`·`node` 잡도 success. 로그에 `failed` 없음.
- **완료**: 필수 문서 3개에 모두 체크해야 스튜디오가 열리는 게이트, 선택 항목(AI 학습, 기본 해제), 설정에서 철회·계정 삭제 요청·취소. 화면 변이 6종 적발.
- **미검증**: 서버 강제(이 PR 시점엔 없음 → 다음 PR), 재동의 화면 E2E, 모바일 폭 게이트 레이아웃, 문서 본문(앱에 없음).
- **차단**: 문서 본문·법률 빈칸(입력 필요).

### 2026-11-09 · PR #27 (머지 c074810) — 설계 창 패치 8/9: deps_upgrade (문서만)
- **CI (head 7b6db80, run 42613840354)**: backend success — pytest `842 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`, `4/4 account flow`. 로그에 `failed` 없음.
- **완료**: 패치의 의존성 상향은 PR #18로 이미 main에 있음을 확인(코드 변경 없음). `pip-audit -r requirements.txt` → `No known vulnerabilities found`.
- **미검증**: 알려진 취약점 DB 기준일 뿐; 잠금 파일 없음; 프런트 API 클라이언트의 `contentMediaType` 사용 여부; 배포 환경의 requirements.
- **차단**: 없음.

**설계 창 패치 9개 반영 완료(2026-11-09)**: #20 legal, #21 consent, #22 backup, #23 cost_cap, #24 purge, #25 authz v2, #26 ops_check, #27 deps_upgrade(확인만), #28 e2e. 각 PR의 CI 수치는 위 항목. 새 기능으로 반영한 것은 legal·consent·purge·authz·ops_check, main 구현과 비교해 일부만 이식한 것은 backup·cost_cap·e2e, 변경 없이 확인만 한 것은 deps_upgrade. 패치 자체의 결함을 찾아 고친 것: ops_check 3건(위 #26). 이 문서의 수치는 모두 main(FastAPI 0.162.2)에서 측정한 값이며, 설계 창의 681 통과 등은 다른 기준선의 값이다.

### 2026-11-09 · PR #28 (머지 669dd09) — 설계 창 패치 9/9: e2e
- **CI (head 4e9258f, run 42613136750)**: backend success — pytest `842 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`, **`4/4 account flow`(새 단계)**. 로그에 `failed` 없음.
- **완료**: 패치의 두 번째 하네스는 추가하지 않고 main의 Node 흐름 유지; 빠진 시나리오(법률 문서 수락, 삭제 요청 수명 주기, Character 참조 보호)를 API 수준 흐름 `account_flow.mjs`로 추가하고 CI 단계로 등록. 변이 6종 중 5종 적발, 1종은 동등 변이.
- **미검증**: **화면 시험은 없음**(동의 화면·삭제 요청 화면이 구현되지 않음; 가입·동의 화면 시나리오 미작성), 실제 Supabase.
- **차단**: L-02 프런트 동의 화면(설계 입력 없음).

### 2026-11-09 · PR #26 (머지 e802f6c) — 설계 창 패치 7/9: ops_check
- **CI (head bf70190, run 42612593542)**: backend success — pytest `842 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`. 로그에 `failed` 없음.
- **완료**: 읽기 전용 점검 스크립트(종료 코드 0/1/2). **패치의 결함 3건을 고침**: `idle`·`working` 작업자를 죽은 것으로 봐 거짓 치명을 내던 것, 백업 나이를 폴더 수정 시각으로 계산하던 것(매니페스트 `created_at`으로 변경), 숫자가 아닌 한도 값에서 죽던 것. 시험 6 → 9건, 변이 10종 적발.
- **미검증**: 실제 환경 실행, 알림 전송(없음), PostgreSQL.
- **차단**: 없음.

### 2026-11-09 · PR #25 (머지 cf140fa) — 설계 창 패치 6/9: authz v2
- **CI (head 673ac95, run 42612106352)**: backend success — pytest `833 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`. 로그에 `failed` 없음. (CI 통과 뒤 main과 문서 충돌이 나 main을 병합해 재실행한 결과.)
- **완료**: 인가 행렬 시험 2건(익명 401, 비회원 2xx 금지, viewer 쓰기 2xx 금지). 앱 코드 수정 없이 main에서 통과. 변이 2종 적발.
- **미검증**: 인가가 판정하지 못하는 작업 7개(422로 먼저 거부됨), 본인 범위 조회·`/v1/me/` 쓰기.
- **차단**: 없음.

### 2026-11-09 · PR #24 (머지 0742599) — 설계 창 패치 5/9: purge
- **CI (head c014cdb, run 42611141094)**: backend success — pytest `831 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`. 로그에 `failed` 없음.
- **완료**: 삭제 요청 처리 스크립트(기본 dry-run, 요청 하나씩 `--apply --confirm`, 유예 7일, 알 수 없는 표는 닫힘 실패). 패치 시험 12건 + 내 시험 1건. 현재 main의 실제 스키마에서 막히는 표 없음 확인.
- **미검증**: 실데이터 실행(첫 실행은 승인 필요), 룩북 표, PostgreSQL, 백업에 남은 사본 처리.
- **차단**: 실데이터 첫 실행 승인.

### 2026-11-09 · PR #23 (머지 c6deae2) — 설계 창 패치 4/9: cost_cap
- **CI (head d31797a, run 42610627487)**: backend success — pytest `818 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`. 로그에 `failed` 없음. (이 PR은 CI 통과 뒤 main과 문서 충돌이 나서 main을 병합하고 표를 손으로 합친 뒤 CI를 다시 돌렸음; 코드는 같음.)
- **완료**: main의 일일 상한은 유지하고 월간 워크스페이스 상한·전역 월간 상한·mock 면제·킬 스위치 `AI_JOBS_DISABLED`(API + 워커) 추가. 변이 8종 모두 적발.
- **미검증**: 실제 Provider 비용과의 대응(단위는 작업 수), PostgreSQL 경로(미적용), 기본 월 200건의 근거.
- **차단**: 없음.

### 2026-11-09 · PR #22 (머지 fe8ec24) — 설계 창 패치 3/9: backup
- **CI (head 469cda0, run 42609868876)**: backend success — pytest `811 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`. 로그에 `failed` 없음.
- **완료**: main 구현 유지, 패치에서 심볼릭 링크 건너뛰기와 매니페스트에 없는 파일 보고를 이식(시험 +2, 변이 2종 적발, 동등 변이 1종은 코드 삭제).
- **미검증**: 심볼릭 링크로 연결된 실제 저장소 구성, 실제 배포 환경에서의 백업·복구.
- **차단**: 없음.

### 2026-11-09 · PR #21 (머지 3ab4616) — 설계 창 패치 2/9: consent
- **CI (head 79e0929, run 42608986871)**: backend success — pytest `809 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 + 3 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`. 로그에 `failed` 없음.
- **완료**: `consents` 테이블과 `GET /v1/me/consents`, `PUT /v1/me/consents/{purpose}`(목적은 `ai_training` 하나, 기본은 미동의, 이력은 추가만 하고 현재 상태는 마지막 행). 스냅샷 +2 경로(89→91).
- **미검증**: 동의가 학습 파이프라인에서 실제로 존중되는지(그런 파이프라인이 아직 없음), 프런트엔드 동의 화면(L-02 프런트, 미구현), PostgreSQL 이식(SQLite 전용).
- **차단**: 없음.

### 2026-11-09 · PR #20 (머지 d26aab9) — 설계 창 패치 1/9: legal
- **CI (head 65fe0ab, run 42608327049)**: backend success — pytest `804 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 + 3 pass/0 fail, `vite build` 통과; e2e success — `10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`. 로그에 `failed` 없음.
- **완료**: 약관·개인정보 동의 기록 API와 삭제 요청 기록 API(새 경로 5개). 변이 12종 중 11종 적발(1종은 동치). 세부 §14.
- **미검증**: 동의 화면(프런트) 없음; 다른 라우트에서 동의를 강제하지 않음; 삭제 요청은 기록만 하고 실제 삭제는 패치 5(purge) 몫; SQLite 전용; 법률 본문은 초안이며 빈칸을 채우지 않았음.
- **차단**: 법률 빈칸(연락처 이메일, 개인정보 보호책임자, 책임 한도, 관할 법원, 시행일, 생성물 권리) — 사용자 결정 필요.

### 2026-11-09 · PR #18 (머지 3625e18) — FastAPI 0.162.2 / Starlette 1.10 업그레이드
- **CI (head 239e066, run 42602714915)**: backend success — pytest `792 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 + 3 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`, `11/11 layout`. **dependency-audit(run 42602714668)**: python `No known vulnerabilities found`, node `found 0 vulnerabilities`. 로그에 `failed` 없음.
- **완료**: Starlette 7건 해결로 백엔드 알려진 취약점 0건(31개 패키지); 보안 표면 시험의 맹점(감싼 라우터를 건너뛰어 `/internal/` 시험이 아무것도 검사하지 않고 통과) 수정 + OpenAPI 대조 자체 검증, 변이 4/4 적발; 주간·PR 자동 점검 워크플로. 세부 §13.
- **미검증**: 주요 버전 점프(Starlette 0.46 → 1.10)의 시험 밖 동작 변화, 주간 예약 실행(아직 한 번도 안 돌았음), 잠금 파일 없음.
- **차단**: 없음.

### 2026-11-09 · PR #17 (머지 a20944c) — Pillow 13·pytest 9
- **CI (head d8cdf6b, run 42573509167)**: backend success — pytest `791 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 + 3 pass/0 fail, `vite build` 통과; e2e success — `10/10`, `6/6`, `6/6`, `4/4`, `11/11 layout`. 로그에 `failed` 없음.
- **완료**: `pip-audit`가 찾은 `pillow` 39건(이미지 처리 라이브러리)·`pytest` 1건을 상향으로 해결(`Pillow>=13,<14`, `pytest>=9.0.3,<10`); 프런트 `npm audit` 0건 확인.
- **미검증·남은 것**: 이 시점에는 `starlette` 7건이 남아 있었음(PR #18에서 해결).
- **차단**: 없음.

### 2026-11-09 · PR #16 (머지 e15871d) — 태블릿 폭 레이아웃 수정
- **CI (head df7dd19, run 42572608929)**: backend success — pytest `791 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 + 3 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10`, `6/6`, `6/6`, `4/4`, **`11/11 layout checks (10 widths x 7 screens)`**. 로그에 `failed` 없음.
- **완료**: 768px에서 4개 화면이 가로로 넘치던 실제 결함 수정(2열→1열 기준 760→900px), 반응형 E2E 추가, 변이 3/3 적발. 세부 §12.
- **미검증**: 3D 스튜디오·검수 화면 미포함, 터치 크기·가독성 미확인, 헤드리스 Chromium만.
- **차단**: 없음.

### 2026-11-09 · PR #15 (머지 5593ea1) — 출시 체크리스트 초판
- **CI (head 8755d93, run 42571538514)**: backend success — pytest `791 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 + 3 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`. 로그에 `failed` 없음. (문서만 바뀐 PR이라 코드 시험 수치는 직전과 같음.)
- **완료**: `docs/LAUNCH_CHECKLIST.md` 32개 항목을 증거 유무로 분류(완료 6·부분 12·미완료 8·차단 6), L-08 차단 기록.
- **미검증**: 항목은 이 세션의 구성이며 원본 체크리스트가 아님.
- **차단**: L-08 절차 명세.

### 2026-11-09 · PR #14 (머지 55d5e37) — L-05 접근 로그
- **CI (head 8a375b2, run 42571076849)**: backend success — pytest `791 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 + 3 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`. 로그에 `failed` 없음.
- **완료**: 요청당 JSON 한 줄 접근 로그(라우트 템플릿, 상태, 소요, 가명 actor, 검증된 요청 ID, 쿼리·헤더·토큰·서명 미기록), 일 단위 회전·보관 일수 설정. 변이 19/19 적발. 세부 §11.
- **미검증**: 항목·보관 기간(30일)은 법적 명세와 대조하지 않은 임시값; 보안 이벤트 전용 로그·외부 전송·변조 방지 없음; 부하 시 성능 미측정.
- **차단**: 법적 보관 기간·항목 명세.

### 2026-11-09 · PR #13 (머지 b6c011d) — 심층 점검·런북·워커 판정 수정
- **CI (head c7faed7, run 42570558102)**: backend success — pytest `777 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 + 3 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`. 로그에 `failed` 없음.
- **완료**: `GET /internal/ops/health`(DB·저장소·디스크·필수 워커·백업, 실패 시 503), `docs/RUNBOOK.md`, 결함 2건 수정(idle/working 워커의 거짓 critical 알림, 점검이 없는 DB를 만들던 부작용). 변이 20/20 적발. 세부 §10.
- **미검증**: 런북 절차를 실제 배포에서 실행해 본 적 없음; 점검 임계값 기본값은 근거 없는 출발점; 외부 서비스 가용성은 점검하지 않음.
- **차단**: 배포 대상 정보(영속 디스크 유무).

### 2026-11-09 · PR #12 (머지 1567d9e) — L-07 AI 생성물 표시
- **CI (head 4789581, run 42569714594)**: backend success — pytest `745 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 + 3 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`, `4/4 disclosure`. 로그에 `failed` 없음.
- **완료**: Provider 작업 출력의 AI 생성물 표시(목록·검수 API, 내부 manifest, 검수 화면 배지). 사진·룩북의 기존 `is_ai_generated: false`는 중복 구현하지 않고 시험으로 고정. 변이 백엔드 9/9·브라우저 4/4 적발. 세부는 §9.
- **미검증**: 실제 Provider 경로(E2E의 작업 출력은 시드); 법적으로 요구되는 표기 문구·워터마크·메타데이터; 내보낸 이미지 파일 자체의 AI 표시 없음.
- **차단**: 표기 문구는 법무 입력 필요.

### 2026-11-09 · PR #11 (머지 911fa32) — 백업·복구
- **CI (head 4f86afe, run 42568761241)**: backend success — pytest `740 passed, 1 warning`, 실DB 단계 `78 passed, 1 warning`; frontend success — `tsc` 통과, `test:source` 8 + 4 + 4 pass/0 fail, `vite build` 통과; e2e success — `SUMMARY 10/10`, `6/6 rights`, `6/6 role scenarios`. 로그에 `failed` 없음.
- **완료**: SQLite 온라인 백업 + 파일 저장소 + 매니페스트 해시 검증, 새 빈 디렉터리로만 복구, 백업→복구→API 조회 일치 시험 15건, 소요 시간 기록(§8). 시험 중 결함 2건 발견·수정(스냅샷의 WAL 부산물, 손상 시 원시 sqlite 오류 노출). 변이 13종 적발, 2종은 동치로 판단(적발 못 함).
- **미검증**: 실제 서버·네트워크 디스크 소요 시간, 외부 보관·암호화·보존·스케줄, 실제 배포에서의 복구 훈련.
- **차단**: L-01 영구 삭제(삭제 요청 테이블·API 없음).

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

## 차단 (입력·승인이 없어 하지 못한 것; 다른 작업은 계속 진행) — 2026-11-09 갱신
이전 표의 "패치 zip 없음·D1 미확인·삭제 스크립트 없음" 등은 패키지를 받아 모두 해소되었다(§14, §15~§18). 지금 남은 것:

| 항목 | 이유 | 필요한 것 |
|---|---|---|
| 실제 Supabase TEST 로그인 확인 | 네트워크는 허용됨(새 환경 `ai_studio`에 호스트 `nfhtwefjlhuuorncovoj.supabase.co` 1개). 공개 키를 프록시에 저장했지만 `apikey` 주입이 아직 안 되어 `401 Invalid API key`(프록시 반영 지연일 수 있음, 최대 약 1시간). 또 비밀번호는 요청 **본문**에 들어가야 하는데 프록시 폼은 **헤더**만 주입하므로 제가 로그인할 수 없음. 비밀번호는 채팅에 노출되어 변경 권장 | 사용자가 직접 실행하는 스모크(비밀번호는 실행하는 쪽 환경 변수로만), 또는 키 재확인 |
| 법률 문서 빈칸 | 연락처 이메일, 개인정보 보호책임자, 책임 한도, 관할 법원, 시행일, 생성물 소유권 — 임의로 채우지 않음 | 사용자 결정 |
| 첫 실데이터 purge 실행 | 되돌릴 수 없는 삭제 | 백업·dry-run 확인 후 요청별 승인 |
| L-08 침해 신고 접수·임시 비공개 | 접수 주체·인증·절차·처리 기한·이의제기가 법적 절차라 명세 없음 | 절차 명세 |
| 실제 Provider 검증 | 유료 호출 | 예산 승인·테스트 키 |
| 배포 환경 세부(호스트·디스크·도메인) | 배포 B(프런트 서버리스 + 단일 백엔드 서버, SQLite)는 결정됨, 세부 정보 없음 | 배포 대상 정보 |
| 운영 설정 결정 2가지 | ① `LEGAL_REQUIRE_ACCEPTANCE`를 켤지(서버가 동의를 강제, 기본 꺼짐) ② 업로드 권리 확인을 **기본 필수**로 둘지(현재 켜짐; 설계 창 문서끼리 갈림) | 사용자 결정 |
| TEST Supabase에 0011–0013 적용 | 금지 항목 | — |
| Production Supabase/Vercel, 유료 Provider, Production `DATABASE_BACKEND=postgresql`, 실데이터 영구 삭제, 비밀·키 입력·저장 | 금지 항목 | — |

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
| L-02 프런트 동의 화면 | **구현(§15)** — 문서 본문은 초안이라 앱에 없음, 서버는 강제하지 않음 |
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

## 9. AI 생성물 표시 (큐 10 / L-07, 브랜치 ai-label)
- **이미 있던 것(중복 구현 안 함)**: 사진 스튜디오 manifest·룩북 출력/패키지 manifest·파생 자산 출처에는 `is_ai_generated: false`가 이미 있고, 사진 UI는 "비AI 로컬 조정"을 표시함(Pillow 기반 결정적 조정이라 사실과 일치).
- **빠져 있던 것(이번에 구현)**: 외부 Provider가 만든 **작업 출력**에는 표시가 전혀 없었음. 이제 ① 출력 목록 API(`/v1/generation-jobs/{id}/outputs`)에 `is_ai_generated`·`provider`·`model`, ② 검수 API 응답의 `output.is_ai_generated`, ③ 내부 내보내기 manifest의 최상위·출력별 `is_ai_generated`, ④ 결과물 검수 화면의 배지("AI 생성물 · fashn / tryon-v1.6" / "AI 미사용 출력" / 서버가 값을 안 주면 "AI 생성 여부 미확인").
- 판정 규칙(`app/ai_disclosure.py`): Provider가 `mock`이면 AI 아님, **그 외·알 수 없음·비어 있음은 AI 생성물로 표시**(애매하면 공개 쪽). 판정은 작업의 Provider 하나로만 하며 저장소는 건드리지 않음(SQLite/PG 공통, OpenAPI 스냅샷에는 선택 필드 4개만 추가).
- 시험: 백엔드 API 시험 5건(mock/fashn/미지정, 목록·검수·manifest, 헬퍼) — 변이 9/9 적발; 프런트 로직 3건; 브라우저 `disclosure_flow.mjs` 4/4 단계(10회 연속 통과) + 파이프라인 흐름에서 ZIP의 `manifest.json`이 `is_ai_generated: false`임을 확인 — 변이 4/4 적발(배지 제거, 항상 AI 미사용, API 미표시, 패키지 manifest 반전).
- **한계/미검증**: ① mock Provider는 이미지를 만들지 않아 **E2E의 작업 출력은 시드한 것**(단위 시험과 같은 방식) — 실제 Provider 경로는 끝까지 시험하지 않음. ② 표시 문구는 제품 문구이며 법적으로 요구되는 표기 문구·형식(워터마크, 메타데이터 삽입 등)은 정하지 않음 — 법무 입력 필요. ③ 내보낸 이미지 파일 자체에는 AI 표시를 넣지 않음(manifest와 화면에만). ④ 작업 출력 manifest는 SQLite 구현에만 있음(PG에는 해당 manifest 구현이 없음). ⑤ 룩북에 Provider 출력이 들어오는 경로는 아직 없어 룩북 항목별 AI 판정은 "로컬 보정 = 아님"으로 고정(그 경로가 생기면 다시 판정해야 함).

## 10. 심층 점검과 런북 (큐 14, 브랜치 health-runbook)
- `GET /internal/ops/health`(운영자 전용): DB 존재·읽기·`PRAGMA quick_check`, 저장 폴더 쓰기, 디스크 여유 비율(경고 15% 미만, 실패 5% 미만), 필수 워커의 신선한 하트비트(+ 수동 조정이 필요한 제출 수), 최신 백업 나이(26시간 초과·없음·미설정은 경고). 전체 상태는 가장 나쁜 값이고 **실패면 HTTP 503**. 응답에 파일 경로·비밀 없음. `/health`는 공개 최소 생존 확인 그대로.
- `docs/RUNBOOK.md`: 프로세스, 설정 표, 점검 해석, 백업·복구 절차, 장애 대응 표, 배포·롤백, 다루지 않는 것. **실제 배포에서 실행해 본 적은 없음**(배포 대상 정보 없음).
- **시험 중 발견·수정한 결함 2건**: ① 워커 건강 판정이 상태 `running`만 인정해서, `idle`/`working`만 보내는 `output_asset_link` 워커가 **항상 비정상**으로 판정되고 기본 `REQUIRED_WORKER_TYPES`에 포함되어 있어 운영 알림에 `worker:output_asset_link:stale` **거짓 critical 알림**이 났음(기존 `/internal/ops/workers`·`metrics`도 같은 영향) → `running`·`idle`·`working`+신선한 하트비트를 살아 있음으로 통일(SQLite 두 곳). ② 점검이 호출하는 워커 상태 조회가 스키마를 초기화하면서 **없는 DB 파일을 새로 만들었음**(장애로 DB가 사라졌을 때 빈 DB가 생겨 문제를 가림) → DB 파일이 없으면 만들지 않고 실패 보고. 이 둘은 새 시험이 기준선에서 먼저 빨갛게 나온 것으로 확인했고(수정 전 실패 확인), 수정 후 통과.
- 시험: `tests/test_deep_health.py` 24건(각 점검의 ok/warn/fail, 없는 DB·손상 DB·quick_check 실패·폴더 아님·쓰기 불가·디스크 임계값·필수 워커 없음/오래됨·수동 조정·백업 신선도·가장 나쁜 값·엔드포인트 인증·503), `tests/test_worker_liveness.py` 8건. 변이 20/20 적발(처음 1건이 살아남아 사유 문구·"DB를 만들지 않음" 단언을 추가해 적발, 그 과정에서 위 결함 ②를 발견). 시험은 실제 디스크 여유에 의존하지 않도록 `disk_usage`를 고정(이 샌드박스는 실제 여유가 11.7%라 경고가 나왔음).
- OpenAPI 스냅샷: 새 경로 1개만 추가(45줄 추가, 삭제 0).
- **미검증/한계**: `PRAGMA quick_check`는 전체 `integrity_check`보다 약함; 디스크 임계값·백업 나이 기본값은 근거 있는 값이 아니라 출발점; PG 런타임 점검은 범위 밖(런타임은 SQLite); 점검은 외부 서비스(Supabase Auth, Provider)의 가용성을 보지 않음; 점검 결과를 외부 모니터에 연결하는 일은 하지 않았음.

## 11. 접근 로그와 보관 설정 (큐 15 / L-05, 브랜치 access-log)
- `app/access_log.py`: 요청마다 JSON 한 줄. 항목·비기록 항목·설정은 `docs/RUNBOOK.md` 3-1절. 요청 ID는 짧은 일반 토큰일 때만 받아들이고(줄바꿈·공백 등은 새 ID로 교체해 로그 위조 방지) 응답 헤더로 돌려줌. 보관: `ACCESS_LOG_DIR` 지정 시 UTC 자정 회전 + `ACCESS_LOG_RETENTION_DAYS`개 유지(0은 시작 시 거부). 인증 의존성이 `request.state.actor`를 채우되 기존 `current_user("Bearer …")` 직접 호출 시그니처는 유지.
- **발견**: 이 앱에는 로깅이 전혀 없었고 uvicorn 기본 접근 로그는 쿼리 문자열을 남겨 서명 URL의 `signature`가 로그에 들어감 → 런북에 `--no-access-log` 권고.
- 시험 `tests/test_access_log.py` 14건 + 기존 전체 통과. 변이 19/19 적발(원본 경로 기록, 쿼리·Authorization 기록, 임의 요청 ID 수용, ID 검증 제거, 헤더 미반환, 작업공간 ID 검증 제거, 항상 평문/none 무시, IP 항상 기록, 비활성화 불가, 500 미기록, 오류 메시지 노출, 보관·회전 미적용, 핸들러 중복, 보관 0 허용, 잘못된 actor 모드 허용, actor 미기록). 시험 작성 중 내용 없는 단언(`or True`)을 스스로 발견해 실제 검증으로 교체.
- **한계/미검증 — 중요**: ① **로그 항목 목록과 보관 기간(30일)은 내가 정한 엔지니어링 선택이며 법적 명세와 대조하지 않았다**(L-05 문서 없음). 법적 보관 기간·접근 통제·열람·삭제 요청 시 처리 정책은 정해지지 않음. ② 보안 이벤트 전용 로그(로그인 실패 집계, 권한 거절 알림)는 없음 — 상태 코드 401/403이 접근 로그에 남을 뿐. ③ 로그 파일 외부 전송·변조 방지·암호화 없음. ④ 워커 프로세스는 접근 로그를 남기지 않음(HTTP 요청이 없음). ⑤ 한 번에 많은 요청이 올 때의 성능 영향은 측정하지 않음. ⑥ 해시는 `ASSET_SIGNING_SECRET`을 솔트로 쓰며, 그 값을 바꾸면 같은 사용자의 해시가 달라짐.

## 12. 반응형 레이아웃 (체크리스트 #30, 브랜치 e2e-mobile)
- **발견·수정한 결함**: 태블릿 폭(예: 768px)에서 프로젝트·상품·포토·룩북 4개 화면이 가로로 넘쳤음(`scrollWidth` 최대 849px > 768px). 원인: 2열 격자는 760px 이하에서 1열이 되지만 사이드바(248px)는 그 구간에서 여전히 본문 옆에 있어, 본문 폭(768px에서 418px)이 2열 최소 폭 합(260+220+간격=496px)보다 작아 오른쪽 열이 밖으로 나감. 수정: 1열 전환 기준을 760px → 900px(2열이 들어가려면 850px 이상 필요). 처음 시도한 `min-width:0`·`overflow-wrap` 보정은 부분 개선(849→795px)에 그쳐 원인이 아니라고 판단하고 되돌림.
- 시험: `e2e/layout_flow.mjs` — 10개 폭(360·390·700·701·768·840·900·901·1024·1280) × 7개 화면에서 문서 `scrollWidth`가 뷰포트를 넘지 않는지 확인. 로컬 3회 연속 `11/11`. 변이 3/3 적발(상품·포토 격자를 예전 기준으로 복원 → 768px에서 795px·854px 넘침, 강제 폭 1100px).
- **미검증/한계**: 3D 스튜디오(WebGL)와 결과물 검수 화면(작업 필요)은 대상 아님; 가로 넘침만 봄 — 터치 대상 크기·글자 크기·가독성·세로 길이는 확인하지 않음; 헤드리스 Chromium만; 폰 폭의 하단 탭 바는 의도적으로 가로 스크롤(문서 폭만 측정).
## 13. 의존성 취약점 점검 (체크리스트 #25, PR #17 + 브랜치 fastapi-upgrade)
- **실행한 것**: 프런트 `npm audit`(130개 패키지) → **취약점 0건**. 백엔드 `pip-audit 2.7.3 -r requirements.txt`(공개 취약점 DB 조회만, 비밀·유료 호출 없음).
- **발견(수정 전, 29개 패키지)**: `pillow 12.3.0` 39건(수정 버전 13.0.0 이상 — 사용자가 올린 이미지를 처리하는 라이브러리), `starlette 0.46.2` 7건(수정 버전 1.3.1 이상), `pytest 8.4.2` 1건(개발용).
- **수정 1 (PR #17)**: `Pillow>=13,<14`(예전 상한 `<13`이 수정 버전을 막고 있었음), `pytest>=9.0.3,<10`. 전체 `713 passed, 78 skipped`, 실DB `78 passed`. 재점검 시 `starlette` 7건만 남음.
- **수정 2 (이 PR)**: `fastapi==0.115.14` → `0.162.2`, `starlette>=1.3.1,<2.0`(FastAPI 0.115는 starlette<0.47로 묶고 있었음). 새 스택(FastAPI 0.162.2 + Starlette 1.10.0)에서: 전체 `714 passed, 78 skipped`, 실DB 3회 연속 `78 passed`, 브라우저 E2E 5개 흐름 전부 통과(10/10·6/6·6/6·4/4·11/11), `test:source` 통과. **재점검 결과 알려진 취약점 없음(31개 패키지, 종료 코드 0)**.
- **업그레이드로 드러난 시험의 맹점과 수정**: 새 FastAPI는 포함된 라우터를 `_IncludedRouter`로 감싸는데, 기존 보안 표면 시험은 `isinstance(route, APIRoute)`로 걸러서 **감싼 라우트를 조용히 건너뛰었음** — `/internal/` 시험은 실패하지도 않고 **아무것도 검사하지 않은 채 통과**했고, 다른 시험은 우연히 공개 라우트 목록 불일치로만 실패. 감싼 라우터를 재귀로 따라가는 도우미로 바꾸고, **모든 라우트가 OpenAPI 문서의 경로와 일치하는지 대조**하는 자체 검증과 `/internal/` 라우트 개수 하한을 추가. 변이 4/4 적발(재귀 제거, 포함된 라우터에 인증 없는 라우트 추가, 내부 라우트 인증 제거, 공개 라우트가 인증을 요구하도록 변경).
- OpenAPI 스냅샷 차이: 프레임워크가 만드는 부분뿐(파일 필드 `format: binary` → `contentMediaType`, ValidationError 스키마의 `ctx`·`input`; 10줄 추가·3줄 삭제).
- **자동 점검**: `.github/workflows/dependency-audit.yml`(매주 월요일 + 요구사항·잠금 파일 변경 PR + 수동 실행)로 `pip-audit`·`npm audit`를 돌림. 메인 CI와 분리(새 권고가 무관한 PR을 막지 않게). 결과는 이 PR의 체크와 아래 PR 항목에 적음.
- **미검증/한계**: 알려진 취약점 DB 기준이며 "안전하다"는 증명이 아님; 잠금 파일이 없어 고정되지 않은 전이 의존성은 설치 시점에 따라 달라짐; 주간 예약 실행은 기본 브랜치 머지 후에야 동작하므로 아직 실행된 적 없음; 컨테이너·OS 패키지는 배포 환경이 없어 대상 아님; 업그레이드는 주요 버전(Starlette 0.46 → 1.10)이라 **시험에 없는 동작 변화가 있을 수 있음** — 배포 전 실제 환경 확인 필요.

## 14. 설계 창 패치 반영 (`APPLY_ORDER_20261109.md`의 순서, 패치 9개; 전달문 `DEV_HANDOFF_20261109.md`)
패키지 `ai_studio_window_a_package_20261109.zip`(체크섬 `SHA256SUMS` 전부 일치)을 받아 순서대로 PR 하나씩 반영한다. 설계 창의 수치(예: 681 통과)는 a1fc935 기준 환경의 것이고, **여기 적는 수치는 main(FastAPI 0.162.2 / Starlette 1.10 / Pillow 13 / pytest 9)에서 새로 측정한 값**이다.

| # | 패치 | 처리 | PR | 비고 |
|---|---|---|---|---|
| 1 | legal | 반영(새 기능) | #20 (머지 d26aab9) | `git apply`가 충돌 없이 적용됨. 스냅샷 재생성: 새 경로 5개만 추가(84→89, 삭제 0) |
| 2 | consent | 반영(새 기능, legal.py 덮어씀) | #21 (머지 3ab4616) | `legal.py`·시험 파일은 패치 파일 그대로, 스냅샷은 덮어쓰지 않고 재생성(+2 경로: `/v1/me/consents`, `/v1/me/consents/{purpose}`, 삭제 0). 패치 시험 4건 + 내가 추가한 1건(동의 행에 저장되는 문서 버전 검증 — 기존 시험이 이를 확인하지 않아 변이 1종이 살아남았음) |
| 3 | backup | **비교 후 main 구현 유지**, 두 가지만 이식 | #22 (머지 fe8ec24) | 패치(`backup.py`+`restore.py`+12 시험)와 main의 `scripts/backup_restore.py`(+15 시험)는 둘 다 SQLite 온라인 백업 API, 복사본 `journal_mode=DELETE`, sha256 매니페스트, 새 위치에만 복구, 변조 거부를 독립적으로 갖춤. **패치에만 있던 것(이식)**: ① 파일 영역의 심볼릭 링크를 따라가거나 복사하지 않음(링크로 영역 밖 파일이 백업에 섞이는 것 차단) ② `verify`가 매니페스트에 없는 파일을 보고. **main에만 있는 것(유지)**: 백업 위치가 데이터 안/밖으로 겹치면 거부, 소요시간 기록, 복구 후 파일 재해시, 없는 영역 기록, 읽을 수 없는 DB를 `BackupVerificationError`로 보고. 패치의 `tests/test_backup_restore.py`는 main의 같은 이름 파일과 충돌해 추가하지 않음. 시험 +2(심볼릭 링크, 미기재 파일). 변이 검증: 링크 건너뛰기 제거 → 시험 실패(적발), 미기재 파일 검사 제거 → 시험 실패(적발); 디렉터리 링크 가지치기 제거는 `os.walk(followlinks=False)`가 이미 막아 **동등 변이**라 해당 코드를 삭제함 |
| 4 | cost_cap | **비교 후 main의 일일 상한 유지, 부족한 보장만 이식** | #23 (머지 c6deae2) | main(PR #9): 워크스페이스별 **일일** 작업 수 상한(`GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE`, 기본 0=끔), 생성 트랜잭션 안에서 원자적(SQLite·PostgreSQL), 멱등 재시도는 세지 않음, mock도 셈. 패치: **월간** 워크스페이스 상한(기본 200)·**전역 월간** 상한(기본 없음), **mock 제외**, **킬 스위치 `AI_JOBS_DISABLED`**(API 생성 거부 + 워커가 유료 Provider를 호출하지 않음). 결정: 서로 다른 한도라 **함께 둠**(일일은 폭주 방지, 월간·전역은 예산 방지). 패치의 `app/cost_cap.py`·`tests/test_cost_cap.py` 그대로 + APPLY.md의 3곳 수정. 시험 +7(738 통과, 78 스킵). 변이 8종 전부 적발. **한계**: 단위는 작업 수(크레딧 아님); **PostgreSQL 경로에는 월간·킬 스위치 미적용**(런타임은 SQLite); 킬 스위치로 막힌 기존 대기 작업은 `unknown`이 되어 재조정 API로 정리해야 함; 기본 월 200건은 패치의 값이며 근거 있는 한도가 아님 |
| 5 | purge | 반영(새 기능) | #24 (머지 0742599) | 새 파일 2개(`scripts/purge_requests.py`, `tests/test_purge_requests.py`), 기존 파일 수정 없음. 기본 dry-run, `--apply --confirm <request_id>`로 요청 하나씩, 유예기간 기본 7일(결정 문서와 일치). 스키마를 읽어 범위를 찾고 **알 수 없는 표가 있으면 아무것도 지우지 않음(닫힘 실패)**. 패치 시험 12건 + 내가 추가한 1건(제품·프로젝트·포토 초안 표가 실제로 생성된 DB에서 계정 삭제가 막히지 않고, 워크스페이스 행이 0이 되고, actor/owner/created_by에 사용자 ID가 남지 않음). 변이 9종 + 추가 시험이 잡은 1종 모두 적발. **한계**: SQLite 전용(PostgreSQL 미지원), 룩북 표는 시험에서 만들지 않음, **백업에 남은 사본은 지우지 않음**(백업 보관 30일), 실데이터 첫 실행은 승인 필요(차단) — 임시 DB로만 시험함 |
| 6 | authz v2 | 반영(새 시험) | #25 (머지 cf140fa) | 새 파일 1개(`tests/test_authz_matrix.py`, 시험 2건), 앱 코드 수정 없음. OpenAPI의 모든 작업을 돌며 익명 401, 비회원 2xx 금지, viewer의 쓰기 2xx 금지를 확인. main(FastAPI 0.162.2)에서 **수정 없이 통과**(`allow-list` 갱신 불필요). 변이 2종 적발(역할 검사 제거, 비회원에게 owner 부여). **한계(패치 문서 그대로)**: 인가가 판정하지 못하는 작업 7개(photo-drafts process-local, lookbook-drafts 생성·수정·export 다운로드, product variants 생성·수정)는 422 등으로 먼저 거부되어 이 시험이 인가를 확인하지 못함; 본인 데이터만 돌려주는 조회와 `/v1/me/` 쓰기는 본인 범위로 간주 |
| 7 | ops_check | 반영(새 스크립트) + **패치 결함 수정 3건** | #26 (머지 e802f6c) | `scripts/ops_check.py`(읽기 전용, 종료 코드 0/1/2: 작업자 하트비트, 막힌 작업, 출력함 적체, 월 유료 작업 수 대 상한, 유예기간 지난 삭제 요청, 최신 백업 나이)와 시험. main의 `/internal/ops/health`(PR #14)와 겹치는 작업자·백업 점검은 있으나, 월 유료 작업·막힌 작업·삭제 대기·종료 코드는 main에 없어 추가. **패치 그대로는 결함이 있어 고침**: ① 작업자를 `state='running'`만 살아 있다고 봄 → `idle`·`working` 작업자가 있어도 **거짓 치명(CRIT)** (main이 PR #14에서 고친 것과 같은 결함; `ALIVE_WORKER_STATES` 사용으로 수정) ② 백업 나이를 폴더 수정 시각으로 계산 → 쓰다 만 폴더·복사한 폴더가 "최신 백업"으로 인정됨; main처럼 `manifest.json`의 `created_at`으로 변경 ③ 한도 환경 변수가 숫자가 아니면 예외로 종료 → `cost_cap`의 안전한 파서 사용. 시험 6 → 9건(+idle/working, 매니페스트 없는 폴더, 잘못된 한도 값). 변이 10종 전부 적발. **한계**: 알림 전송은 없음(cron·외부 모니터가 종료 코드를 봄), PostgreSQL 미지원, 실제 환경에서 실행한 적 없음 |
| 8 | deps_upgrade | **이미 반영됨(PR #18); 변경 없음, 확인만** | #27 (머지 c074810, 문서만) | 패치의 `requirements.txt`는 main과 같은 버전 제약(fastapi 0.162.2, starlette>=1.3.1, Pillow 13, pytest>=9.0.3; 차이는 `<10.0`↔`<10`, `>=13.0`↔`>=13` 표기뿐). 패치의 `test_api_security_surface.py`는 라우터를 따라 내려가는 도우미만 추가했지만, main 것은 감싼 라우터를 재귀로 따라가고 OpenAPI와 대조하며 `/internal/` 라우트 수 하한까지 검사(PR #18, 변이 4/4 적발)해 **더 강하므로 덮어쓰지 않음**. 패치의 OpenAPI 스냅샷은 legal·consent 시점의 것이라 main의 현재 스냅샷(이후 패치 경로 포함)과 달라 **덮어쓰지 않음**(main의 스냅샷은 자신의 시험을 통과). 확인: `pip-audit -r requirements.txt` → `No known vulnerabilities found`(2026-11-09 재실행). **한계**: 알려진 취약점 DB 기준, 잠금 파일 없음, 프런트 API 클라이언트가 `contentMediaType`을 쓰는지는 확인 못 함(프런트 빌드·소스 시험은 통과), 배포 환경이 같은 requirements를 쓰는지 미확인 |
| 9 | e2e | **비교 후 main의 `e2e/`(Node) 유지, 빠진 시나리오만 이식** | #28 (머지 669dd09) | 패치는 Python/pytest 하네스 + 시험 5건(로그인→대시보드, 3D 자산 업로드·목록·삭제 화면, 다른 사용자의 워크스페이스·자산 격리 2건, Character 연결 자산 삭제 409). main은 Node/Playwright 흐름 5개(10/10, 6/6 권리 확인, 6/6 역할, 4/4 AI 표시, 11/11 반응형)가 CI에서 돌고 있어 **하네스를 둘 두지 않음**(패치의 `conftest.py`·`test_e2e_smoke.py`는 추가 안 함). 패치가 겹치는 부분: 로그인·3D 업로드·격리는 main의 pilot/roles 흐름이 다룸. **main에 없던 것을 이식**: Character 연결 자산 삭제 409 + D4의 나머지 시나리오 중 화면 없이 가능한 것(법률 문서 수락, 삭제 요청 생성·재요청·목록·취소·타인 접근 차단·워크스페이스 범위는 소유자만) → `e2e/account_flow.mjs` 4단계, CI에 단계 추가(`SUMMARY 4/4 account flow steps passed`). 변이 6종 시행: 5종 적발(오래된 문서 버전 수락, 취소 두 번 허용, 타인이 취소 가능, 편집자가 워크스페이스 삭제 요청, Character 보호 제거), 1종은 **동등 변이**로 미적발(중복 요청 재사용 분기 제거: 열린 요청 유니크 인덱스가 같은 결과를 내서 시험이 구분 못 함). **한계**: 이 흐름은 API 수준이며 **화면은 없다**(동의 화면·삭제 요청 화면 미구현이라 화면 시험 불가; 가입·동의 화면 시나리오는 여전히 미작성), Supabase는 모의 |
| 10 | authz_seeded | 반영(새 시험; 새 패키지 `window_a_package` 2차에서 추가됨) | #34 (머지 4b33004) | 새 파일 1개(`tests/test_authz_seeded_objects.py`, 시험 3건), 앱 코드 수정 없음. 실제 객체가 있는 상태에서 인가 행렬이 판정하지 못했던 경로(상품 변형 생성·수정, Lookbook 생성·수정, Photo process-local)를 비멤버(403/404)·뷰어(쓰기 403)로 확인. main에서 수정 없이 통과. 변이: **패치 README의 변이는 `routes.require_role`을 깨는 것인데 이 경로들은 `app/ports/workspace.require_role`로 인가해서 여기선 적발되지 않음**(그 층에서는 3건 통과) → 올바른 층에서 다시 시행: 쓰기 역할 검사 제거, 비멤버를 owner로 취급, Lookbook 생성의 쓰기 검사 약화, process-local의 쓰기 검사 약화 — 4종 모두 적발; Photo **초안 생성**의 쓰기 검사 약화는 이 시험이 다루지 않아(인가 행렬 시험 몫) 적발 안 됨. **한계(패치 그대로)**: Lookbook 내보내기 다운로드(서명 토큰 경로)와 `POST /v1/workspaces`(자기 범위)는 여전히 판정 못 함 — 다운로드 인가는 `tests/test_assets_api.py`가 확인(익명 401, 변조·만료 서명 403, 멤버 취소 후 404) |
| 11 | launch_gate | 반영(새 스크립트, **main에 맞게 수정**) | #35 (머지 a1a3372) | `scripts/launch_gate.py`(시험·의존성 점검·백업 훈련을 한 번에 돌려 PASS/FAIL/NOT_RUN을 세고, 사람·실서비스가 필요한 5개 항목은 항상 NOT_RUN — **출시를 승인하지 않음**)와 시험. **패치 그대로는 main에서 백업 훈련이 실패함**: 패치의 `scripts/backup.py`·`scripts/restore.py`는 main에 없고(main은 `scripts/backup_restore.py`의 `backup`/`verify`/`restore` 하위 명령), 설정된 DB가 없는 저장소에서는 백업 대상이 없음 → 훈련을 임시 폴더의 **일회용 DB**(워크스페이스 1개)에서 `backup → verify → restore(새 폴더)`로 바꿈(실데이터를 읽지도 쓰지도 않음, DB 없는 체크아웃에서도 동작). 시험 3 → 6건(+훈련이 실제로 통과, 검증 실패 시 FAIL, 모든 명령이 임시 경로로만 실행). 실제 실행(로컬, FastAPI 0.162.2 환경): `tests: passed=776 failed=0 errors=0 skipped=78`, `audit: NOT_RUN`(그 환경에 pip-audit 미설치), `backup_drill: PASS`, 수동 5건 NOT_RUN → **종료 코드 2**(필수 단계가 안 돌았으므로 설계대로). 변이 5종 모두 적발(첫 시도에서 "실제 환경 사용" 변이는 백업이 읽기 전용이라 바이트 비교로는 못 잡아 시험을 각 명령이 받는 환경 검사로 바꾼 뒤 적발). **한계**: 의존성 점검은 *설치된 환경*을 대상으로 하며 requirements.txt가 아님; CI에서 실행하지 않음 |
| 12 | d2_reference | **기준 구현과 대조, 내 구현 유지**(3차 패키지에서 추가됨) | (이 PR, 위 §18) | 기준 구현의 인수 시험 4건·삭제 연동 시험 2건을 내 구현에 돌려 통과 확인(설정 이름 상수만 변경). 기준 구현의 파일은 덮어쓰지 않음(내 L-04 구현과 겹침: `app/assets/rights.py`·`store.py`·`routes.py`·`purge_requests.py`). 차이와 이유는 §18 |

## 17. E2E 시험의 경합 하나 수정 (`pilot_flow` "save a photo draft", 브랜치 fix-pilot-flake)
- **발견**: PR #32의 CI e2e가 `save a photo draft for the product image`에서 `0 !== 1`로 실패(같은 시험은 이전 CI 실행 여러 번과 로컬에서 통과; **같은 결함이 그 앞의 main 푸시 실행에서도 한 번 있었음 — §25**). 원인은 제품 결함이 아니라 **시험의 경합**: "저장된 Photo Draft" 목록은 초안이 0개여도 화면에 있으므로, 그 목록을 기다린 뒤 API로 초안 수를 세면 저장 요청이 끝나기 전에 셀 수 있다.
- **재현**: 임시 사본에서 초안 저장 POST를 600 ms 지연시키면 고치기 전 시험이 실패했다(재현 확인).
- **수정**: 저장 요청의 응답(201)을 기다린 뒤 확인. 같은 지연을 주고 다시 돌리면 통과, 지연 없이 3회 연속 `10/10`.
- **미검증·한계**: 같은 모양(목록 대기 뒤 곧바로 API로 개수 확인)의 다른 단계가 더 있는지 전수 점검하지 않았다 — 이 PR은 실제로 실패한 한 곳만 고쳤다. CI에서 이 시험이 지금까지 통과한 것은 우연한 타이밍 덕이었을 수 있다.

## 15. 동의 화면·삭제 요청 화면 (L-02 프런트 / L-01 화면, 브랜치 feat-legal-screen)
- **구현**: 로그인 직후 `GET /v1/me/legal-status`를 확인해 필수 문서 3개(이용약관·개인정보 처리방침·콘텐츠 정책)에 모두 체크해야 "동의하고 계속"이 켜지는 화면(`LegalGate`)을 보여 주고, 그 뒤에야 스튜디오를 그린다. AI 학습 사용은 **별도 선택 항목(기본 해제)**이며 필수 동의가 성공한 뒤에만, 체크했을 때만 기록한다. 설정 패널(`AccountPanel`)에서 이 동의를 철회하고, 계정 삭제를 요청·취소한다(요청은 기록만 하며 즉시 삭제하지 않는다고 화면에 적음; 유예 7일·백업 30일은 결정 문서의 값).
- **실패 시 닫힘**: 동의 상태 조회가 실패하면 연결 전체가 실패하고 화면이 열리지 않는다(동의된 것으로 취급하지 않음).
- **시험**: `legalApi.test.mjs` 5건(실제 호출 본문·토큰·버전, 게이트 판정), 브라우저 E2E `legal_flow.mjs` 5단계(게이트 뒤에 스튜디오가 그려지지 않음, 필수 3개 모두 필요, 선택은 기본 해제, 선택 체크 시 기록·설정에서 철회, 삭제 요청 생성·취소와 워크스페이스 유지, 거부 후 로그아웃은 아무것도 기록하지 않음). 다른 E2E 흐름은 `loginThroughUi`가 같은 게이트를 화면으로 통과한다(그래서 모든 흐름이 게이트를 지난다). 기존 `pilot_flow`의 "설정 패널 입력 3개" 확인은 연결 정보 입력만 세도록 좁혔다(새 계정 패널이 입력을 더 가지므로; 목적은 API 주소 입력이 없음을 보는 것).
- **변이 검증**: 화면 쪽 6종 모두 적발 — 게이트 우회(E2E 1단계), 필수 중 하나만 체크해도 활성화(E2E 1단계), 선택 항목 기본 체크(E2E 1단계), 선택을 항상 전송(E2E 2단계), 조회 실패를 '열림'으로 판정(단위), 필요한 것 전부 전송(단위). 첫 시도의 게이트 우회 변이는 빌드가 실패해 옛 번들로 돌아 **무효**였고 다시 했다.
- **미검증·한계**: **화면 차단일 뿐 서버가 강제하지 않는다** — 토큰으로 API를 직접 호출하면 동의 없이 쓸 수 있다(서버 강제는 별도 결정 필요). **문서 본문이 앱에 없다**(초안 버전 번호만 표시; 본문을 어디서 보여 줄지는 정해지지 않았고 임의로 채우지 않았다). 문서 버전이 올라간 뒤 재동의 흐름은 PR #30 시점엔 서버 시험만 있었고, **이후 `legal_flow` 6번째 단계로 추가**(버전 상승을 DB의 수락 기록을 옛 버전으로 바꿔 흉내 냄 — 실제 환경 변수로 서버를 다시 띄운 것은 아님; 바뀐 문서만 다시 묻고, 서버도 다시 닫히고, 이력은 옛 수락을 남김; 모든 문서를 다시 묻는 변이로 실패 확인). 모바일 폭에서 게이트 화면의 레이아웃은 PR #30 시점엔 반응형 시험 대상이 아니었고, **이후 `layout_flow`에 설정(계정 패널)과 게이트를 열 개 폭(360~1280 px)으로 추가**(13/13; 각각 `min-width` 변이로 실패함을 확인, 가로 넘침 없음). 동의 문구 자체는 법무 승인 전 임시 문구.

## 16. 서버의 동의 강제 (`LEGAL_REQUIRE_ACCEPTANCE`, 브랜치 feat-legal-enforce)
- **구현**: 설정이 켜지면 인증된 사용자가 현재 문서 버전에 모두 동의하지 않았을 때 `/v1/auth/me`, `/v1/me/legal-status`, `/v1/me/legal-acceptances`, `/v1/me/consents`, `/v1/me/deletion-requests`, `/internal/`를 뺀 모든 경로가 **403 `LEGAL_ACCEPTANCE_REQUIRED`**. 모든 라우트가 `current_user`를 거치므로 한곳(`app/assets/routes.py`)에서 처리. **기본은 꺼짐**(기존 클라이언트 호환). 인증이 먼저(401이 403보다 앞). 문서 버전이 올라가면 다시 닫히고 재동의 뒤 열린다.
- **프런트 순서 변경**: 연결 때 워크스페이스를 동의 확인 **뒤에** 불러오거나 만든다(이전엔 동시에 불러와서 서버가 강제하면 연결이 막혀 게이트가 안 뜸). 동의 전 사용자에게는 워크스페이스가 만들어지지 않는다.
- **시험**: `tests/test_legal_enforcement.py` 6건(미동의 거부, 열어 둔 경로, 동의 뒤 열림·사용자별, 버전 상승 시 재차단, 꺼짐이면 변화 없음, 인증 우선). 전체 `770 passed, 78 skipped`(로컬, FastAPI 0.162.2). 변이 7종 적발(강제 제거, 항상 강제는 픽스처가 깨져 오류로 적발, 판정 뒤집기, 삭제 요청 경로 비면제, 동의 수락 경로 비면제, 면제가 너무 넓음, 동의 경로 비면제). 브라우저 `legal_flow`는 서버를 이 설정으로 띄워 **직접 API 호출이 403, 동의 뒤 200**임을 확인; 강제 제거 변이로 이 단계가 실패함을 확인.
- **미검증·한계**: 운영 배포에서 이 설정을 켤지는 결정이 필요(켜면 동의하지 않은 기존 사용자는 다음 로그인 때 게이트를 거침). 동의 상태 조회가 요청마다 SQLite 질의 1회(부하 측정 안 함). 다른 E2E 흐름은 API로 먼저 데이터를 만들기 때문에 설정을 켜지 않고 돈다(켠 상태의 전체 흐름은 시험하지 않음). PostgreSQL 경로 없음.

## 18. D2 업로드 권리 확인: 기본 필수 + 기록 표 + 보존 결정 (브랜치 feat-d2-rights, `DEV_NONSTOP_PROMPT_20261109.md` 큐 4)
- **구현**: ① `ASSET_REQUIRE_RIGHTS_CONFIRMATION`의 **기본값을 켬으로 변경**(명시적 0/false/no/off만 끔; 모르는 값은 켬 쪽). 이전엔 기본 꺼짐이었음(§6의 "켜진 때만 422"는 이 PR 이후 사실이 아님). ② 표 `upload_rights_confirmations(asset_id PK, workspace_id, user_id, depicts_person, likeness_consent, policy_version, confirmed_at)` — 권리를 확인한 업로드마다 같은 트랜잭션에서 1행(`policy_version`은 현재 콘텐츠 정책 버전). 확인하지 않은 선언(꺼진 모드에서 false)은 기록하지 않음. ③ `GET /v1/assets/{asset_id}/rights-confirmation` — 확인 기록이 없는 이전 자산은 `unconfirmed`로 읽히며 계속 쓸 수 있음(소급 차단 없음). 멤버(뷰어 포함)만 읽음, 외부인 404. 스냅샷 +1 경로(92).
- **보존 결정(결정 문서의 충돌 해소; 갱신된 결정문 "자산이 삭제되면 기록도 삭제, 자산이 남으면 계정 삭제 시 `deleted-user`로 익명화"를 따름)**: **API로 자산을 지우면 그 기록 행도 같이 지운다**(처음엔 익명화해 남기도록 만들었다가 갱신된 결정문에 맞춰 바꿈). 워크스페이스 콘텐츠·혼자 쓰는 계정 삭제는 표의 `workspace_id`로 기록째 삭제(purge가 표를 인식). **공유 워크스페이스에서 한 구성원의 계정을 purge**하면 그 구성원의 `user_id`를 익명화하도록 purge에 표별 규칙(`ANON_BY_TABLE`)을 추가(그래서 purge가 멈추지 않고, 개인 식별자도 남지 않음). 다른 표의 `user_id`(동의·수락 기록)는 삭제 대상이라 이 규칙에 넣지 않음.
- **시험**: 설계 창의 `tests/test_upload_rights_acceptance.py` 4건과 `tests/test_upload_rights_purge.py` 2건(설정 이름 상수 하나만 바꿔 그대로 사용) + 내 `tests/test_upload_rights_record.py` 10건(기본값은 새 인터프리터에서 확인, 미확인 업로드 422·저장 없음, 확인 시 정확히 1행, 사람 포함 시 동의 필요, 같은 자산 중복 방지, 이전 자산 호환, 멤버십별 접근, 자산 삭제 시 그 기록 삭제, 공유 워크스페이스 계정 purge 후 사용자 ID 없음, 꺼진 모드의 미확인 선언은 기록 안 함). 변이 8종 적발(기본값을 끔으로, 422 제거, 기록 제거, 미확인도 기록, 유일성 제거, 자산 삭제 시 기록 삭제 제거, purge 익명화 제거, 접근 검사 제거). 전체 `795 passed, 78 skipped`(로컬, FastAPI 0.162.2).
- **시험 방식의 변화(숨기지 않음)**: 기본이 켜지면서 이미지를 선언 없이 올리던 기존 시험 78건이 깨져, `tests/conftest.py`가 **기본적으로 옛 모드(꺼짐)** 로 돌리고 권리 시험만 직접 켠다. 즉 기존 시험 대부분은 새 기본값이 아니라 옛 모드를 시험한다(새 기본값은 새 파일이 새 인터프리터로 확인). E2E는 시드·시험 업로드에 권리 필드를 넣고 사진 업로드 화면에서 권리 체크를 켠다(`roles_flow`의 뷰어 단계도 체크 후 시도하므로 거부 이유가 역할임을 더 분명히 함).
- **기준 구현(`patch_d2_reference`, 3차 패키지)과의 대조**: 같은 점 — `POST /v1/assets/images` 폼 필드 `rights_confirmed`, 422 `RIGHTS_CONFIRMATION_REQUIRED`, 표 `upload_rights_confirmations`(asset_id 기본키·user_id·confirmed_at·policy_version), 자산 저장과 **같은 트랜잭션**에 기록, PostgreSQL 자산 포트엔 미구현, purge가 자산이 사라지면 기록 삭제·자산이 남으면 `deleted-user` 익명화. 다른 점(기록함) — ① **기본값**: 기준은 꺼짐(`UPLOAD_RIGHTS_REQUIRED`, 파일럿에서 1로 켬; 호환 우선), 나는 **켜짐**(`ASSET_REQUIRE_RIGHTS_CONFIRMATION`, 명시적으로 꺼야 꺼짐; `DEV_NONSTOP_PROMPT` 4번의 "필수"를 따름). 설계 창 문서끼리도 갈리므로(`W04_D2_ACCEPTANCE`는 호환 유지) **결정이 필요하면 환경 변수 하나로 뒤집을 수 있음**. ② 표에 `workspace_id`·사람 포함·초상권 동의 열이 더 있고 FK는 없음(purge가 `workspace_id`로 직접 범위를 잡음). ③ `policy_version`: 기준은 환경 변수(`2026-11-draft`), 나는 현재 콘텐츠 정책 문서 버전. ④ 추가 구현: 읽기 엔드포인트와 '미확인' 표시(기준은 "조회 시 미확인 표시 없음"이 한계), 프런트 체크박스(PR #8). 설계 창의 인수 시험 4건과 삭제 연동 시험 2건은 **내 구현에서 통과**; 이 6건만으로는 내 변이 3종(미확인 선언도 기록, 유일성 제거, 기본값을 끔으로)을 못 잡아 내 시험을 따로 둠.
- **인수 문서의 코드 대조 체크리스트 5항목**: (1) 사진이 올라가는 경로 — `POST /v1/assets/images`가 유일한 사용자 이미지 업로드이고, 파생 이미지(`save_derived_image_asset`)는 사용자 업로드가 아니라 대상 아님 / (2) 서버 강제 — 라우트가 아니라 `build_upload_confirmation`에서 서버가 판정 / (3) 기존 자산 — '미확인'으로 읽히고 차단 안 됨(시험) / (4) 같은 트랜잭션 — `save_asset`의 한 `with _connect()` 안에서 자산·버전·출처·확인 기록을 씀 / (5) 변이 검증 — 8종(위).
- **미검증·한계**: PostgreSQL 저장소에는 표·익명화 없음(런타임 미사용). 정책 버전은 문서 초안 버전이라 확정 전 값. 프런트는 이미 권리 확인을 보낸다(PR #8).

## 19. D2 코드 대조 5항목 결과와 그 과정에서 찾은 결함 2건 (브랜치 fix-d2-version-upload)
`W04_D2_ACCEPTANCE`의 코드 대조 체크리스트를 실제 코드로 확인했고, 두 곳이 기준에 못 미쳐 고쳤다.
- **결함 1 — 이미지 자산의 새 버전 업로드가 권리 확인을 건너뜀**: `POST /v1/assets/{asset_id}/versions`(`app/assets/routes.py::upload_asset_version`)는 이미지 자산에 새 이미지(=새 사진)를 올릴 수 있는데 선언을 요구하지 않았다. 인수 문서는 "버전 업로드는 사진이 아니므로 대상 아님"이라 적었지만 **이미지 자산의 버전은 사진**이다. 수정: 이미지 버전은 `POST /v1/assets/images`와 같은 선언을 서버가 강제(`build_upload_confirmation`)하고, 선언을 새 버전의 출처 기록(`asset.version_created` 이벤트의 `details.rights`)에 남긴다. 3D 모델 버전은 영향 없음. **한계**: 확인 표 `upload_rights_confirmations`는 자산당 한 행(원 업로드)이므로 이후 버전의 선언은 표가 아니라 출처 기록에만 있다(그래서 `GET .../rights-confirmation`은 원 업로드의 확인을 반영). PostgreSQL 포트는 선언이 오면 `NotImplementedError`(기준 구현과 같은 방침).
- **결함 2 — `save_asset`이 한 트랜잭션이 아니었음(체크리스트 4번)**: 저장소 연결이 `isolation_level=None`(자동 커밋)이라 `with _connect()` 안의 `INSERT` 여러 개가 각각 바로 커밋되고 `rollback()`은 아무것도 되돌리지 못했다. 중간에 실패하면 자산 행만 남고 파일은 지워져 **파일 없는 자산**이 생길 수 있었다(이 PR 전에도 있던 결함이며, 확인 기록 삽입을 같은 블록에 넣으면서 시험으로 드러남). 수정: 블록 첫머리에 명시적 `BEGIN IMMEDIATE`(`create_asset_version`·`delete_asset`이 이미 쓰는 방식). 고장 주입 시험(기록 단계에서 예외)으로 자산 행·확인 행·저장 파일이 모두 남지 않음을 확인.
- **같은 모양의 다른 쓰기 함수는 전수 점검하지 않았다**: `app/assets/store.py`의 여러 `with _connect()` 블록(예: `save_derived_image_asset`, `create_workspace`, `restore_asset_version`, `create_asset_relation`, `add_workspace_member`)이 명시적 `BEGIN` 없이 여러 문장을 실행하는지는 확인하지 못했다. 별도 점검 항목으로 올림.
- **시험**: `tests/test_upload_rights_versions.py` 6건(버전 선언 거부·사람 동의·기록·꺼진 모드·3D 모델 영향 없음·원자성). 변이 4종 적발(BEGIN 제거, 버전 검사 제거, 선언 미기록, 모델에도 요구). 전체 `801 passed, 78 skipped`(로컬, FastAPI 0.162.2). OpenAPI 스냅샷 재생성(폼 필드 3개 추가; 경로 수는 92 그대로).
- **업로드 화면의 권리 확인란**: 있음 — `src/PhotoDraftWorkspace.tsx`의 `<fieldset aria-label="이미지 사용 확인">`(체크박스 3개: 권리 확인, 사람 포함, 초상권 동의), 문구는 `src/rightsConfirmationCopy.ts`, 전송은 `src/app/rightsDeclaration.mjs::appendRightsDeclaration`. 브라우저 `rights_flow` 6/6이 미체크 거부·목록에 새 항목 없음을 확인. 이미지를 올리는 다른 화면은 없다(`AssetWorkspace`는 GLB 전용, 이미지 버전 업로드 화면도 없음).

## 20. L-07 AI 생성물 표시를 `DEV_ACCEPTANCE_PACK` 기준으로 검수 (브랜치 l07-check)
| 기준 | 결과 | 근거(파일·함수·시험) |
|---|---|---|
| 출력 화면에 표시 | 통과 | `src/OutputReviewWorkspace.tsx`가 `src/app/aiDisclosure.mjs::aiDisclosureLabel`로 배지를 그림(mock=AI 미사용, 그 외·미지정=AI 생성물, 생성기 이름 표시). 브라우저 `disclosure_flow` 4/4 |
| 출력 목록·검수·내보내기 manifest | 통과 | `app/ai_disclosure.py::disclose_job_outputs`·`is_ai_generated_provider`, `app/repositories/output_review.py`; 시험 `tests/test_output_asset_link_worker.py`(mock·비mock 모두, 목록·검수·manifest 최상위와 `outputs[*]`) |
| 룩북 내보내기 manifest의 `outputs[*]` | 코드는 이미 있었음, **시험이 없어 추가** | `app/lookbook.py`(내보내기 manifest 생성부). `tests/test_assets_api.py`에 `outputs[*].is_ai_generated is False`·`provider_dispatched is False` 단언 추가 |
| 내려받는 패키지(ZIP) 안 manifest | 코드는 이미 있었음, **시험이 없어 추가** | `app/lookbook.py::write_lookbook_package`(`outputs[*]`)와 패키지 manifest 최상위. ZIP을 열어 최상위와 `outputs[*]`를 단언 |
| 사용자가 끌 수 없음 | 통과(시험 추가) | 서버가 결정: `disclose_job_outputs`가 항목에 이미 있는 값(저장된 false 포함)도 덮어씀; 쓰기 모델(`CreateTryOnJob`, `PhotoDraftInput`, `LookbookDraftInput`)에 표시 필드가 없음; 작업 요청에 `is_ai_generated: false`를 끼워도 무시(저장 안 됨). `tests/test_ai_disclosure_inputs.py` 3건 |
| 변이: manifest 필드 생성 코드를 제거하면 시험 실패 | 통과 | 5종 모두 적발: 내보내기 manifest `outputs[*]` 필드 제거, 패키지 `outputs[*]` 제거, 패키지 최상위 제거, 서버 덮어쓰기를 `setdefault`로 약화, 알 수 없는 provider를 AI 아님으로 취급 |

- **한계(기준이 요구한 범위 명시)**: 이 표시는 **메타데이터와 화면 배지**뿐이다. **이미지 자체에 눈에 보이는 표시(워터마크·라벨)는 넣지 않았다.** 딥페이크 사례처럼 눈에 보이는 표시가 필요한지, 문구가 무엇이어야 하는지는 **법무 검토 사항**이라 임의로 정하지 않았다. 사진 스튜디오·룩북은 결정론적 로컬 처리(생성형 AI 아님)라 `false`가 맞고, 외부 생성 Provider 출력만 `true`다 — 실제 Provider로 검증한 적은 없다(mock 외 경로는 시험용 provider 이름으로만 확인).
- **미검증**: PostgreSQL 경로의 manifest(`postgres_lookbooks.py`)는 같은 필드를 갖지만 이번에 시험을 추가하지 않음(런타임은 SQLite). 룩북 내보내기 manifest의 **최상위**에는 필드가 없고 `outputs[*]`에만 있음(패키지 manifest는 둘 다 있음) — 기준 문구상 충족으로 보되 일관성은 후속 정리 후보.
- **시험**: 백엔드 `tests/test_ai_disclosure_inputs.py` 3건 + `tests/test_assets_api.py` 단언 2곳 추가.

## 21. L-05 접속 로그를 `DEV_ACCEPTANCE_PACK` 기준으로 검수 (브랜치 l05-check)
| 기준 | 결과 | 근거(파일·함수·시험) |
|---|---|---|
| 문서의 항목 목록과 코드가 일치 | **자동 확인 장치가 없어 추가** | 코드의 단일 출처 `app/access_log.py::LOGGED_FIELDS`(9개)·`OPTIONAL_FIELDS`(`error`, `client_ip`). `docs/RUNBOOK.md` §3-1에 키 표를 넣고 `tests/test_access_log.py::test_the_runbook_documents_exactly_the_keys_the_code_can_log`가 표의 키 집합 = 코드의 키 집합을 확인; `test_a_log_line_has_only_the_documented_keys`가 실제 로그 줄(정상·인증 실패·없는 경로·IP 켠 경우)의 키가 목록과 같음을 확인 |
| 요청 본문이 로그에 없음 | **시험이 없어 추가** | `test_request_bodies_and_signed_urls_inside_bodies_never_reach_the_log`: 작업 생성 요청의 본문 문구와 필드 이름이 로그에 없음 |
| 토큰이 로그에 없음 | 통과(기존 시험 + 변이) | `test_secrets_and_query_strings_never_reach_the_log`; 변이로 `authorization` 헤더를 기록하게 하면 4건 실패 |
| 이미지 URL의 서명 값이 로그에 없음 | 통과(경로·쿼리) + **본문 안의 서명 URL은 시험 추가** | 쿼리 문자열은 기록하지 않음(라우트 템플릿만). 본문의 `model_image_url?signature=...`도 로그에 없음을 단언 |
| 보관 기간 설정 | 통과 | `ACCESS_LOG_RETENTION_DAYS`(기본 30, 0은 거부) → `TimedRotatingFileHandler(backupCount=...)`; 시험 `test_file_logging_rotates_daily_and_keeps_a_bounded_number_of_files`와 `test_log_settings_reject_unsafe_values`; 보관 일수를 무시하는 변이 적발 |
| 만료된 로그를 지우는 방법의 문서화 | **문서 보강** | RUNBOOK §3-1: 회전 시 자동 삭제(시험으로 확인) + 수동 삭제 명령(`find ... -mtime +N -delete`, **명령 자체는 시험하지 않음**) + 표준 출력 사용 시에는 받는 쪽 책임 |
| 방침의 보유 기간과 일치 | **확인하지 못함** | 정책 문서의 보유 기간이 확정되지 않았고 저장소에 없음(`LEGAL_W02_RESULT`도 "접속 로그 실제 수집 항목"을 미확정으로 남김). 30일은 임시 기본값 |

- **변이 검증(6종 적발)**: 본문 기록, `authorization` 기록, 원본 URL(쿼리 포함) 기록, 경로+쿼리 기록, 항목 목록에서 `actor` 누락(문서·코드 불일치), 보관 일수 무시.
- **시험**: `tests/test_access_log.py` 12 → 16건(+4: 본문·본문 속 서명, 키 일치 2).
- **한계(그대로)**: uvicorn 기본 접근 로그는 쿼리 문자열을 남기므로 운영에서 `--no-access-log` 필요(RUNBOOK에 있음, 배포 파일이 없어 강제하지 못함). 로그 파일은 백업 대상이 아님. `actor`는 가명이지만 `ASSET_SIGNING_SECRET`이 바뀌면 해시가 달라짐. 접속 로그의 법적 항목·보유 기간·접근 통제는 법무 확정 전.

## 22. L-08 권리 침해 신고와 임시 비공개 (브랜치 l08-takedown, `DEV_ACCEPTANCE_PACK` 기준)
이전에는 "절차 명세 없음"으로 막혀 있었으나, 검수 기준 문서(통과 조건 4줄)와 `FRONTEND_SPEC_W16`의 절차 개요(접수 → 임시 비공개 → 당사자 확인 → 삭제 또는 복구)가 생겨 **그 범위 안에서** 구현했다. 정책·법적 절차는 여전히 정해지지 않았다(아래 "정하지 않은 것").
- **흐름**: `POST /v1/content-reports`(로그인한 누구나; 분류 copyright·likeness·other, 설명 2000자) → 즉시 자산이 `under_review`로 비공개 → 운영자(`OPS_ADMIN_USER_IDS`)가 `GET /internal/moderation/reports`로 보고 `POST /internal/moderation/reports/{id}/resolve`로 `restore`(기각: 다른 열린 신고가 없을 때 비공개 해제, 자산은 그대로) 또는 `remove`(인정: 모두에게 영구 비공개) 처리. `remove`는 `POST /internal/moderation/assets/{id}/reinstate`로 되돌린다.
- **비공개의 실제 효과**: `under_review` 중에는 자산의 **소유자(`assets.owner_id`)만** 접근. 다른 구성원(편집자·뷰어, 워크스페이스 소유자 포함)은 `/v1/assets/{id}` 아래 모든 경로(상세·버전·출처·관계·권리 기록·미리보기 URL 발급·미리보기 내용)와 목록에서 404. `removed`면 소유자도 이 경로들에서 404. 서명 미리보기 URL(토큰 없이 서명만 쓰는 경로)은 신원이 없으므로 보류된 자산이면 항상 404 → **비공개 이전에 발급된 링크도 멎는다**. 구현: `app/assets/routes.py::asset_visibility`(라우터 수준 의존성) + `app/takedown.py::visible_to`·`filter_listing`.
- **소유자 데이터 보존**: 비공개는 아무것도 지우지 않는다(저장 파일 목록 불변을 시험). 임시 비공개 중 소유자가 자기 자산을 지우려 하면 409 `TAKEDOWN_ACTIVE`(증거 인멸 방지). **복구하면 메타데이터·바이트·체크섬이 신고 전과 같고** 소유자는 다시 지울 수 있다. 운영자의 "삭제"(`remove`)도 **물리 삭제가 아니라 영구 비공개**다(되돌릴 수 없는 삭제는 승인 항목).
- **소유자 상태 표시**: `GET /v1/assets/{id}/takedown`(소유자에게만 상태, 다른 구성원은 비공개 중 404)과 `GET /v1/me/takedowns`(내 자산 중 보류된 것과 상태). **화면(UI)은 만들지 않았다** — API뿐.
- **신고자 비노출**: 소유자가 받는 모든 응답(자산 경로들·상태·목록·내 보류 목록)에 신고자 ID·분류·신고 문구가 없음을 시험(문자열 검사). 운영자 목록에는 신고자 ID·분류·설명이 있다(후속 연락용). 신고자 계정을 purge하면 `reporter_id`·`resolved_by`가 `deleted-user`로 익명화된다(`ANON_BY_TABLE`).
- **남용 방지**: 같은 신고자의 같은 자산 열린 신고는 하나(중복은 같은 응답), 신고자당 하루 `CONTENT_REPORT_DAILY_LIMIT`건(기본 20, 초과 429), 자기 자산 신고는 효과 없음. 존재하지 않는 자산 ID와 실제 자산에 **같은 응답** `{"status":"received"}`(존재 여부를 알 수 없게; 인가 행렬 시험에 `ANSWERS_ALIKE`로 반영).
- **시험**: `tests/test_takedown.py` 11건. 변이 12종 모두 적발(가시성 검사 제거, 목록 필터 제거, 신고가 비공개를 만들지 않음, 소유자 삭제 허용, 소유자에게 신고자 노출, 복구가 비공개를 못 풂, 다른 열린 신고를 무시하고 해제, 제거가 숨기지 않음, 운영자 검사 제거, 신원 없는 서명 링크 허용, 일일 한도 제거, purge가 신고자를 안 지움). 인가 행렬 시험의 허용 목록에 `GET /v1/me/takedowns`(본인 범위)와 `POST /v1/content-reports`(누구나, 응답 동일)를 이유와 함께 추가. 전체 백엔드: 이 브랜치에서 `806 passed, 78 skipped`, main(#38~#41)을 합친 뒤 `819 passed, 78 skipped`(로컬, FastAPI 0.162.2). 스냅샷 98경로(+6).
- **정하지 않은 것(임의로 정하지 않음)**: ① 신고할 수 있는 사람의 범위(지금은 로그인한 누구나; 외부 제3자 신고 경로·본인 확인 없음) ② 처리 기한 ③ 소유자에게 알림·이의제기 절차(소유자는 상태만 볼 수 있고 사유는 못 봄) ④ 신고자 정보를 소유자에게 줄지(보수적으로 숨김, 기준대로) ⑤ `remove`된 파일의 물리 삭제 시점 ⑥ 한 번의 신고로 즉시 비공개되는 것의 남용 위험(한도·중복 방지만 있음).
- **덮지 못한 경로(한계)**: 자산 ID로 오는 **자산 API 경로만** 막는다. 보류된 자산을 이미 참조하는 Photo Draft·Lookbook·상품·캐릭터가 그 자산을 읽는 경로(예: `process-local`이 원본 바이트를 읽는 것, 룩북 패키지에 들어가는 바이트)는 이번에 막지 않았다. 보류된 자산에서 파생된 출력은 별도 자산이라 그대로 보인다. PostgreSQL 저장소엔 표·가드 없음(런타임 미사용).

## 23. 자동 커밋 연결 위의 다중 쓰기 점검 (브랜치 fix-store-atomicity, §19 후속)
§19에서 `save_asset`이 한 트랜잭션이 아니었던 것을 고치며 "같은 모양의 다른 함수는 전수 점검하지 않았다"고 적었다. 이번에 점검했다.
- **방법**: `app/` 아래 SQLite 경로 파일을 AST로 훑어, 같은 함수 안에서 `INSERT`/`UPDATE`/`DELETE`가 2개 이상인데 `BEGIN`·`transaction(`이 없는 함수를 찾고, `app/assets/store.py`의 쓰기 함수는 하나씩 직접 읽었다(휴리스틱이 놓칠 수 있어서). PostgreSQL 저장소와 `app/ports/`는 대상에서 뺐다.
- **결과**: 문제는 **둘**이었고 고쳤다 — `app/assets/store.py::create_workspace`(워크스페이스와 소유자 멤버 INSERT 둘; 둘째가 실패하면 소유자 없는 워크스페이스가 남고 같은 ID로 다시 만들 수도 없었음), `app/output_asset_link_worker.py::import_output_asset`(자산·버전·출처 INSERT 셋; 중간에 실패하면 반쯤 들어간 자산이 남고, 이 함수가 재시도 때마다 "무결성 검증 실패"로 영구히 거절함). 둘 다 블록 첫머리에 `BEGIN IMMEDIATE` 추가. **`save_derived_image_asset`·`restore_asset_version`·`create_asset_version`·`create_asset_relation`·`delete_asset`은 이미 `BEGIN IMMEDIATE`를 쓰고 있어 정상**이었다.
- **고치지 않은 것(이유)**: `app/assets/store.py::initialize`는 쓰기 5개가 `BEGIN` 없이 있지만 전부 멱등(`CREATE ... IF NOT EXISTS`, `INSERT OR IGNORE` 보충)이라 중간 실패 뒤 다시 실행하면 이어서 완성된다. `app/legal.py::accept_legal_documents`는 문서마다 `INSERT OR IGNORE`를 반복하는데 같은 이유로 재시도하면 완성된다(중간 실패 시 일부 문서만 수락된 상태가 잠깐 보일 수 있음).
- **시험**: `tests/test_store_atomicity.py` 2건(트리거로 마지막 INSERT에 실패를 주입 → 아무것도 안 남고, 트리거를 지운 뒤 재시도가 성공). 변이 2종(두 곳의 `BEGIN` 제거) 적발.
- **한계**: 정규식·AST 휴리스틱과 손으로 읽기 기준이다. `lookbook.py`·`photo_engine.py`·`products.py`·`projects.py`·`characters.py`는 다른 연결 헬퍼를 쓰는데, 같은 기준으로 훑었을 때 걸리지 않았을 뿐 줄 단위로 모두 읽지는 않았다. PostgreSQL 경로는 점검하지 않았다.

- **덮지 못한 경로(한계; 그중 사진·룩북 경로는 §24에서 막음)**: 자산 ID로 오는 **자산 API 경로만** 막는다. 보류된 자산을 이미 참조하는 Photo Draft·Lookbook·상품·캐릭터가 그 자산을 읽는 경로(예: `process-local`이 원본 바이트를 읽는 것, 룩북 패키지에 들어가는 바이트)는 이번에 막지 않았다. 보류된 자산에서 파생된 출력은 별도 자산이라 그대로 보인다. PostgreSQL 저장소엔 표·가드 없음(런타임 미사용).

## 24. L-08 후속: 보류된 자산 위에 새 작업을 쌓지 못하게 함 (브랜치 l08-derived-paths)
§22가 "덮지 못한 경로"로 적었던 것 중 사진 스튜디오와 룩북을 막았다.
- **사진 스튜디오**: 원본 자산이 보류(`under_review`·`removed`) 중이면 ① Photo Draft **생성·수정**이 409 `ASSET_UNDER_REVIEW`(`app/photo_engine.py::_snapshot_source_version`) ② 이미 저장된 초안의 `process-local`이 **실행 기록을 선점하기 전에** 409로 거절(`execute_local_processing` 앞부분; 그래서 실패한 실행이 남지 않고 거절 사유가 정확함) ③ 선점과 렌더링 사이에 보류가 걸려도 렌더링 단계에서 다시 확인(`_render_local_image`; 이 경우는 선점된 뒤라 422로 실패 처리됨).
- **룩북**: 보류된 Photo 출력은 룩북에 **붙일 수 없고**(`attach_approved_photo_output`), 출력 중 하나라도 보류면 **내보내기 manifest와 패키지(ZIP)가 409**(`create_lookbook_output_manifest`, `create_lookbook_output_package`). 복구되면 다시 만들어진다(시험).
- **공용 도우미**: `app/takedown.py::held_among(db, asset_ids)`(열려 있는 연결로 보류 여부 조회).
- **시험**: `tests/test_takedown_derived_paths.py` 4건(초안 생성·실행 거절과 복구 뒤 정상화, `removed`도 거절, 선점 뒤 보류의 레이스) + `tests/test_assets_api.py`의 룩북 전체 흐름 끝에 보류 단언(attach·manifest·패키지가 보류 중 409, 복구 뒤 200). 변이 7종 적발(초안 가드, 선점 전 확인, 렌더링 시점 확인, attach 가드, 패키지 가드, manifest 가드, 도우미가 `removed` 상태를 무시).
- **시험 중 내가 만든 허점**: 처음 시험의 멱등 키(`"k1"`)가 8자 미만이라 "보류 중 실행이 거절됨" 단언이 **키 길이 때문에 통과**하고 있었다. 키를 고치고 거절 사유(메시지 `under review`, 409, 실패한 실행 기록 없음)를 단언하도록 바꾼 뒤에야 의미 있는 시험이 됐다.
- **여전히 못 덮은 것**: 상품·캐릭터가 보류된 자산 ID를 **참조로 들고 있는 것**(자산 API는 막히지만 상품·캐릭터 응답에 그 ID가 보임; 바이트는 안 나감), 이미 만들어진 파생 출력(별도 자산이라 그대로 보임), UI. PostgreSQL 경로 없음. 소유자에게 상태를 알려 주는 화면 없음.

## 25. CI 안정성 기록 (e2e를 필수 체크로 지정할 조건, `DEV_NONSTOP_PROMPT` 6번)
`DEV_NONSTOP_PROMPT` 6번: e2e를 CI 잡으로 올리되 **연속 10회 통과 전에는 필수 체크로 지정하지 않는다.** GitHub의 `ci` 워크플로 실행 기록(`gh api repos/.../actions/runs`, 완료된 실행 97회, 2026-11-09 02:24 UTC ~ 2026-11-10 01:58 UTC)으로 직접 센 값:
- **실패는 두 번**, 둘 다 같은 원인: `pilot_flow`의 "save a photo draft for the product image" 시험 경합(목록이 화면에 있다는 것과 저장 요청이 끝났다는 것을 혼동). ① 2026-11-09 11:53 UTC **main 푸시 실행**(`cf140fa`, PR #25 머지 커밋; run 42612537151) ② 13:26 UTC PR #32 실행(run 42625437022). §17은 ②만 적었다 — **①도 같은 결함이었다는 것을 이번에 확인**했다(그때는 PR 단계 CI가 통과한 직후라 main 푸시 실패를 놓쳤고, 당시 보고에는 없었다).
- **수정(PR #33, 머지 2026-11-09 13:34:29 UTC) 이후**: 완료된 CI 실행 **29회가 전부 성공, 실패 0**. 동시성으로 취소된 실행 3회는 제외(실패가 아님). 이 29회에는 수정 이후 코드(동의 화면·D2·L-05·L-07·L-08 등)가 들어간 PR 실행과 main 푸시 실행이 모두 섞여 있다.
- **해석**: "연속 10회 통과" 조건은 기록상 충족됐다. 다만 이것은 같은 한 가지 경합이 사라졌다는 증거이지 e2e 전체가 안정하다는 증명은 아니다(경합이 약 97회 중 2회, 즉 약 2%의 빈도로 나타났었다는 점에서, 다른 단계에 비슷한 경합이 더 있을 수 있고 전수 점검은 하지 않았다).
- **필수 체크로 지정하는 것은 하지 않았다**: GitHub 저장소 설정(브랜치 보호) 변경이고 협업자 전체에 영향을 주므로 사용자 결정으로 둔다. 지정할 때의 잡 이름은 `backend`, `frontend`, `e2e`.
