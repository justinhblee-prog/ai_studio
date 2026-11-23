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


## 10. 갱신 (R-059~R-066 반영, 위 표의 일부를 대체) + 응답 예시
**표 갱신**: ①마켓(§6)은 **구현됨** → `docs/MARKET_CONTRACT.md`. ②검수는 **자산 단위 API 추가**(`/v1/workspaces/{id}/reviews*`, 상태 `requested|approved|changes_requested|rejected|withdrawn`; 홈페이지 `req/ok/chg/rej`와 대응, `draft`=기록 없음). ③운영자 읽기 경로는 `docs/OPS_READ_CONTRACT.md`(감사 로그 `GET /internal/ops/audit` 추가). ④라이브러리 항목은 `attrs`, `thumbs`(480/960 서명 주소)를 가짐, 작업 결과 저장 `POST …/library/from-job`. ⑤생성 요청은 `style`·`region`·`prompt_prefix`를 받음. ⑥AI가 만든 사진은 내려받을 때 파일 안에 AI 표시가 들어감. ⑦"내 작업" 범용 저장소(R-069)는 아직 없음.

### `GET /v1/features` (로그인한 사용자, 작업공간과 무관)
<!-- contract: getFeatures 200 -->
```json
{"features": {
  "tryon":     {"enabled": true,  "status": "available"},
  "character": {"enabled": true,  "status": "available"},
  "three_d":   {"enabled": false, "status": "pilot_preview"},
  "video":     {"enabled": false, "status": "pilot_preview"},
  "market":    {"enabled": false, "status": "pilot_preview"}
}}
```
- 이름은 항상 이 5개(`tryon, character, three_d, video, market`). `enabled=false`면 `status="pilot_preview"`("미리보기로만 보임, 운영자가 켤 수 있음"), `true`면 `"available"`. **값은 서버 환경 설정(`FEATURE_<이름>`)이며 기본은 모두 꺼짐** — 실제 켜짐 여부는 배포 설정에 따름(예시의 true/false는 모양을 보여 주는 값).
- 빈 값 규칙: 목록이 비는 일 없음. 인증 없으면 401.
- ⚠ `market.enabled`는 **홈페이지 표시용 스위치일 뿐이고 `/v1/market/*`를 막지 않습니다**(서버 경로는 항상 열려 있음).

### `GET /v1/workspaces/{id}/library/facets?kind=garment` (보기 권한 이상)
<!-- contract: listWorkspaceLibraryFacets 200 -->
```json
{"kind": "garment",
 "facets": [
  {"key": "category", "values": [{"value": "pants", "count": 1}, {"value": "top", "count": 2}]},
  {"key": "colors",   "values": [{"value": "beige", "count": 1}, {"value": "white", "count": 1}]},
  {"key": "season",   "values": [{"value": "summer", "count": 1}, {"value": "winter", "count": 1}]},
  {"key": "size_no",  "values": [{"value": "95", "count": 1}]}
 ]}
```
- `kind`을 생략하면 `"kind": null`로 **모든 종류**를 합산. 항목이 없거나 속성이 없으면 `{"kind": ..., "facets": []}`.
- `facets`는 **키 이름 순**, `values`는 **값 순**(글자 정렬). **숫자 값은 글자로 돌려줌**(`95` → `"95"`), **목록 값은 원소마다 한 번씩 셈**(`colors: ["white","beige"]` → white 1, beige 1), 신고로 가려진 항목은 제외.
- 필터로 쓸 때: `GET …/library?attr=category:top&attr=season:summer`(여러 개는 **모두 일치**, 값은 글자 비교·대소문자 구분).
- 예시의 키 이름(`category`, `colors`…)은 **분류표가 확정되기 전의 예**이며 서버는 키를 강제하지 않음(R-058).

### `GET /v1/workspaces/{id}/library/{item_id}` — 라이브러리 항목 한 개 (목록의 `items[]` 원소도 같은 모양)
<!-- contract: getWorkspaceLibraryItem 200 -->
```json
{"item_id": "wli_0f3a9c1d2b7e4a5f8c6d1e2f3a4b5c6d", "workspace_id": "ws-demo", "asset_id": "ast_5c1e7f0a9b2d4c6e8f1a3b5d7c9e0f12",
 "kind": "garment", "origin": "upload", "is_ai_generated": false, "name": "린넨 셔츠", "tags": ["여름", "린넨"],
 "attrs": {"category": "top", "season": "summer", "size_no": 95, "colors": ["white", "beige"]},
 "created_by": "user-a", "created_at": "2026-11-16T09:00:00+00:00", "updated_at": "2026-11-16T09:00:00+00:00",
 "original_filename": "shirt.png", "media_type": "image/png", "size_bytes": 48213, "thumbnail_asset_id": null,
 "thumbs": {"480": "/v1/assets/ast_5c1e7f0a9b2d4c6e8f1a3b5d7c9e0f12/thumb/480?expires=1763290000&signature=ab12", "960": "/v1/assets/ast_5c1e7f0a9b2d4c6e8f1a3b5d7c9e0f12/thumb/960?expires=1763290000&signature=cd34"}}
```
- `origin`: `ai`(AI가 만든 결과) · `upload`(올린 파일) · `work`(작업 결과). `thumbs`는 이미지만, 서명이 없으면 `null`. `thumbnail_asset_id`는 3D 항목이 올린 미리보기 그림의 자산 ID(없으면 `null`).

### `GET /v1/workspaces/{id}/reviews/{review_id}` — 자산 검수 한 건 (요청·승인·변경 요청·반려·재요청·철회 응답도 같은 모양)
<!-- contract: getAssetReview 200 -->
```json
{"review_id": "rev_0a1b2c3d4e5f60718293a4b5c6d7e8f9", "workspace_id": "ws-demo", "asset_id": "ast_5c1e7f0a9b2d4c6e8f1a3b5d7c9e0f12", "status": "approved",
 "requested_by": "user-d", "requested_at": "2026-11-16T09:00:00+00:00", "handled_by": "user-e", "handled_at": "2026-11-16T09:30:00+00:00", "comment": "좋습니다",
 "updated_at": "2026-11-16T09:30:00+00:00", "version": 2}
```
- `status`: `requested | approved | changes_requested | rejected | withdrawn`. 처리 전(`requested`)에는 `handled_by`·`handled_at`이 `null`.

## 11. 기본 인체 모델 (공개 읽기, 로그인 불필요) — 레인 2/5, 2026-11-17
코드로 직접 만든 양식화 인체 GLB(저폴리, 얼굴·스캔·사진·제3자 에셋 없음). 홈페이지 작업실의 임시 마네킹 교체용.
- `GET /v1/base-models` → `{"sexes":["male","female"],"top_styles":["tank","tshirt","longsleeve"],"bottom_styles":["shorts","pants"],"default_colors":{"skin":"e0ac69","top":"3c5aa0","bottom":"32323c"},"materials":["skin","top","bottom"], ...}`
- `GET /v1/base-models/{sex}/glb?top_style=tshirt&bottom_style=pants&top=ff0000&bottom=00ff00&skin=e0ac69` → `model/gltf-binary` (색은 `#` 없는 16진수 6자리, 대소문자 무관). 헤더 `ETag`, `Cache-Control: public, max-age=86400`, `If-None-Match` 일치 시 304. 잘못된 값은 422(파일 없음).
- **몸 치수 반영(선택)**: 쿼리 `height_cm`(120~220), `chest_cm`(60~160), `waist_cm`(50~150), `hips_cm`(70~170) — 일부만 보내도 됨. 키는 모델 전체를 비례 확대, 둘레는 그 단면만 조정(근사치·양식화, 실제 몸 형태 아님). 프리셋 둘레는 `GET /v1/base-models`의 `preset_circumferences_cm`.
- 옷 색 교체: 받은 GLB의 재질 `top`/`bottom`/`skin`의 `baseColorFactor`를 바꾸거나, 위 쿼리로 서버가 색을 입힌 파일을 다시 받는다. 스타일 교체도 같은 쿼리.
- 한계: 매우 단순한 "나무 인형" 모양, 옷은 색·길이만 바뀌며 실제 의류 메시가 아님.

## 12. 3D 돌려보기 작업 `AIS_API.work.render3d` (R-ENGINE-10, 자체 엔진 own3d · **mock · 기능 플래그 기본 닫힘**)
서버 플래그 `RENDER3D_ENABLED`가 꺼져 있으면(기본) 아래 세 경로는 로그인·멤버십·역할 검사 뒤 모두 **409 `RENDER3D_CLOSED`**. 켜면:

| 화면 호출 | 서버 | 비고 |
|---|---|---|
| `AIS_API.work.render3d({sex, measurements, garments:[{kind, id}], bg, angles})` → `{job_id}` | `POST /v1/workspaces/{id}/render3d-jobs` → **202** `{job_id, status:"queued", …}` | 편집자 이상. `sex` male\|female, `measurements`(선택) `height_cm·chest_cm·waist_cm·hips_cm`, `garments` 최대 3(종류 top·bottom·skirt·dress·jacket, **id는 내장 샘플 `sample`만** — 라이브러리 옷은 아직 불가), `bg` white\|light\|gray\|studio, `angles` 0~345의 15의 배수 최대 8개(기본 `[0,45,90,180,270]`), `mp4`(기본 true) |
| 폴링 | `GET /v1/workspaces/{id}/render3d-jobs/{job_id}` → `{status: queued→running→succeeded\|failed, images:[{angle, asset_id}], mp4:{asset_id, seconds:5, size:[720,1280], cuts:8}\|null, qc, error_code}` | 열람자도 읽기 가능. 파일은 기존 자산 경로로 받는다(`image/png`, `video/mp4`) |
| 목록 | `GET /v1/workspaces/{id}/render3d-jobs` | 최신순 100개 |

- 오류 코드: `RENDER3D_CLOSED`(409) · `RENDER3D_MEASUREMENT_INVALID` · `RENDER3D_GARMENT_UNKNOWN` · `RENDER3D_GARMENT_CONFLICT`(422) · `RENDER3D_DAILY_LIMIT`(429, 기본 하루 20건) · `FFMPEG_MISSING`(503, mp4 요청인데 서버에 ffmpeg 없음 — 그림만 받으려면 `mp4:false`) · 작업 실패 시 `FIT_REFUSED`·`QC_FAILED`·`RENDER_FAILED`(`error_code`).
- **정직한 한계**: 그림은 **소프트웨어 렌더(mock)**: 마네킹·평면 색·조명 1개, 사진 품질 아님. mp4는 45° 간격 8컷을 섞어 만든 5초 회전(겹쳐 보이는 가장자리 있음). 작업은 서버 재시작 시 복구되지 않음. 실제 AI 모델·GPU·외부 호출 없음.
- **`qc.render_check` (R-ENGINE-11)**: 작업 결과 `qc` 안의 `render_check`는 `render-cuts.v1` **기록**이다(작업 성공·실패를 정하지 않음; `qc.passed`는 빈 그림 검사 그대로). 옷마다·각도마다 `visible_share`(몸 없이 그린 옷 윤곽 대비 몸 앞에 실제로 보이는 옷 비율 = 윤곽 IoU; **정면·후면(`frontal:true`)만 판정**, 측면은 몸의 팔이 소매 없는 옷을 정당하게 가려 기록만), `colour_distance`(요청한 색과의 색도 거리), `penetration_points`(맞춤 보고의 관통 점 수), `passed`. 기준(`min_visible_share 0.98`, `max_colour_distance 0.05`)은 **제안값**. 로고·글자·무늬·손·길이는 이 점검으로 판단할 수 없어 **`None`**, 비교할 것이 없으면 `passed:null`. 같은 기록이 own3d mock의 `output.qc`에도 들어간다. 소매 없는 옷은 팔을 뺀 몸 기준으로 판정하고(`occluder:"body_without_arms"`), 팔을 포함한 수치는 `visible_share_incl_arms`에 남긴다(R-ENGINE-09b).

## 13. 사진 일괄 처리 `POST /v1/workspaces/{id}/photo-steps/batch` (E-09e)
한 가지 레시피를 최대 **20장**에 적용. 본문 `{asset_ids:[…], steps:[…] | preset_id}` — **steps 또는 preset_id 중 정확히 하나**(둘 다·둘 다 없음 = 422 `BATCH_RECIPE_REQUIRED`), 같은 그림 두 번 = 422 `BATCH_DUPLICATE_ASSET`, 레시피가 잘못되면 **시작 전에 통째로 422**(아무것도 저장 안 됨). 편집자 이상.
응답 201: `{batch_id, preset_id, total, succeeded, failed, not_run, items:[{asset_id, status: ok|failed|not_run, asset, steps, error_code, message}]}` — 이미지마다 따로 처리해 **일부 실패는 나머지를 막지 않는다**(없는 그림 `ASSET_NOT_FOUND`, 확대 결과가 너무 큼 `STEP_RESULT_TOO_LARGE` 등). 이미지 1장이 생성 속도 제한 1회로 센다; 한도에 닿으면 **나머지는 `not_run`(`RATE_LIMITED`)** 으로 보고하고 대기열에 쌓지 않는다(나중에 다시 호출). 결과는 모두 새 자산, 원본 불변, 출처 기록에 `batch_id`(+`preset_id`).
새 단계 `upscale`(E-09d)도 이 레시피에 쓸 수 있다(`docs/UPSCALE_EVAL.md`).

## 14. 3D 모델 내보내기 `GET /v1/assets/{asset_id}/versions/{version_id}/export` (E-05)
저장된 `.glb` 한 버전을 **출처 정보가 든 파일**로 내려준다. 편집자 이상(열람자는 미리보기는 되지만 내보내기는 403), 로그인 필수, 다른 작업공간은 403/404, 보류(takedown)된 자산은 404, `.glb`가 아니면 422 `EXPORT_NOT_GLB`, 내려주기 전에 **저장 파일의 크기·SHA-256을 기록과 대조**(어긋나면 409, 아무것도 안 보내고 기록도 안 남김), `download` 속도 제한 적용.
- 파일 = 저장된 GLB + **`asset.extras.acs_export` 한 블록**(`schema: acs-3d-export.v1`, `asset_id`, `version_id`, `version_number`, `source_sha256`(저장 파일의 해시), `exported_at`, `ai_disclosure{is_ai_generated, digital_source_type(IPTC), text}`). **형상·재질·텍스처 등 나머지는 한 바이트도 안 바뀐다**(시험: BIN 바이트·메시·재질·접근자 동일, 기존 `asset.extras` 보존). 저장 파일은 불변.
- AI 표시는 출처 기록으로 판정(AI 공급자 결과면 표시, 업로드·로컬 처리·내장 mock은 표시 안 함); 문구는 그림 표시와 같은 설정(`AI_MARK_TEXT_*`, 최종 법무 문구는 대기).
- 응답 머리: `ETag`·`X-Content-SHA256` = **보내는 파일**의 해시, `Content-Disposition: attachment`, `Cache-Control: private, no-store`. 내보낸 사실은 출처 기록(`asset.exported`: 누가·어느 버전·원본 해시·내보낸 파일 해시·바이트 수)에 남는다.
- **USDZ는 만들지 않는다**(변환 도구 미승인). `.gltf`(분리형)도 내보내기 대상 아님.

## 15. 사이즈 비교 `POST /v1/workspaces/{id}/fit-check` (M4 화면 계약, 레인 2)
같은 몸에 옷 S·M·L을 입혔을 때 **어디가 얼마나 여유 있는지**와 추천 사이즈를 돌려준다(`app/ease_api.py` → `app/ease_map.py`, 설명 `docs/EASE_MAP.md`). 열람자 이상(작업공간에서 읽는 것도 쓰는 것도 없음), 로그인 필수, **own3d 기능 플래그 `RENDER3D_ENABLED` 뒤**(기본 닫힘 → 409 `RENDER3D_CLOSED`). 호출 한 번 약 0.2초, 저장 없음, 결정적.
- 본문 `{sex: male|female, kind: top|bottom|skirt|dress|jacket, measurements?: {height_cm,chest_cm,waist_cm,hips_cm 중 일부}, nominal?: {chest_cm,waist_cm,hips_cm 중 일부(40~200)}}` — `nominal`은 M 사이즈가 맞춰진 기준 몸(없으면 프리셋 둘레). 모르는 필드 422.
- 응답 200: `{kind, sex, measurements, nominal, sizes:{S|M|L: {zones:{chest_cm|waist_cm|hips_cm: {ease_cm, class: tight|fitted|regular|loose, …}}, tight_zones[], below_min_ease_zones[], clearance_cm:{min,median,p95}, pressure_share}}, recommended: "S"|"M"|"L"|null, limits:{min_ease_cm, max_pressure_share, source:"proposal"}, proposal_class_limits_cm[], note, engine:"own3d"}`. `recommended` = 모든 부위에 여유가 충분하고 몸을 누르는 꼭짓점 비율이 한도 이하인 **가장 작은** 사이즈, 맞는 것이 없으면 null.
- 오류: `RENDER3D_CLOSED`(409) · `FIT_CHECK_INVALID`(422: 몸 치수나 기준 둘레가 범위 밖) · 권한 403/404.
- **정직한 한계**: 정형화된 마네킹 위의 기하 안내이며 천의 늘어남·실제 사이즈표 표준이 아니다. 여유 한도(2 cm 등)와 등급 경계(0/4/10 cm)는 **제안값**(`limits.source`). 사진 일괄 처리는 §13, 3D 모델 내보내기는 §14에 이미 있다.

## 16. 자료 등록(우리 자료) 대화상자 ↔ 서버 (D-01, 답신 69 C.6)
홈페이지 `site/assets/lib.js`의 `L.register`(등록 대화상자)는 이미 있는 작업공간 라이브러리 API(R-045·R-058, §3)로 **그대로** 저장된다 — 새 API는 필요 없었다. 대응(`tests/test_library_register_contract.py`가 고정):
| 화면 필드 | 서버 |
|---|---|
| 종류 model/garment/prop/bg/pose(/3d/render) | `kind` |
| 이름(30자 이하) | `name`(서버 상한 120) |
| 세부 종류(shape)·종류(type)·대표색(`#rrggbb`)·계절 등 선택 항목·품번(SKU)·컬렉션 | `attrs` = `{shape, type, color, season, …, sku, collection}`(키는 소문자·숫자·밑줄, 값은 60자 이하 글자 또는 0~9999 정수; 어기면 422 `ATTR_*`) |
| 사용 권리 확인(업로드 체크박스) | 업로드 시 `rights_confirmed`(+`depicts_person`·`likeness_consent`) → `asset_provenance`(L-04와 동일, 서버 설정 `ASSET_REQUIRE_RIGHTS_CONFIRMATION` 켜면 없을 때 거부) |
| 출처 origin(ai/upload/work) | **서버가 자산 출처 기록으로 정함**(화면이 보내는 값은 쓰지 않음) |
| 저장·목록·삭제 | `POST …/library`(업로드) · `GET …/library?kind=&attr=키:값` · `PATCH`(`attrs` 통째 교체) · `DELETE`(편집자 이상, 열람자는 읽기만) · `GET …/library/facets` |
- 범위는 **작업공간**(다른 작업공간은 404, 시험으로 확인). 화면의 `L.scope`(전체/기본 제공/우리 자료)는 지금 브라우저 저장값이며 서버 연결 시 `origin`·`/v1/library`(공용)로 나뉜다 — 화면 쪽 연결은 미실행.
- 한계: 대표색 "자동" 추출·썸네일은 화면이 하고 서버는 값만 저장한다.

## 17. AI 편집 이력 `GET /v1/assets/{asset_id}/edits` (답신 69 C.7)
자산마다 **편집 목록** `edits:[{op, by:'user'|'ai', provider?, at}]`과 거기서 **자동 판정한 AI 표시**를 돌려준다(`app/edit_provenance.py`). 열람자 이상, 다른 작업공간 403/404, 보류 자산 404. **새로 저장하지 않는다** — 출처 기록(`asset_provenance`)에서 만든다: AI 공급자 작업 결과 가져오기(`asset.generated_output_imported`) → `generate`(AI가 만듦) 또는 `ai_edit`(고객 사진을 AI가 고침), 로컬 사진 단계(`asset.photo_steps`) → 단계마다 `by:'user'`, 명시 기록(`asset.edit`, `record_edit()`: 앞으로의 AI 보정 단계용). 원본 자산(`source_asset_id`)의 이력을 앞에 이어 붙인다(깊이 10).
- `decision`: `is_ai_generated`(AI가 만듦) · `ai_assisted`(고객 원본을 AI 단계가 바꿈) · `ai_steps` · `mark_kind`(`generated`|`edited`|null, 사진 표시 `ai_marking`과 같은 값) · `digital_source_type`(IPTC) · `basis` · **`status:"temporary_pending_legal_review"`**. 규칙: AI의 `generate` 있음 → 생성; 그 밖의 AI 단계가 하나라도 있음 → 보조; AI 단계 없음(자르기·크기·색·고전 배경 제거 등 사용자·로컬 편집, 또는 편집 없음) → 표시 없음. 이후의 로컬 자르기는 판정을 바꾸지 않는다.
- **판정 기준은 임시**: "보조"가 어디서 시작하는지(AI 단계 하나라도? 눈에 보이는 것만?)와 문구는 법무 질문 Q11-5·Q11-6 대기 → 지금은 **가장 엄격한 해석**(AI 단계 하나라도 보조). 응답의 `rule`에 그대로 적힘.
- 한계: ① 지금 서버에 있는 AI 단계는 공급자 작업 결과뿐이라 `ai_retouch` 등 개별 AI 단계는 아직 **기록하는 곳이 없다**(`record_edit`만 준비됨, 호출처 미연결). ② 그림 내려받기 표시(`ai_marking`)와 3D 내보내기의 `ai_disclosure`는 아직 이 판정이 아니라 기존 규칙을 쓴다(연결은 법무 답 이후, 미실행). ③ 작업 결과 파일에서의 `edits` 노출은 이 경로뿐이다.

## 18. 팀 작업 보드 `…/jobs` · `…/team/summary` (R-TEAM-01)
상세·권한 표·상태 전이 표는 `docs/TEAM_JOBS.md`. 요약: `POST/GET /v1/workspaces/{id}/jobs`, `GET …/jobs/{job}`(이력·의견 포함), `POST …/jobs/{job}/transition {to,note}`, `POST …/jobs/{job}/comments {body}`, `POST …/jobs:bulk-transition {ids,to,note}`(항목별 결과), `GET …/team/summary?period=`. 상태 `draft|review|changes|approved|rejected`, 작업실 `photo|tryon|character|3d|video`. 오류 `JOB_TRANSITION_INVALID`(409)·`JOB_NOTE_REQUIRED`(422)·`JOB_DATE_INVALID`·`JOB_TITLE_REQUIRED`·`JOB_COMMENT_REQUIRED`·`JOB_BULK_DUPLICATE`. 한계: `credits_used`는 null(원장에 사용자 없음), 기존 작업실이 이 레코드를 자동으로 만들지는 않는다.

## 19. Photo PSD 주고받기 (R-PSD-01)
`POST /v1/workspaces/{id}/photo-psd`(레이어 PSD 내려받기, 원본 해상도, 8·16비트, ICC) · `POST …/photo-psd/import`(고친 PSD 올리기 → 새 원본 자산 + 출처 기록 `asset.psd_import`). 레이어 구성·오류 코드(`PSD_*`)·한계는 `docs/PSD_ROUNDTRIP.md`. **포토샵·Photopea 등 실제 프로그램에서 열어 본 시험은 미실행.**

## 20. 3D 작업실 실연결 `AIS_API.studio3d.*` (D-1, 답신 73) — `site/assets/ais_api_live.js`
화면 HTML은 고치지 않고 이 파일 한 곳이 서버를 부른다. **서버 꺼짐·설정 없음·플래그(`RENDER3D_ENABLED`) 닫힘·로그인/권한 없음 → 조용히 `null`**(호출한 쪽이 지금의 로컬 동작을 그대로 쓴다). 서버가 거절한 것(잘못된 값)만 `{code,message}`로 던진다. 설정은 부트스트랩이 `AIS_LIVE.configure({base, token(문자열 또는 함수), workspaceId})`로 넣는다(파일에 키·주소 없음).
| 함수 | 서버 | 반환 |
|---|---|---|
| `poses()` | `GET …/render3d-jobs/poses` | `[{id,label_ko,label_en}]`(standing·walking·hand_on_hip·sitting·arms_raised) |
| `render({modelId\|sex, garments:[kind], pose, angles, measurements?, bg?, renderer?='photo'})` | `POST …/render3d-jobs`(요청에 **`pose`·`renderer:'soft'\|'photo'` 추가**) → 폴링 → `GET /v1/assets/{id}/preview` | `{job_id, images:[{angle,asset_id,url,blob}], qc, ms}` (`url`은 blob 주소) |
| `fitCheck({sex,kind,measurements?,nominal?})` | `POST …/fit-check` (§15) | 응답 그대로 |
| `export({assetId, versionId?, format:'glb'})` | `GET /v1/assets/{id}/versions/{v}/export` (§14) | `{blob,url,sha256,filename,bytes}` |
| `saveToLibrary(images,{name?})` | `POST …/library/attach` (kind `render`) | 라이브러리 항목 배열 |
| `toVideo({itemIds, aspect?, duration?, motion?})` | `POST …/video-jobs` → 폴링 | 영상 작업 |
- `modelId`→성별: `mf*·cw*·f*`는 여성, 그 밖은 남성(화면이 `sex`를 직접 주면 그것). 옷 id는 아직 내장 샘플 종류(top·bottom·skirt·dress·jacket)만.
- 서버 변경: 렌더 작업 요청에 `pose`(기본 standing)·`renderer`(기본 soft) 추가, `GET …/render3d-jobs/poses`. 사진 렌더는 느리다(아래).
- **시간(이 개발 PC, 컷 5각도·옷 2벌·360×640)**: 사진 렌더 15.6초 + 자세 적용 0.28초, 모의 렌더 2.4초. **8 GB급 PC 시간은 미측정.** 사진 렌더는 작업(job)이라 화면은 폴링한다.
- 알려진 한계: 걷기 자세에서 허벅지 안쪽 살갗이 바지 밖으로 비침(`docs/POSES.md`), 옷은 내장 샘플만, 3D 미리보기(three.js)는 그대로(자세는 서버 컷에만 반영).

## 21. 사진 → 몸 치수 추정 `POST /v1/workspaces/{id}/photo-body` (D-2)
`{asset_id, sex: male|female, height_cm?(120~220)}` → `{estimated:true, label, measurements:{height_cm,chest_cm,waist_cm,hips_cm}, silhouette_px, warnings[], chest_from_prior, assumptions[]}`. 편집자 이상, own3d 플래그 뒤(닫힘 409 `RENDER3D_CLOSED`), 저장 없음. 오류 `PHOTO_BODY_NOT_FOUND|CLIPPED|POSE|UNREADABLE|SEX|HEIGHT`(422). 화면 함수 `AIS_API.studio3d.bodyFromPhoto`(§20). **합성 사진에서만 시험, 실제 사람 사진은 미실행**; 방법·한계는 `docs/PHOTO_BODY.md`.
