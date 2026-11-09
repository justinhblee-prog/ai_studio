# BUILD-00187 Verification Report

## Input integrity
- BUILD-00186 archive: `/mnt/data/AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00186.zip`.
- SHA-256 sidecar check: passed (`3b5e055c9406d606ecd54f0c36eb89b3e314d47c9b2c36690a01fbb01eab6eee`).
- ZIP CRC/integrity test: passed (`No errors detected in compressed data`).
- Extracted into fresh `/mnt/data/build187/`.

## Backend
- Test files: **52**.
- Individual tests: **367 passed, 0 failed, 0 skipped**.
- All four logical groups passed, with the first group split after the outer command window ended following eight files. The first eight files account for 204 tests; the remaining five files passed 19 tests. Other groups passed 49, 46, and 49 tests respectively. Total: 367.
- Every per-file pytest invocation used a fresh subprocess and has a retained log under `build187_logs/backend_group_*/`.
- Backend Python compileall: passed.

## Viewer
- Dependency-free JavaScript scripts: **17 passed, 0 failed**.
- `test_three_resource_integration.mjs`: not run; required `three` package is unavailable.
- Viewer Python scripts: **7 passed**.
- TypeScript syntax/transpile: **10 source files + 14 declaration parses, 0 syntax errors**. Global TypeScript CLI is 5.8.3. This is not a semantic typecheck.
- API contract: **63/63** calls matched; 0 missing, query mismatches, or unresolved dynamic segments.
- Request contract: **15** JSON body calls checked; 0 findings.
- Response contract: **50** JSON endpoints documented across **52** routes and **28** models; 0 missing routes, schemas, or unresolved dynamic segments.
- Package integrity: 0 findings.
- Viewer Python compileall: passed.

## Dependency/runtime investigation
- Searched project/global Node module paths and likely shared package directories. No usable `three`, React/ReactDOM runtime dependency tree, or `@types/react` / `@types/three` installation was available. A React static bundle inside Jupyter UI assets is not a valid substitute for the declared project dependencies.
- The existing Chromium WebGL2 capability probe failed: `webgl2=false`, `renderer=null`, error `WebGL2 context unavailable`.
- Two additional Chromium SwiftShader/ANGLE variants also failed to create WebGL2 contexts.
- Browser probe scope is capability-only and does not load the React/Three.js Viewer.
- No dependency manifest, version, or lockfile changes were made.

## Explicitly unverified / blocked acceptance
- Semantic React/Three.js TypeScript typecheck.
- Actual Three.js resource integration.
- Authenticated React browser E2E.
- Real renderer context-loss/restoration.
- GPU stress and repeated model replacement/unmount under a real renderer.
- Target-device performance and real external AI generation / end-to-end production acceptance.

## Source review
- Reviewed `Studio3DViewer.tsx` and `webglContextLifecycle.mjs` around renderer initialization, resource rollback, request ownership, GLTF parse/commit/disposal, and WebGL recovery.
- Existing deterministic lifecycle and rollback tests passed. No additional production code change was made without a reproducible defect or a working real renderer/dependency environment.

## Logs
- All BUILD-00187 fresh command outputs are retained in `build187_logs/`.
