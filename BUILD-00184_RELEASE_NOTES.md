# BUILD-00184 Release Notes

## Scope
Fresh verification refresh of the BUILD-00183 source baseline. No application runtime source, API behavior, dependency manifest, dependency version, or lockfile was changed.

## Input integrity
- Restored `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00183.zip` from the Library.
- SHA-256 sidecar validation: PASS.
- ZIP CRC validation: PASS.
- Extracted into a clean BUILD-00184 workspace.

## Fresh verification
- Backend: all 52 `test_*.py` files passed in 13 direct four-file pytest groups: **367 passed, 0 failed, 0 skipped**.
- Backend pytest shard-runner diagnostic: an 8-file subset passed 8/8 files and 24/24 tests (19.64 seconds). This confirms the runner works for the sampled files; it does not establish that a full 52-file wrapper run is reliable.
- Viewer JavaScript: 17 dependency-free scripts passed. The actual Three.js resource integration script remains blocked because `three` is unavailable.
- Viewer Python: 7 scripts passed.
- TypeScript syntax/transpile: 10 source files + 14 declaration parses, 0 syntax errors. This is not a semantic typecheck.
- API contract: 63/63 calls matched.
- Request contract: 15 JSON body calls checked, 0 findings.
- Response contract: 50 JSON endpoints documented across 52 routes, 0 missing routes/schemas.
- Package integrity: 0 findings.
- Viewer and backend Python compileall: PASS.

## Dependency and browser diagnostics
- Local search found no installed/cached `three`, React, ReactDOM, TypeScript, `@types/react`, or `@types/three` packages in inspected module/cache locations.
- Exact registry probe `npm view three@0.180.0 version` failed with DNS `EAI_AGAIN registry.npmjs.org`; no dependency installation or version/lockfile change was made.
- Chromium capability probe: Chromium executable present, resize observation works, but WebGL2 context unavailable. Probe scope is browser capability smoke only; it does not load the React/Three.js Viewer.

## Acceptance gates still open
- Actual Three.js resource integration and semantic TypeScript typecheck.
- Authenticated React Viewer browser E2E.
- Actual WebGL2 renderer creation and context-loss/restoration.
- GPU stress, repeated model replacement/unmount under a real renderer, and target-device performance.
- Full 52-file wrapper orchestration reliability. All backend tests passed through direct grouped invocations; the 8-file runner diagnostic passed.

## Package
Full source and handoff package: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00184.zip`.

## Delivery
BUILD-00184 is packaged locally with a SHA-256 sidecar and verified ZIP CRC. Library upload is not attempted in this build because the most recent Library operation reported a seven-hour throttling window; the retry window has not elapsed.
