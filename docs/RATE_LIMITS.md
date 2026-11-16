# 속도 제한·남용 방지 현황표 (R-067)

## 1. 한눈에 (있음/없음/값)
| 구간 | 상태 | 값(기본) | 설정(환경 변수) | 단위 |
|---|---|---|---|---|
| **가입·로그인 시도** | **서버에 없음** — 인증은 Supabase Auth가 처리 | Supabase 쪽 설정(이 서버에서 확인 못 함 → **미확인**) | Supabase 대시보드(운영 설정이라 제가 바꾸지 않음) | — |
| **업로드**(이미지·3D·버전·라이브러리 업로드) | **이번에 신설** | **30회/분/사용자 + 300회/시간/작업공간** | `RATE_UPLOAD_USER_PER_MINUTE`, `RATE_UPLOAD_WORKSPACE_PER_HOUR` | 요청 수 |
| 〃 크기 | 있음(기존) | 이미지 25MB, 3D 등 100MB | `IMAGE_MAX_UPLOAD_BYTES`, `ASSET_MAX_UPLOAD_BYTES` | 바이트 |
| **생성 요청**(가상 착용 작업·영상·모델 시안·사진 단계) | **이번에 신설**(한 예산을 함께 씀) | **10회/분/사용자 + 120회/시간/작업공간** | `RATE_GENERATE_USER_PER_MINUTE`, `RATE_GENERATE_WORKSPACE_PER_HOUR` | 요청 수 |
| 〃 일일 작업 수 | 있음(기존) | **0 = 제한 없음**(기본) | `GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE` | 작업공간/일 |
| 〃 월 한도·킬 스위치·USD 상한·공급자 일일 상한 | 있음(기존, R-037) | 작업공간 100/월, 전체 500/월, USD 상한 **미설정이면 실공급자 작업 거부** | `AI_JOB_LIMIT_PER_WORKSPACE_MONTH`, `AI_JOB_LIMIT_GLOBAL_MONTH`, `AI_JOBS_DISABLED`, `AI_COST_LIMIT_USD_MONTH`, `AI_PROVIDER_DAILY_LIMIT[_<공급자>]` | 작업/월 |
| 〃 영상 | 있음(기존) | 20/일/작업공간 | `VIDEO_DAILY_LIMIT` | |
| 〃 도움말 해석 | 있음(기존) | 30/분/사용자 + 외부 해석 200/일/작업공간 | `ASSIST_PER_MINUTE`, `ASSIST_LLM_DAILY_LIMIT` | |
| 〃 공급자로 나가는 호출 | 있음(기존) | 60/분, 동시 4 | `PROVIDER_MAX_PER_MINUTE`, `PROVIDER_MAX_CONCURRENCY` | 외부 호출 |
| 〃 공용 라이브러리 가져오기 | 있음(기존) | 200/일/작업공간 | `LIBRARY_IMPORT_DAILY_LIMIT` | |
| **내려받기**(작업 결과·버전 원본·내보내기 ZIP·룩북 패키지) | **이번에 신설** | **60회/분/사용자** | `RATE_DOWNLOAD_USER_PER_MINUTE` | 요청 수 |
| 〃 룩북 패키지 월 한도 | 있음(기존) | **0 = 제한 없음**(기본) | `DOWNLOAD_MONTHLY_LIMIT` | 작업공간/월 |
| 〃 서명 미리보기 링크(로그인 없이 쓰는 짧은 링크) | **없음** — 사용자 정보가 없어 사용자별 제한 불가, 링크 수명 300초가 한계 | — | `ASSET_PREVIEW_TTL_SECONDS` | |
| **신고**(콘텐츠·마켓) | **이번에 분당 제한 신설** + 기존 일일 | **5회/분/사용자** + 콘텐츠 20/일, 마켓 10/일 | `RATE_REPORT_USER_PER_MINUTE`, `CONTENT_REPORT_DAILY_LIMIT`, `MARKET_REPORT_DAILY_LIMIT` | |
| **내보내기 ZIP**(R-065) | 있음 | 3회/일/작업공간(계정은 사용자) | `EXPORT_DAILY_LIMIT_PER_WORKSPACE` | |
| **IP 기준 제한** | **없음** | — | — (프록시가 전달하는 주소 처리 방식이 정해지지 않음) | |

`0`으로 두면 그 규칙만 꺼지고, `RATE_LIMITS_ENABLED=0`이면 **이번에 신설한 규칙 전체**가 꺼짐(기존 일일·월 한도는 영향 없음). 기본값은 보수적으로 잡은 **임시값**이며 실제 사용 패턴을 본 뒤 조정해야 함(**실측 미실행**).

## 2. 429 응답 형식(통일)
HTTP **429** + 헤더 `Retry-After: <초>` + 본문
```json
{"detail": {"code": "RATE_LIMITED", "message": "too many upload requests; try again shortly",
            "retry_after_seconds": 42, "retry_at": "2026-11-16T14:03:21.123456+00:00",
            "scope": "upload", "per": "user", "limit": 30, "window_seconds": 60}}
```
- 신설 규칙은 `code=RATE_LIMITED` + `scope`(`upload|generate|download|report`)·`per`(`user|workspace`)·`limit`·`window_seconds`.
- **기존 한도도 같은 모양**(기존 키는 그대로 두고 `retry_after_seconds`·`retry_at`을 추가): `DAILY_JOB_LIMIT_EXCEEDED`, `ASSIST_RATE_LIMITED`, `REPORT_DAILY_LIMIT`(전에는 글자 한 줄이던 것), `EXPORT_LIMIT`, `VIDEO_DAILY_LIMIT`, `LIBRARY_IMPORT_LIMIT`, `DOWNLOAD_MONTHLY_LIMIT`(다음 달 1일까지).
- **재시도 시각은 가능하면 실제 계산**(가장 오래된 기록이 창을 벗어나는 때). 계산할 수 없는 경우(영상·가져오기 일일 한도, 도움말 30초)는 `retry_estimated: true`로 **추정치임을 표시**.
- **예외: 비용 한도·킬 스위치 응답**(`GLOBAL_MONTHLY_LIMIT`, `AI_JOBS_DISABLED` 등)은 서비스 전체 운영 수치를 노출하지 않으려고 `{code, message}`만 유지(기존 시험이 이 모양을 고정) — 재시도 시각 없음.
- 거부된 동작은 **횟수에 세지 않고 아무것도 저장하지 않음**(시험). 멱등 키로 재전송한 요청은 새 동작이 아니라 세지 않음.

## 3. 운영 지표
- `GET /internal/ops/rate-limits?days=7`(운영자): 적용 중인 규칙표(값·켜짐 여부·환경 변수)와 **일별·구간별 거부 횟수**(이름·ID 없음).
- `GET /internal/ops/usage`의 `blocked`: **이번 규칙이 거부한 건**이 서비스 이름(`upload`·`generate`…)으로 집계됨. **일일·월 한도와 비용 한도의 거부는 저장되지 않아 `blocked`에 없음**(응답의 `not_measured`가 그렇게 말함).
- 카운터는 **일방향 해시만** 보관하고 1시간 지난 행은 규칙 검사 때 지움. 거부 기록(`rate_limit_blocked`)에는 작업공간·사용자 ID가 있어 **삭제 스크립트가 작업공간 삭제 때 지우고 계정 삭제 때 익명화**(시험).

## 4. 한계·결정 필요
가입·로그인 제한은 Supabase 설정 확인 필요(NEED_USER), IP 기준 제한은 프록시 구성이 정해져야 가능, 기본값은 실측 전 임시값, 서명 미리보기 링크는 사용자별 제한 불가. 다중 서버 환경에서도 카운터가 DB에 있어 유지되지만 **SQLite 전용**(PostgreSQL 포트는 비활성).
