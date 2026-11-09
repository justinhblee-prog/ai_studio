# AI CREATOR STUDIO — Current Handoff BUILD-00163

## Resume point

Continue from BUILD-00163. Do not restart completed work or mark blocked checks as passed. The next highest-priority gate remains obtaining the exact declared React/Three.js packages in a network-enabled or approved cached environment, then running real Three.js integration and React Viewer E2E.

## Completed in BUILD-00163

1. Added `disposeWebGLContextLifecycleWithRetry` with a strict maximum of five attempts; production `Studio3DViewer` uses two synchronous attempts during React effect cleanup.
2. If both attempts fail, cleanup throws a descriptive error so `runViewerCleanupSteps` records the failure instead of silently counting a `false` return as completed.
3. Added regression tests for transient removal failure, only retrying the failed listener, idempotent completion, persistent failure bounds, and invalid attempt limits.
4. WebGL lifecycle suite: 53 assertions passed.
5. All 12 dependency-free Viewer `.mjs` suites passed; all 7 Viewer Python test scripts passed.
6. Fresh Viewer contract validation passed: API 63/63, response 0 missing routes/schemas, request 0 findings, package integrity 0 findings.
7. TypeScript syntax/transpile validation passed (10 source files + 12 declaration files).
8. Backend suite: 367 passed in 22.75s.

## Still incomplete

P0 — dependency environment
- `three` ^0.180.0 is declared but not installed/cached. React and React DOM peer dependencies and `@types/react`, `@types/three` are also unavailable.
- Global TypeScript 5.8.3 is present, but `npm run typecheck` is blocked by missing React/Three modules and declarations.
- Bounded npm registry probe failed with `EAI_AGAIN registry.npmjs.org`.
- Do not change dependency declarations or fabricate local stubs to claim semantic typecheck or renderer integration.

P1 — real Viewer E2E
- Mount React Viewer in Chromium with actual Three.js.
- Load authenticated GLTF fixture; capture pixels and console/network errors.
- Replace model, unmount, and verify abort/cleanup.

P2 — renderer/GPU lifecycle
- Test context recovery through an actual Three.js WebGLRenderer.
- Stress repeated model replacement/mount/unmount; measure renderer/resource counts and memory trends.
- Run target-device performance checks.

## Exact commands

From `ai_creator_studio_3d_viewer`:

- `npm install` (network-enabled/approved cached environment; preserve declared versions)
- `npm run typecheck`
- `npm run test:three-resource-integration`
- `npm run test:webgl-context-lifecycle`

From `ai_creator_studio_backend_starter`:

- `PYTHONPATH=. pytest -q`

## Scope constraints

No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes. See `BUILD-00163_RELEASE_NOTES.md` and `BUILD-00163_VERIFICATION.md`.
