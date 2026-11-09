# BUILD-00198 Release Notes — PostgreSQL SQL lexical splitting hardening

Date: 2026-11-05

## Changes

- Hardened `_split_sql_statements` to recognize PostgreSQL line comments, nested block comments, dollar-quoted bodies, ordinary quoted values/identifiers, and `E'...'` escape strings.
- Semicolons inside comments and escape strings no longer split executable SQL into invalid fragments.
- Unterminated block comments now fail closed with a clear validation error.
- Added three focused adversarial regression tests.

## Validation

- Migration-focused tests: 40 passed / 0 failed.
- Full backend suite: 52 test files, 403 passed / 0 failed.
- Backend `compileall`: passed.
- Viewer offline scripts: 17 of 18 JavaScript scripts passed; the actual Three.js integration script remains blocked because the declared `three` package is not installed. Seven Python viewer scripts passed.
- Viewer structural validation: 143 passed.
- API contract: 63/63 calls matched.
- Request contract: 15 JSON body calls checked, 0 findings.
- Response contract: 50 documented JSON endpoint contracts across 52 endpoints and 28 models; 0 missing routes/schemas.
- Viewer package integrity: 0 findings.
- ZIP CRC and SHA-256 verified after packaging.

## Limitations

No PostgreSQL server/driver/container runtime is available; live database migration and runtime repository integration remain unverified. React/Three.js packages are absent, so semantic TypeScript checking and actual React/Three.js E2E remain blocked. No live AI provider request was made because credentials, authorized test inputs, and explicit cost authorization are unavailable.
