# AI CREATOR STUDIO v0.42

## Poll Task Administration Repository Extraction

- Added `PollTaskAdminRepository` and `SQLitePollTaskAdminRepository` in `app/repositories/poll_admin.py`.
- Added an explicit dependency factory in `app/dependencies.py`.
- Poll Task list/retry API routes now depend on the dedicated admin repository instead of the general JobRepository.
- Workspace role checks, status validation, and API response/error behavior remain in the route layer.
- PostgreSQL remains fail-closed; no SQLite fallback.

## Verification
- Backend: 162 tests passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
