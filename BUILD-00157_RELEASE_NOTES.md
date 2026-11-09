# BUILD-00157 — Animation Loop Failure Isolation & Browser Capability Baseline

## Summary

BUILD-00157 continues the Viewer lifecycle work from BUILD-00156. It extracts the `requestAnimationFrame` chain into a small lifecycle controller and integrates that controller into `Studio3DViewer`.

## Changes

- Added `ai_creator_studio_3d_viewer/src/animationFrameController.mjs` and its TypeScript declaration.
- Added idempotent start/stop, one-pending-frame ownership, restart support, render-error isolation, and guarded error reporting.
- Replaced the inline recursive RAF loop in `Studio3DViewer` with the controller; teardown now stops the owned loop through the existing failure-isolated cleanup runner.
- Added `scripts/test_animation_frame_controller.mjs` and `npm run test:animation-frame-controller`.
- Updated the BUILD-00157 roadmap, handoff, validation report, and test evidence.

## Verification

- Backend full pytest: 367 passed.
- Viewer source structural checks: 143 passed.
- Viewer lifecycle integration: 32 assertions passed.
- Animation frame controller: 19 assertions passed.
- Cleanup helper: 10 assertions passed; GLTF disposal and failure-isolation suites passed.
- API contract: 63/63; request contract: 15 calls checked, 0 findings; response contract: 50 JSON endpoints / 52 endpoints / 28 models, 0 missing schemas/routes.
- Package integrity: 0 findings; TypeScript syntax/transpile checks: 0 errors.
- Chromium WebGL2 capability smoke under Xvfb/SwiftShader: pass (WebGL2, triangle draw, ResizeObserver, requestAnimationFrame).

## Explicit limitations

- Actual Three.js runtime objects, React Viewer mount, authenticated GLTF visual rendering, model replacement in a browser, GPU memory/leak profiling, and WebGL context-loss recovery were not verified.
- `npm run typecheck` remains blocked because React, Three.js, and typings are not installed. An npm dependency installation attempt timed out; no lockfile or dependency-version changes were made.
- Browser capability smoke is not React/Three Viewer E2E.

## Scope boundary

No API, database, dependency version, Provider, credit, publication, rights, production-data, or deployment changes.
