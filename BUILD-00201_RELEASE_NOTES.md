# BUILD-00201 Release Notes — Output Asset Link Worker Lease Safety

Date: 2026-11-06
Base: BUILD-00200

## Changes

- Applied shared worker identity and lease-duration validation to the Output→Asset link outbox claim path.
- Rejects blank/non-string/overlong worker IDs and lease durations that are not positive integers before initialization or database access.
- Validates link identifiers and failure retry limits before storage access.
- Failure acknowledgement now repeats the processing-state, worker-owner, and live-lease predicates in the UPDATE itself, preventing a stale read from clearing a lease that has changed ownership.
- Added 14 parameterized/adversarial regression cases covering invalid worker IDs, lease durations, and retry limits.

## Verification

- Full backend suite: 442 passed / 0 failed.
- Focused Output Asset Link, Poll, and Outbox repository suite: 49 passed / 0 failed.
- Backend app/scripts/tests compileall: passed.
- Existing Viewer offline/API contract checks carried forward unchanged from BUILD-00200; no Viewer source changed.

## Compatibility

- Valid SQLite worker operations retain existing behavior.
- No schema migration or runtime dependency change.
- External database, browser, and paid AI provider tests remain deferred by project decision.
