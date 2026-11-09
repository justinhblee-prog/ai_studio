# BUILD-00175 Release Notes

## Recovery provenance
This build is reconstructed from the latest complete source package actually present in the AI_CREATOR_STUDIO Library: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00166.zip`. The previously discussed BUILD-00167 through BUILD-00174 archives were not present in the Library or current execution filesystem during this session. This release does not claim to contain those unavailable changes.

## Change
- Hardened `src/animationFrameController.mjs` against `requestFrame()` throwing during initial or subsequent scheduling.
- A scheduler failure now atomically clears `running` and `pendingFrameId` before notifying the optional error callback.
- Error-notification callback failures remain isolated and cannot leave the controller reporting a healthy/running loop when no next frame exists.
- Extended `scripts/test_animation_frame_controller.mjs` with scheduler-failure, state-reset, idempotent-stop, and throwing-diagnostic regression coverage.

## Rationale
The WebGL context lifecycle uses the animation controller's `running` state to determine whether rendering resumed after context restoration. A thrown frame-scheduler call previously could leave `running === true` despite there being no pending animation frame, falsely signaling a healthy render loop.

## Scope
No dependency versions or lockfiles were changed. No claim is made that real browser/WebGL restoration, React E2E, GPU behavior, or actual Three.js resource integration was exercised.
