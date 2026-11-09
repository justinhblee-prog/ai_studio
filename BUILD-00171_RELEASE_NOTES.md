# BUILD-00171 Release Notes

## GLTF parse-result commit rollback

- Added `finalizeGltfLoad.mjs` and its declaration file to make the synchronous GLTF scene-commit phase transactional.
- Late GLTF parse results arriving after model replacement or unmount are routed through rollback and disposed rather than attached to the scene.
- If scene traversal, bounds calculation, scene attachment, animation setup, or camera fitting throws during commit, rollback removes any partially attached model, stops/uncaches a published mixer, clears matching refs, and disposes the GLTF resources.
- AnimationMixer ownership is published immediately after construction, before clip actions are configured, so a partial clip-setup failure is included in rollback.
- Consumer `onLoad` callback exceptions are isolated after a successful commit and cannot leave the UI stuck in loading or invalidate the committed model.
- Added `test_finalize_gltf_load.mjs` with 18 assertions covering successful commit, stale/cancelled result disposal, commit failure rollback, and rollback-failure reporting.
- Updated authenticated GLTF loading and Viewer cleanup structural checks to assert the new lifecycle contract.

## Compatibility and safety

- No API, database, provider, authentication, credits, publication, deployment, dependency version, or lockfile changes.
- Declared React/Three.js dependency versions were not changed.
