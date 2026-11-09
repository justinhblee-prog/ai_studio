# BUILD-00167 Release Notes

## Scope
Continued the 3D Viewer lifecycle audit from BUILD-00166. No application source behavior was changed in this build; this is a verification and handoff build.

## Verified
- Viewer dependency-free JavaScript test scripts: 13 passed.
- Viewer Python structural/contract test scripts: 7 passed.
- Backend pytest: 367 passed.
- ZIP integrity of the BUILD-00166 input archive: passed before extraction.

## Outstanding / blocked
- `scripts/test_three_resource_integration.mjs` is blocked because the declared `three` package is not installed (`ERR_MODULE_NOT_FOUND`).
- React/Three.js semantic TypeScript check and browser E2E remain unverified.
- GPU stress and target-device performance remain unverified.

## Lifecycle audit finding
The Viewer setup effect creates scene, camera, renderer, lights, stage resources, controls, observer, and context lifecycle before returning its cleanup function. An exception in an intermediate setup operation can occur before React receives the cleanup callback. This potential partial-initialization leak is not claimed fixed in BUILD-00167. Next work should introduce a transactional setup/rollback boundary with deterministic tests, preserving all existing disposal semantics.

## Change policy
No API, database, provider, credits, publication, rights, deployment, dependency-version, or lockfile changes.
