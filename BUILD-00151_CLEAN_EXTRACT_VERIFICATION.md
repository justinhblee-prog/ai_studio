# BUILD-00151 Clean Extraction Verification

## Archive integrity
- Archive: `AI_CREATOR_STUDIO_BUILD-00151_relative-gltf-base-path.zip`
- SHA-256: recorded in the companion `.zip.sha256` file.
- ZIP extraction completed into a separate clean verification directory.
- The archive was CRC-tested and the extracted source was used for all tests below.

## Tests rerun from extracted source
- Backend full pytest: **367 passed**.
- Model base path runtime: **10/10**.
- Authenticated GLTF structural: **10/10**.
- Bounded download runtime: **17/17**; structural: **19/19**.
- Viewer API contract: **63/63**, no missing calls or query mismatches.
- Request body contract: **15 checked, 0 findings**.
- Response contract: **50 JSON endpoints / 52 total endpoints / 28 models / 0 missing routes or schemas**.
- TypeScript syntax/transpilation: **10 source + 7 declarations / 0 syntax errors**; not semantic type checking.
- Package integrity tests: **4 passed**; Python compileall passed.
- Individual clean-extraction logs are included as `BUILD-00151_CLEAN_*.log`.

## Scope note
This verifies the packaged source and deterministic tests in a clean extraction. It does not establish actual React/Three.js browser rendering, semantic TypeScript correctness, target-device memory behavior, or production readiness.
