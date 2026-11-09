# BUILD-00156 Clean Extraction Verification

## Archive integrity
- ZIP CRC test: passed; `unzip -t` reported no compressed-data errors.
- SHA-256: `e3e5bea5cdd4daedb9de557ff8dfd5799c05ce765f1599da96d82012675e85e6` (recomputed after final documentation update in the adjacent `.sha256` file).
- Archive extracted into `/mnt/data/acs_build156_clean_verify/`, independent of the source build directory.

## Independent extraction checks
- Viewer lifecycle integration 32 assertions; cleanup helper 10 runtime; lifecycle structural 13/13; diagnostic integration 4/4.
- GLTF disposal 33 assertions; authenticated GLTF 15/15; bounded download 17 runtime/19 structural; model base path 10/10.
- RequestScopeGate 7; KeyedRequestGate 7; project lifecycle 4; Lookbook links 12; Lookbook recovery 19/19; authenticated preview Object URLs 5.
- API contract 63/63; request body contract 15 checked/0 findings; response contract 50 JSON/52 endpoints/28 models/0 missing.
- TypeScript syntax 10 source + 10 declarations/0 errors; package integrity 0 findings; source structural validation 143 passed.
- Backend full-suite evidence is the successful 367-pass run recorded in `BUILD-00156_VERIFICATION.md`; backend sources were unchanged in this build. A duplicate run timed out before completion, so no clean-extraction backend rerun is claimed.
- Chromium WebGL2 capability smoke passed under Xvfb on the source build; it does not load React/Three Viewer or GLTF.
