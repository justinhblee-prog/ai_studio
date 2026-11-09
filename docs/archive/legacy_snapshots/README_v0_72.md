# AI CREATOR STUDIO v0.72

## Credit Ledger refund provenance validation
- Added DB-neutral `validate_refund_reference`.
- A REFUND must reference a supplied CAPTURE event and match its organization and credit account.
- Batch validation now checks refund provenance when the original CAPTURE is included in the same batch.
- Does not impose refund amount equality or cumulative refund ceilings; partial/cumulative refund policy remains unresolved and must be enforced against persisted history transactionally.

## Verification
- Backend pytest: 214 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
- No database persistence, billing API, or refund policy was added.
