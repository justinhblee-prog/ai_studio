# BUILD-00168 Release Notes

## Scope
Implemented transactional rollback for partial initialization of the React Three.js Viewer. The goal is to ensure resources acquired before a React effect returns its normal cleanup callback are released if a later setup step throws.

## Production changes
- Added `src/resourceRollback.mjs`, a small transaction-scoped disposer stack. Disposers are registered immediately after acquisition, run in reverse acquisition order, and are failure-isolated. `commit()` clears the stack after successful setup so normal unmount teardown remains governed by the existing cleanup runner.
- Integrated rollback into `Studio3DViewer.tsx` for scene resources, renderer, inserted canvas, key-light shadow, OrbitControls, ResizeObserver, WebGL context listeners, animation loop, and viewer references.
- Renderer-construction failure now rolls back the scene/camera setup before returning the existing actionable WebGL error state.
- Any later synchronous setup failure triggers best-effort rollback, an actionable Korean error state, and the existing failure-isolated consumer error callback.
- Added `scripts/test_resource_rollback.mjs` with reverse-order, idempotency, commit, disposer-failure isolation, ownership-transfer release, and seven setup failure-injection positions (17 assertions).
- Added the `test:resource-rollback` package script and extended Viewer cleanup structural checks.

## Fresh verification
- Viewer dependency-free JavaScript scripts: 14 passed (the actual Three.js integration script is excluded because `three` is not installed).
- Viewer Python scripts: 7 passed.
- Backend pytest: 367 passed.
- TypeScript syntax/transpile validation: 10 TS/TSX source files + 13 declaration files, 0 errors.
- API contract: 63/63 calls matched; no missing calls, query mismatches, or unresolved dynamic segments.
- Request contract: 15 JSON body calls checked; 0 findings. Request structural tests: 2 passed.
- Response contract: 50 JSON endpoints documented across 52 endpoints; 0 missing routes/schemas or unresolved dynamic segments.
- Package integrity: 0 findings.

## Blocked / not verified
- `scripts/test_three_resource_integration.mjs` was attempted and is blocked by `ERR_MODULE_NOT_FOUND` for the declared `three` package.
- React/Three.js semantic typecheck, browser React E2E, actual WebGLRenderer context recovery, GPU stress, and target-device performance remain unverified.
- No claim is made that failure injection exercised a real browser or actual Three.js resource objects; it exercises the dependency-free rollback helper and static integration contract.

## Change boundaries
No API, database, provider, credits, publication, rights, deployment, dependency-version, or lockfile changes. Existing normal teardown sequence and cleanup runner remain in place.
