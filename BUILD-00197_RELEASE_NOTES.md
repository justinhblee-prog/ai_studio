# BUILD-00197 Release Notes — Atomic Migration Bundle Publication

Date: 2026-11-05
Baseline: BUILD-00196 full handoff archive (SHA-256 and ZIP CRC verified before extraction)

## Changes

1. Migration export now writes to a unique sibling staging directory on the same filesystem.
2. The final bundle is published with a same-filesystem atomic rename only after schema, data files and manifest have all been written and the SQLite read transaction has completed.
3. Failed exports remove their staging directory and do not leave partial bundles at the requested destination.
4. Existing non-empty destinations remain rejected; an existing empty destination directory is supported and replaced only at successful publication.
5. Destination symlinks are rejected before export.
6. Added tests for partial-export cleanup, empty-destination publication and symlink destination refusal.

## Validation

- Migration-focused suite: **37 passed, 0 failed**.
- Backend Python compileall: passed.
- Viewer structural source validation: **143 passed**.
- Viewer package integrity: **0 findings**.
- Full backend regression suite is not re-claimed for this build; BUILD-00196 full-suite attempt did not complete in the execution window. BUILD-00195 baseline remains 394 passed / 0 failed.
- Live PostgreSQL, React/Three.js E2E and live AI provider generation remain blocked by unavailable server/dependencies/credentials/authorization.

## Scope

No application runtime API, dependency manifest, lockfile or provider configuration changed. SQLite remains the supported runtime database.
