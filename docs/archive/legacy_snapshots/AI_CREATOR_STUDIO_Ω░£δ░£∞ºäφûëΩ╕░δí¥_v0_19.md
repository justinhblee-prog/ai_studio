# AI CREATOR STUDIO 개발 진행 기록 v0.19

## 개발 목표
v0.18의 제출 Worker와 Provider Poll Worker 운영 상태를 계측하고, Worker 중단·대기열 지연·수동 복구 적체를 운영자가 확인할 수 있게 한다.

## 구현
- DB migration v5: `generation_ops_alerts`, `generation_ops_alert_deliveries`
- `app/monitor_worker.py`: 독립 운영 모니터, alert evaluation, 선택적 HTTPS webhook dispatch
- `app/job_repository.py`: operational snapshot, alert deduplication/resolution, webhook delivery retry, Prometheus metrics
- `app/main.py`: `/internal/ops/metrics`, `/internal/ops/alerts`; 글로벌 ops endpoints에 `OPS_ADMIN_USER_IDS` 적용
- `app/worker.py`: heartbeat에 `worker_type=outbox` 기록
- `.env.example`, README 및 운영 문서 갱신

## 검증
- pytest 99 passed
- compileall passed
- OpenAPI 22 paths
- API version 0.7.0
- Viewer structural validation 19/19

## 보안/운영 결정
- Workspace owner/admin은 전역 운영 지표 접근 권한을 자동으로 얻지 않는다. `OPS_ADMIN_USER_IDS`에 명시된 계정만 전역 ops endpoint 접근 가능.
- Webhook은 HTTPS만 허용하고 URL 내 사용자명/비밀번호를 거부한다.
- Webhook delivery는 at-least-once이므로 수신 측은 alert_id로 중복 제거해야 한다.
- Webhook 미설정 시 알림은 DB에 저장되며 외부 전송은 하지 않는다.

## 미완료
PostgreSQL, 멀티 인스턴스 잠금, 운영 Webhook/Prometheus 배포, 실제 FASHN 계약 검증, Credit Ledger, UI/E2E 검증은 후속 작업.
