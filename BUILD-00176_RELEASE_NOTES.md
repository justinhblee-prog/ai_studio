# BUILD-00176 Release Notes

## Baseline and scope

- Built transparently from the complete BUILD-00175 package, whose source recovery baseline was the latest Library archive actually available, BUILD-00166.
- No claim is made that unavailable BUILD-00167 through BUILD-00174 source changes were recovered.

## Changes

- Hardened `animationFrameController.mjs` with a generation token for each start/stop lifecycle.
- A stale animation callback that arrives after stop is ignored.
- A render callback that synchronously stops and restarts the controller cannot cause the previous callback to create a duplicate animation-frame chain.
- Scheduler/render failures invalidate the owning generation and keep the controller stopped before isolated error reporting.
- Expanded `test_animation_frame_controller.mjs` to 34 assertions, including reentrant restart and late stale callback scenarios.

## Known limitations

- Actual Three.js resource integration remains blocked because the declared `three` dependency is not installed in this runtime.
- React semantic typecheck, React browser E2E, actual WebGLRenderer context loss/restoration, GPU stress, and target-device performance remain unverified.
