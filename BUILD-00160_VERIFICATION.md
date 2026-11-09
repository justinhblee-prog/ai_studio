# BUILD-00160 Verification

## Passed

- Backend: `PYTHONPATH=. pytest -q` — 367 passed.
- WebGL context lifecycle helper — 15 assertions passed.
- WebGL restoration retry behavior — 5 assertions passed.
- Viewer production wiring and teardown contract — 5 assertions passed.
- Animation frame controller — 19 assertions passed.
- Viewer lifecycle integration — 32 assertions passed.
- Viewer cleanup lifecycle structural checks — 13/13 passed.
- Viewer disposal diagnostic integration — 4/4 passed.
- Authenticated GLTF loading contract — 15/15 passed.
- Viewer response contract — 50 JSON endpoints documented across 52 endpoints; 0 missing routes/schemas/unresolved dynamic segments.
- Viewer API contract — 63/63 calls matched.
- Viewer request contract — 15 JSON body calls checked; 0 findings.
- Package integrity — 0 findings.
- TypeScript syntax/transpile check — 10 source files + 12 declaration parses; 0 errors.
- Chromium WebGL2 capability smoke under Xvfb/SwiftShader — WebGL2, triangle pixel, animation frame, resize observer, context loss and context restore all passed.
- ZIP CRC and independent extraction check — passed.

## Blocked / not verified

- `npm install --ignore-scripts --no-package-lock --no-save --prefer-offline --fetch-retries=0 --fetch-timeout=30000` failed with `EAI_AGAIN registry.npmjs.org`.
- `npm run typecheck` is blocked because React, Three.js, and their type packages are not installed. The output includes missing-module and downstream JSX/type errors; do not treat this as a source typecheck pass.
- `node scripts/test_three_resource_integration.mjs` correctly exits 1 with `ERR_MODULE_NOT_FOUND` for `three`; no false-green skip.
- Browser capability smoke is not a React/Three.js Viewer E2E. Real authenticated GLTF rendering, model replacement/unmount, renderer-level context recovery, and GPU memory stress remain unverified.

## Environment notes

Running `python scripts/probe_browser_runtime.py` without Xvfb fails because the environment has no X server. Running `xvfb-run -a python scripts/probe_browser_runtime.py` passes the browser capability smoke.
