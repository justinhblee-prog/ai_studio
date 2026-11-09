# BUILD-00123 Release Notes

- Adds an optional Playwright/Chromium browser capability probe for WebGL2 context creation, shader compile/link, triangle rendering/readback, ResizeObserver and requestAnimationFrame.
- Adds `npm run probe:browser-runtime` and an optional pinned dependency file `ai_creator_studio_3d_viewer/requirements-browser-audit.txt`; no runtime app dependencies changed.
- Verified under Xvfb/SwiftShader with Chromium 144: WebGL2, triangle pixel readback, ResizeObserver and requestAnimationFrame all pass.
- This is not React/Three.js Viewer E2E and does not verify GLTF model loading. Actual Viewer E2E remains blocked by unavailable React/Three.js packages and typings.
- No application runtime behavior, API behavior, dependency versions, or database schema changed.
