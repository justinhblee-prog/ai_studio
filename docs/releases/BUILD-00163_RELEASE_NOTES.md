# BUILD-00163 Release Notes

## Scope

Continues the 3D Viewer WebGL lifecycle hardening from BUILD-00162. This increment integrates a bounded listener-removal retry into the actual React Viewer cleanup path and records a fresh dependency/test-environment audit. No API, DB, Provider, credits, publication, rights, production-data, deployment, dependency-version, or lockfile changes were made.

## Changes

- Added `disposeWebGLContextLifecycleWithRetry(lifecycle, maxAttempts)` with a strict 1–5 attempt bound (production Viewer uses 2 attempts).
- Integrated the bounded retry into `Studio3DViewer`'s one-shot React effect cleanup. A persistent failure is surfaced to the existing cleanup diagnostics instead of silently treating a `false` return as successful cleanup.
- Added tests for transient failure recovery, avoiding a second removal of an already-detached listener, idempotent completion, persistent failure, and invalid retry bounds.
- WebGL lifecycle suite now covers 53 assertions.
- Re-audited dependency availability. The global TypeScript compiler exists, but React, React DOM, Three.js and their type packages are not installed or cached. A bounded registry metadata request failed with `EAI_AGAIN`; no dependency or lockfile was changed.

## Compatibility and constraints

- Runtime dependency declarations remain unchanged (`three: ^0.180.0`, React/React DOM peer dependencies `>=18.2.0`).
- No package lockfile was present in the Viewer package; no lockfile was created or changed.
- The bounded retry is synchronous and finite; it introduces no timer, browser API, or background retry loop.
