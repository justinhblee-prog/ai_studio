# BUILD-00184 Verification Report

## Provenance and package input
- Input archive: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00183.zip`, restored from Library.
- SHA-256 sidecar validation: PASS.
- ZIP CRC validation: PASS.
- Fresh extraction into an empty BUILD-00184 workspace: PASS.

## Backend
- Enumerated 52 backend `test_*.py` files.
- Executed 13 direct pytest groups of four files each.
- Group results: 150, 54, 14, 21, 15, 10, 18, 8, 16, 14, 16, 17, 14.
- **Total: 367 passed, 0 failed, 0 skipped.**
- Backend `python3 -m compileall -q app tests scripts`: PASS.
- Runner diagnostic: eight selected files passed in the isolated shard runner (8/8 files, 24 tests, 19.64s). The full 52-file runner was not run as one invocation; do not infer full-wrapper reliability from this sample.

## Viewer
- Dependency-free JavaScript scripts: 17 passed.
- Actual Three.js resource integration: BLOCKED because the declared `three` package is not installed or cached.
- Viewer Python scripts: 7 passed.
- TypeScript syntax/transpile: 10 source files + 14 declaration parses, 0 syntax errors. This does not replace `tsc --noEmit` semantic typechecking.
- API contract: 63/63 calls matched; no missing calls, query mismatches, or unresolved dynamic segments.
- Request contract: 15 JSON body calls checked, 0 findings.
- Response contract: 50 JSON endpoints documented across 52 routes; 0 missing routes/schemas and 0 unresolved dynamic segments.
- Package integrity: 0 findings.
- Viewer Python compileall: PASS.

## Dependencies
- No installed or cached copies of `three`, `react`, `react-dom`, `typescript`, `@types/react`, or `@types/three` were found in the inspected locations.
- Exact npm registry probe for `three@0.180.0` failed with `EAI_AGAIN` resolving `registry.npmjs.org`.
- No dependency versions, package manifests, or lockfiles were changed.

## Browser capability
- Chromium executable found at `/usr/bin/chromium`.
- Browser capability probe reported `webgl2: false`, `renderer: null`, and `error: WebGL2 context unavailable`.
- Resize observation succeeded. This is only a capability smoke test and does not load React or Three.js.

## Verdict
The source package and all available dependency-free automated checks are verified. All 367 backend tests passed. Production acceptance is **not complete** because actual Three.js integration, semantic TypeScript checking, authenticated React browser E2E, WebGL2 renderer recovery, GPU stress, and target-device performance remain blocked or unverified.

## Logs
See `build184_logs/` for grouped pytest output, per-script Viewer results, TypeScript/contract validators, dependency probe, browser capability probe, and compileall records.
