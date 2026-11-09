# BUILD-00190 Verification Report

## Integrity and baseline

- Input archive: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00189.zip`
- Input SHA-256 sidecar: verified successfully before extraction.
- Input ZIP CRC: `unzip -t` reported no errors.
- Work performed in a fresh `build190/` extraction.

## Test results

| Area | Result | Notes |
|---|---:|---|
| Backend pytest | 367 passed / 0 failed | 52 test files |
| Viewer JavaScript | 17 scripts / 322 assertions passed | Three.js-specific integration excluded due missing package |
| Viewer Python | 7 scripts / 87 checks passed | Includes contract, cleanup and request tests |
| TypeScript syntax | 10 source + 14 declaration files; 0 errors | Transpile/syntax only |
| API contract | 63/63 | No mismatch |
| Request contract | 15 checked / 0 findings | JSON body calls |
| Response contract | 50 JSON endpoints / 52 routes / 28 models | 0 missing routes or schemas |
| Structural source audit | 143 passed | Not a runtime execution test |
| Package integrity | Passed | 0 findings |
| Python compileall | Passed | Viewer and backend |
| Chromium WebGL2 capability | Passed | Xvfb + SwiftShader; not React/Three E2E |

## Backend execution detail

All 52 backend test files were executed. Most were run in isolated groups of four through `scripts/run_backend_test_shards.py`; six files affected by command-window interruption were rerun individually and their outputs retained. Aggregated count: 367 passed, 0 failed, 0 skipped. The runner invocation itself was not treated as the test result; the individual pytest outputs are the evidence.

## Browser capability probe

`xvfb-run -a python3 scripts/probe_browser_runtime.py`

Result: `status=pass`; WebGL2 context, triangle pixel readback, ResizeObserver, requestAnimationFrame, context-loss event, and context-restored event all true. Renderer string: `WebKit WebGL` (SwiftShader software renderer). The script explicitly scopes itself as browser capability smoke only and does not load the React/Three.js Viewer.

## Dependency and typecheck blockers

- Local package search: no usable `three`, `react`, `react-dom`, `@types/react`, or `@types/three` installation found.
- npm cache: no cached `three` or React packages.
- DNS: `registry.npmjs.org`, `unpkg.com`, and `cdn.jsdelivr.net` did not resolve.
- `node scripts/test_three_resource_integration.mjs`: blocked with `ERR_MODULE_NOT_FOUND` for `three`.
- `npx --no-install tsc --noEmit`: blocked by missing `react`, `react/jsx-runtime`, `three`, and associated type declarations. This is an environment/dependency block; no semantic typecheck pass is claimed.

## AI provider execution boundary

The backend live FASHN smoke preflight returned `Live generation is disabled: explicit cost confirmation is required.` No credentials or test image URLs were configured. No external provider request was sent and no charge was incurred. This preserves the explicit cost gate; a real live generation test remains unverified.

## Source changes

No application source, API contract, package manifest, dependency version, or lockfile changes were made. Only verification logs, handoff, roadmap, release notes, and package inventory were updated.

## Final status

BUILD-00190 is a verified audit/diagnostic package, not a completed 3D integration release. Actual React/Three viewer E2E, Three.js resource integration, semantic typecheck, GPU/device acceptance, and live AI generation remain open.
