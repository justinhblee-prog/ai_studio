# BUILD-00187 Release Notes

## Scope
Fresh dependency/runtime blocker investigation, source review, and verification refresh. No application runtime source, API behavior, dependency manifest, dependency versions, or lockfiles were changed. No production change was justified by the available executable evidence.

## Verification highlights
- Input BUILD-00186 ZIP SHA-256 and ZIP CRC verified before clean extraction.
- Backend: 52 test files, **367 passed / 0 failed / 0 skipped**. Per-file shard logs retained. The first grouped invocation exceeded the outer execution window after eight files; the remaining files were rerun in smaller groups and every test file passed.
- Viewer JavaScript: all 17 dependency-free scripts passed; `test_three_resource_integration.mjs` remains blocked because `three` is not installed.
- Viewer Python: 7 scripts passed.
- TypeScript syntax/transpile: 10 source files + 14 declaration parses, 0 syntax errors. This is not a semantic typecheck.
- API contract: 63/63; request contract: 15 JSON body calls / 0 findings; response contract: 50 JSON endpoints across 52 routes and 28 models / 0 missing routes or schemas; package integrity: 0 findings.
- Backend and Viewer Python compileall passed.

## Dependency and browser investigation
- Local/global Node module locations and likely package directories were searched; no usable `three`, React/ReactDOM runtime package, or React/Three type packages were found. A React static bundle exists inside Jupyter's UI assets, but it is not a project dependency installation and cannot substitute for a validated React package tree. No package was copied into the project.
- Two additional Chromium SwiftShader/ANGLE launch variants were tested. Both returned `webgl2: false`, with no renderer/vendor. The existing full browser capability probe also remains blocked at WebGL2 context creation.
- No dependency or lockfile was modified, and no false claim of a real Three.js/browser E2E test is made.

## Explicitly unverified
- Semantic React/Three.js TypeScript typecheck.
- Actual Three.js resource integration test.
- Authenticated React browser E2E.
- Real WebGLRenderer context-loss/restoration in a WebGL2-capable browser.
- GPU stress, repeated model replacement/unmount under a real renderer, and target-device performance.
- Real external AI generation and end-to-end production workflow acceptance.

## Delivery
Full source and verification evidence are packaged in `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00187.zip` with a SHA-256 sidecar. Local archive integrity is verified. Library upload availability is not asserted in this build.
