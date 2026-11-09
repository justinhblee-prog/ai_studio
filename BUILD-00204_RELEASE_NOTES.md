# BUILD-00204 Release Notes — Administrative Recovery Safety

Date: 2026-11-06

## Scope

Audited privileged recovery mutations for Poll Tasks, Provider Outbox reconciliation, and Output→Asset link retries. The work hardens repository-level validation and ensures state changes remain conditional on the expected recoverable state.

## Implementation

- Added shared `operator_validation` helpers for actor identity, resource identifiers, and bounded non-empty operator reasons.
- Poll Task retry validates actor/reason/task/workspace identifiers before delegation or storage initialization. Its pending transition is fenced by `status='needs_reconciliation'`; the paired Job update is fenced by the observed Job status. Any mismatch aborts the transaction.
- Output Asset Link retry validates operator identity/reason and resource identifiers. Its transition is fenced by `status='failed'`; audit event insertion and state transition remain in one transaction, with row-count enforcement.
- Provider Outbox reconciliation validates actor/reason/job identifier and provider request reference. Both reconciliation actions fence Outbox acknowledgement by `status='needs_reconciliation'`, clear stale claim metadata, and fail closed if the expected row was not changed.
- Added adversarial validation and compatibility-delegation tests.

## Compatibility

- Repository callers must provide a non-empty actor ID (maximum 128 characters) and an operator reason containing 1–500 non-whitespace characters.
- Provider request IDs must be non-empty and at most 256 characters when supplied.
- Existing HTTP routes already require a reason; validation is now also enforced at the repository boundary so direct/internal callers cannot bypass it.
- No schema migration or runtime dependency change.

## Verification

- Full backend suite: 466 passed, 0 failed.
- Focused operator recovery/API/Outbox/Output Asset Link suite: 111 passed, 0 failed.
- Python compileall for app/scripts/tests: passed.
- BUILD-00203 source archive SHA-256 and CRC verified before clean extraction; BUILD-00204 archive CRC and SHA-256 verified after packaging.
- Viewer/API offline checks were not rerun because this build changes backend repository code only.
- PostgreSQL live tests, React/Three.js E2E, and live AI-provider calls remain deferred by project decision.

## Remaining constraints

- SQLite remains the only implemented runtime storage adapter; PostgreSQL adapters/live verification are not claimed.
- React/Three.js package integration, semantic TypeScript checks and Viewer E2E remain pending.
- Live AI generation remains pending credentials, authorized test inputs and explicit cost approval.
- API design/runtime OpenAPI drift remains an explicit product/API decision; this build does not silently rewrite public contracts.
