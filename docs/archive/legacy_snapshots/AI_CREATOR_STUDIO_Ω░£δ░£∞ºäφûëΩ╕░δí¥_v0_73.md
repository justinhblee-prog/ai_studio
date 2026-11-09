# AI CREATOR STUDIO 개발 진행 기록 v0.73

## 목표
Credit Ledger 도메인 계약 다음 단계로 영속성 계층의 경계를 정의하되, 결정되지 않은 과금 정책을 임의로 확정하지 않는다.

## 변경
- `app/credits/repository.py` 추가
- `CreditLedgerRepository` Protocol: `append_batch`, `get_event`, `list_account_events`
- append는 원자적 all-or-nothing, append-only, 멱등성, 영속 이력 참조 검증을 요구
- SQL 유니크 제약을 통한 다중 프로세스 중복 방지 필요성을 명시
- 인메모리 계약 테스트 추가. 운영 어댑터가 아님을 명시
- `docs/CREDIT_LEDGER_REPOSITORY_PORT_v0_1.md` 추가

## 검증 경계
- 이 버전은 Repository Port 계약만 구현한다.
- Credit 잔액/차감/충전/예약 DB 저장은 구현하지 않았다.
- PostgreSQL 동시성 및 내구성은 검증하지 않았다.

## 다음
- 계정 소유 범위와 정밀도 등 정책 결정 항목의 승인 여부 확인
- 결정 전에는 영속화/과금 API를 임의 구현하지 않음
- 승인 가능한 정책 범위에서 SQLite/PostgreSQL 어댑터와 실제 DB 테스트 설계
