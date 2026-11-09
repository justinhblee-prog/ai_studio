# AI CREATOR STUDIO — Current Handoff BUILD-00178

Active continuation point: **BUILD-00178**. This build continues from BUILD-00177, which restored the Library-root BUILD-00167–00174 archives and retained the later scheduler hardening.

## Latest change

`ai_creator_studio_3d_viewer/src/webglContextLifecycle.mjs` now protects WebGL context restoration against reentrant context-loss events. Recovery uses a generation token and checks ownership after clock restart, resize, and animation-loop restart. A nested restore event is ignored while recovery is in progress. Disposal invalidates pending recovery.

Regression tests were added to `scripts/test_webgl_context_lifecycle.mjs` for reentrant loss during resize, reentrant loss during animation-loop restart, and duplicate nested restore events.

## Verification

- 17 dependency-free Viewer JavaScript test scripts passed; actual Three.js integration test blocked by missing `three` dependency.
- Viewer Python: 7 scripts passed.
- Backend: 367 pytest tests passed; compileall passed.
- TypeScript syntax/transpile: 10 source + 14 declaration parses, 0 errors (not semantic typecheck).
- API 63/63; request contract 15 JSON-body calls, 0 findings; response contract 50 JSON endpoints across 52 routes, 0 missing; package integrity 0 findings.

## Remaining acceptance work

1. Install exact declared React/Three.js dependencies in an approved network-enabled or cached environment without changing package versions, then run semantic typecheck and actual Three.js integration.
2. Run React Viewer E2E in a WebGL2-capable browser with authenticated GLTF fixtures.
3. Exercise actual renderer context loss/restoration, repeated replacement/unmount, GPU stress, and target-device performance.

See `BUILD-00178_RELEASE_NOTES.md`, `BUILD-00178_VERIFICATION.md`, and `build178_logs/`.
