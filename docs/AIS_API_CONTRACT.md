# AIS_API ↔ 서버 연결표 (R-068)

기준: 홈페이지 `ai_studio_site_v4_20261116d.zip` 의 `v4/src/ais.js`, `cmd.js`, `lib.js`, `ops_usage.js`, `ops_page.py`, `studios_page.py`, `demo_page.py`.
서버 기준: `main` 의 `docs/api/openapi.runtime.v1.json`(경로 124개). 홈페이지는 `window.AIS_API`가 있으면 쓰고, 없거나 메서드가 없으면 브라우저 저장소로 동작한다.
공통: 서버 인증은 `Authorization: Bearer <Supabase 토큰>`(홈페이지의 자체 로그인과 다름 — 아래 §1). 작업공간 ID가 경로·본문에 필요하다(홈페이지의 `company` = 서버의 `workspace_id`).
상태 표기: **있음**(바로 연결 가능) · **형태 다름**(서버에 비슷한 기능이 있으나 모양·단위가 다름, 어댑터 필요) · **서버 없음**(미구현) · **홈페이지 모름**(서버에만 있음).
오류 형식: 서버는 `{"detail": {"code": "...", "message": "..."}}` 또는 `{"detail": "문장"}`. 한도 초과는 429(재시도 시각 형식 통일은 R-067에서). 홈페이지가 기다리는 코드는 `NO_API, EXISTS, BADCODE, NOCOMPANY, NOUSER, UNVERIFIED, NOCODE, EXPIRED, TOOMANY, WAIT, NOTSTAFF, SERVER`(전부 로컬 모드용 이름).

## 1. 로그인·계정 (`AIS_API.auth.*`, `AIS_API.session`)
| 홈페이지가 부르는 것 | 서버 | 상태 | 비고 |
|---|---|---|---|
| `auth.signup({name,email,password,company\|code})` | 없음 — **Supabase Auth**가 가입을 처리 | **서버 없음** | 어댑터는 Supabase `signUp` 호출 → 성공 후 소유자가 `POST /v1/workspaces`(회사=작업공간 생성)와 `POST /v1/workspaces/{id}/acquisition`(R-057, 수집 켜진 경우만, 꺼져 있으면 409 `COLLECTION_DISABLED`)를 호출 |
| `auth.signup` 의 `code`(초대 코드) | `POST /v1/workspaces/{id}/members` | **형태 다름** | 서버는 초대 코드가 아니라 **소유자·관리자가 이메일/사용자 ID로 멤버를 추가**하는 방식. 홈페이지의 `INV-xxxxxx` 코드 흐름은 서버에 없음 |
| `auth.verify({email,code})`, `auth.resend(email)` | Supabase 이메일 인증 | **서버 없음** | 6자리 코드 방식이 아니라 Supabase의 인증 메일(링크 또는 OTP). 코드 시도 5회·재전송 60초 규칙은 Supabase 설정이 정함(NEED_USER: 가입 메일 도메인) |
| `auth.login({email,password})` | Supabase `signInWithPassword` | **서버 없음** | 토큰은 이후 모든 서버 호출의 Bearer |
| `auth.logout()` | Supabase `signOut` | **서버 없음** | |
| `session` = `{user:{name,email}, company, role}` | `GET /v1/auth/me` + `GET /v1/workspaces` | **형태 다름** | `me`는 사용자 ID와 작업공간 목록·역할을 줌. **이름·이메일은 서버가 모름**(인증 제공자에만 있음). `company`는 작업공간 ID |
| 역할 `owner\|admin\|approver\|editor\|viewer` | 서버 역할 `owner\|admin\|editor\|viewer` | **형태 다름** | **`approver`(승인자) 역할이 서버에 없음.** 서버에서 승인(검수) 권한은 R-063에서 별도 검수자 역할로 정의 필요 → 설계 창 결정 |
| (홈페이지 모름) `/v1/me/legal-status`, `/v1/me/legal-acceptances`, `/v1/legal/documents`, `/v1/me/consents*`, `/v1/me/deletion-requests*`, `/v1/me/takedowns` | 있음 | **홈페이지 모름** | 약관 동의·개인정보 동의·계정 삭제 요청. 로그인 직후 약관 게이트가 필요(`LEGAL_REQUIRE_ACCEPTANCE`는 현재 꺼짐) |

## 2. 엔진·생성 (`AIS_API.engines`, `AIS_API.run(req)`)
`run`의 `req.task` 별:
| task | 홈페이지가 보내는 것 | 서버 | 상태 | 비고 |
|---|---|---|---|---|
| `engines` 목록 | 엔진 id 배열 | `GET /v1/engines/capabilities`, `GET /v1/engines/models` | **형태 다름** | 서버는 공급자별 능력·모델표를 줌. 켜진 엔진 id만 추려 주는 어댑터 필요. 현재 서버는 **mock만**, 실공급자는 꺼짐(키·비용 결정 대기) |
| `tryon` | `{engine, model, garment, category, mode, resolution, output_format, num_images, prompt}` (이미지는 dataURL) | `POST /v1/generation-jobs` (`CreateTryOnJob`: `workspace_id, model_image_url\|model_item_id, garment_image_url\|garment_item_id, category, mode, resolution, output_format, prompt`) → 비동기 → `GET /v1/generation-jobs/{id}`, `/outputs` | **형태 다름** | 서버는 **작업을 만들고 폴링/이벤트로 받는 비동기**. 홈페이지 `run`은 한 번에 결과를 돌려받는 약속(`Promise<{image}>`)이라 어댑터가 작업 생성→상태 확인→출력 가져오기를 묶어야 함. 입력은 **dataURL이 아니라 라이브러리 항목 ID**(`*_item_id`) 또는 https 주소. `engine`·`num_images`는 서버 본문에 없음(공급자 선택은 서버 설정, 후보 수 미지원) |
| `character-scene` | `{engine, image(dataURL), scene, …}` | `POST /v1/workspaces/{id}/characters`(캐릭터 저장)만 있음 | **서버 없음** | 캐릭터를 **장면에 넣어 생성**하는 작업 경로가 없음 |
| `3d-generate` | `{engine, image, …}` → `{glb}` | 없음 (`library` 에 3D 업로드·`model-info`만) | **서버 없음** | 이미지→3D 생성 작업이 서버에 없음(공급자 미연결) |
| `video-generate` | `{engine, image, prompt}` → `{video}` | `POST /v1/workspaces/{id}/video-jobs` (mock 움직이는 WebP) | **형태 다름** | 서버는 mock 움직이는 WebP, 실제 영상 공급자 없음. `{video: url}`이 아니라 자산 ID |
| `describe` (사진 설명) | `{engine, image, prompt}` → `{text}` | 없음 | **서버 없음** | 이미지→글 설명 엔드포인트 없음 |
| `auto:<style>` (Photo 자동 보정, `shop\|scene\|clear`) | `{engine, image, prompt, settings}` → `{image}` | `POST /v1/workspaces/{id}/photo-steps`, `POST /v1/photo-drafts/{id}/process-local` | **형태 다름** | 서버는 **로컬(공급자 없는) 규칙 처리**. 홈페이지가 엔진이 꺼졌을 때 쓰는 브라우저 처리와 같은 종류 |
| `market-buy` | `{…}` | 없음 | **서버 없음** | 결제 없음(결정 대기). 마켓은 R-064 |
| `team-invite` | `{name\|email, role}` | `POST /v1/workspaces/{id}/members` | **형태 다름** | 서버는 사용자 ID가 필요(이메일로 초대 불가) — 초대 메일 발송 없음 |
| `apikey.create` | `{name}` | 없음 | **서버 없음** | 외부 개발자용 API 키 발급 기능 자체가 서버에 없음 |
| `webhook.save` | `{url}` | 없음 | **서버 없음** | 웹훅 저장·전송 없음 |

## 3. 라이브러리 (`AIS_API.library()` → `[{id,name,src,attrs:{skin,hair,body,age,region}}]`)
| 홈페이지 | 서버 | 상태 | 비고 |
|---|---|---|---|
| `library()` 목록 | `GET /v1/workspaces/{id}/library?kind=&origin=&q=&attr=키:값` (R-045, R-058) | **형태 다름** | 항목은 `{item_id, kind(model\|garment\|prop\|bg\|pose\|3d\|render), name, tags, attrs, asset_id, thumbnail_asset_id, origin, is_ai_generated}`. 홈페이지의 `id→item_id`, `src`는 **미리보기 주소를 별도로 받아야 함**(`POST /v1/assets/{asset_id}/preview-url`, 만료 주소). `attrs`의 키는 자유(R-058) — 홈페이지 `skin·hair·body·age·region` 키를 그대로 쓰면 됨 |
| 홈페이지 내장 샘플(모델·의류·소품·배경·포즈 SVG) | 없음 | — | 서버 라이브러리는 **빈 상태에서 시작**(내장 샘플은 서버에 없음) |
| (홈페이지 모름) 항목 추가·수정·삭제 | `POST …/library`(업로드), `POST …/library/attach`, `PATCH`, `DELETE`, `PUT …/{id}/thumbnail`, `GET …/{id}/model-info`, `GET …/library/facets` | **홈페이지 모름** | 홈페이지는 목록 읽기만 정의 |
| (홈페이지 모름) 공용 라이브러리 `/v1/library/items*` | 있음 | **홈페이지 모름** | 서비스가 제공하는 공용 항목(가져오기 `import`) |

## 4. 내 작업 기록 (`AIS_API.work = {upsert(item)}`; 로컬 `list/get/remove/newId`)
| 홈페이지 | 서버 | 상태 | 비고 |
|---|---|---|---|
| `work.upsert(item)` (`item={id, status(draft\|req\|ok\|chg\|rej\|done), data, company, by, updated, …}`) | 서비스별로 쪼개져 있음: `/v1/photo-drafts*`, `/v1/lookbook-drafts*`, `/v1/projects*`, `/v1/products*`, 작업 `/v1/generation-jobs*` | **형태 다름** | 서버에는 "작업 기록" **하나의 범용 저장소가 없음**. 홈페이지 작업 항목을 어느 서버 개체에 매핑할지 결정 필요. 상태 값: 서버 검수 상태는 `pending/approved/rejected/changes_requested` 계열 — `draft·req·ok·chg·rej·done`과 이름이 다름 |
| `work.list/get/remove` | `GET` 목록·조회·`archive` | **형태 다름** | 서버는 **삭제가 아니라 보관(archive)** |
| 검수 `req→ok/chg/rej` | `POST …/review/approve`, `/reject`, `/request-changes`(작업 출력·사진 실행), 룩북 `approve`, `request-changes`, `submit` | **형태 다름** | 현재 서버의 검수는 **출력(output)·사진 실행(run)·룩북 초안 단위**. 홈페이지 작업 항목 단위 검수 기록은 R-063에서 새로 만들어야 함 |

## 5. 도움말 해석 (`AIS_API.assist.interpret({text,page,controls})` → `[{action,target,value}]`)
| 서버 | 상태 | 비고 |
|---|---|---|
| `POST /v1/assist/interpret` (R-048) | **있음** | 본문: `{text, page, controls:[이름…]}`. 응답 단계 `{action: set\|click\|nav\|…, target, value, risk?}` — 위험 동작은 확인 필요 표시. 홈페이지 `cmd.js viaServer`가 기대하는 모양과 같음 |

## 6. 마켓 (`AIS_API.market = {list(), publish(item)}`)
| 서버 | 상태 | 비고 |
|---|---|---|
| 없음 | **서버 없음** | R-064(결제 없는 부분)에서 만들 예정. 전까지 홈페이지는 브라우저 저장소 사용 |

## 7. 운영 (`AIS_API.ops.*`)
| 홈페이지 | 서버 | 상태 | 비고 |
|---|---|---|---|
| `ops.auth.login/verify` (운영자 로그인, 코드 확인) | 없음 | **서버 없음** | 서버는 `OPS_ADMIN_USER_IDS` 목록의 사용자(같은 Supabase 로그인)만 운영 경로 허용. **운영자 2단계 인증·5역할은 구현되어 있지 않음**(NEED_USER) |
| `ops.usage(...)` | `GET /internal/ops/usage` (R-054) | **형태 다름** | 응답에 측정/추정/미측정 `coverage`. 회사·사용자 단위는 작업공간·사용자 ID(이름·이메일 없음) |
| `ops.customers`·`ops.marketing` (R-057 요청) | `GET /internal/ops/customers?from&to&group_by&by`, `…/customers/companies`, `…/customers/retention`, `GET/PUT …/customers/{id}/contract`, `…/history` | **있음** | 현재 `ais.js`에는 호출이 아직 없음(`ops.customers` 정의 없음) |
| 서버 상태 목록(`/health`, 작업자 하트비트, 대기열 적체, 마지막 백업) | `GET /health`, `/internal/ops/health`, `/workers`, `/metrics`, `/overview`, `/runtime-readiness`, `/poll-tasks` | **형태 다름** | 마지막 백업은 서버에 **없음**(미측정) |
| 신고 대기열 | `GET /internal/moderation/reports`, `POST …/{id}/resolve`, `POST …/assets/{id}/reinstate` | **홈페이지 모름** | |
| 한도 알림 | `GET /internal/ops/alerts`, `/rollup`, `/downloads`, `/failed-jobs`, `/provider-registry`, `/deletion-requests` | **홈페이지 모름** | |
| 사이트 설정(공지·배너·점검 모드·회사 정보·히어로) `ais_site_cfg·ais_site_info·ais_site_hero` | 없음 | **서버 없음** | 지금은 운영자의 브라우저에만 저장되어 **다른 방문자에게 안 보임**. 서버 저장·공개 조회 경로가 필요(운영 쓰기 → 2단계 인증 결정과 묶임) |

## 8. 로그·내려받기
| 홈페이지 | 서버 | 상태 | 비고 |
|---|---|---|---|
| `AIS.log({service,engine,status,...})` → 브라우저 `ais_usage` | `GET /v1/workspaces/{id}/usage`, `GET /internal/ops/usage` | **형태 다름** | 서버 사용량은 **서버가 실제로 처리한 작업에서** 집계(브라우저가 보낸 로그를 받지 않음). 홈페이지 로컬 로그와 숫자가 일치하지 않음 — 서버 값이 기준 |
| `AIS.download(href, name)` | `GET /v1/assets/{id}/…preview-content`, `POST /v1/generation-jobs/{id}/outputs/export-manifest`, 룩북 `package-export`, `…/exports/{id}/download` | **형태 다름** | 서버는 서명된 만료 주소로 내려받음. **AI 생성 표시 삽입은 R-062에서**(지금 내려받기에는 없음) |
| 신고(콘텐츠 신고) | `POST /v1/content-reports` | **홈페이지 모름** | |
| 외부 공급자 전송 고지 | `POST /v1/external-provider-notices` | **홈페이지 모름** | 실공급자를 켜면 전송 전 고지 확인이 필요 |
| 기능 표시 | `GET /v1/features` | **홈페이지 모름** | 서버가 켜 둔 기능 목록(홈페이지가 버튼을 켜고 끄는 데 쓸 수 있음) |

## 9. 요약: 서버에 없는 것 / 홈페이지가 모르는 것
**홈페이지가 쓰는데 서버에 없음**: 가입·로그인·인증 메일(Supabase에 위임, 홈페이지 코드 흐름과 다름), 초대 코드, `approver` 역할, 캐릭터 장면 생성, 이미지→3D 생성, 이미지 설명(`describe`), 실영상 생성, 마켓(R-064), 결제(`market-buy`), API 키 발급, 웹훅, 운영자 로그인·2단계 인증·역할, 사이트 설정 서버 저장, 내 작업 범용 저장소, 마지막 백업 시각.
**서버에 있는데 홈페이지가 모름**: 약관 동의 게이트·개인정보 동의·계정 삭제 요청, 콘텐츠 신고, 외부 공급자 고지, `features`, 라이브러리 쓰기·facets·썸네일·3D 정보, 공용 라이브러리 가져오기, 자산 버전·관계·출처, 검수 API(출력·사진 실행·룩북), 프로젝트·상품 개체, 모델 시안(`model-drafts`), 사진 단계·프리셋, 영상 작업, 운영 지표·알림·신고 대기열.
**양쪽 모양이 달라 어댑터가 필요한 것**: 생성(동기 약속 vs 서버 비동기 작업), 라이브러리 항목 모양과 미리보기 주소, 작업 기록, 사용량 로그, 내려받기, 역할 이름, 세션(이름·이메일 없음).
