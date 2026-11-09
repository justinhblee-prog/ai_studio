# AI CREATOR STUDIO — Current Handoff BUILD-00160

## Resume point

The project was paused at BUILD-00159. Continue from the remaining acceptance gates in `ROADMAP_BUILD-00157.md`; do not restart completed work or mislabel blocked checks as passed.

## Completed in BUILD-00160

1. Implemented WebGL context-loss and restoration lifecycle helper.
2. Wired the helper into `Studio3DViewer` after Three.js renderer construction so the renderer's own restoration listener is registered first.
3. Stops RAF and clock on loss; prevents default context loss; resizes and restarts after restoration.
4. Keeps the context in a lost state when resize/restart fails, allowing a later restore event to retry.
5. Adds visible Viewer status during context loss and removes listeners during teardown.
6. Added TypeScript declaration and package test script.
7. Added 27 helper assertions plus 5 production wiring/cleanup assertions.
8. Backend suite: 367 passed. Viewer lifecycle/contract/package checks passed. Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader.

## Still incomplete

P0 — dependency environment
- npm registry resolution fails with `EAI_AGAIN registry.npmjs.org`.
- `three`, React, and type dependencies are absent; `npm run typecheck` and actual Three.js integration cannot pass until dependencies are installed in an approved network-enabled or cached environment.

P1 — real Viewer E2E
- Mount React Viewer in Chromium with actual Three.js.
- Load authenticated GLTF fixture; capture pixels and console/network errors.
- Replace model, unmount, and verify abort/cleanup.

P2 — renderer/GPU lifecycle
- Test context recovery through an actual Three.js WebGLRenderer, not only browser capability smoke and lifecycle helper.
- Repeat model replacement/mount/unmount; measure renderer/resource counts and memory trends.
- Run target-device performance checks.

## Exact commands

From `ai_creator_studio_3d_viewer`:

- `npm install` (network-enabled/cached environment; preserve declared versions and do not alter lockfiles without review)
- `npm run typecheck`
- `npm run test:three-resource-integration`
- `npm run test:webgl-context-lifecycle`

From `ai_creator_studio_backend_starter`:

- `PYTHONPATH=. pytest -q`

## Scope constraints

No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes.

See `BUILD-00160_RELEASE_NOTES.md` and `BUILD-00160_VERIFICATION.md`.

> Superseded by `CURRENT_HANDOFF_BUILD-00161.md`. Continue from BUILD-00161; its verification report records the new exceptional-path tests and remaining dependency/E2E blockers.
