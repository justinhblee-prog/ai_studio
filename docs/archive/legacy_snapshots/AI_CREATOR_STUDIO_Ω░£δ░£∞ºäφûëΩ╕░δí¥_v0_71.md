# AI CREATOR STUDIO 개발 진행 기록 v0.71

- Credit Ledger domain batch validation 추가.
- Event ID 재사용 시 payload 충돌 거부.
- scope + idempotency key 재사용 시 payload 충돌 거부.
- 동일 event replay는 batch canonicalization 단계에서 중복 제거.
- 단일 RESERVE에 대한 CAPTURE/RELEASE 복수 terminal settlement 거부.
- RESERVE와 settlement가 같은 batch에 존재하면 참조·조직·계정·Job·금액 일치 검증.
- 이전 batch에 저장된 RESERVE 참조는 향후 DB adapter 트랜잭션 안에서 검증하도록 명시.
- Backend 211 passed, compileall passed, Viewer 19/19.
- Credit DB persistence, Quote, API, billing은 미구현이며 정책 승인 대기.
