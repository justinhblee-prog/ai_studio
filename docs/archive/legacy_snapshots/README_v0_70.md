# AI CREATOR STUDIO v0.70

## Credit Ledger DB-neutral Domain Contracts
- Added immutable `CreditLedgerEvent` and `CreditReservationSettlement` domain models.
- Validates positive Decimal magnitude, timezone-aware timestamps, required Job/reservation/reversal/audit references, and single CAPTURE/RELEASE settlement shape.
- Added pure `validate_reservation_settlement` to verify organization/account/job/reference/amount consistency.
- No database tables, SQL, API endpoints, account ownership, unit precision, expiry/lot, partial capture, or balance serialization strategy were selected.
- This is domain validation only, not a persisted Credit Ledger or billing implementation.

## Verification
- Backend pytest: 206 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
