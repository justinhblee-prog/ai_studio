# AI CREATOR STUDIO Handoff — 2026-11-02 / v5.40

## Current source

- Latest source folder: `AI_CREATOR_STUDIO_v0_80/`
- Latest source ZIP: `AI_CREATOR_STUDIO_v0_80_provider_output_contract_validation.zip`
- Base: v0.79

## v0.80 completed

- Provider success output reference validation before durable Job handoff.
- Enforces non-empty <=4096 character HTTPS URL, hostname, no credentials, no whitespace/control chars.
- Output finalization repository validates supported image MIME, matching file extension, plain filename storage key, positive size <= configured max, and exact Job-specific authenticated private output route.
- Invalid inputs are rejected before DB state changes.
- Existing download-time HTTPS host allowlist, redirect-disabled fetch, content-type and binary signature checks remain in place.
- Backend 248 passed; compileall passed; Viewer 19/19 passed; ZIP integrity passed.

## Current constraints / unresolved

- SQLite is the only implemented runtime DB adapter. PostgreSQL runtime adapter and real PG tests are not implemented.
- Single-host SQLite tests do not prove multi-host/distributed Lease safety.
- FASHN live contract, rights, retention, and commercial-use verification remain open.
- Credit Quote and append-only Credit Ledger persistence are not implemented; v0.70-v0.74 are domain/port/UoW contracts only.
- Credit policy decisions remain open: account ownership scope, unit precision, expiry/lot allocation, partial capture, refund/payment semantics, ADJUST approval policy, and balance serialization/locking.
- QA T-01..T-14 and gates G0-G5 remain unclosed/unpassed unless separately evidenced.
- TypeScript typecheck, browser/WebGL runtime, Android E2E, production deployment, and production readiness are not verified.
- MANUAL provider selection must not auto-fallback. Unknown provider submission outcomes must not be blindly replayed.

## Next suggested work

- v0.81: inspect the local output file lifecycle around lease loss and process crash. Specifically assess whether a stale worker can overwrite a deterministic per-Job output file before its DB finalization is rejected. If a safe change is made, use attempt-scoped temporary artifacts and promote only under the valid Lease transaction boundary; do not claim filesystem+SQLite atomicity without a recovery protocol.
- Preserve current policy blockers; do not start credit persistence or PostgreSQL adapter without the necessary decisions/environment.
