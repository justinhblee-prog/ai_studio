# AI CREATOR STUDIO — Project Status & Handoff BUILD-00223

| Area | Status | Evidence / next gate |
|---|---|---|
| Backend API and domain | Partially implemented | 548 local tests pass |
| SQLite persistence | Locally verified | Additive Asset locator columns; legacy rows remain local |
| PostgreSQL/Supabase DB | Partial adapters, not runtime-ready | Migration 0005 authored but not live-applied; repository parity/live tests pending |
| Supabase Storage | Adapter + Asset gateway + locator schema foundation | Asset API routes not yet wired; no live transfer |
| Asset lifecycle | Local upload/version/restore/preview/integrity/delete exists | Route all binary I/O through gateway and add compensation/retry |
| Worker | Local process code exists | PostgreSQL Poll/Outbox/Operations composition and lease tests |
| Vercel | Bootstrap Production only | Source-backed Preview not verified |
| 3D Viewer | Source and automated contracts exist | Browser E2E and visible GLB rendering remain unverified |
| AI generation | Provider interface/mock | Real generation not run |
| Marketplace/Billing | Incomplete | Product, checkout, settlement and entitlement workflows |
| Video pipeline | Partial/incomplete | Real encoding, storage and delivery validation |
| Public website | Design/partial implementation | Full portal workflow and deployment validation |

## BUILD-00223 completed
- Added Asset/AssetVersion backend and bucket locator metadata in SQLite and PostgreSQL schema design.
- Added backwards-compatible SQLite schema upgrade logic.
- Extended PostgreSQL metadata adapter to validate and persist locators.
- Full Backend: 548 passed, 0 failed; compileall and OpenAPI snapshot check passed.

## Key distinction
Storage locator metadata is groundwork, not remote-storage integration. Asset routes remain local-only; PostgreSQL migration 0005 and Supabase Storage transfer were not run live.

See `CURRENT_HANDOFF_BUILD-00223.md`, `BUILD-00223_RELEASE_NOTES.md`, and `BUILD-00223_VERIFICATION.md`.
