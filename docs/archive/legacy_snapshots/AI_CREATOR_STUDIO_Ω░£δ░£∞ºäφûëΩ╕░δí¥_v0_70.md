# AI CREATOR STUDIO v0.70 개발 진행 기록

- Credit Ledger Transaction Specification v0.1을 기준으로 DB-neutral 도메인 검증 모델을 추가했습니다.
- Ledger Event는 frozen immutable 모델이며 amount 양수, timezone-aware timestamp, idempotency/actor/account 필수 필드를 검증합니다.
- RESERVE는 Job 참조, CAPTURE/RELEASE는 RESERVE 참조, REFUND는 원본 Capture 참조, ADJUST는 사유 및 승인 참조를 요구합니다.
- Reservation Settlement는 단일 CAPTURED/RELEASED만 모델링하고 부분 정산은 추가하지 않았습니다.
- RESERVE와 Settlement 간 Organization/Account/Job/Amount/reference 일치 검증을 추가했습니다.
- DB schema/SQL/API/잔액 projection은 추가하지 않았습니다. 계정 소유 범위, 단위 정밀도, 만료/lot, 부분 Capture, refund semantics 및 DB 동시성 정책이 미결정이기 때문입니다.

검증: Backend pytest 206 passed, compileall passed, Viewer 19/19.
