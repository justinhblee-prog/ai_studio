# 운영자 읽기 계약표 (`AIS_API.ops.*`) — R-066

범위: 운영 화면이 **읽기만** 하는 경로. 쓰기(정지·설정·공지 등)는 R-052 결정 대기라 서버에 **없음**.
공통
- 인증: `Authorization: Bearer <Supabase 토큰>`. 운영자 판정은 **지금은 한 단계**(환경 변수 `OPS_ADMIN_USER_IDS`에 든 계정). 아니면 **403** `Platform operations role required`, 토큰 없으면 **401**.
- **역할 열은 R-052의 5역할(총괄 lead · 콘텐츠 content · 고객지원 support · 법무 legal · 정산 billing)과 R-057이 제안한 마케팅(mkt)에 대한 *제안***입니다. **서버에는 아직 역할 표가 없어 지금은 운영자 전원이 모두 읽습니다**(제안과 구현의 차이).
- 시각은 UTC ISO 8601. 값이 없는 필드는 **키를 생략하지 않고 `null`**, 목록은 `[]`, 합계는 `0`.
- 사람 이름·이메일은 어디에도 없음(ID만 — 인증 제공자 서버 키 미확보, NEED_USER).
- "측정/추정/미측정": ●측정 ◐추정 ○미측정.

## 한눈에 보기
| 화면 항목 | 경로 | 상태 | 제안 읽기 권한 |
|---|---|---|---|
| 전체 현황(회사·공급자·지연·한도) | `GET /internal/ops/overview` | **있음**(R-043) | 전원 |
| 사용량 집계(기간·회사/사용자/서비스/공급자/화풍/지역) | `GET /internal/ops/usage` | **있음**(R-054, R-059) | 전원, 비용 열은 billing·lead |
| 기간별 작업·비용 롤업 | `GET /internal/ops/rollup` | **있음**(R-043 C) | 전원 |
| 큐 지표(지연·적체) | `overview.latency_seconds`, `GET /internal/ops/workers`, `GET /internal/ops/poll-tasks`, `GET /internal/ops/metrics` | **있음**(R-043 B, 기존) | 전원 |
| 한도 알림 이력 | `GET /internal/ops/alerts?status=active\|resolved` | **있음**(기존) | 전원 |
| 실패 작업 | `GET /internal/ops/failed-jobs` | **있음** | support·lead |
| 내려받기 감사 | `GET /internal/ops/downloads` | **있음** | legal·support·lead |
| 삭제 요청 대기열 | `GET /internal/ops/deletion-requests` | **있음** | legal·lead |
| 신고 대기열(읽기) | `GET /internal/moderation/reports` | **있음**(기존) | legal·support·lead |
| **감사 로그 조회(필터·페이지)** | **`GET /internal/ops/audit`** | **이번에 구현**(R-066) | lead·legal |
| 고객·계약·유입(마케팅) | `GET /internal/ops/customers`, `…/companies`, `…/retention`, `…/customers/{id}/contract`, `…/history`, `GET /internal/ops/marketing` 없음 → `customers`가 대체 | **있음**(R-057) | lead·mkt·support(계약은 billing) |
| 서비스 상태 | `GET /health`(공개), `GET /internal/ops/health`, `GET /internal/ops/runtime-readiness`, `GET /internal/ops/provider-registry` | **있음** | 전원 |
| 서비스 상태: **마지막 백업 시각** | — | **미구현** | — |
| 작업자 하트비트 | `GET /internal/ops/workers` | **있음** | 전원 |
| 계정·회사 정지 상태, 설정값, 사이트 콘텐츠, 운영자 역할 | — | **미구현**(R-052 결정 대기) | — |

## 1. `GET /internal/ops/overview?month=YYYY-MM`
응답: `{month, jobs, failed, failure_rate, active_companies, estimated_cost_usd, latency_seconds:{count,avg,p50,p95}, controls:{kill_switch_on, global_monthly_limit, workspace_monthly_limit, stop_percent, usd_limit_month_configured}, providers:[{provider,jobs,failed,estimated_cost_usd}], companies:[{workspace_id,members,jobs,failed,estimated_cost_usd}]}`
- 빈 값: 작업이 없으면 `jobs=0, failed=0, failure_rate=0, providers=[]`, `latency_seconds` = `{count:0, avg:null, p50:null, p95:null}`. `month` 생략 시 이번 달.
- ● 작업 수·실패·회사·구성원 수 ◐ `estimated_cost_usd`(공급자 단가×횟수, 청구서와 대조 안 함) ○ 실제 청구액.

## 2. `GET /internal/ops/usage?group_by=hour|day|month&by=company|user|service|provider|style|region&from=&to=`
응답: `{granularity, by, from, to, rows:[{bucket,key,events,success,failed,pending,blocked,estimated_cost_usd,duration_ms_total,duration_ms_count,bytes}], totals, storage_bytes_now, limits, coverage, not_measured:[…], truncated_services:[…]}`
- 빈 값: `rows=[]`, `totals` 모두 0. 버킷 상한 초과·`from>=to`는 422.
- **`coverage`가 서비스별로 ● 측정/◐ 추정/○ 미측정을 직접 말함**(예: `tryon`: 횟수·상태·공급자 ●, `cost_usd` ◐, `duration_ms`·`bytes` ○). `blocked`는 한도로 거절된 요청이 저장되지 않아 **항상 0**. `style`/`region` 축은 가상 착용 작업에만 기록되고 나머지는 `unknown`.

## 3. `GET /internal/ops/rollup?granularity=day|month&start=&end=`
응답: `{granularity,start,end,buckets:[{bucket,jobs,failed,estimated_cost_usd}]}`. 빈 값: 작업 없는 날도 `0`으로 채움(시험 있음).

## 4. 큐 지표·작업자
- `GET /internal/ops/workers` → `{workers:[…하트비트], outbox_counts:{상태:건수}, poll_task_counts:{상태:건수}, stale_after_seconds}`. 빈 값: `workers=[]`(= 작업자가 한 번도 신호를 안 보냄, **중단과 구별 안 됨** ○).
- `GET /internal/ops/poll-tasks?workspace_id=&status=` → `{workspace_id, items:[…]}`. `GET /internal/ops/metrics` → Prometheus **텍스트**(JSON 아님).

## 5. `GET /internal/ops/alerts?status=active|resolved&limit=`
응답: `{snapshot:{…현재 지표}, items:[알림…]}`. 빈 값: `items=[]`. **이력**은 `status=resolved`로 봄(보관 기간은 정해진 값 없음 — 법무/운영 결정 필요).

## 6. 목록 3종
- `GET /internal/ops/failed-jobs?limit=` → `[{job_id,workspace_id,provider,error_code|null,created_at,updated_at}]`(프롬프트·이미지 주소 없음).
- `GET /internal/ops/downloads?limit=` → `[{download_id,workspace_id,actor_id,kind,object_id,size_bytes,created_at}]`.
- `GET /internal/ops/deletion-requests?status=&limit=` → `[{request_id,user_id,workspace_id|null,scope,status,requested_at,due_at,grace_expired}]`. 비어 있으면 `[]`. **승인·실행은 읽기 범위 밖**(R-052: 실제 삭제는 서버 스크립트).

## 7. 신고 대기열(읽기) `GET /internal/moderation/reports?status=open|upheld|rejected|all`
응답: `{items:[{report_id,asset_id,workspace_id,reporter_id,category,details,status,created_at,resolved_at,resolved_by,resolution_note}]}`. 빈 값 `items=[]`.
- ⚠ **`details`·`resolution_note`는 자유 글**이라 개인정보가 들어갈 수 있음 → 읽기 권한은 legal·lead 위주로 좁힐 것을 권고(제안). 감사 로그 조회(§8)에는 이 글을 **넣지 않음**.

## 8. **감사 로그 `GET /internal/ops/audit`** (이번에 구현)
쿼리: `workspace_id`, `actor_id`, `source`(반복 가능: `review|contract|download|report|asset`, 생략=전부), `from`, `to`(ISO 날짜·시각), `limit`(1~200, 기본 50), `offset`(offset+limit ≤ 1000, 더 깊이는 기간을 좁혀서).
응답: `{items:[{at, source, workspace_id|null, actor_id|null, action, object_type, object_id|null}], next_offset|null, sources:[…], coverage:{measured, not_measured, tamper_evidence}}` — 최신순.
- `action` 예: `review.request|approve|request-changes|reject|resubmit|withdraw`, `company.<필드>.changed`, `download.<종류>`, `report.opened|upheld|rejected`, 자산 이벤트(`asset.uploaded` 등 출처 기록의 이벤트 이름).
- **의견·메모·신고 내용·파일 이름은 절대 포함하지 않음**(시험으로 고정). 이름·이메일 없음(ID만).
- 빈 값: `items=[]`, `next_offset=null`.
- **이미 있는 기록의 "보기"일 뿐 새 기록이 아님**: 운영자 쓰기(정지·설정·공지·역할)는 **아직 없으므로 기록도 없음**, 운영자의 **읽기 행위**와 작업 이벤트(`generation_job_events`)는 **포함 안 함**(○). 변조 방지: 검수·계약 이력은 DB가 수정·삭제를 거부, 나머지는 일반 표(해시 체인 없음 — R-052 `ops_audit` 설계가 들어오면 대체).

## 9. 서비스 상태
- `GET /health`(공개): 생존 여부만. `GET /internal/ops/health`(운영자): `{status: ok|degraded|fail, checked_at, checks:{…}}`, `status=fail`이면 **HTTP 503**. `GET /internal/ops/runtime-readiness`: 출시 준비 점검 목록. `GET /internal/ops/provider-registry`: 공급자 등록표·라우팅 방식(**키 값은 없음**, 설정 여부만).
- **마지막 백업 시각**: 서버에 기록이 없음 → **미구현**(백업 도구가 매니페스트를 남기는 곳이 `deep_health`의 백업 확인에 일부 쓰임 — 화면용 필드로 정리 안 됨).

## 10. 고객·마케팅(R-057) 요약
`GET /internal/ops/customers?from=&to=&group_by=month|year&by=channel|industry|size|plan` → `{group_by,by,from,to,rows:[{bucket,key,signups,churned,active_end,trials,converted}],totals,coverage,collection_enabled,notes}`; 회사 한 줄 목록 `…/customers/companies`; 코호트 `…/customers/retention`; 계약 `GET|PUT …/customers/{작업공간}/contract`, 이력 `…/history`. 빈 값: `rows=[]`. 수집이 꺼져 있으면 `channel` 축은 전부 `unknown`(`collection_enabled=false`).

## 11. 미구현·결정 대기 항목
계정·회사 정지, 설정값(킬 스위치·월 한도), 사이트 콘텐츠·점검 모드, 운영자 역할 표와 2단계 인증, 운영자 쓰기 감사(`ops_audit` 해시 체인), 마지막 백업 시각. 모두 R-052의 결정 9건에 묶여 있음.

## 응답 예시 (시험이 OpenAPI와 대조함)
### `GET /internal/ops/audit`
<!-- contract: listOpsAudit 200 -->
```json
{"items": [{"at": "2026-11-16T09:30:00+00:00", "source": "review", "workspace_id": "ws-demo", "actor_id": "user-e", "action": "review.approve", "object_type": "review", "object_id": "rev_0a1b2c3d4e5f60718293a4b5c6d7e8f9"}],
 "next_offset": null, "sources": ["review", "contract", "download", "report", "asset"],
 "coverage": {"measured": {"review": "asset_review_events (append-only)"}, "not_measured": ["operator reads are not recorded"], "tamper_evidence": "review and contract history refuse UPDATE/DELETE"}}
```
