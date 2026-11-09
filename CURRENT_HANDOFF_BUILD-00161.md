# AI CREATOR STUDIO — Current Handoff BUILD-00161

## Resume point

Resume from BUILD-00161 and the remaining acceptance gates in `ROADMAP_BUILD-00157.md`. Do not restart completed work or mislabel blocked checks as passed.

## Completed in BUILD-00161

1. Hardened WebGL loss handling so animation-loop stop failure does not prevent clock stop or the loss callback.
2. Isolated diagnostic callback failures.
3. Made event-listener registration transactional with rollback if restore-listener registration fails.
4. Made listener teardown best-effort across both WebGL events.
5. Added regression tests for all three exceptional paths; WebGL lifecycle suite now has 37 assertions.
6. Re-ran all 12 dependency-free Viewer JavaScript suites and all 7 Viewer Python scripts; all passed.
7. Re-ran backend suite: 367 passed in 21.12s.
8. API/response/request contracts, package integrity, TypeScript syntax parsing, Python compilation, and Chromium raw WebGL2 capability smoke passed.

## Still incomplete

P0 — dependency environment
- `three`, React, and React type packages remain absent.
- Online npm installation did not complete in the bounded attempt; offline installation failed with `ENOTCACHED`.
- Semantic TypeScript check remains blocked by missing dependencies.

P1 — real Viewer E2E
- Mount React Viewer in Chromium with actual Three.js.
- Load authenticated GLTF fixture; capture pixels and console/network errors.
- Replace model, unmount, and verify abort/cleanup.

P2 — renderer/GPU lifecycle
- Test context recovery through an actual Three.js WebGLRenderer, not only browser capability smoke and lifecycle helper doubles.
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

See `BUILD-00161_RELEASE_NOTES.md` and `BUILD-00161_VERIFICATION.md`.
