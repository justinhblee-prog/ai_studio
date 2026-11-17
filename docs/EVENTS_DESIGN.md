# 이벤트·웹훅 설계 초안 (B-18, 초안 — 아무것도 연결되지 않음)

코드: `ai_creator_studio_backend_starter/app/events.py`, 시험: `tests/test_events.py`. 발송·구독 저장·비밀 관리는 **아직 없음**(결정 필요).

## 이벤트 종류(v1)
| type | data(식별자·상태만) |
|---|---|
| job.completed / job.canceled | job_id, status |
| job.failed | job_id, status, error_code |
| review.requested / approved / changes_requested / rejected / withdrawn | review_id, asset_id, status |

## 봉투
`id`(evt_+32hex), `type`, `version`(1), `occurred_at`(UTC Z), `workspace_id`, `data`. 이름·이메일·지시문·검수 코멘트·서명 URL·파일 내용은 넣지 않음(받는 쪽이 자기 로그인으로 조회).

## 서명
헤더 `t=<초>,v1=<HMAC-SHA256("<t>.<본문>")>`, 허용 오차 300초(과거·미래 모두). 본문은 키 정렬·공백 없는 JSON.

## 전달 의미(다음 단계 제안)
최소 1회 전달 → 받는 쪽이 `id`로 중복 제거. 순서 보장 없음(`occurred_at` 참고). 실패 시 재시도 간격·횟수, 구독 URL 등록·검증(https만, 사설망 차단), 서명 비밀 회전은 **설계 결정 후** 구현.

## 열린 결정(NEED_USER 성격 아님, 설계 창 답 필요)
1. 홈페이지가 웹훅을 받을 수 있는지, 아니면 폴링(`GET /v1/events?after=`)이 먼저인지
2. 이벤트 종류 추가 요청(자산 삭제·takedown 등은 법무 문구와 얽혀 보류)
