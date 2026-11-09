# BUILD-00202 Verification Report

## Baseline integrity

- BUILD-00201 ZIP SHA-256 and ZIP CRC verified before clean extraction.

## Transaction and repository review

- Confirmed SQLite storage transaction context owns one connection per command, commits on normal exit, rolls back on any `BaseException`, and closes the connection.
- Confirmed Job lifecycle state, Execution state, and append-only Event insertion use the same transaction connection.
- Added injected Event failure tests for Job create and metadata update; rollback assertions cover the complete associated row sets and version/state invariants.
- Outbox completion and unknown-outcome acknowledgement now require matching worker owner and unexpired lease. The conditional predicates are repeated in the actual UPDATE statements.
- Stale-owner tests cover ownership change, lease expiry, rejection of stale completion/acknowledgement, and no automatic replay of uncertain provider POST outcomes.

## Test results

- Full backend suite: **447 passed / 0 failed** (`build202_logs/backend_full_pytest.log`).
- Focused transaction/Outbox/UoW/API suite: **140 passed / 0 failed** (`build202_logs/backend_transaction_outbox_focus.log`).
- Python compileall for backend app/scripts/tests: passed (`build202_logs/compileall.log`).

## Viewer and API

No Viewer or API route source was changed. BUILD-00201 offline Viewer/API logs are carried forward for reference, not represented as freshly rerun:
- Viewer JavaScript: 17 scripts.
- Viewer Python: 7 scripts.
- Source structural validation: 143 checks.
- API contract: 63/63 calls matched.
- Request contract: 15 checked / 0 findings.
- Response contract: 50 JSON endpoint contracts across 52 endpoints and 28 models / 0 missing.
- Package integrity: 0 findings.
- TypeScript syntax parsing only; no semantic typecheck.

## Not run / deferred

- No live PostgreSQL tests or PostgreSQL runtime adapter implementation.
- No React/Three.js package integration or Viewer E2E.
- No live paid AI provider generation.
- These external tests remain deferred by the user's project decision.

## Compatibility impact

- `complete_outbox_submission` and `mark_outbox_unknown` now require `worker_id`; all in-repository worker and facade callers pass the identity associated with the claim. External custom callers must be updated accordingly.
- No schema migration or new runtime dependency.
