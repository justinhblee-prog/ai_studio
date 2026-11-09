# AI CREATOR STUDIO 전체 현황 및 인수인계 — BUILD-00215

## 전체 판정

프로젝트는 Backend Starter와 3D Viewer를 중심으로 개발 중이며 Production-ready가 아닙니다. BUILD-00215는 PostgreSQL migration/schema foundation만 추가했습니다. 실제 PostgreSQL runtime Repository Adapter는 아직 없으므로 SQLite가 유일하게 활성화된 backend입니다.

| 영역 | 상태 | 증거 / 다음 관문 |
|---|---|---|
| Backend API 및 도메인 | 부분 구현 | pytest 500 passed; 제품 전체 기능은 미완료 |
| SQLite 영속성 | 로컬 검증 가능 | 기본 런타임 |
| PostgreSQL schema/migration foundation | 내부 구현 | migration SQL 구조 테스트; Supabase 적용 전 |
| PostgreSQL runtime Repository Adapter | 미구현 | aggregate contract 및 transaction parity 필요 |
| Supabase DB 통합 | 미완료 | 테스트 DB에 migration 미적용 |
| Supabase Storage | 기반 private buckets 3개 | 앱 adapter 및 object policies 미구현 |
| Worker | 로컬 worker 코드 존재 | PostgreSQL lease 및 multi-instance 검증 필요 |
| Vercel | bootstrap Production READY | 실제 앱 Preview 배포 미수행 |
| 3D Viewer | 소스 및 자동 계약 테스트 존재 | 실제 브라우저 E2E/GLB 렌더 미검증 |
| AI 생성 | Provider interface/mock | 유료 실생성 미수행 |
| Marketplace / Billing | 미완료 | 제품/결제/정산 구현 필요 |
| Video Pipeline | 부분/미완료 | 실제 인코딩·저장 검증 필요 |
| Public Website | 설계/일부 구현 | 포털 전체 흐름과 배포 검증 필요 |

## BUILD-00215 변경

- psycopg 3 dependency 추가.
- transaction-scoped advisory lock과 checksum ledger를 갖춘 PostgreSQL migration runner.
- 13개 핵심 generation aggregate 테이블 및 FK/index/lease columns.
- Output review/export append-only triggers.
- 모든 앱 테이블 RLS enabled; client policy가 없어 default-deny.
- Backend pytest 500 passed, compileall PASS, OpenAPI snapshot PASS.

## 실환경 검증 상태

- Supabase test project infrastructure healthy; private bucket 3개.
- App schema migration은 아직 적용하지 않음.
- Vercel bootstrap root/health HTTP 200이나 전체 앱 소스 배포는 아님.
- Vercel Preview deployment 없음.
- Real AI provider 호출 없음.

상세 기록: `CURRENT_HANDOFF_BUILD-00215.md` 및 `docs/reports/BUILD-00214_SUPABASE_VERCEL_LIVE_SMOKE.md`.
