# AI CREATOR STUDIO 개발 진행 기록 v0.74

## 목표
v0.73 Repository Port에 트랜잭션 경계 및 애플리케이션 오류 계약을 추가한다.

## 변경
- CreditLedgerUnitOfWork 및 Factory Protocol 추가
- 동일 트랜잭션 연결 공유, 성공 시 Commit, 실패 시 Rollback, Commit 실패 전파 요구사항 명시
- CreditLedgerError 하위의 Validation/Idempotency/Reference/Concurrency/Transaction 오류 정의
- 인메모리 Fake UoW 기반 계약 테스트 추가
- 상세 명세 `docs/CREDIT_LEDGER_UOW_AND_ERRORS_v0_1.md`

## 제한
실제 DB 트랜잭션, isolation, 동시성, durability 검증은 아니다. 과금 및 잔액 계산은 미구현.
