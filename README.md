# AI CREATOR STUDIO — BUILD-00218

최신 전체 인수인계 패키지입니다. 제품 전체의 Production-ready 상태를 의미하지 않으며 소스, 설계, 검증 증거 및 미완료 항목을 포함합니다.

## 먼저 읽기
1. [`CURRENT_HANDOFF_BUILD-00218.md`](CURRENT_HANDOFF_BUILD-00218.md)
2. [`PROJECT_STATUS_AND_HANDOFF_BUILD-00218.md`](PROJECT_STATUS_AND_HANDOFF_BUILD-00218.md)
3. [`BUILD-00218_VERIFICATION.md`](BUILD-00218_VERIFICATION.md)
4. [`BUILD-00218_RELEASE_NOTES.md`](BUILD-00218_RELEASE_NOTES.md)

## 소스
- `ai_creator_studio_backend_starter/` — FastAPI backend, repositories, workers, scripts, tests
- `ai_creator_studio_3d_viewer/` — React/TypeScript 3D viewer
- `docs/` — 제품 기준, API, 데이터 모델, 설계, 보안, 검증 문서

## BUILD-00218 검증
- Backend pytest: **509 passed / 0 failed**
- Python compileall: PASS
- Runtime OpenAPI snapshot: PASS
- PostgreSQL adapters: fake-connection/unit checks only; no live DB integration claim

Supabase/Vercel read-only smoke evidence: `docs/reports/BUILD-00214_SUPABASE_VERCEL_LIVE_SMOKE.md`.

## 미완료
- PostgreSQL Poll state transitions/output persistence and Asset/Output/Workspace/Product adapters
- Actual PostgreSQL/Supabase DB integration and tenant-safe RLS policies
- Supabase Storage app adapter/object policies
- Vercel source-backed Preview deployment
- Browser React/Three E2E and actual GLB render
- Real AI provider generation; Marketplace, Billing, full Video Pipeline

Unverified features are not marked complete.

---

## Latest verified handoff: BUILD-00219

See `CURRENT_HANDOFF_BUILD-00219.md` and `PROJECT_STATUS_AND_HANDOFF_BUILD-00219.md` for current status. BUILD-00219 adds PostgreSQL Output and Workspace/Asset metadata foundations. These adapters are not yet live-verified or runtime activated. The latest local backend verification is 524 passed / 0 failed; live Supabase and Vercel Preview integration remain pending.

## Latest verified handoff: BUILD-00220

The dedicated Supabase test project has the Generation and Workspace/Asset schemas applied (20 application tables, all RLS-enabled). Client table/sequence privileges were revoked for `anon` and `authenticated`; service-role access remains. A live transactional schema probe was rolled back with zero residual rows. See `docs/reports/BUILD-00220_SUPABASE_LIVE_INTEGRATION.md`. Local backend verification: 535 passed. Vercel remains bootstrap-only; no source-backed Preview deployment exists.
