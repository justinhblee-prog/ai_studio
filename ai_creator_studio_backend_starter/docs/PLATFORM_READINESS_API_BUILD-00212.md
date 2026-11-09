# Platform Runtime Readiness API — BUILD-00212

Endpoint: `GET /internal/ops/runtime-readiness`

## Access

- Requires Bearer authentication via the existing API token mapping.
- Requires the resolved user ID to be present in `OPS_ADMIN_USER_IDS`.
- Unauthenticated: 401. Authenticated non-operator: 403.

## Behavior

- Read-only preflight report.
- Does not open a database connection, call external APIs, mutate Supabase, or upload files.
- Reports database runtime, Supabase PostgreSQL, Supabase Storage, worker topology, AI provider mode, and Vercel Preview status.
- Exposes only whether a secret is configured, never its value.
- It is a source-maintained capability inventory, not a dynamic live-health test.

## Local verification

`tests/test_platform_readiness.py` and `tests/test_platform_readiness_api.py` cover status classification, secret redaction, and the operator authorization boundary.
