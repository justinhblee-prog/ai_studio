# BUILD-00178 Release Notes

## WebGL context restoration reentrancy hardening

- Added a lifecycle generation token to WebGL context recovery. A restore transaction checks ownership after each host-controlled operation (`clock.start`, `resize`, and `animationLoop.start`).
- A new context-loss event dispatched reentrantly during restoration invalidates the in-flight restore operation, stops the clock/loop again, and remains authoritative.
- Added a `restoring` guard to suppress nested duplicate restoration events while one recovery transaction is active.
- Disposal invalidates any in-flight recovery generation before listener teardown.
- Added regression coverage for context loss triggered by resize, context loss triggered by animation-loop restart, and nested duplicate restore dispatch.

This build continues from the recovered and integrated BUILD-00177 source baseline. No dependency versions or package lockfiles were changed.
