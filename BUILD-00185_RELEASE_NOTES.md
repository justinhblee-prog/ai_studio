# BUILD-00185 Release Notes

## Scope
Fresh verification refresh and backend test-runner isolation diagnosis. No application runtime source, API behavior, dependency manifest, dependency version, or lockfile changes.

## Verification
- Recovered BUILD-00184 archive passed ZIP CRC validation and clean extraction.
- Backend: 52 test files, 367/367 tests passed. Groups 1–7 and 9–13 passed as grouped invocations (282 + 77 tests); group 8's four files passed individually (8 tests). The combined group-8 invocation exceeded the execution window, but all four constituent files passed individually. A separate shard-runner run for those four files passed 4/4 files and 8/8 tests.
- Viewer: 17 dependency-free JavaScript scripts passed; actual Three.js integration remains blocked by absent `three` package.
- Viewer Python: 7 test scripts passed.
- TypeScript syntax/transpile: 10 source files + 14 declaration parses, 0 syntax errors. This is not semantic typecheck.
- API contract 63/63; request contract 15 checked / 0 findings; response contract 50 JSON endpoints across 52 routes / 0 missing routes or schemas; package integrity 0 findings.
- Viewer and backend Python compileall passed.
- Local dependency audit: no npm registry cache entries; TypeScript CLI exists globally, but `three`, React/ReactDOM, and their type packages are not installed in searched global locations.

## Blockers
- Exact declared dependencies cannot be installed in this environment due npm registry DNS `EAI_AGAIN`; no versions or lockfiles were changed.
- Actual Three.js integration, semantic TypeScript typecheck, React browser E2E, WebGL2 renderer recovery, GPU stress, and target-device performance remain unverified.
- Chromium capability probe from BUILD-00184 reports WebGL2 context unavailable.

## Next
1. Obtain exact declared packages in an approved network-enabled or pre-populated environment.
2. Run `tsc --noEmit` and actual Three.js resource integration.
3. Run authenticated React Viewer browser E2E in a WebGL2-capable browser.
4. Validate renderer context loss/restoration, repeated model replacement/unmount, GPU stress, and target-device performance.
5. Continue isolating grouped pytest orchestration behavior; do not interpret a combined-command timeout as an application test failure when individual test files pass.
