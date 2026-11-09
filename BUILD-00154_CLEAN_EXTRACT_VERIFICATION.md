# BUILD-00154 Independent Clean Extraction Verification

## Procedure
- Created the BUILD-00154 release ZIP from the updated project root.
- Verified archive CRC with `unzip -t`.
- Extracted the ZIP into `/mnt/data/acs_build154_clean_verify/`, independent of the staging directory.
- Re-ran the disposal runtime, backend full test suite, core viewer tests/contracts, syntax, package integrity, and Python compile checks from the extracted copy.

## Results from extracted copy
- Backend full pytest: **367 passed**.
- GLTF disposal runtime: **33 assertions passed**.
- Authenticated GLTF structural: **15/15**; model base path: **10/10**.
- Bounded download structural: **19/19**; Lookbook preview recovery: **19/19**.
- Viewer API contract: **63/63**; request body contract: **15 checked / 0 findings**.
- Response contract: **50 JSON / 52 total / 28 models / 0 missing**.
- TypeScript syntax: **10 source + 8 declarations / 0 errors**; package integrity: **0 findings**; Python compileall passed.

## Staged-only capability check
Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader on the staged project tree. It is not React/Three component E2E and did not load GLTF.

## Limitations
Semantic TypeScript typecheck remains blocked by missing React/Three dependencies. Actual React/Three component E2E and GLTF rendering are not established by the WebGL capability smoke.
