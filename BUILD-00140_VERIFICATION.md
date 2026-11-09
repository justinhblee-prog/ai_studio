# BUILD-00140 Verification Report

## Results

| Check | Result |
|---|---:|
| Lookbook preview recovery structural assertions | 15/15 PASS |
| Lookbook signed-link / stale-preview helper assertions | 12 PASS |
| KeyedRequestGate | 7 assertions PASS |
| RequestScopeGate | 7 assertions PASS |
| Project lifecycle event helper | 4 assertions PASS |
| TypeScript syntax/transpilation | 10 `.ts`/`.tsx` sources + 4 `.d.mts` declarations; 0 errors |
| Viewer API contract | 63/63 matched |
| Request body contract | 15 checked; 0 findings |
| Response schema contract | 51 JSON endpoints across 52 method/path endpoints; 28 models; 0 missing routes/schemas |
| Viewer contract/validator tests | 2 passed |
| Package integrity | 0 findings |
| Python compileall | PASS |
| Backend full pytest | 359 passed |
| Clean ZIP extraction verification | PASS (see `BUILD-00140_CLEAN_EXTRACT_VERIFICATION.md`) |

## Clean extraction

The final source package was extracted into a fresh directory and re-tested: Lookbook structural 15/15, helper 12 assertions, TypeScript syntax 10 sources + 4 declarations / 0 errors, package integrity 0 findings, API 63/63, request body 15/0 findings, response 51 JSON / 52 endpoints / 28 models, viewer contract tests 2 passed, and backend 359 passed in 15.17s. See `BUILD-00140_CLEAN_EXTRACT_VERIFICATION.md`.

## Implemented behavior

- Lookbook preview requests are bound to the exact `asset_id` and `asset_version_id` of each attached output item. State is keyed by output item, latest-request sequencing prevents superseded requests from applying, and current-scope checks reject stale workspace responses.
- Preview URL expiry is displayed. URL issuance failures and image-load failures clear the stale URL and expose a manual retry. Delayed `onError` events are ignored unless the failed URL is still the current URL for that output item.
- Package UI now distinguishes the signed URL's 15-minute `expires` timestamp from the package record's 24-hour `expires_at` retention deadline.
- ZIP download uses a signed-link expiry preflight and `cache: no-store` fetch; errors are surfaced. A fresh internal ZIP and signed link can be created explicitly after expiry or failure.
- No immutable AssetVersion, checksum, provenance, assembly approval, or rights/publication state is mutated by preview/download recovery. The backend assembly integration test now verifies that preview URL refresh leaves the attached `asset_id`, `asset_version_id`, and checksum unchanged, and that the approved package manifest and ZIP page filename preserve the exact immutable asset/version identity and Product Variant snapshot.

## Evidence logs

- `BUILD-00140_LOOKBOOK_PREVIEW_RECOVERY_STRUCTURAL.log`
- `BUILD-00140_LOOKBOOK_SIGNED_LINK_TEST.log`
- `BUILD-00140_KEYED_REQUEST_GATE_TEST.log`
- `BUILD-00140_SCOPE_GATE_TEST.log`
- `BUILD-00140_PROJECT_LIFECYCLE_TEST.log`
- `BUILD-00140_TYPESCRIPT_SYNTAX.log`
- `BUILD-00140_API_CONTRACT.log`
- `BUILD-00140_REQUEST_CONTRACT.log`
- `BUILD-00140_RESPONSE_CONTRACT.log`
- `BUILD-00140_VIEWER_TESTS.log`
- `BUILD-00140_PACKAGE_INTEGRITY.log`
- `BUILD-00140_PYTHON_COMPILE.log`
- `BUILD-00140_BACKEND_PYTEST.log`

## Explicitly unverified

- Semantic TypeScript `tsc --noEmit` and actual React/Three.js browser component E2E remain unverified because trusted dependencies and typings are unavailable.
- Browser-driven signed preview expiry/image retry and actual ZIP Blob download are not covered by a real browser component E2E.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.

No live Provider calls, paid APIs, production data changes, destructive migrations, publication, rights grants or deployment were performed.
