# AI CREATOR STUDIO — Current Handoff BUILD-00162

## Resume point

Continue from BUILD-00162. Do not restart completed work or mark blocked checks as passed. Next priority is obtaining the exact declared dependencies in an approved network-enabled or pre-populated environment, then running the real Three.js integration and React Viewer E2E gates.

## Completed in BUILD-00162

1. WebGL listener teardown now becomes inert immediately when disposal is requested.
2. Tracks listener attachment independently; failed removals can be retried without re-removing listeners already detached.
3. `disposed` becomes true only after both listener removals succeed; successful disposal remains idempotent.
4. Added transient listener-removal retry regression tests. WebGL lifecycle suite: 45 assertions passed.
5. All 12 dependency-free Viewer `.mjs` suites passed (the real Three.js integration gate is intentionally excluded because its dependency is missing).
6. All 7 Viewer Python test scripts passed.
7. Backend suite: 367 passed in 21.92s.

## Still incomplete

P0 — dependency environment
- `three` ^0.180.0, React, React DOM and corresponding type packages are not installed in this environment.
- npm registry/cache access previously failed (`EAI_AGAIN` / `ENOTCACHED`). Do not alter declared versions or lockfiles to work around this.
- Semantic TypeScript check remains blocked.

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

- `npm install` (network-enabled/cached environment; preserve declared versions and lockfiles)
- `npm run typecheck`
- `npm run test:three-resource-integration`
- `npm run test:webgl-context-lifecycle`

From `ai_creator_studio_backend_starter`:

- `PYTHONPATH=. pytest -q`

## Scope constraints

No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes. See `BUILD-00162_RELEASE_NOTES.md` and `BUILD-00162_VERIFICATION.md`.
