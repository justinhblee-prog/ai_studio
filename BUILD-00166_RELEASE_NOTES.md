# BUILD-00166 Release Notes

## Scope
Harden optional error-callback handling in the React 3D Viewer.

## Changes
- Added `src/notifyViewerError.mjs` and its TypeScript declaration. The helper accepts an optional callback, invokes it with the safe user-facing message, and returns a boolean result. Missing/non-function callbacks and callbacks that throw are isolated.
- Routed all five production `onErrorRef` notification sites in `Studio3DViewer.tsx` through the helper. This prevents consumer callback exceptions from escaping renderer initialization fallback, animation/context lifecycle error handlers, GLTF parse errors, and download failures.
- Added seven dependency-free unit assertions and updated the Viewer cleanup lifecycle structural test to verify all five production call sites use the helper.

## Compatibility / risk
- No API, database, provider, credit, publication, rights, deployment, dependency-version, or lockfile changes.
- Existing callback signature and user-facing messages are unchanged. Callback failures are intentionally best-effort and do not replace the viewer's own error state.
