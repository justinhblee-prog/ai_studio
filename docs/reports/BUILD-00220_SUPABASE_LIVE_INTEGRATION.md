# BUILD-00220 — Supabase Live Integration Evidence

Date: 2026-11-06
Target: dedicated test project `AI-CREATOR-STUDIO-TEST` (`niktytizbtvxypwswbcc`)

## Applied migrations
1. `acs_private_storage_buckets` — pre-existing bucket setup
2. `acs_generation_core_0001` — generation jobs, executions, events, outputs, worker queues, operations tables
3. `acs_assets_workspaces_0002` — Workspace RBAC, Assets, versions, relations, provenance
4. `acs_harden_append_only_function_search_path` — pins `acs_reject_append_only_mutation()` search_path to `pg_catalog`
5. `acs_restrict_public_app_table_grants` — revokes all table and sequence privileges from `anon` and `authenticated`, including default privileges for future objects

## Live verification
- `public` application tables: 20.
- All 20 application tables report `rls_enabled=true`.
- Application row counts: 0.
- `pg_policies` count: 0. This is intentional default-deny; tenant policies are not yet ready and no client role can access these tables.
- Privilege checks after hardening:
  - `anon` SELECT: false
  - `anon` TRUNCATE: false
  - `authenticated` INSERT: false
  - `service_role` INSERT: true
- Transactional schema probe: inserted a temporary Workspace, membership, Asset, version, and provenance row inside a transaction, then rolled back. Follow-up query confirmed `residual_probe_rows=0`.
- Security Advisor: 20 informational `rls_enabled_no_policy` findings remain (expected until reviewed tenant policies are implemented); prior mutable function search_path warning is no longer present.
- Health Advisor: 0 lints.
- Storage buckets remain private; no object policies or objects were added.

## Scope and limitations
- This verifies migration execution, constraints, foreign keys, RLS flags, role grants, and rollback behavior through Supabase's SQL execution path.
- It does not verify application-to-PostgreSQL connectivity through `psycopg`, service-role API authentication, tenant RLS policies, Storage object upload/download, or Worker concurrency under multiple live processes.
- No production Supabase project was modified.
- No Vercel deployment or environment variables were changed.
- No real AI provider was called.

## Security decision
Do not create permissive client policies merely to clear the informational advisor findings. Keep the database default-deny and service-role-only until Supabase Auth user identity mapping and workspace membership policies are implemented and tested with two distinct users.


## Local Storage adapter follow-up
- The local BlobStore mock-transport suite verifies private bucket allowlisting, MIME/size checks, non-upsert uploads, safe error handling, and workspace-prefixed object-key generation. These are local tests, not a live Supabase Storage transfer.
