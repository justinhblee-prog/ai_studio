# BUILD-00185 Verification Report

## Input integrity
- BUILD-00184 ZIP: `unzip -t` passed before extraction.
- Clean extraction completed under a fresh BUILD-00185 working directory.

## Backend
- 52 test files; 367 tests passed, 0 failed, 0 skipped.
- Group counts: 150, 54, 14, 21, 15, 10, 18; group 8 combined invocation timed out at command level, so its files were run individually: 3 + 1 + 2 + 2 = 8 passed; groups 9–13: 16, 14, 16, 17, 14.
- Isolated shard runner for group 8: 4 files passed, 8 tests passed, 0 failed, 0 timed out.
- Total independently confirmed tests: 367.
- Backend `compileall`: passed.

## Viewer
- JavaScript dependency-free scripts: 17 passed. `test_three_resource_integration.mjs` not run because `three` is not installed.
- Python scripts: 7 passed.
- TypeScript syntax/transpile: 10 source + 14 declaration parses, 0 errors; semantic typecheck not performed.
- API contract: 63/63.
- Request contract: 15 JSON body calls checked, 0 findings.
- Response contract: 50 JSON endpoints documented across 52 endpoints; 0 missing routes/schemas.
- Package integrity: 0 findings.
- Viewer Python compileall: passed.

## Dependency/runtime gate
- npm cache contains 0 registry entries in this environment.
- Global TypeScript CLI is present; `three`, React/ReactDOM and `@types` packages are not found in searched global package locations.
- BUILD-00184's exact registry probe failed with DNS `EAI_AGAIN`; no dependency or lockfile changes were made.
- Chromium WebGL2 capability remains blocked per BUILD-00184 probe. This build did not claim browser E2E or renderer acceptance.

## Result
Backend and dependency-free static/contract verification passed. Actual Three.js integration, semantic TypeScript, React browser E2E, WebGL2/GPU recovery and target-device performance remain open.
