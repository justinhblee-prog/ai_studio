# BUILD-00183 Verification Report

## Provenance and package input
- Input: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00182.zip`.
- SHA-256 sidecar validation: PASS.
- ZIP CRC validation: PASS.
- Fresh extraction performed into an empty BUILD-00183 working directory.

## Fresh test evidence

### Backend
- All 52 backend `test_*.py` files were executed successfully.
- **367 passed, 0 failed, 0 skipped.**
- The first seven four-file groups passed (282 tests). The eighth combined group stalled without reporting a test failure; the files in that group and all subsequent files were then run individually. Every individual run completed successfully.
- Do not interpret the combined group stall as an application test failure or as a successful combined invocation. See `build183_logs/backend_grouped_test_results.log`, `group8_verbose_diagnostic.log`, `backend_remaining_individual.log`, and `backend_final_individual.log`.
- Backend `python3 -m compileall -q app tests scripts`: PASS.

### Viewer
- Dependency-free JavaScript test scripts: 17 passed.
- Actual Three.js resource integration: BLOCKED because the declared `three` package is not installed or cached locally.
- Viewer Python test scripts: 7 passed.
- TypeScript syntax/transpile: 10 source files + 14 declaration parses, 0 syntax errors. This is not a semantic typecheck.
- API contract: 63/63 calls matched.
- Request contract: 15 JSON body calls checked, 0 findings.
- Response contract: 50 JSON endpoints documented across 52 routes; 0 missing routes/schemas.
- Package integrity: 0 findings.
- Viewer Python compileall: PASS.

### Dependencies and browser runtime
- Local dependency-cache inspection found no installed/cached `three`, React, or TypeScript packages in the inspected local module locations.
- BUILD-00182 recorded exact `three@0.180.0` npm registry lookup failure (`EAI_AGAIN`). No network retry was made in this build.
- Chromium WebGL2 capability probe from BUILD-00182 remains the latest runtime evidence: WebGL2 context unavailable. It is not a React/Three.js E2E test.

## Verdict
All 367 backend tests and all dependency-free Viewer/contract checks passed. The package is integrity-verified. Actual Three.js integration and browser/GPU/device acceptance remain blocked or unverified; the project is not declared fully production-accepted.

## Delivery status
- Local ZIP and SHA-256 sidecar verified successfully. Library upload was attempted but all six operations were rejected with `throttled` (retry window reported as 7 hours). No Library upload is claimed.
