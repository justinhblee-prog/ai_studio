# BUILD-00155 — Viewer Renderer Teardown Resilience

## Changes
- Added dependency-free `runViewerCleanupSteps.mjs` and typed declaration.
- Renderer teardown now runs each cleanup operation independently: frame cancellation, observer disconnection, controls disposal, animation stop/root uncache, GLTF/stage cleanup, shadow target disposal, renderer disposal, canvas removal, and reference clearing.
- Model replacement uses the same failure-isolated sequencing for model removal, mixer stop/root uncache, GLTF disposal, and reference clearing.
- Cleanup returns attempted/completed counts and named error diagnostics; a failing step cannot suppress later independent cleanup.
- Added runtime failure-injection coverage and structural lifecycle-order assertions.
- Added `npm run test:viewer-cleanup`.

## Boundaries
No dependency installation, lockfile changes, API/schema/DB changes, Provider calls, credit operations, publication, rights grants, production-data changes, or deployment.
