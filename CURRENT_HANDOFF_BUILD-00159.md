# AI CREATOR STUDIO — Current Handoff BUILD-00159

## Current baseline

- Source baseline: BUILD-00158.
- Current increment: BUILD-00159 — strict Three.js integration dependency gate and disposal-failure cross-pass regression.
- Build-00159 is a validation-integrity increment; it does not claim the real Three.js integration has passed.

## Completed in BUILD-00159

1. Real Three.js integration test now fails non-zero if `three` is absent; no more successful skip.
2. Added regression proving a throwing resource dispose is attempted once globally, its error is reported on first pass, later resources are still disposed, and later passes do not repeat the failed side effect.
3. Re-ran the complete backend suite: 367 passed in 31.60s.
4. Re-ran dependency-free Viewer tests and contract/structural checks; see `BUILD-00159_VERIFICATION.md`.
5. Ran Chromium WebGL2 capability smoke with Xvfb/SwiftShader; capability test passed.

## Remaining work (not complete)

P0 — Environment/dependency gate
- Provide a network-enabled or approved cached dependency environment. Install the declared package dependencies without changing versions/lockfiles unless separately reviewed.
- Run `npm run test:three-resource-integration` and `npm run typecheck`; record exact output.

P1 — Real Viewer browser E2E
- Mount the React Viewer in Chromium with real Three.js runtime.
- Load an authenticated GLTF fixture, capture render output and console/network errors.
- Replace model, unmount, and verify request cancellation and cleanup.

P2 — GPU lifecycle
- Test WebGL context lost/restored behavior.
- Repeat mount/unmount and model replacement; measure renderer/resource counts and memory trends.
- Run target browser/device performance tests.

## Important distinction

Chromium WebGL2 capability smoke is not a React/Three.js E2E. TypeScript syntax/transpile is not semantic typechecking. The Three.js integration test is currently blocked and must not be reported as passed.

## Scope constraints

No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes were made.
