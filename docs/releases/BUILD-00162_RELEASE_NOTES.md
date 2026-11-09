# BUILD-00162 Release Notes

## Scope

Continues the 3D Viewer lifecycle acceptance work from BUILD-00161. This increment fixes retry semantics for WebGL event-listener teardown after transient host removal failures. No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes were made.

## Changes

- WebGL lifecycle disposal now becomes immediately inert once disposal is requested, preventing callbacks from running while cleanup is pending.
- Tracks loss/restoration listeners independently and retries only listener removals that previously threw.
- `disposed` is true only after both listeners are confirmed removed; repeated successful disposal is idempotent.
- Added regression coverage for transient removal failure, retry completion, and not repeating already successful listener removal.
- WebGL lifecycle suite now passes 45 assertions.

## Compatibility

No runtime dependencies or lockfiles changed. The declared Three.js version remains `^0.180.0`.
