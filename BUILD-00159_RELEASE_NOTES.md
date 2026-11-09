# BUILD-00159 — Strict Three.js Integration Gate & Disposal Failure Policy

## Summary

BUILD-00159 closes a false-green test condition in the real Three.js resource integration test and adds an explicit regression for cross-pass cleanup after a resource disposal exception. It also records the corrected browser capability probe invocation and the actual full backend test result.

## Changes

- `scripts/test_three_resource_integration.mjs` no longer exits successfully when the `three` dependency is missing. The test now emits a clear BLOCKED diagnostic and exits non-zero, preventing a skipped integration test from being counted as passed.
- Added a regression for a texture whose `dispose()` throws: the first pass reports the error, the material cleanup still proceeds, and the second pass does not repeat the failed resource side effect.
- No production runtime behavior, API, database, provider, credit, publication, rights, deployment, dependency version, or lockfile changes.

## Verification

Passed:

- Backend pytest: **367 passed in 31.60s**.
- Viewer dependency-free executable tests: animation frame controller 19 assertions; authenticated preview object URLs 5; bounded download runtime 17/17; GLTF disposal suite including new failed-dispose cross-pass policy; keyed request gate 7; lookbook preview links 12; model base path 10/10; project lifecycle events 4; request scope gate 7; viewer cleanup runtime 10; viewer lifecycle integration 32.
- Viewer Python checks: authenticated GLTF loading 15/15; bounded download/recovery 19/19; lookbook recovery 19/19; API contract validator unit tests 2; package integrity unit tests 4; cleanup lifecycle 13/13 plus diagnostics 4/4; request contract unit tests 2.
- Viewer source/contract checks: API contract 63/63; response contract 50 JSON endpoints across 52 endpoints, 28 models, zero missing routes/schemas; request contract 15 checked calls, zero findings; package integrity zero findings; structural source validation 143 checks; TypeScript syntax/transpile 10 source + 11 declaration parses, zero errors.
- Chromium WebGL2 capability smoke under `xvfb-run`: WebGL2 context, shader compile/link, triangle pixel, animation frame, ResizeObserver, and raw WebGL context loss/restore all passed (renderer reported `WebKit WebGL`).
- ZIP integrity: passed after packaging.

Blocked / not verified:

- `npm run test:three-resource-integration` now correctly exits non-zero because `three` is not installed in this container. npm registry access previously failed with `EAI_AGAIN`; no dependency or lockfile changes were made.
- Semantic TypeScript check (`tsc --noEmit`) remains blocked by absent React/Three.js type dependencies. Syntax/transpile checks are not a substitute.
- Chromium capability smoke is not a React/Three.js Viewer E2E test. Authenticated GLTF rendering, model replacement/unmount in a live browser, WebGL context-loss recovery, GPU memory profiling, and target-device stress remain unverified.

## Test gate behavior

The Three.js integration command is intentionally a hard dependency gate. A dependency-missing result is a failure/blocker, never a pass or skip. Run `npm install` in a network-enabled environment, then `npm run test:three-resource-integration`.
