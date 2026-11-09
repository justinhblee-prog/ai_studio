# BUILD-00149 Clean Extraction Verification

The final ZIP was extracted into an independent directory. Checks below were rerun from that extracted copy.

- ZIP CRC/integrity: no errors.
- Backend full pytest: 367 passed.
- Bounded GLTF download runtime: 16/16.
- Bounded GLTF download structural: 19/19.
- Authenticated GLTF loading: 9/9.
- Authenticated preview Object URL lifecycle: 5 assertions.
- RequestScopeGate: 7 assertions; KeyedRequestGate: 7 assertions; project lifecycle: 4 assertions.
- Lookbook signed-link: 12 assertions; Lookbook preview recovery: 19/19.
- Viewer API contract: 63/63; request-body contract: 15 checked / 0 findings; response contract: 50 JSON / 52 total / 28 models / 0 missing.
- TypeScript syntax/transpilation: 10 source + 6 declarations / 0 syntax errors (not semantic type checking).
- Package integrity: 0 findings; Python compileall passed.

All test commands were executed from `/mnt/data/acs_build149_clean_verify/AI_CREATOR_STUDIO_BUILD-00149`, not from the working source directory. See adjacent `BUILD-00149_CLEAN_*.log` evidence files.
