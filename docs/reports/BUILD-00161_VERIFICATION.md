# BUILD-00161 Verification

## Passed

- Backend: `PYTHONPATH=. pytest -q` — 367 passed in 21.12s.
- All 12 dependency-free Viewer `.mjs` test suites passed.
- All 7 Viewer Python test scripts passed.
- WebGL context lifecycle — 15 assertions passed.
- WebGL restoration retry — 5 assertions passed.
- Viewer wiring/teardown contract — 5 assertions passed.
- Render-loop restart failure — 2 assertions passed.
- Loss-handler failure isolation — 4 assertions passed.
- Listener registration rollback — 2 assertions passed.
- Listener teardown failure isolation — 4 assertions passed.
- Total WebGL lifecycle suite: 37 assertions passed.
- Viewer API contract — 63/63 calls matched.
- Viewer response contract — 50 JSON endpoints across 52 endpoints; 28 models; 0 missing routes/schemas/unresolved dynamic segments.
- Viewer request contract — 15 JSON body calls checked; 0 findings.
- Package integrity — 0 findings.
- TypeScript syntax/transpile — 10 source files + 12 declaration parses; 0 syntax errors.
- Python compileall — passed.
- Chromium WebGL2 capability smoke under Xvfb/SwiftShader — WebGL2, triangle pixel, animation frame, resize observer, raw context loss and restore all passed.

## Blocked / not verified

- Online `npm install --ignore-scripts --no-audit --no-fund --prefer-offline` did not complete within the 20-second bounded attempt.
- Offline npm installation failed with `ENOTCACHED` for `@types/react`; the required packages are not present in npm cache.
- `node scripts/test_three_resource_integration.mjs` exits non-zero with `ERR_MODULE_NOT_FOUND` for `three`. This is an intentional BLOCKED result, not a pass.
- `tsc --noEmit` remains blocked by missing `react`, `three`, and type declarations; missing JSX types produce downstream diagnostics. TypeScript syntax parsing is not semantic typechecking.
- Browser capability smoke is not a React/Three.js Viewer E2E. Authenticated GLTF rendering, actual Three.js renderer context recovery, model replacement/unmount in a mounted Viewer, GPU memory stress, and target-device performance remain unverified.

## Environment / scope

No dependency version, package manifest, or lockfile was changed. Browser smoke used `/usr/bin/chromium` under Xvfb and SwiftShader. The helper tests exercise production lifecycle code with deterministic event-target/animation-loop doubles; they do not substitute for an actual Three.js renderer test.
