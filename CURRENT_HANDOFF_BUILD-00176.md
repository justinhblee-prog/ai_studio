# Current Handoff — BUILD-00176

## Verified baseline

BUILD-00176 is a continuation from BUILD-00175. BUILD-00175 itself was recovered from the latest complete Library source archive found in the active Library, BUILD-00166. The previously reported BUILD-00167–00174 archives were not available in the active Library/runtime and are not assumed to be incorporated.

## BUILD-00176 changes

`animationFrameController.mjs` now assigns a generation token to each start/stop lifecycle. Stale callbacks from an older generation are ignored. This closes a reentrancy edge case where a render callback could synchronously stop and restart the controller, after which the old callback could schedule a second RAF chain. Regression suite: 34 assertions.

## Fresh verification

- Viewer JS: 13 passed; 1 Three.js integration test blocked by missing `three` package.
- Viewer Python: 7 passed.
- Backend: 367 passed.
- TypeScript syntax/transpile: 10 source + 13 declarations, 0 errors.
- API 63/63; request/response contracts clean; package integrity clean; compileall passed.

## Outstanding acceptance gates

1. Restore the missing BUILD-00167–00174 source deltas from an authoritative source if they become available.
2. Install exact declared React/Three.js dependencies in an approved network-enabled/cached environment without changing declared versions or lockfiles.
3. Run semantic TypeScript checks and actual Three.js resource integration.
4. Run React Viewer browser E2E with authenticated GLTF fixtures.
5. Exercise actual WebGLRenderer context loss/restoration and GPU resource stress.
6. Measure performance on target devices.

## Provenance correction (BUILD-00177)

A later Library-root audit located the BUILD-00167–00174 archives that were missed by the earlier folder-scoped lookup. BUILD-00177 restores those deltas from BUILD-00174 and reapplies the BUILD-00175/00176 animation changes. See `RECOVERY_AUDIT_BUILD-00177.md`.
