# AI CREATOR STUDIO v0.43

## Outbox Reconciliation Administration Repository

- Added `OutboxAdminRepository` and `SQLiteOutboxAdminRepository`.
- Added explicit dependency factory `get_outbox_admin_repository`.
- Provider submission reconciliation API now uses the dedicated operator repository rather than the generic JobLifecycleService dependency.
- Existing job lookup, workspace role authorization, request validation, and 409 error mapping remain intact.
- PostgreSQL remains fail-closed.

## Verification
- Backend: 164 tests passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
