# BUILD-00170 Release Notes

## WebGL context-listener registration rollback hardening

- Hardened `attachWebGLContextLifecycle()` when registering the `webglcontextrestored` fails after the `webglcontextlost` listener has already been attached.
- Partial-registration rollback now retries removal of the first listener once, with a strict two-attempt bound.
- If listener removal remains blocked, the helper throws an `AggregateError` containing the original registration failure and cleanup failures rather than hiding a potentially leaked listener.
- Added regression coverage for transient rollback success and persistent rollback failure reporting.
- No dependency versions, lockfiles, API contracts, database schemas, providers, deployment settings, or external services were changed.

## Verification

- 14 dependency-free Viewer JavaScript test scripts passed (including the expanded WebGL lifecycle suite).
- 7 Viewer Python test scripts passed.
- Backend pytest: 367 passed.
- TypeScript syntax/transpile, API/request/response contracts, package integrity, and Python compileall passed.
- Three.js integration and semantic TypeScript remain blocked by missing dependencies; the bounded npm registry probe failed with `EAI_AGAIN`.
- Headless Chromium starts and exposes ResizeObserver/requestAnimationFrame, but WebGL2 context creation remains unavailable. This is not a React/Three.js E2E pass.
