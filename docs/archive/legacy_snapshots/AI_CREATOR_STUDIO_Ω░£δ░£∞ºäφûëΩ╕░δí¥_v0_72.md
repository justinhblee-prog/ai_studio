# AI CREATOR STUDIO 개발 진행 기록 v0.72

- Credit Ledger REFUND provenance 검증 추가.
- REFUND가 CAPTURE 이벤트를 참조하는지 확인.
- 조직 및 Credit Account 일치 검증.
- Batch 내 원본 CAPTURE가 있으면 함께 검증.
- 환불 금액 동일성·누적 환불 한도는 부분 환불 정책 미결정으로 강제하지 않음.
- 과거 원장 참조의 누적 환불 한도는 향후 DB 트랜잭션 어댑터 책임.
- Backend 214 passed, compileall passed, Viewer 19/19.
