# BUILD-00164 Release Notes

## Scope

Continues the 3D Viewer lifecycle hardening from BUILD-00163. This increment fixes a diagnostic visibility gap: cleanup failures were collected by `runViewerCleanupSteps` but discarded by both production call sites. Cleanup now forwards its complete error summary to a best-effort diagnostic callback, and both React Viewer teardown paths report failures to the console without allowing a broken diagnostic sink to interrupt cleanup.

No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes were made.

## Changes

- Extended `runViewerCleanupSteps(steps, onError?)` with an optional diagnostic callback, invoked once after all cleanup steps when one or more operations fail.
- Diagnostic callback exceptions are isolated; later cleanup steps still run and the structured result is still returned.
- Wired the full Viewer unmount cleanup and previous-model replacement cleanup to report collected failures through `console.error`.
- Updated the `.d.mts` declaration and added regression coverage for diagnostic payload delivery, callback timing, and callback failure isolation.
- Viewer cleanup runtime suite: 14 assertions passed; lifecycle structural checks: 13/13 plus 4 disposal-diagnostic integration checks.

## Validation

- All 12 dependency-free Viewer `.mjs` suites passed. The actual Three.js integration suite is excluded because `three` is unavailable.
- All 7 Viewer Python test scripts passed.
- WebGL lifecycle suite: 53 assertions passed.
- API contract: 63/63; response contract: 50 JSON endpoints documented across 52 endpoints, 0 missing routes/schemas; request contract: 15 JSON-body calls, 0 findings; package integrity: 0 findings.
- TypeScript syntax/transpile: 10 TS/TSX source files and 12 declaration files, 0 syntax errors.
- Backend: `PYTHONPATH=. pytest -q` — 367 passed in 20.01s.
- `npm run typecheck` remains blocked by missing React/Three.js modules and declarations. The real Three.js integration test fails closed with `ERR_MODULE_NOT_FOUND` for `three`.
- Dependency audit: no local `node_modules`, no matching npm cache entries, no global React/Three.js packages; bounded registry lookup failed with `EAI_AGAIN registry.npmjs.org`.

## Still unverified

Actual Three.js resource integration, semantic TypeScript checking, React Viewer browser E2E, real WebGLRenderer context-loss recovery, GPU stress/resource telemetry, and target-device performance. These are not represented as passing.
