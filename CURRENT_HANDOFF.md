# AI CREATOR STUDIO — Current Handoff BUILD-00209

Active continuation point: **BUILD-00209 completed (local audit + dependency manifest repair)**.

## Verified baseline
- Canonical latest source package available in Library: BUILD-00208 ZIP.
- Supabase project `AI Characters STUDIO` (`lmdhgqfqvfyymfrovaty`) is ACTIVE_HEALTHY in Seoul (`ap-northeast-2`), PostgreSQL 17.11.
- Cloud migration ledger contains four migrations: initial app schema, security policy/index hardening, advisor remediation, and private worker-table lockdown.
- Eight app tables in `public` have RLS enabled and authenticated policies.
- Two `private` worker/internal tables have no ordinary-role schema USAGE; service_role table grants only.
- All three Supabase Storage buckets (`acs-assets`, `acs-gallery`, `acs-outputs`) are private.
- Security Advisor returned zero lints. Performance Advisor lists unused-index informational findings; do not remove without workload evidence.
- A broad SQL grant issue remains: `anon` has DML and table-level TRUNCATE/TRIGGER/REFERENCES on app tables; `authenticated` also has TRUNCATE. RLS does not replace SQL privileges. A narrowly scoped grant-hardening migration is recommended but was not executed.

## Completed in BUILD-00209
- Added `ai_creator_studio_backend_starter/docs/SUPABASE_LIVE_READINESS_AUDIT_BUILD-00209.md`.
- Fixed `requirements.txt` malformed escaped newline between `python-multipart` and `Pillow`.
- Revalidated all backend tests: 475 passed / 0 failed.
- Python compileall and requirement-line assertions passed.
- No cloud database/data mutation was performed.

## Architecture boundary
- Source uses SQLite for all runtime repositories and local filesystem for private assets/output storage.
- PostgreSQL selection fails closed. The SQLite-to-PostgreSQL bundle tool is a migration utility, not a runtime adapter.
- No Supabase Storage adapter is present.
- Vercel integration awaits connection. Viewer is currently packaged as a React/Three.js library; backend uses durable independent workers and local file storage, and should not be force-deployed as one serverless function.
- AI Provider defaults to mock and no real generation was called.

## Next priorities
1. Reconcile least-privilege grants for `anon` and `authenticated` against actual API usage. Implement and validate on an isolated development schema/project before production application.
2. Add tests for RLS, owner membership triggers, cross-workspace access and role escalation with actual authenticated test identities.
3. Implement the PostgreSQL runtime adapter for all repositories/workers and transaction/lease/idempotency semantics; then validate against Supabase branch/dev project.
4. Implement private Supabase Storage adapter and lifecycle tests before switching off local storage.
5. Connect Vercel and audit frontend build entrypoint; prepare Preview deploy only after app build is deterministic.
6. Continue baseline BUILD-00208 next priorities: output→asset import state review, dry-run orphan-file inventory and Lookbook archive/restore idempotency/race tests.

## Validation record
- Full backend pytest: 475 passed / 0 failed.
- Focused Postgres readiness/migration/storage/repository tests: 56 passed.
- `compileall app tests`: PASS.
- PostgreSQL local environment probe: BLOCKED (no driver, server tools, Docker/Podman).
- No live PostgreSQL runtime or Vercel deployment test claimed.
