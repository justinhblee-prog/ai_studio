# AI CREATOR STUDIO — Current Handoff BUILD-00197

Active continuation point: **BUILD-00197**. BUILD-00196 archive SHA-256 and ZIP CRC were verified before extraction.

## BUILD-00197 work

Migration export now uses a sibling staging directory and publishes the completed bundle via atomic rename. Failures clean up staging rather than leaving a partial bundle at the final destination. Non-empty destinations and symlink destinations are rejected; an existing empty directory can be atomically replaced after successful export. Added regression tests for failed-export cleanup, empty destination publication and symlink refusal.

## Verification

- Migration-focused suite: **37 passed / 0 failed**.
- Backend Python compileall: passed.
- Viewer structural validation: **143 passed**.
- Viewer package integrity: **0 findings**.
- BUILD-00195 remains latest full backend suite baseline: 394 passed / 0 failed. No fresh full-suite pass is claimed in BUILD-00197.
- Full ZIP CRC and SHA-256 passed.

## Blockers

1. No PostgreSQL server, psql, Docker/Podman or psycopg 3. Live DB import/rollback/trigger/constraint/sequence tests remain unverified.
2. PostgreSQL runtime Repository/transaction adapters remain unimplemented; SQLite remains supported runtime DB.
3. React/ReactDOM/Three.js and typings unavailable; actual Three.js integration and React Viewer E2E remain blocked.
4. Live AI generation not invoked; no credentials, authorized test inputs or explicit cost authorization.
5. Product-design OpenAPI draft differs from runtime snapshot; runtime snapshot is authoritative for implemented behavior.
6. Bundle SHA-256 is integrity metadata, not signed provenance/authentication.

## Next priorities

1. Provision a disposable PostgreSQL environment and psycopg 3; run real migration, rollback, triggers, constraints, sequences and repeat-import tests.
2. Implement PostgreSQL runtime adapters against the verified disposable DB while preserving SQLite.
3. Acquire trusted React/Three.js packages and run semantic typecheck and actual Viewer E2E.
4. Reconcile design OpenAPI and runtime API contracts.
5. Execute live AI generation only after credentials, authorized inputs and cost approval.

See `BUILD-00197_RELEASE_NOTES.md`, `BUILD-00197_VERIFICATION.md`, and `build197_logs/`.

## Delivery

BUILD-00197 archive and SHA-256 sidecar generated and locally verified. Library upload status is not asserted.
