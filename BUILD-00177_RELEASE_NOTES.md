# BUILD-00177 Release Notes

## Scope — source recovery, integration, and regression hardening

BUILD-00177 corrects an incomplete-source packaging issue discovered during a Library-wide audit. BUILD-00167 through BUILD-00174 archives were present in the Library root, although an earlier folder-scoped lookup had not surfaced them. BUILD-00174 is the recovered source baseline for this build. BUILD-00175 and BUILD-00176 are retained as later animation-loop changes and their source/test updates are integrated on top of BUILD-00174.

## Recovered source changes

- **BUILD-00167:** lifecycle audit and partial-initialization leak finding; no application behavior change.
- **BUILD-00168:** transactional rollback for partial React Three.js Viewer initialization (`resourceRollback.mjs`), including reverse-order disposer registration and setup-failure cleanup.
- **BUILD-00169:** immediate OrbitControls rollback ownership registration; headless Chromium capability probe improvements.
- **BUILD-00170:** bounded rollback/retry for partial WebGL context-listener registration failures, with aggregate error reporting for persistent cleanup failure.
- **BUILD-00171:** transactional GLTF parse-result commit/rollback (`finalizeGltfLoad.mjs`), including stale-result disposal and partial scene/mixer rollback.
- **BUILD-00172:** stale, non-abortable GLTF parse error callback suppression.
- **BUILD-00173:** shared owner-aware GLTF parse error transition (`reportGltfParseError.mjs`) and focused regression tests.
- **BUILD-00174:** keyed model-request ownership across fetch, parse success/failure, and effect cleanup, preventing stale model callbacks from mutating the active Viewer.
- **BUILD-00175:** animation scheduler exceptions atomically stop the owning loop and clear pending frame state before error notification.
- **BUILD-00176:** generation-token protection against callbacks from stopped generations and duplicate RAF chains after synchronous stop/restart.

## BUILD-00177 changes

- Rebased the packaged source on the recovered BUILD-00174 archive, rather than the incomplete BUILD-00166-derived source tree used by the prior BUILD-00175/00176 package attempts.
- Retained the BUILD-00176 animation-frame controller implementation and expanded its regression suite to 46 assertions.
- Added checks for stale callbacks arriving after a newer generation starts, cancellation exceptions leaving the controller stopped with no phantom frame id, and error callbacks that synchronously restart the controller.
- No production API, backend, database, provider, credits, publication, deployment, dependency-version, or lockfile changes were made in BUILD-00177 itself; the recovered application source changes are those recorded in BUILD-00168–00176.

## Verification summary

- Viewer JavaScript: 17 dependency-free scripts passed; actual Three.js integration remains blocked by the missing `three` package.
- Viewer Python scripts: 7 passed.
- Backend: 367 tests passed; Python compileall passed.
- TypeScript syntax/transpile: 10 source files + 14 declaration files, 0 syntax errors.
- API contract: 63/63 matched; request contract: 15 JSON body calls, 0 findings; response contract: 50 JSON endpoints documented across 52, 0 missing routes/schemas; package integrity: 0 findings.
- Semantic React typecheck is blocked by missing `react` and its type declarations. Browser React E2E, actual WebGLRenderer context restoration, GPU stress, and target-device performance remain unverified.

## Provenance correction

The earlier BUILD-00175/00176 notes stated that BUILD-00167–00174 archives were unavailable. That statement reflected a folder-scoped lookup that missed the Library-root uploads. BUILD-00177 located and materialized the root-level archives, verified their ZIP integrity, and restored their source changes. The earlier notes are retained as historical records; this release is the corrected integrated source package.
