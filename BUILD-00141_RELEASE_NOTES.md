# BUILD-00141 — Lookbook Export History & Page-Order Integrity

- Added draft-scoped internal ZIP export history to Lookbook assembly UI, including export ID, timestamps, page count, package size, package SHA-256, approved snapshot SHA-256, retention expiry, and file status.
- Backend history now distinguishes available, expired, and missing ZIP files using safe `lstat` checks. The history read is observational only; append-only audit rows are retained and no files are deleted or repaired by this endpoint.
- Successful package creation refreshes the visible history immediately.
- Added a regression proving page order participates in the assembly snapshot hash and out-of-band reorder is detected as `integrity_error` after review submission.
- Added integration coverage for missing/restored package files while preserving the audit record.
- Verification: backend 359 passed; syntax 10 sources + 4 declarations / 0 errors; Lookbook structural 19/19; helper 12; API 64/64; request body 15 checked / 0 findings; response 52 JSON / 53 endpoints / 29 models; request-contract tests 2 passed; package integrity 0 findings; Python compileall passed.
- No new routes, DB schema, migrations, dependencies, Provider/credit/publication/rights behavior. Actual React/Three browser E2E and semantic TypeScript remain unverified due missing trusted packages and typings.
