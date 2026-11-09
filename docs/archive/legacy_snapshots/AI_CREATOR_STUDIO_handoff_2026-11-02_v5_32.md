# AI CREATOR STUDIO Handoff v5.32 — v0.70

## Completed
- Added DB-neutral immutable Credit Ledger Event and Reservation Settlement domain contracts.
- Added validation for event references and single CAPTURE/RELEASE settlement consistency.
- Added T-01..T-14 evidence crosswalk; original IDs retained and all G0..G5 remain unpassed.

## Next
1. Do not add persisted Credit tables or reserve/capture/release API until PO decisions are made: Organization vs Workspace account ownership, credit unit precision, expiry/lot allocation, partial capture, refund/payment semantics, ADJUST approval policy.
2. Once policy decisions are approved, choose a database-backed serialization strategy and implement CL-01..CL-12 including concurrent reserve/capture/release, idempotency, append-only enforcement, and projection reconciliation.
3. Keep PostgreSQL adapter blocked until a real server and driver are provisioned; current environment lacks psycopg/psycopg2/asyncpg, PostgreSQL binaries, and Docker.
4. Continue real Provider, browser/WebGL, and process-crash evidence before promoting T-07/T-09/T-12/T-13/T-14 or any Gate.

## Open risks
- SQLite remains the only implemented runtime backend; PostgreSQL live integration not run.
- Credit Quote/Ledger persistence and billing integration remain unimplemented; v0.70 is domain validation only.
- FASHN contract/rights/retention/commercial-use verification remains open.
- Frontend TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
- No production zero-downtime migration/cutover/rollback proof.
