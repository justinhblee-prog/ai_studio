# BUILD-00139 Verification Report

## Summary

| Check | Result |
|---|---:|
| Structural source checks | 140/140 PASS |
| KeyedRequestGate behavior | 7 assertions PASS |
| RequestScopeGate behavior | 7 assertions PASS |
| TypeScript syntax/transpilation | 10 `.ts`/`.tsx` sources + 3 `.d.mts` declarations; 0 errors |
| Viewer API contract | 63/63 matched |
| Request body contract | 15 checked; 0 findings |
| Response schema contract | 51 JSON endpoints across 52 method/path endpoints; 28 models; 0 missing routes/schemas |
| Viewer contract/validator/package tests | 8 passed |
| Package integrity | 0 findings |
| Python compileall | PASS |
| Backend full pytest | 359 passed in 15.11s (clean extraction 15.18s) |
| Clean ZIP extraction verification | PASS (see `BUILD-00139_CLEAN_EXTRACT_VERIFICATION.md`) |

## Implemented behavior

- Photo Draft preview state is keyed by the exact immutable `asset_id:version_id` pair. A retry obtains a fresh signed preview URL; response `expires_at` is retained and shown in the UI. Failed image loading clears only the still-current failed URL and exposes a manual reissue action.
- Output Review preview state is keyed by output ID while the preview request itself uses the exact immutable asset and version returned by that output's review record. Missing asset/version references and signed URL issuance failures are visible per output.
- Output Review automatic preview hydration and manual retries share `KeyedRequestGate`; stale automatic results cannot overwrite a newer manual retry. A delayed image error from an older URL is ignored if the current URL has changed.
- Preview recovery does not change the output's AssetVersion, checksum, provenance, review state, or any rights/publication status.

## Evidence logs

- `BUILD-00139_STRUCTURAL.log`
- `BUILD-00139_KEYED_REQUEST_GATE_TEST.log`
- `BUILD-00139_SCOPE_GATE_TEST.log`
- `BUILD-00139_TYPESCRIPT_SYNTAX.log`
- `BUILD-00139_API_CONTRACT.log`
- `BUILD-00139_REQUEST_CONTRACT.log`
- `BUILD-00139_RESPONSE_CONTRACT.log`
- `BUILD-00139_VIEWER_PYTEST.log`
- `BUILD-00139_PACKAGE_INTEGRITY.log`
- `BUILD-00139_PYTHON_COMPILE.log`
- `BUILD-00139_BACKEND_PYTEST.log`

## Explicitly unverified

- Semantic TypeScript `tsc --noEmit` and actual React/Three.js component browser E2E. Trusted React/Three.js packages and typings remain unavailable in the environment.
- Browser-driven expired-signature image fetch/retry behavior is covered structurally and by request-gate tests but has not been exercised in a real React component E2E.
- PostgreSQL runtime/multi-host integration, Android build/device testing, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment.

No live Provider calls, paid APIs, production data changes, destructive migrations, publication, rights grants or deployment were performed.
