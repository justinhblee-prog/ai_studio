# AI CREATOR STUDIO — Current Handoff BUILD-00164

## Resume point

Continue from BUILD-00164. The next highest-priority gate remains obtaining the exact declared React/Three.js packages in a network-enabled or approved cached environment, then running real Three.js integration and React Viewer E2E. Do not restart completed work or mark blocked checks as passed.

## Completed in BUILD-00164

1. Fixed cleanup diagnostic loss: `runViewerCleanupSteps` now accepts an optional error callback and sends it the complete result after all teardown steps finish when failures occurred.
2. Both production cleanup call sites in `Studio3DViewer.tsx` now report cleanup failures using best-effort `console.error`. Diagnostic sink exceptions are isolated and cannot abort cleanup.
3. Updated the `.d.mts` declaration and added tests for diagnostic payload delivery, callback timing, and callback exception isolation.
4. Viewer cleanup runtime: 14 assertions; cleanup lifecycle structural: 13/13; disposal diagnostic integration: 4/4.
5. All 12 dependency-free Viewer `.mjs` suites and all 7 Viewer Python test scripts passed. WebGL lifecycle suite: 53 assertions.
6. Fresh contract checks: API 63/63; response 0 missing routes/schemas; request 0 findings; package integrity 0 findings.
7. TypeScript syntax/transpile validation: 10 source files + 12 declaration files passed.
8. Backend suite: 367 passed in 20.01s.

## Still incomplete

P0 — dependency environment
- `three` ^0.180.0 and React/React DOM peer dependencies, plus `@types/react` and `@types/three`, are not installed or cached.
- Global TypeScript 5.8.3 is present, but `npm run typecheck` is blocked by missing modules and declarations.
- Bounded registry metadata request failed with `EAI_AGAIN registry.npmjs.org`.
- No package versions, package manifest, or lockfile was changed.

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

No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes. See `BUILD-00164_RELEASE_NOTES.md` and `BUILD-00164_VERIFICATION.md`.
