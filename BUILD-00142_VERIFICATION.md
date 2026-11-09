# BUILD-00142 Verification Report

## Automated results

| Check | Result |
|---|---:|
| Backend full pytest | 361 passed |
| Python compileall | PASS |
| Viewer structural source checks | 140 passed |
| Lookbook signed-link/stale-preview helpers | 12 passed |
| KeyedRequestGate | 7 passed |
| RequestScopeGate | 7 passed |
| Project lifecycle event helper | 4 passed |
| TypeScript syntax/transpilation | 10 source + 4 declaration parses, 0 errors |
| Viewer API contract | 64/64 matched |
| Request body contract | 15 checked, 0 findings |
| Response contract | 52 JSON / 53 endpoints / 29 models, 0 missing |
| Viewer request-contract tests | 2 passed |
| Package integrity | 0 findings |
| Browser capability smoke (Xvfb) | PASS: WebGL2, rendered triangle readback, ResizeObserver, animation frame |
| Semantic TypeScript `tsc --noEmit` | BLOCKED: React and React typings unavailable |

## Security regression details

- No Authorization header on signed ZIP download returns 401.
- A current workspace viewer can download a valid signed URL.
- Removing that viewer from `workspace_members` makes the same still-valid signed URL return 404; re-adding membership restores access.
- A symlink substituted for the package file returns 409 even if the target contains identical package bytes.
- Existing invalid-signature, expiry, tampered-package checksum, package-size, and private response checks remain covered.
- Package audit records remain append-only and are not removed by cleanup.

## Cleanup observability

- Dry-run JSON exposes `mode`, `limit`, `candidate_count`, `inspected`, `would_remove`, `removed`, `missing`, `invalid_paths`, `non_regular`, `failed`, `partial_failure`, `audit_rows_retained`, `duration_ms`, and `completed_at`.
- Partial file failures produce `partial_failure: true` and exit code 2; remaining candidates continue to be processed.
- Dry-run remains the default; deletion requires explicit `--apply`.

## Browser and type-check limitations

- The browser capability probe passed under `xvfb-run`, but explicitly does not load the React/Three.js Viewer. Component E2E and actual ZIP Blob download remain unverified.
- Semantic TypeScript typecheck was attempted and blocked by missing `react`, `react/jsx-runtime`, and React type declarations. Separate syntax/transpilation checks passed.

## Not verified

PostgreSQL runtime/multi-host integration, Android build/device tests, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants, and deployment.

No live Provider calls, paid APIs, credit charges, publication, rights grants, destructive migrations, production data changes, or deployment were performed.
