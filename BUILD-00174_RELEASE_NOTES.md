# BUILD-00174 Release Notes

## Scope
Strengthen asynchronous GLTF model replacement ownership so every fetch and parser completion is validated against the currently active model request.

## Changes
- Added a `KeyedRequestGate` owner token to `Studio3DViewer`'s model-loading effect.
- Fetch completion, fetch failure, GLTF parse success, and GLTF parse failure now verify the same request identity before mutating viewer state or committing a scene.
- Effect cleanup invalidates the model owner synchronously before aborting the fetch. This also invalidates callbacks from `GLTFLoader.parse`, which is not abortable.
- Added `test_viewer_model_request_ownership.mjs` with 13 assertions for rapid replacement, stale parse success rollback, stale parse failure suppression, active newest-request commit, and unmount invalidation.
- Added npm script `test:viewer-model-request-ownership`.
- Updated the authenticated GLTF source-contract test to require owner-token invalidation and validation.

## Compatibility and safety
No API, database, provider, credit, publication, rights, deployment, dependency version, or lockfile changes. Existing authenticated fetch and immutable AssetVersion behavior remain unchanged.

## Verification
See `BUILD-00174_VERIFICATION.md` and `build174_logs/`.
