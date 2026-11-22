# 문서 색인 (docs/*.md)

자동 생성: `python ai_creator_studio_backend_starter/scripts/docs_check.py --write`. 새 문서를 `docs/`에 추가하면 이 표도 갱신해야 CI가 통과한다(`--check`).
오래된 문서 점검은 `--stale 90`(월 1회), 사라진 파일을 가리키는 언급은 `--refs`. 하위 폴더의 역할은 `README.md`.

| 문서 | 제목 | 첫 줄 |
|---|---|---|
| `AIS_API_CONTRACT.md` | AIS_API ↔ 서버 연결표 (R-068) | 기준: 홈페이지 `ai_studio_site_v4_20261116d.zip` 의 `v4/src/ais.js`, `cmd.js`, `lib.js`, `ops_usage.js`, `ops_page.py… |
| `AUDIO_RESEARCH.md` | 영상 음원 조사 (레인 4 · 6c, 회신 56 ⑫ · 답신 61) | **이 문서는 조사다.** 어떤 소리를 쓸 수 있게 할지는 **법무·대표 결정**이라 정하지 않았다(답신 61). 기술적으로 가능한 것만 코드(`app/video_mp4.py::add_audio`)… |
| `BG_REMOVAL_EVAL.md` | E-09a 배경 제거 후보 비교 (2026-11-17, 레인 3) | **범위**: Pillow만 쓰는 고전 영상 처리 후보 2종 + 둘을 섞은 `auto`. AI 컷아웃 모델(U²-Net, rembg, 유료 API)은 새 의존성·모델 파일·외부 전송이 필요해 **이… |
| `CHANGELOG.md` | BUILD-00157 — Viewer Animation Loop Failure Isolation | - Extracted the Studio3DViewer requestAnimationFrame loop into a dependency-free controller with one-frame own… |
| `DATA_LIFECYCLE.md` | 데이터 수명주기 — 내보내기·삭제·보관 (R-065) | / 단계 / 어디서 / 상태 / |
| `ERROR_CODES.md` | 오류 코드 → 안내 문구 표 (자동 생성 — 직접 고치지 않음) | 버전 `2026-11-17.1`. 원본은 `ai_creator_studio_backend_starter/app/error_catalog.py`, 같은 내용을 `GET /v1/error-catalog… |
| `EVENTS_DESIGN.md` | 이벤트·웹훅 설계 초안 (B-18, 초안 — 아무것도 연결되지 않음) | 코드: `ai_creator_studio_backend_starter/app/events.py`, 시험: `tests/test_events.py`. 발송·구독 저장·비밀 관리는 **아직 없음**(결… |
| `FEATURE_SCOPE_STATUS.md` | AI CREATOR STUDIO — Current Feature Scope | **As of BUILD-00151.** This is the current product-scope reference. Older BUILD-00093/00096 notes describe the… |
| `GARMENT_DEFORM.md` | 의류 메시 변형 맞춤 (R-ENGINE-03b · 트랙 A 1단계) | `app/garment_deform.py` — `garment.v1` 의류(GLB + 사이즈표, `app/garments.py`)를 **기본 인체(`app/base_models.py`)에 몸 치수를… |
| `GARMENT_FIT.md` | 상의 껍데기 맞춤 (R-ENGINE-03a · 트랙 A 1단계) | `ai_creator_studio_backend_starter/app/garment_fit.py` — 레인 2의 치수 마네킹(`app/mannequin.py`) 둘레에 **상의 껍데기**를 씌워 한… |
| `GLTF_COMPRESSION_EVAL.md` | 3D 압축 도구 측정 (2026-11-17, 레인 1 / E-01 후속, 회신 55) | **승인 범위**: glTF-Transform CLI를 **개발 환경·CI에서만** 사용(운영 서버에 설치하지 않음). 이 저장소에는 `tools/gltf_compress/`(package.json… |
| `INTEGRATION_ENVIRONMENT_STATUS_BUILD-00212.md` | Supabase / Vercel Integration Environment Status — BUILD-00212 | Date: 2026-11-06. This is an environment inventory, not a successful app integration test. |
| `LAUNCH_CHECKLIST.md` | 출시 체크리스트 (제한된 B2B 파일럿) — 증거 유무 표 | > **초판 2026-11-09, 11/28에 갱신할 것.** 저장소에는 별도의 출시 기준 문서가 없어서 **항목은 이 세션이 구성한 것**이다(법률 항목은 `docs/project-design/i… |
| `LAUNCH_STATUS.md` | LAUNCH STATUS | > 이 파일은 2026-11-09 세션에서 **새로 만들었다**. 이전에는 저장소의 어느 브랜치와 로컬 파일시스템에도 `docs/LAUNCH_STATUS.md`가 없었다(검색으로 확인). 따라서 이… |
| `LIBRARY_OPERATIONS.md` | 기본 자산 라이브러리 운영 안내 (항목 추가·수정·내리기) | 대상: 이미지와 표(manifest)만 준비하면 되는 비개발자 운영 담당. 명령 실행은 개발 PC에서 개발 창이 하거나, 아래 순서를 그대로 따라 할 수 있습니다. |
| `MARKET_CONTRACT.md` | 마켓 연결 계약표 (`AIS_API.market.*`) — R-064 | 범위: **결제 없는 부분**만. 구매·정산·환불·수수료·통화는 **결정 대기라 서버에 없음**(`price`는 0 이상의 정수 자리일 뿐, 통화 필드 없음 — 홈페이지는 지금 "KRW"로 표시하지… |
| `ONBOARDING.md` | 개발자 온보딩 — 10분 안에 로컬 API 띄우기 (B-21) | 목표: 저장소를 받은 사람이 **명령 몇 개로** 무료 mock 모드의 API를 띄우고 응답을 확인한다. 외부 AI 서비스·유료 호출·Supabase/Vercel·공유 DB는 **쓰지 않는다**(전… |
| `OPS_READ_CONTRACT.md` | 운영자 읽기 계약표 (`AIS_API.ops.*`) — R-066 | 범위: 운영 화면이 **읽기만** 하는 경로. 쓰기(정지·설정·공지 등)는 R-052 결정 대기라 서버에 **없음**. |
| `OPTION_IMAGES.md` | 옵션·도감 이미지 정적 자산 규칙 (R-051) | 홈페이지(설계 창 정적 사이트, 배포 위치 `public/site/` 예정 — R-025 결정 대기)의 선택 견본 그림을 **파일로만** 둔다. 서버 코드는 이 그림을 만들거나 전송하지 않는다. |
| `POSTGRES_RACE_PRIMITIVES.md` | PostgreSQL 전환: 경합 보호 대체표 (B-05 · D-66c 1단계) | SQLite 전용 모듈 43개가 "확인 후 쓰기"를 지키는 방식과, PostgreSQL(기본 READ COMMITTED, 읽기는 막지 않음)에서 그것을 대체할 구성. **모든 행은 `tests/te… |
| `RATE_LIMITS.md` | 속도 제한·남용 방지 현황표 (R-067) | / 구간 / 상태 / 값(기본) / 설정(환경 변수) / 단위 / |
| `README.md` | 문서 인덱스 | 문서는 문서의 목적과 수명에 따라 관리합니다. 매 작업마다 README, 개발기록, 인수인계 파일을 각각 새 버전으로 복제하지 않습니다. |
| `RESTORE_DRILL.md` | 복구 훈련 (RTO 측정) — R-077 | `scripts/restore_drill.py`가 **백업 → 검증 → 새 빈 폴더로 복원 → 복원본 무결성 검사**를 한 번에 돌리고 단계별 시간을 JSON으로 냅니다. 운영 백업·운영 DB는 쓰… |
| `RUNBOOK.md` | 운영 런북 (제한된 B2B 파일럿, SQLite 단일 인스턴스) | > **상태**: 이 문서의 명령과 설정은 코드에서 확인했고, 점검·백업·복구 절차는 시험으로 검증했다. 그러나 **실제 배포 환경에서 실행해 본 적은 없다**(배포 대상 정보 없음 — `docs/… |
| `THIRD_PARTY_FONTS.md` | 서드파티 글꼴 (자막용) | / 항목 / 내용 / |
| `VERSIONING.md` | 버전 및 문서 관리 규칙 | / 식별자 / 형식 / 목적 / 증가 기준 / |
| `VIDEO_MP4.md` | 실제 MP4 출력 (레인 4 · E-08a) | `ai_creator_studio_backend_starter/app/video_mp4.py` — 정지 그림 1~8장을 카메라 움직임이 있는 **실제 MP4**로 만든다. AI·외부 공급자·네트워크… |
| `WORK_ITEMS_CONTRACT.md` | 작업 항목(내 작업) 연결 계약표 — `AIS_API.work.*` ↔ 서버 `work-items` (R-069) | 서버: `/v1/workspaces/{작업공간 ID}/work-items`. 홈페이지의 `company` = 작업공간 ID. 권한은 라이브러리와 같음(읽기: 보기 이상, 쓰기: 편집자 이상, 관리자… |
