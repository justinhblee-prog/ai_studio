# BUILD-00200 Release Notes — Worker Lease Input Safety

Date: 2026-11-06
Base: BUILD-00199

## Changes

- Added a shared worker-lease validator for Outbox and Poll repository adapters.
- Worker identifiers must be non-empty strings of at most 128 characters.
- Lease durations must be positive integers; booleans, floats, strings, zero and negative values are rejected explicitly.
- Validation occurs before compatibility implementation delegation or database access, so invalid requests cannot create immediately expired leases.
- Poll lease renewal now uses the same validation and rejects blank task identifiers.
- Added parameterized regression coverage for invalid worker identifiers, lease values and task identifiers.

## Compatibility

- Valid existing calls and SQLite persistence behavior are unchanged.
- PostgreSQL remains intentionally fail-closed and is not implemented by this build.
- No external service, database server, package installation or paid AI provider was used.
