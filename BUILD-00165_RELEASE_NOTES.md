# BUILD-00165 Release Notes

## Scope

Hardening the real Three.js Viewer initialization failure path. No product/API/DB/provider/credits/publication/deployment or dependency-version changes.

## Change

`ai_creator_studio_3d_viewer/src/Studio3DViewer.tsx`

- Guarded `new THREE.WebGLRenderer(...)` because construction can throw when WebGL is unavailable, browser context quotas are exhausted, or GPU initialization fails.
- On constructor failure, the Viewer now clears the scene/camera refs, sets a Korean actionable error state, calls the optional consumer error callback on a best-effort basis, and returns before registering renderer-dependent resources.
- A consumer `onError` callback throwing does not suppress the fallback UI.
- Added structural regression assertions for the guarded constructor and fallback path.

## Verification

- All 12 dependency-free Viewer `.mjs` suites passed, including cleanup, lifecycle, request, download, and WebGL lifecycle tests.
- All 7 Viewer Python test scripts passed.
- Viewer cleanup structural check: 18/18; disposal diagnostic integration: 4/4.
- WebGL context lifecycle suite: 53 assertions passed.
- Backend: 367 passed in 19.49s.
- TypeScript syntax/transpile validation: 10 TS/TSX files + 12 declaration files, 0 syntax errors.
- API contract: 63/63 matched; response contract: 50 JSON endpoints documented across 52 endpoints, 0 missing routes/schemas; request contract: 8 source files, 15 JSON-body calls, 0 findings; package integrity: 0 findings.

## Blocked / unverified

- `npm run typecheck` remains blocked by absent `react`, `react/jsx-runtime`, `three`, Three.js addons, and React/Three.js type declarations. The resulting implicit-any/JSX errors are dependency-cascade diagnostics; semantic typecheck is not passed.
- Actual Three.js resource integration exits non-zero with `ERR_MODULE_NOT_FOUND` for `three`.
- React Viewer browser E2E, actual Three.js renderer context-loss recovery, GPU stress/resource telemetry, and target-device performance remain unverified.
- No package manifest, dependency version, or lockfile was changed; no dependencies could be acquired in this environment.

## Artifacts

- `BUILD-00165_VERIFICATION.md`
- `CURRENT_HANDOFF_BUILD-00165.md`
- `BUILD-00165_*` verification logs
