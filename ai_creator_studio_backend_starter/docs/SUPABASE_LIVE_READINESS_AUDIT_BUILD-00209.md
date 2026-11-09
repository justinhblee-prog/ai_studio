# Supabase Live Readiness Audit — BUILD-00209

- Audit date: 2026-11-06 (Asia/Seoul)
- Source baseline: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00208.zip`
- Supabase project: `AI Characters STUDIO` (`lmdhgqfqvfyymfrovaty`)
- Supabase region: `ap-northeast-2` (Seoul)
- Scope: non-destructive metadata, grants, policy, migration, bucket and Advisor inspection; local dependency manifest repair.

## Verified cloud state

- Project state reported `ACTIVE_HEALTHY`; PostgreSQL 17.11.
- Four migrations present: `acs_initial_app_schema`, `acs_security_policy_and_index_hardening`, `acs_advisor_remediation`, `acs_private_worker_tables_lockdown`.
- App tables in `public`: `workspaces`, `workspace_members`, `assets`, `characters`, `character_assets`, `character_bundle_imports`, `generation_jobs`, `gallery_images`.
- RLS enabled on all listed public app tables. Policies target `authenticated` and use owner/workspace checks.
- `private` schema has no USAGE grant for `anon`, `authenticated` or `service_role`; its two worker/internal tables grant privileges to `service_role` only. RLS is disabled there, but the schema is not exposed to the ordinary API roles based on inspected grants.
- One `SECURITY DEFINER` function exists in `private`: `add_workspace_owner_membership()`, owner `postgres`, with empty `search_path`. Its inspected body inserts the new workspace owner into `public.workspace_members` and on conflict changes that membership role to `owner`. It references `public.workspace_members` with a fully qualified name, and the empty search path reduces object-shadowing risk. Keep `EXECUTE` privileges restricted to the trigger execution path; no function or grant change was made.
- Security Advisor returned zero lints.
- Performance Advisor showed 23 unused-index informational findings in a new/empty schema; do not drop them absent workload evidence.
- Three private Storage buckets exist: `acs-assets` (100 MiB, GLB/GLTF/octet-stream), `acs-gallery` (20 MiB, JPEG/PNG/WebP), `acs-outputs` (25 MiB, JPEG/PNG/WebP). All are `public=false`.
- No user rows were found in the app tables during the metadata listing. No test account or test object has been created.

## Security finding — public schema grants

The `anon` role currently has broad table-level privileges on all eight app tables, including `TRUNCATE`, `TRIGGER`, `REFERENCES`, and DML privileges. `authenticated` also has table-level `TRUNCATE` privilege. `public` schema USAGE is enabled for `anon` and `authenticated`.

RLS policies do not replace SQL privilege checks and do not constrain table-level operations such as `TRUNCATE`. The current app policies are scoped to `authenticated`; this means current data row policy protections should not be treated as a complete justification for broad grants.

**Recommended hardening (not executed):** revoke all table privileges on the eight app tables from `anon`; grant only required DML privileges to `authenticated`; revoke `TRUNCATE`, `TRIGGER`, and `REFERENCES` from `authenticated` unless a documented feature needs them; keep privileged worker operations on backend-only service credentials. Confirm frontend code paths and role grants before applying. Do not execute blanket schema-wide revokes blindly because Supabase Auth and generated API behavior may depend on other grants.

## Source-to-cloud mismatch

The BUILD-00208 source still explicitly supports SQLite only. `app/storage.py`, `app/dependencies.py`, `app/repository_contract.py`, and repository factories fail closed for PostgreSQL. All runtime SQL modules use SQLite APIs/dialect. The SQLite-to-PostgreSQL migration bundle tool is not a runtime adapter. Therefore the cloud schema being present does not establish that the application can use Supabase Postgres.

Supabase database schema also includes an app schema and RLS policies that are not represented as a versioned SQL migration directory in this source package. Treat the cloud migration ledger as its own deployment history; do not replay source or cloud DDL without reconciling both histories.

## Storage mismatch

Source `ASSET_STORAGE_DIR` is a local filesystem directory; Supabase has three private buckets, but no Supabase Storage adapter exists in this baseline. Do not route uploads to these buckets until key naming, tenant path policy, content-type validation, checksum verification, signed URL expiry, rollback and deletion lifecycle have a tested adapter.

## Local source repair in BUILD-00209

Fixed a literal escaped newline in `requirements.txt` so `python-multipart` and `Pillow` resolve as two independent requirement lines. Before repair, pip would parse the combined string as one invalid requirement. No cloud resources or database objects were changed.

## Tests and limitations

- Focused tests executed before source repair: 56 passed (`test_postgres_readiness.py`, `test_sqlite_to_postgres_migration.py`, `test_storage_port.py`, `test_repository_contract.py`).
- Local readiness probe: exit 2; no psycopg/psycopg2/asyncpg, postgres/initdb/pg_ctl/psql, Docker or Podman available in the execution environment.
- No Postgres live runtime/transaction/worker concurrency test was run.
- No authenticated-user HTTP/API test, Storage upload/download, Vercel Preview deployment, or external AI provider test was run.
- No schema or data mutation was performed in Supabase.

## Next steps

1. Continue independent policy/role-escalation tests, including owner-membership trigger behavior.
2. Reconcile app grants with actual frontend/server access pattern and produce a narrowly scoped grant-hardening migration for a disposable development project/branch.
3. Build an explicit PostgreSQL runtime adapter covering every repository and worker before enabling `DATABASE_BACKEND=postgresql`.
4. Add Supabase Storage adapter with isolated bucket tests and strict tenant path policy.
5. Vercel integration awaits user connection; host the frontend there only after identifying a real deployable app entrypoint. Current viewer package is a library, and the backend uses durable independent workers plus local disk; those are not directly deployable as a single Vercel function.
6. Keep actual generation provider calls disabled until a non-billable/test provider agreement and API credentials are explicitly configured.
