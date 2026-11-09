# AI CREATOR STUDIO — Current Handoff BUILD-00165

## Resume point

Continue from BUILD-00165. Do not restart completed work. Highest-priority acceptance gate remains dependency provisioning for the exact declared React/Three.js packages in a network-enabled or approved cached environment.

## Completed in BUILD-00165

1. Guarded `THREE.WebGLRenderer` construction in `Studio3DViewer.tsx`. If WebGL/GPU initialization throws, the component now clears scene/camera refs, presents an actionable Korean error state, and safely invokes optional `onError` without allowing a consumer callback exception to break fallback UI.
2. Added five structural regression assertions for constructor failure handling.
3. All 12 dependency-free Viewer `.mjs` suites passed.
4. All 7 Viewer Python test scripts passed. Cleanup structural: 18/18; disposal diagnostic integration: 4/4; WebGL lifecycle: 53 assertions.
5. Backend: 367 passed in 19.49s.
6. TypeScript syntax/transpile: 10 source files + 12 declarations, 0 syntax errors.
7. Fresh contracts: API 63/63; response 0 missing routes/schemas; request 0 findings; package integrity 0 findings.

## Still incomplete / blocked

P0 — exact dependencies
- `three` ^0.180.0 and React/React DOM peer dependencies, plus `@types/react` and `@types/three`, are absent.
- `npm run typecheck` was executed and is blocked by missing React/Three.js modules and type declarations. Semantic typecheck is not passed.
- Actual Three.js integration was executed and exits non-zero with `ERR_MODULE_NOT_FOUND` for `three`.
- No dependency versions, package manifest, or lockfile changed.

P1 — real Viewer E2E
- Mount React Viewer in Chromium with actual React/Three.js.
- Load authenticated GLTF fixture; capture pixels and console/network errors.
- Replace model, unmount, and verify abort/cleanup.

P2 — renderer/GPU lifecycle
- Exercise context recovery through an actual Three.js WebGLRenderer.
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

No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes. See `BUILD-00165_RELEASE_NOTES.md` and `BUILD-00165_VERIFICATION.md`.
