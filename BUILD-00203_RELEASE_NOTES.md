# BUILD-00203 Release Notes — Alert Delivery Lease Fencing

Date: 2026-11-06

## Scope

Completed the cross-repository Worker mutation audit for operational alert webhook deliveries. The alert delivery path previously claimed a row without a durable owner identity or expiry and acknowledged results using only `delivery_id`. A delayed/old worker could therefore mark a delivery complete or reschedule it after another process had reclaimed it.

## Implementation

- Added SQLite schema migration 10 with `claimed_by` and `lease_expires_at` on `generation_ops_alert_deliveries`.
- Legacy in-flight delivery rows receive a bounded two-minute migration lease under `legacy-unknown`; old rows become reclaimable after expiry.
- Claims now require a validated `worker_id` and positive integer lease duration, persist owner/expiry, and return both fields.
- Finish operations require the claiming `worker_id`, validate inputs, require processing status/current owner/unexpired lease, and repeat those predicates in the final UPDATE.
- Expired deliveries are requeued only after their lease expires; reclaim clears the previous owner and lease.
- Alert regeneration/upsert clears stale claim metadata when resetting a delivery to pending.
- Updated `monitor_worker`, Worker repository ports, the compatibility facade, and `GenerationJobRepository` protocol/adapter.
- Added tests for stale owners, expired owners, lease reclaim, invalid identities, migration of legacy in-flight rows, and concurrent single-winner claims.

## Compatibility

Custom callers of `claim_alert_delivery` must now provide `worker_id`; `finish_alert_delivery` must provide the same `worker_id` used for the claim. This is an intentional safety requirement. Existing in-repository monitor worker and repository adapters have been updated.

## Delivery semantics

Webhook delivery remains at-least-once. If a remote endpoint accepts a notification but the process loses the acknowledgement before persisting it, a later lease expiry may cause a duplicate notification. Consumers should deduplicate using the alert fingerprint/delivery identity. This change prevents stale local state mutation; it does not provide remote exactly-once delivery.

## Verification

- Full backend suite: 451 passed, 0 failed.
- Worker/alert/repository/API focused suite: 118 passed, 0 failed.
- Python compileall for app/scripts/tests: passed.
- ZIP CRC and SHA-256: verified after packaging.
- PostgreSQL live tests, React/Three.js E2E, and live AI-provider calls remain deferred by project decision.
