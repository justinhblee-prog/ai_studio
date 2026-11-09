# BUILD-00123 Verification Report

## Scope

Adds an optional browser-engine capability probe. No application runtime code or runtime dependency versions changed.

## Probe implementation

- `ai_creator_studio_3d_viewer/scripts/probe_browser_runtime.py`
- `ai_creator_studio_3d_viewer/requirements-browser-audit.txt` (optional, Playwright 1.57.0)
- npm script `probe:browser-runtime`

The probe launches system Chromium under an Xvfb display with SwiftShader, compiles and links WebGL2 shaders, draws a triangle, reads a pixel back, and checks ResizeObserver/requestAnimationFrame.

## Actual result

Command:
```bash
xvfb-run -a python3 scripts/probe_browser_runtime.py
```

Result:
- Chromium executable: `/usr/bin/chromium` (Chromium 144.0.7559.96)
- WebGL2 context: PASS
- Triangle draw/readback: PASS
- ResizeObserver: PASS
- requestAnimationFrame: PASS
- Renderer string: `WebKit WebGL` (software-backed SwiftShader path)

## Scope limitation

This is a browser engine/WebGL capability smoke test only. It does not load React, Three.js, the AI CREATOR STUDIO Viewer component, or a GLTF asset. React/ReactDOM/Three.js and typings remain unavailable because the npm registry cannot be resolved in this execution environment. Full TypeScript semantic typecheck was attempted and is blocked by missing React/Three.js modules and typings (732 cascading diagnostics; see `BUILD-00123_TYPECHECK_BLOCKER.md`). Actual Viewer E2E remains unverified.

## Carried verification

BUILD-00121 remains the latest full executable application verification: backend 359 passed; Viewer runtime HTTP JSON 47/47; API 58/58; request 10/10; response schema 47/47; structural 65/65; Viewer script tests 8 passed; package integrity 0 findings; TypeScript syntax/transpilation 8 files / 0 diagnostics; compileall and OpenAPI snapshot check passed.
