# Build Information

- Build: BUILD-00208
- Base: BUILD-00207
- Release: Read-only Historical Workspace Integrity Auditor
- Verification: Backend pytest 475 passed / 0 failed; auditor tests 2 passed; Python compileall passed; source ZIP CRC and SHA-256 verified before extraction.
- Added a read-only SQLite auditor for historical Product, Variant, Character, Lookbook Asset and Lookbook entity relationships.
- Auditor reports missing, deleted, cross-workspace, invalid-media and stale-parent references; no repair or deletion is performed.
- PostgreSQL parity, automated orphan private-file cleanup, live PostgreSQL, React/Three.js E2E and live AI provider tests remain unverified/deferred.
- Canonical handoff: `CURRENT_HANDOFF.md` and `docs/handoff/CURRENT_HANDOFF.md`.
