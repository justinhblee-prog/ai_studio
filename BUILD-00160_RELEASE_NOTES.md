# BUILD-00160 Release Notes

## Scope

Resumed the paused 3D Viewer lifecycle roadmap from BUILD-00159. This increment implements WebGL context-loss/restoration handling without changing API, DB, provider, credits, publication, rights, production data, deployment, dependency versions, or lockfiles.

## Changes

- Added `webglContextLifecycle.mjs` to bind `webglcontextlost` and `webglcontextrestored` to the Viewer animation loop and clock.
- Context loss calls `preventDefault`, stops the animation loop, stops the clock, and exposes a recoverable status overlay.
- Context restoration restarts the clock, resizes the renderer, and restarts the animation loop.
- Failed restoration remains in the lost state and can be retried by a later restore event; it is not reported as recovered.
- Added idempotent listener teardown and wired it into the Viewer cleanup sequence after animation-frame cancellation.
- Added `webglContextLifecycle.d.mts` for strict TypeScript consumers.
- Added 27 helper assertions and 5 production wiring/teardown contract assertions.
- Added `npm run test:webgl-context-lifecycle`.

## Compatibility

No dependency or lockfile changes. Existing API and backend behavior are unchanged.
