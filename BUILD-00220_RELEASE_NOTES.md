# BUILD-00220 Release Notes

## Local implementation
- Added private binary storage port with local filesystem and explicit Supabase Storage HTTP adapter.
- Supabase adapter requires HTTPS and service-role credentials, allowlists only `acs-assets`, `acs-gallery`, and `acs-outputs`, enforces bucket MIME/size limits, rejects path traversal, uses non-upsert upload, and avoids leaking response bodies or credentials in errors.
- Added PostgreSQL migrations 0003 and 0004 for function search_path hardening and least-privilege client grants.
- PostgreSQL Asset metadata adapter includes Workspace RBAC, Asset registration, versioning, provenance, relations, and soft deletion.

## Supabase live test project
- Applied generation core and Workspace/Asset migrations.
- Applied append-only function search_path hardening.
- Revoked all public table/sequence privileges from anon/authenticated and future default grants.
- Verified 20 application tables with RLS enabled, no policies, zero app rows, and service_role-only DML privileges.
- Executed temporary relational data probe and rolled it back; follow-up confirmed no residue.
- Security Advisor retains only expected informational RLS-no-policy findings (20); Health Advisor 0.

## Local verification
- Backend pytest: 535 passed / 0 failed.
- Python compileall: PASS.
- Live Supabase SQL/migration/privilege checks: PASS within the scope above.
- Live psycopg app connection, tenant RLS, Supabase Storage HTTP upload/download, and Worker concurrency: NOT RUN.
- Vercel source-backed Preview deployment: BLOCKED; project has no linked Git repository and no source deployment was created.
- Production was not changed.

### Additional continuation
- Added canonical `tenant_object_key(workspace_id, asset_id, filename)` construction so Asset object keys are workspace-prefixed and path-safe.
- Final backend rerun after this addition: 536 passed / 0 failed.
