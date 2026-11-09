# BUILD-00186 Verification Report

## Input integrity
- BUILD-00185 ZIP SHA-256: verified against its sidecar (`f5f3c08079fb7d34f02f0b32ceddf9bfa9cca3848af2c44498c6d68201a1ebdf`).
- BUILD-00185 ZIP CRC test: passed with no compressed-data errors.
- Extracted into a fresh BUILD-00186 working directory.

## Backend
- Test files: 52.
- Tests: **367 passed, 0 failed, 0 skipped**.
- Fresh execution breakdown:
  - First eight files: 204 passed.
  - Next five four-file groups: 78 passed.
  - The four files in the previously problematic group: 8 passed individually (3 + 1 + 2 + 2).
  - Final five four-file groups: 77 passed.
- The full sequential shard-runner command exceeded the outer 300-second command window after the first eight files. The ninth file (`test_credit_ledger_uow_contract.py`) was then independently rerun and passed (4 tests); remaining groups were run successfully. This execution interruption is not counted as a test failure.
- Backend Python compileall: passed.

## Viewer
- Dependency-free JavaScript scripts: 17 passed, 0 failed.
- `test_three_resource_integration.mjs`: not run; `three` package unavailable.
- Viewer Python scripts: 7 passed, 0 failed.
- TypeScript syntax/transpile: 10 source files + 14 declaration parses, 0 errors. This is not a semantic typecheck.
- API contract: 63/63 calls matched.
- Request contract: 15 JSON-body calls checked, 0 findings.
- Response contract: 50 JSON endpoints documented across 52 routes and 28 models; 0 missing routes/schemas.
- Package integrity: 0 findings.
- Viewer Python compileall: passed.

## Dependency and browser capability
- `npm cache ls` returned no cached package entries.
- Searched local data and global Node module paths; no local `three`, React/ReactDOM, or `@types` package directories were found.
- Global TypeScript CLI: 5.8.3.
- Chromium executable exists at `/usr/bin/chromium`, but the fresh browser capability probe reports `webgl2: false`, `renderer: null`, and `WebGL2 context unavailable`.
- The browser probe is only a capability smoke test; it does not load the React/Three.js viewer.
- Prior exact registry lookup failed with DNS `EAI_AGAIN`; no dependency or lockfile changes were made.

## Explicitly unverified
- Semantic React/Three.js TypeScript typecheck.
- Actual Three.js resource integration test.
- Authenticated React browser E2E.
- Real renderer WebGL context-loss and restoration.
- GPU stress, repeated model replacement/unmount under a real renderer, and target-device performance.

## Logs
All fresh BUILD-00186 command outputs are retained in `build186_logs/`.
