# BUILD-00153 Independent Clean Extraction Verification

## Procedure
- Created the BUILD-00153 release ZIP from the staged source tree.
- Verified the ZIP archive with `unzip -t` (no compressed-data errors).
- Extracted the archive into `/mnt/data/acs_build153_clean_verify/` independently of the staging directory.
- Re-ran backend and core viewer tests/contracts from the extracted copy.

## Results from extracted copy
- Backend full pytest: **367 passed**.
- GLTF disposal runtime: **14 assertions passed**.
- Authenticated GLTF structural: **15/15**; model base path: **10/10**.
- Bounded download runtime: **17 assertions**; structural: **19/19**.
- Authenticated preview Object URL: **5**; RequestScopeGate: **7**; KeyedRequestGate: **7**; project lifecycle: **4**.
- Lookbook signed-link: **12**; Lookbook preview recovery: **19/19**.
- Viewer API contract: **63/63**; request body contract: **15 checked / 0 findings**.
- Response contract: **50 JSON / 52 total / 28 models / 0 missing routes or schemas**.
- TypeScript syntax: **10 source + 8 declarations / 0 errors**; package integrity: **0 findings**; Python compileall passed.

## Browser and typecheck notes
- Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader on the staged build; this is not React/Three component E2E and does not prove GLTF rendering.
- Semantic TypeScript check remains blocked by missing React/Three dependencies and declarations; no dependency install or lockfile change was made.

## Integrity
- ZIP CRC verification passed.
- SHA-256 companion file is generated alongside the release archive.
