# BUILD-00161 Release Notes

## Scope

Continues the paused 3D Viewer acceptance work from BUILD-00160. This increment hardens WebGL context event handling and teardown under exceptional browser/event-target behavior. No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes were made.

## Changes

- Isolated animation-loop stop, clock stop, and loss callback failures so one failing operation does not suppress the remaining loss handling.
- Added a safe diagnostic reporter so an exception thrown by the `onError` callback cannot interrupt lifecycle handling.
- Made context listener registration transactional: if registering the restore listener fails, the already-registered loss listener is rolled back.
- Made listener teardown best-effort across both event listeners; failure removing one listener no longer prevents attempting the other.
- Added regression coverage for stop failures, listener registration rollback, and partial listener-removal failures.
- Expanded WebGL lifecycle test coverage from 27 to 37 assertions (including Viewer wiring/teardown contracts).

## Compatibility

No runtime dependencies or lockfiles changed. The declared Three.js version remains `^0.180.0`.
