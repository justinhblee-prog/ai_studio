# BUILD-00158 — Cross-pass GPU Resource Ownership & Three.js Integration Gate

## Summary

BUILD-00158 hardens GLTF resource teardown against duplicate disposal across separate lifecycle cleanup passes and adds an executable integration suite using real Three.js classes.

## Changes

- `disposeGltfResources` now tracks attempted resource objects in a module-level `WeakSet`.
- Repeated cleanup paths cannot emit duplicate Three.js `dispose` events for the same object during the module lifetime.
- Added a cross-pass idempotency regression test (3 assertions).
- Added `scripts/test_three_resource_integration.mjs`, which constructs real `Scene`, `Mesh`, `SkinnedMesh`, `BufferGeometry`, `MeshStandardMaterial`, `Texture`, `Bone`, and `Skeleton` instances and verifies dispose events and repeated-pass behavior.
- Added `npm run test:three-resource-integration`.
- Updated the stale viewer-cleanup structural test to locate the BUILD-00157 animation-frame controller teardown instead of the removed inline render callback.

## Verification

Passed in this environment:

- GLTF disposer legacy/resource graph tests, including cross-pass idempotency.
- Viewer lifecycle integration: 32 assertions.
- Viewer cleanup structural + disposal diagnostic integration: 17 assertions.
- Authenticated GLTF loading checks: 15/15.
- Animation frame controller: 19 assertions.
- New real Three.js integration test syntax check.

Blocked / not verified:

- Real Three.js integration execution: skipped because `three` is not installed in the execution container.
- `npm install` attempted without changing dependency versions or lockfiles; it failed with `EAI_AGAIN` resolving `registry.npmjs.org`.
- No claim is made that real Three.js object disposal passed. Run `npm install` followed by `npm run test:three-resource-integration` in an environment with npm registry access.
- Browser React/GLTF E2E, GPU memory profiling, and context-loss recovery remain outstanding.

## Scope boundary

No API, database, Provider, credit, publication, rights, production-data, deployment, or dependency-version changes. No lockfile was generated.
