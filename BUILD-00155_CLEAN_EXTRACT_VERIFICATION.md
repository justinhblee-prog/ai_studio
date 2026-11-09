# BUILD-00155 Clean Extraction Verification

- The release ZIP was created from the staged BUILD-00155 source tree and independently extracted to `/mnt/data/acs_build155_clean_verify/`.
- ZIP CRC test passed with no compressed-data errors.
- Backend full pytest from extracted copy: **367 passed**.
- GLTF disposal runtime: **33 assertions**.
- Viewer cleanup runtime: **10 assertions**; lifecycle structure **13/13**.
- Authenticated GLTF **15/15**; model base path **10/10**; bounded download **17 runtime / 19 structural**.
- Preview Object URL **5**; RequestScopeGate **7**; KeyedRequestGate **7**; project lifecycle **4**; Lookbook links **12**; Lookbook recovery **19/19**.
- Viewer API **63/63**; request body **15 checked / 0 findings**; response contract **50 JSON / 52 endpoints / 28 models / 0 missing**.
- TypeScript syntax **10 source + 9 declaration files / 0 errors**; package integrity **0 findings**; Python compileall passed.
- Browser WebGL2 capability smoke passed under Xvfb/SwiftShader; this is not React/Three component E2E.
- Semantic typecheck remains blocked by absent React/Three dependencies.
