# BUILD-00213 Release Notes

## Added
- Read-only platform integration readiness report.
- Operator-only runtime readiness API endpoint.
- Readiness unit and API authorization/secret-redaction tests.

## Changed
- Runtime OpenAPI snapshot updated to include the readiness endpoint.
- Latest handoff and overall status documents refreshed.

## Verification
- Backend pytest: 495 passed, 0 failed.
- Python compileall: PASS.
- OpenAPI snapshot check: PASS.
- Requirements manifest check: PASS.

## Not included / not claimed
- No PostgreSQL runtime adapter.
- No Supabase Storage application adapter.
- No Supabase live app integration test.
- No Vercel source-backed Preview deployment.
- No real AI generation test.

## PostgreSQL fail-closed coverage
- Added regression tests for 15 repository factories and the storage selector.
- Added a coverage matrix for all persistence domains.
- Static scan identified 106 SQLite-specific references that require explicit dialect conversion.
