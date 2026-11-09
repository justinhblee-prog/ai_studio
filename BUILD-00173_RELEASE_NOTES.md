# BUILD-00173 Release Notes

## Scope
Harden the GLTF parse-failure lifecycle and make cancellation behavior directly executable in dependency-free regression tests.

## Changes
- Added `src/reportGltfParseError.mjs` as the single owner-aware transition for GLTF parse failures.
- The helper exits before any UI state mutation or consumer notification when its request has been cancelled.
- Wired `Studio3DViewer.tsx`'s non-abortable `GLTFLoader.parse` error callback through the helper.
- Added `scripts/test_report_gltf_parse_error.mjs` with 8 assertions covering stale failure suppression, active failure reporting, optional consumers, and exactly-once notification.
- Registered `npm run test:report-gltf-parse-error`.
- Updated the authenticated GLTF source-contract test to assert the shared cancellation guard.

## Compatibility and safety
No API, database, provider, credit, publication, rights, deployment, dependency version, or lockfile changes. No external resource fetching behavior changed.

## Verification
See `BUILD-00173_VERIFICATION.md` and `build173_logs/`.
