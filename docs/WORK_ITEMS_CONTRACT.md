# 작업 항목(내 작업) 연결 계약표 — `AIS_API.work.*` ↔ 서버 `work-items` (R-069)

서버: `/v1/workspaces/{작업공간 ID}/work-items`. 홈페이지의 `company` = 작업공간 ID. 권한은 라이브러리와 같음(읽기: 보기 이상, 쓰기: 편집자 이상, 관리자·소유자 포함). 오류: `{"detail":{"code","message"}}`.

## 1. 홈페이지 항목 ↔ 서버 항목
| 홈페이지(`ais_work`) | 서버 | 비고 |
|---|---|---|
| `id` (`w…`) | `item_id` (`wk_…`) | 홈페이지가 만든 로컬 ID는 서버가 새로 부여하므로 **어댑터가 대응을 기억**해야 함 |
| `service` | `kind` | 소문자·숫자·하이픈 ≤20자(허용 목록 없음) |
| `title` | `title` | 1~120자 |
| `status` (`draft/req/ok/chg/rej/done`) | `status` | **홈페이지 값 그대로 받음**(소문자 단어, 첫 글자 문자, ≤16자). **서버는 상태 기계를 두지 않음** — 아무 전이나 허용 |
| `data` (그림 dataURL 등 큰 값) | **받지 않음** | 자유 `data` 필드는 422. **그림은 자산(`POST /v1/assets/images`)으로 올리고 `asset_ids`로 연결**, 가벼운 설정값은 `attrs`(글자 ≤60자 또는 0~9999 정수 — R-058 규칙, 20개까지) |
| `company`, `by`, `created`, `updated` | `workspace_id`, `created_by`(계정 ID), `created_at`, `updated_at` | 이름·이메일은 서버가 모름 |
| (없음) | `asset_ids`(≤20), `assets[]`, `asset_review_summary`, `archived_at`, `version` | 아래 §3 |

## 2. 메서드
| `AIS_API.work.` | 서버 | 메모 |
|---|---|---|
| `upsert(item)` | 없으면 `POST …/work-items`, 있으면 `PATCH …/work-items/{id}` | `PATCH`는 일부 필드만, `attrs`·`asset_ids`는 **통째로 교체**(`{}`/`[]`로 비움), `expected_version`을 보내면 동시 수정 시 409 `WORK_ITEM_CHANGED` |
| `list()` | `GET …/work-items?kind=&status=&q=&asset_id=&archived=&limit=&offset=` | **최근 변경 순**. 기본은 보관되지 않은 것만, `archived=true`면 보관된 것만. `q`는 제목 검색(`%`·`_`는 글자 그대로) |
| `get(id)` | `GET …/work-items/{id}` | 보관된 항목도 id로는 읽힘 |
| `remove(id)` | `DELETE …/work-items/{id}` | **지우지 않고 보관(archive)** — 목록에서 빠짐, 되돌리기 `POST …/{id}/restore`. 같은 항목을 두 번 보관해도 204 |
| (새) 이력 | `GET …/work-items/{id}/events` | 만듦·수정·**상태 변경**·보관·복원, 행위자·시각, 추가 전용(DB가 수정·삭제 거부) |
| `newId()` | — | 서버가 ID를 만들므로 불필요 |

## 3. 상태 이름 대응표 (작업 항목 상태 ↔ 자산 검수 상태)
작업 항목에는 **상태가 두 가지 층**이 있습니다. 섞지 않도록 응답이 따로 줍니다.
1. **항목 자체 상태** `status` — 화면 표시용 **라벨**(홈페이지 `draft/req/ok/chg/rej/done` 그대로). **어떤 권한도 주지 않음**: 편집자가 `ok`로 바꿔도 내보내기가 열리지 않습니다. 승인·내보내기는 **검수 기록(자산 단위, 소유자·관리자만 승인)** 이 결정합니다.
2. **연결된 자산의 검수 상태** — 항목이 자산을 가리키면 응답의 `assets[]`에 자산별 최신 검수 상태가 함께 옵니다.

| 서버 검수 상태(`review_status`) | 화면 상태(`screen_status`) | 뜻 |
|---|---|---|
| `none`(검수 기록 없음) | `draft` | |
| `requested` | `req` | 검수 요청됨 |
| `approved` | `ok` | 승인됨 (`exportable: true`) |
| `changes_requested` | `chg` | 변경 요청됨 |
| `rejected` | `rej` | 반려됨 |
| `withdrawn` | `draft` | 요청이 철회됨 — **홈페이지에 대응 이름이 없어 작성 중으로 표시** |
| (대응 없음) | `done` | **`done`은 항목 자체 상태 전용** — 검수 상태에서는 나오지 않음 |

**`asset_review_summary`**(항목 전체를 한 줄로): 살아 있는 연결 자산 중 **반려가 하나라도 있으면 `rej`**, 아니면 **변경 요청이 있으면 `chg`**, 아니면 **요청 중이 있으면 `req`**, 아니면 **전부 승인이면 `ok`**, 그 밖에(검수 기록 없는 자산이 섞임 등) **`draft`**. 연결 자산이 없거나 모두 삭제됐으면 `null`.
**자산이 없는 항목**(초안 글 등)은 **항목 자체 상태와 이력**(§2의 events)만으로 다룹니다 — 검수 API는 자산에만 걸립니다.
삭제된 자산은 `assets[].state="gone"`으로 보이고(ID는 유지) 요약에서는 제외됩니다.

## 4. 한도·기록
작업공간당 최대 **2,000개**(`WORK_ITEMS_MAX`, **보관된 것도 센다** → 409 `WORK_ITEMS_FULL`). 연결 자산 ≤20, 모두 **같은 작업공간의 살아 있는 자산**이어야 함(422 `WORK_ASSET_INVALID`). 이력은 삭제 스크립트만 지울 수 있고(작업공간 삭제 때), 내보내기 ZIP에 `data/work_items.json`·`data/work_item_events.json`으로 포함됩니다.

## 5. 기존 개체와의 관계
사진 초안·룩북 초안·프로젝트·상품·작업(generation-jobs) 개체는 **그대로 두고 병행**합니다(연결 필드 없음). 홈페이지가 이들을 작업 항목과 이어 보여 주려면 `attrs`에 해당 개체 ID를 문자로 넣어 두는 방식이 지금 가능한 전부입니다(서버가 그 ID의 존재를 검사하지 않음).
