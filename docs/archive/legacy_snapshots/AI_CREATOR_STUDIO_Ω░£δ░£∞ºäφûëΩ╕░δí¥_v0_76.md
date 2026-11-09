# AI CREATOR STUDIO 개발 진행 기록 v0.76

## 목표
Generation Job 생성 시 workspace-scoped idempotency key의 동시 요청 경합을 실제 SQLite 테스트로 검증한다.

## 변경
- 12개 동시 요청으로 동일 workspace/key에 서로 다른 제안 Job ID 생성 시도
- 모든 호출이 동일한 canonical Job ID를 반환하는지 검증
- `created=True`가 정확히 한 건인지 검증
- Job row 및 idempotency row가 각각 한 건인지 검증

## 한계
SQLite 단일 호스트/단일 DB 파일 테스트다. PostgreSQL advisory/row lock, multi-instance, 네트워크 장애, replica behavior 증거가 아니다.
