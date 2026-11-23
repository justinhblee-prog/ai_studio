# 팀 작업 보드 서버 (R-TEAM-01) — `app/team_jobs.py`

홈페이지 작업실 홈 "팀 작업 보드"(`#tb`)가 읽고 쓰는 **작업(job) 레코드·상태 이력·의견·팀 조회·주간 요약**. 화면 필드 대응: `t→title, w→workroom, u→owner(owner_user_id), st→status, due→due_at, cm→comments`. 계약 요약은 `AIS_API_CONTRACT.md` §18.

## API
| 호출 | 설명 |
|---|---|
| `POST /v1/workspaces/{id}/jobs` `{workroom: photo\|tryon\|character\|3d\|video, title, thumb_asset_id?, due_at?}` | 편집자 이상, 본인 소유, 처음 상태 `draft` |
| `GET …/jobs?owner=&workroom=&status=&since=&q=&limit=&offset=` | 목록 `{items,total}` |
| `GET …/jobs/{job}` | 작업 + 상태 이력 `events` + 의견 `comments` |
| `POST …/jobs/{job}/transition` `{to, note?}` | 상태 전이 |
| `POST …/jobs/{job}/comments` `{body}` | 의견 |
| `POST …/jobs:bulk-transition` `{ids(≤50), to, note?}` | 항목별 결과 `{results:[{id,ok,status,error_code}], succeeded, failed}`, 일부 실패 허용 |
| `GET …/team/summary?period=day\|week\|month` | 구성원별 `{jobs, approved, credits_used}` + 상태별 개수 + 24시간 내 마감 수 |

## 권한 표 (reviews·members와 같은 역할: owner / admin / editor / viewer, "승인자"=owner 또는 admin)
| | owner·admin | editor | viewer |
|---|---|---|---|
| 목록·상세 | **전체** | **본인 것만** (남의 상세는 404) | 전체 읽기 |
| 만들기 | ○ | ○ | 403 |
| 보내기(draft/changes→review) | ○ | 본인 작업만 | 403 |
| 결정(approved/changes/rejected) | ○ | 403 | 403 |
| 의견 | 모든 작업 | 본인 작업만 | 403 |
| 팀 요약 | ○ | 403 | ○ |
다른 작업공간은 404. **열람자는 전체 읽기**로 정했다(요청문에 "열람자는 조회만"이라고만 있어 해석함 → 설계 창 확인 요청).

## 상태 전이 표(시험으로 고정)
`draft→review` · `review→approved|changes|rejected` · `changes→review`. approved·rejected는 최종. 그 밖은 409 `JOB_TRANSITION_INVALID`. `changes`·`rejected`는 사유(`note`) 필수(422 `JOB_NOTE_REQUIRED`).
이력(`job_events`)과 의견은 **추가만** 가능(DB가 UPDATE·DELETE 거부). 동시에 바뀌면 409.

## 한계 (정직하게)
- **`credits_used`는 항상 null**: 크레딧 원장(`app/credits`)이 조직 계정 단위이고 사용자가 없어 구성원별 집계가 없다(미연결). 응답에 `credits_note`로 명시.
- 작업은 **직접 만들거나 API로 올려야** 생긴다: 기존 작업실(사진·착장·3D·영상)의 실제 작업이 이 레코드로 **자동 기록되지는 않는다**(각 작업실 연결은 미실행).
- 이 단계는 SQLite(자산 DB) 기준이다. PostgreSQL 전환(`DATABASE_BACKEND`)은 건드리지 않았다.
- 마감 임박은 `due_at`이 지금부터 24시간 안이고 draft/review/changes인 작업 수. 알림·메일은 없다.
