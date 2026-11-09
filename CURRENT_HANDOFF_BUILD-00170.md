# AI CREATOR STUDIO — Current Handoff BUILD-00170

## Baseline
- Built from `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00169.zip`.
- Baseline SHA-256 verified: `4d6db42ab4599968c9b654f18c22a108ce41ff7f208696ecb6de5c00272993a5`.
- Baseline ZIP integrity check passed.

## Build result
BUILD-00170 hardens transactional WebGL context-listener registration. If attaching the restoration listener fails after the loss listener was attached, the helper retries rollback removal once. Persistent rollback failure is surfaced as an `AggregateError` carrying the original registration failure and cleanup failures. Retry attempts are strictly bounded.

## Fresh verification
- 14 dependency-free Viewer JavaScript scripts passed.
- 7 Viewer Python scripts passed.
- Backend pytest: 367 passed.
- WebGL context lifecycle suite: 57 assertions passed.
- Resource rollback suite: 19 assertions passed.
- TypeScript syntax/transpile: 10 source files + 13 declaration files, 0 errors.
- API contract: 63/63; request contract: 15 checked / 0 findings; response contract: 50 JSON endpoints across 52 endpoints / 0 missing; package integrity: 0 findings; Python compileall passed.

## Blockers / remaining acceptance work
- Three.js integration remains blocked: declared `three` package is absent (`ERR_MODULE_NOT_FOUND`). A bounded npm registry probe failed with `EAI_AGAIN`; no dependency or lockfile was modified.
- Semantic typecheck remains blocked by absent `react` and `@types/react` declarations.
- Chromium launches headlessly and supports requestAnimationFrame/ResizeObserver, but WebGL2 is unavailable in this runtime. React Viewer E2E and actual WebGLRenderer context recovery are not verified.
- GPU stress and target-device performance remain unverified.

## Next work
1. Obtain exact declared React/Three.js packages in a network-enabled or approved cached environment without changing versions/lockfiles.
2. Run semantic typecheck and actual Three.js resource integration.
3. Enable a WebGL2-capable Chromium runtime and run React Viewer E2E with authenticated GLTF fixtures.
4. Exercise real renderer context loss/restoration, partial initialization failures, and repeated model replacement/unmount.
5. Run GPU stress and target-device performance acceptance.

## Safety boundaries
No API, DB, provider, credits, publication, rights, deployment, dependency version, or lockfile changes.
