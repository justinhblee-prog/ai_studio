# AI CREATOR STUDIO — BUILD-00180 Release Notes

## Release type
Validation and handoff refresh; no production source changes.

## Baseline integrity
- Started from `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00179.zip`.
- SHA-256 sidecar verification passed before extraction.
- ZIP CRC/integrity test passed before extraction.

## Fresh verification
- Viewer dependency-free JavaScript: 17 scripts passed; 295 emitted assertion-summary counts.
- Viewer Python: 7 scripts passed.
- TypeScript syntax/transpile: 10 source files and 14 declaration files parsed; 0 errors. This is not semantic typechecking.
- Viewer API contract: 63/63 calls matched; 0 findings.
- Request contract: 15 JSON body calls checked; 0 findings.
- Response contract: 50 JSON endpoints documented across 52 routes; 0 missing routes/schemas.
- Package integrity: 0 findings.
- Viewer and backend Python compileall passed.
- ZIP CRC and SHA-256 verification passed for this release package.

## Blocked or incomplete validation
- Backend full pytest rerun was terminated by the execution time limit after progress reached 39%; no test failure was emitted before termination. This is not a fresh pass.
- `three`, `react`, `typescript`, `@types/react`, and `@types/three` are absent from the local Viewer `node_modules`; npm cache has no usable package set. Semantic TypeScript checking and the actual Three.js resource integration test remain blocked.
- Browser React E2E, real WebGLRenderer context restoration, WebGL2/GPU stress, and target-device performance acceptance remain unverified.
- No package versions or lockfiles were changed.

## Next acceptance priorities
1. Run dependency installation and semantic typecheck in a network-enabled or approved cached environment using the exact declared versions.
2. Run the actual Three.js resource integration test.
3. Run authenticated React Viewer E2E in a WebGL2-capable browser.
4. Validate real renderer context loss/restoration, repeated model replacement/unmount, GPU stress, and target-device performance.
