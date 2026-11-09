# BUILD-00189 Release Notes

## Scope
Fresh dependency/runtime investigation, 3D viewer source review, and full verification refresh. The previous BUILD-00188 archive SHA-256 and ZIP CRC were verified before extraction into a clean BUILD-00189 workspace.

No production application source, API behavior, dependency manifest, dependency version, or lockfile was changed. No speculative dependency stubs or unverified vendored packages were introduced.

## Verification
- Backend: all 52 test files passed; **367 individual tests passed, 0 failed**. Every file has a retained per-file pytest log. Two larger orchestration commands were terminated by the outer execution window after partial progress; the remaining files were rerun in smaller isolated groups. The interrupted wrapper invocations are not counted as successful runs.
- Viewer JavaScript: **17 dependency-free scripts passed**. The 18th script, `test_three_resource_integration.mjs`, remains blocked because the declared `three` package is unavailable.
- Viewer Python: **7 scripts passed**.
- WebGL lifecycle regression: prior 71 assertions remain in BUILD-00188 evidence; BUILD-00189 reran the browser capability probe successfully under Xvfb.
- Browser capability smoke: WebGL2 context, rendered triangle pixel, ResizeObserver, requestAnimationFrame, context loss and restoration passed.
- TypeScript syntax/transpile: 10 source files + 14 declaration parses, 0 syntax errors.
- API contract: 63/63; request contract: 15 JSON body calls checked / 0 findings; response contract: 50 JSON endpoints across 52 routes and 28 models / 0 missing routes or schemas; package integrity: 0 findings.
- Viewer and backend Python compileall passed.

## Dependency and runtime findings
- Project declares `three: ^0.180.0`, React/ReactDOM peer dependencies `>=18.2.0`, and `@types/react`, `@types/three`, TypeScript development dependencies.
- No usable project-local or global `three`, React/ReactDOM dependency tree, or React/Three type packages were found. npm cache has no matching entries.
- A fresh DNS/network probe could not resolve `registry.npmjs.org` (`curl: (6) Could not resolve host`). Installing exact dependencies is therefore blocked in this execution environment.
- `xvfb-run -a python3 scripts/probe_browser_runtime.py` again passed. This is browser WebGL capability smoke only and does not mount the React/Three.js viewer.

## Source review
Reviewed `Studio3DViewer.tsx`, `webglContextLifecycle.mjs`, GLTF loading/commit/cancellation, and resource disposal/cleanup ordering. Existing deterministic lifecycle and rollback tests remain green. No reproducible defect requiring a production source change was found in the reviewed paths.

## Explicitly unverified
- Semantic TypeScript check (`tsc --noEmit`) due unavailable React/Three dependencies.
- Actual Three.js resource integration.
- Authenticated React Viewer browser E2E and actual GLTF/GLB model loading.
- Three.js renderer-level context-loss/restoration and repeated model replacement/unmount under the renderer.
- GPU stress, target-device performance, and external real AI-generation end-to-end acceptance.

## Next priorities
1. Run in a network-enabled or pre-populated dependency environment and acquire exact package versions while preserving package/lock consistency.
2. Run semantic TypeScript check and the actual Three.js resource integration test.
3. Mount the actual React Viewer in Chromium under Xvfb and verify authenticated GLTF loading, replacement, unmount cleanup, and renderer recovery.
4. Continue through GPU/device performance and real AI generation acceptance.

See `BUILD-00189_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00189.md`, and `build189_logs/`.

## Library delivery
- Created Library folder `/AI_CREATOR_STUDIO/BUILD-00189` successfully.
- Uploads of the ZIP, SHA-256 sidecar, handoff, verification, release notes, and inventory were all rejected with `throttled`; the Library service reported that the upload limit will reset in 4 hours.
- No BUILD-00189 files were uploaded to Library. Do not interpret folder creation as successful file delivery; retry only after the reported cooldown.
