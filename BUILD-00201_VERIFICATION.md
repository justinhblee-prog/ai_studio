# BUILD-00201 Verification Report

## Baseline integrity

- BUILD-00200 ZIP SHA-256 and ZIP CRC verified before clean extraction.

## Backend

- Full backend suite: **442 passed / 0 failed**.
- Focused Output Asset Link + Poll + Outbox repository tests: **49 passed / 0 failed**.
- Python compileall for backend app/scripts/tests: passed.

## Viewer and API

No Viewer source was changed in this build. BUILD-00200 offline verification logs are carried forward for reference, not represented as freshly rerun:
- Dependency-free Viewer JavaScript: 17 scripts.
- Viewer Python: 7 scripts.
- Source structural validation: 143 checks.
- API contract: 63/63 calls matched.
- Request contract: 15 checked / 0 findings.
- Response contract: 50 JSON endpoint contracts across 52 endpoints and 28 models / 0 missing.
- Package integrity: 0 findings.
- TypeScript syntax parsing only; no semantic typecheck.

## Not run / deferred

- No external PostgreSQL, React/Three.js E2E, or live AI provider tests were attempted, per project decision.
- PostgreSQL runtime adapters, semantic TypeScript checking, full Viewer E2E, and paid provider integration remain future work.

## Logs

`build201_logs/backend_full_pytest.log`, `backend_worker_repository_focus.log`, and `compileall.log` are fresh for this build. Other Viewer/API logs are carried forward from BUILD-00200 and are unchanged because those sources were not modified.
