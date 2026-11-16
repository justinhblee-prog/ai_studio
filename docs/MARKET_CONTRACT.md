# 마켓 연결 계약표 (`AIS_API.market.*`) — R-064

범위: **결제 없는 부분**만. 구매·정산·환불·수수료·통화는 **결정 대기라 서버에 없음**(`price`는 0 이상의 정수 자리일 뿐, 통화 필드 없음 — 홈페이지는 지금 "KRW"로 표시하지만 서버는 단위를 모름).
인증: 모두 `Authorization: Bearer <토큰>`(로그인한 사용자). 시장은 **작업공간이 아니라 사용자 범위**(판매자는 자기 작업공간 이름으로 올림).
오류: `{"detail": {"code": "...", "message": "..."}}`. 아래 코드 표 참고.

## 홈페이지 항목 ↔ 서버 항목
| 홈페이지(`ais_market_local`) | 서버 | 비고 |
|---|---|---|
| `id` | `listing_id` (`mkt_…`) | |
| `title` | `title` (≤80자) | |
| `ty` (`preset`·`template`…) | `kind` (소문자·숫자·하이픈 ≤20자) | **허용 목록 없음**(형식만) |
| `desc` | `description` (≤1000자) | |
| `price` (정수, KRW로 표시) | `price` (정수 0~10,000,000, 0=무료) | 통화 필드 없음 |
| `preset` (Photo 프리셋 설정 객체) | `payload` (객체, ≤20,000바이트) | **서버의 사진 프리셋(`photo-presets`)은 `steps` 목록이라 형식이 다름** → 서버는 `payload`를 **해석하지 않고 그대로 보관**, 가져오기는 홈페이지가 `payload`를 읽어 자기 쪽에 저장 |
| 게시 권리 확인 체크(`rt`) | `rights_confirmed: true`(등록 시 필수) + `publish` 때 `rights_confirmed: true` 다시 | 확인한 사람·시각 기록 |
| (없음) | `license_scope` **필수**(짧은 글, ≤40자) | **법적 문구를 채우지 않음** — 판매자가 직접 적는 값 |
| (없음) | `is_ai_generated` **필수**(true/false 명시) | |
| (없음) | `tags`(≤8개, 각 ≤24자, 소문자로 통일), `cover_asset_id`(같은 작업공간의 이미지 자산) | |

## 메서드
| `AIS_API.market.` | 서버 | 권한 | 응답·메모 |
|---|---|---|---|
| `list(query)` | `GET /v1/market/listings?q=&kind=&tag=&free=&seller=&sort=new\|price_asc\|price_desc&limit=&offset=` | 로그인 사용자 | `{items, total}`. **공개된 항목만**, **`payload` 없음**. `limit` 1~100(기본 24). 검색어의 `%`·`_`는 글자 그대로 |
| `publish(item)` | ① `POST /v1/market/listings` → ② `POST /v1/market/listings/{id}/publish` | 판매자 작업공간의 소유자·관리자·편집자 | **2단계**: 등록(비공개로 시작) → 공개 때 권리 확인 재확인. 홈페이지 `publish`는 두 호출을 이어 주면 됨 |
| `get(id)` | `GET /v1/market/listings/{id}` | 공개 항목은 로그인 사용자, 비공개는 판매자만 | **`payload`는 무료 공개 항목이거나 판매자일 때만** (유료 항목의 `payload`는 구매가 없으므로 판매자에게만) |
| `update(id, patch)` | `PATCH /v1/market/listings/{id}` | 작업공간 소유자·관리자, 또는 **만든 편집자 본인** | 필드 일부만. 버전 검사(동시 수정 시 409 `MARKET_CHANGED`). `clear_payload`, `clear_cover` 플래그 |
| `unpublish(id)` | `POST /v1/market/listings/{id}/unpublish` | 위와 같음 | 비공개로 |
| `remove(id)` | `DELETE /v1/market/listings/{id}` | 위와 같음 | **기록은 지우지 않고** 목록에서 뺌(신고 처리를 위해) |
| `mine()` | `GET /v1/market/mine?visibility=` | 본인 | 내가 만든 항목(비공개 포함), `payload` 포함 |
| `report(id, {reason, details})` | `POST /v1/market/listings/{id}/reports` | 로그인 사용자 | **항상 `202 {"status":"received"}`**(없는 항목·내 항목·중복도 같은 답). `reason`: `copyright\|likeness\|inappropriate\|fraud\|other`, 하루 한도 `MARKET_REPORT_DAILY_LIMIT`(기본 10) 초과 시 429 |
| `profile()` / `saveProfile({display_name, bio})` | `GET`·`PUT /v1/market/profile` | 본인 | 표시 이름 ≤40자, 소개 ≤300자, **링크·이메일·태그 문자 금지** |
| `seller(handle)` | `GET /v1/market/sellers/{handle}` | 로그인 사용자 | `{handle, display_name, bio, listing_count, member_since}`. 프로필이 없으면 404 |
| (운영자) 신고 읽기 | `GET /internal/market/reports?status=open\|all` | 운영자 | 처리(숨기기)는 **운영자 쓰기라 미구현**(R-052) |

**판매자 표시**: 계정 ID 대신 **불투명 핸들**(`sel_` + 일방향 해시 16자) — 다른 회사가 계정 ID나 작업공간 ID를 알 수 없음. `workspace_id`는 판매자 본인에게만 응답에 나옴.

## 오류 코드
`MARKET_RIGHTS_REQUIRED`(권리 확인 안 함) · `MARKET_AI_FLAG_REQUIRED` · `MARKET_LICENSE_REQUIRED` · `MARKET_PRICE_INVALID` · `MARKET_TEXT_REQUIRED` · `MARKET_TEXT_TOO_LONG` · `MARKET_KIND_INVALID` · `MARKET_TAG_INVALID` · `MARKET_PAYLOAD_INVALID` · `MARKET_PAYLOAD_TOO_LARGE` · `MARKET_COVER_INVALID` · `MARKET_NOTHING_TO_CHANGE` · `MARKET_CHANGED`(409) · `MARKET_PROFILE_INVALID` — 모두 422(표시한 것 제외). 권한 없음 403, 비공개 항목을 모르는 사람 404, 공개 항목을 남이 고치려 하면 403.

## 아직 없는 것(결정 대기)
구매·결제·정산·환불·수수료·통화, 유료 항목의 `payload` 전달, 운영자의 항목 숨기기/복원(R-052), 신고 처리 기한·알림 문구(법무), 이용 허락 범위의 **표준 선택지**(현재는 판매자가 적는 짧은 글 — 법적 문구는 법무 빈칸이라 채우지 않음), 평점·후기, 구매자 라이브러리로 가져오기.

## 응답 예시 (시험이 OpenAPI와 대조함)
### `GET /v1/market/listings/{id}` (등록·수정·공개 응답도 같은 모양)
<!-- contract: getMarketListing 200 -->
```json
{"listing_id": "mkt_7c1e0a9b2d4f4e6c8a1b3d5f7e9c0a12", "kind": "preset", "title": "봄 프리셋", "description": "밝고 깨끗한", "tags": ["spring", "clean"], "price": 0, "free": true,
 "cover_asset_id": null, "license_scope": "personal use", "is_ai_generated": false, "visibility": "public", "status": "active",
 "seller": {"handle": "sel_3f9a1c5e7b2d4a60", "display_name": "하늘 스튜디오"}, "created_at": "2026-11-16T09:00:00+00:00", "updated_at": "2026-11-16T09:10:00+00:00",
 "published_at": "2026-11-16T09:10:00+00:00", "version": 2, "payload": {"br": 10, "shadow": true}, "mine": false, "workspace_id": null}
```
### `GET /v1/market/listings` (검색 — `payload`는 항상 `null`)
<!-- contract: searchMarketListings 200 -->
```json
{"items": [{"listing_id": "mkt_7c1e0a9b2d4f4e6c8a1b3d5f7e9c0a12", "kind": "preset", "title": "봄 프리셋", "description": "", "tags": [], "price": 5000, "free": false,
            "cover_asset_id": null, "license_scope": "commercial", "is_ai_generated": true, "visibility": "public", "status": "active",
            "seller": {"handle": "sel_3f9a1c5e7b2d4a60", "display_name": null}, "created_at": "2026-11-16T09:00:00+00:00", "updated_at": "2026-11-16T09:00:00+00:00",
            "published_at": "2026-11-16T09:10:00+00:00", "version": 2, "payload": null, "mine": false, "workspace_id": null}],
 "total": 1}
```
