# BUILD-00142 — Private ZIP Download Authorization & Cleanup Observability

## Highlights
- Lookbook private ZIP downloads now revalidate current workspace membership and role at request time in addition to checking the short-lived HMAC URL.
- The Viewer sends its Bearer Authorization header when fetching ZIP bytes.
- Symlink and other non-regular package filesystem entries are rejected before checksum validation.
- Expired ZIP cleanup emits machine-readable operational metrics and an explicit partial-failure signal while retaining immutable audit rows.

## Compatibility and safety
- Existing signed URLs now require an authenticated current workspace member; clients must send `Authorization: Bearer ...`.
- Viewer implementation updated accordingly.
- No new API routes, database schema changes, migrations, dependencies, Provider calls, credit behavior, publication, or rights behavior.
- Cleanup remains dry-run unless `--apply` is supplied.

## Verification
See `BUILD-00142_VERIFICATION.md` and `CURRENT_HANDOFF_BUILD-00142.md`.
