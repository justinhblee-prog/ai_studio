# AI CREATOR STUDIO — Current Handoff BUILD-00158

## Current state

- Latest source baseline: BUILD-00157.
- Current increment: BUILD-00158 — cross-pass GPU resource ownership guard and real Three.js integration test gate.
- `disposeGltfResources` uses a module-lifetime `WeakSet` to prevent the same resource object from receiving repeated `dispose()` calls across separate cleanup passes.
- Regression test confirms cross-pass idempotency (3 assertions).
- Real Three.js integration test has been added and is wired to `npm run test:three-resource-integration`.
- Existing Viewer cleanup structural test updated to match the extracted animation-frame controller.

## Verification

Passed: disposer suite, Viewer lifecycle integration (32 assertions), Viewer cleanup structural/diagnostic tests, authenticated GLTF loading (15/15), animation frame controller (19 assertions), syntax check of real Three.js integration test.

Blocked: real Three.js integration execution because the container has no installed `three` package and npm registry resolution failed with `EAI_AGAIN`. This is explicitly recorded as blocked, not passed.

## Next work

1. In an environment with npm registry access, install the declared Viewer dependencies and run `npm run test:three-resource-integration`.
2. Run the full Viewer test suite and semantic TypeScript check.
3. Add actual React Viewer + authenticated GLTF fixture browser E2E.
4. Exercise WebGL context loss/restore and repeat mount/unmount/model-replacement stress.
5. Profile GPU resource counts on target browsers/devices.

## Constraints

No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes were made in BUILD-00158.

Additional verification: backend full pytest **367 passed**; Viewer TypeScript syntax/transpile **10 source + 11 declaration parses, 0 errors**; package integrity **0 findings**.


> Superseded by BUILD-00159. See `CURRENT_HANDOFF_BUILD-00159.md`. BUILD-00159 makes the Three.js integration test fail non-zero when its dependency is missing and adds a cross-pass failed-disposal regression.
