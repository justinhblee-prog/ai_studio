# AI CREATOR STUDIO v0.41

## Poll Repository Boundary Extraction

- Added `app.repositories.poll.PollRepository` and `SQLitePollRepository`.
- Moved worker-facing Poll adapter composition out of `worker_repositories.py`.
- Preserved Output repository and Job/Event lifecycle service composition.
- PostgreSQL selection fails closed; no SQLite fallback.
- SQL remains delegated to existing audited SQLite implementation in this boundary-only milestone.

## Verification
- Backend: 160 tests passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
