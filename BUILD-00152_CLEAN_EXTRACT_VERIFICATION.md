# BUILD-00152 Independent Clean Extraction Verification

## Procedure
- Created the release ZIP from the staged BUILD-00152 source tree.
- Verified ZIP CRC with `unzip -t` (no compressed-data errors).
- Extracted the archive into a separate directory: `/mnt/data/acs_build152_clean_verify/AI_CREATOR_STUDIO_BUILD-00152/`.
- Re-ran core executable tests and API/type/package contract checks from the extracted copy, not the staging directory.

## Results from extracted copy
- GLTF disposal runtime: 11 assertions passed (9 base assertions + 2 cycle-guard assertions).
- Authenticated GLTF structural: 11/11.
- Model base path: 10/10.
- Bounded download runtime: 17/17; structural: 19/19.
- Viewer API contract: 63/63.
- Request body contract: 15 checked / 0 findings.
- Response contract: 50 JSON endpoints / 52 total / 28 models / 0 missing routes or schemas.
- TypeScript syntax/transpilation: 10 source + 8 declarations / 0 syntax errors.
- Package integrity: 4 tests passed / 0 findings.
- Backend full pytest: 367 passed.

## Integrity
- ZIP CRC verification passed.
- Companion SHA-256 file is generated alongside the final archive; verify with `sha256sum -c`.

## Limitations
- Semantic TypeScript typecheck remains blocked by missing installed React/Three dependencies.
- Browser capability smoke is separate from actual React/Three component E2E; visible GLTF rendering is not claimed.
