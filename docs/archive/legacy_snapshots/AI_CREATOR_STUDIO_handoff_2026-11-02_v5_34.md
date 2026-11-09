# AI CREATOR STUDIO Handoff v5.34 — v0.72

## Completed
- Added DB-neutral refund provenance validator.
- REFUND must reference a CAPTURE and match organization/account.
- Batch validator checks the relationship when original CAPTURE is present in the batch.
- Refund amount equality and cumulative refund ceilings are intentionally not enforced because partial/cumulative refund policy remains unresolved.
- Backend pytest 214 passed; compileall passed; Viewer structural validation 19/19.

## Next
1. Add reversal/adjustment provenance constraints that do not invent approval or monetary semantics.
2. Define repository transaction contract tests before implementing persistent ledger tables.
3. Keep persistent Credit Ledger, Quote, billing API, unit precision, account ownership, expiry/lot allocation, partial capture, refund/payment semantics, and ADJUST approval blocked pending PO decisions.
4. PostgreSQL runtime remains blocked until a real server and driver are provisioned.
5. Continue actual provider, browser/WebGL, process-crash, and G0-G5 evidence collection.

## Risks
- SQLite is the only implemented runtime backend.
- v0.72 remains pure domain validation, not persistent accounting.
- FASHN terms/rights/retention/commercial use remain unverified.
- TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
