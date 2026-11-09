# BUILD-00137 Clean ZIP Extraction Verification

- Release ZIP: `AI_CREATOR_STUDIO_BUILD-00137_asset-restore-project-assignment-integrity.zip`
- Extracted into a new empty directory: `/mnt/data/acs_build137_final_extract`.
- Structural validation rerun from extracted source: `126 structural checks passed`.
- KeyedRequestGate behavior rerun: `KeyedRequestGate behavior: 7 assertions passed`.
- RequestScopeGate behavior rerun: `RequestScopeGate behavior: 7 assertions passed`.
- TypeScript syntax/transpilation rerun: `TypeScript syntax/transpile check: 10 source files + 2 declaration parses, 0 errors`.
- Package integrity rerun: `Package integrity: 0 findings`.
- Backend full pytest rerun from extracted source: `359 passed in 15.76s`.
- Final ZIP SHA-256 is recorded in the adjacent `.zip.sha256` sidecar and verified after packaging.
- Final ZIP checksum verification: passed against the final archive.

This verifies clean extraction and the listed checks only; it does not establish semantic TypeScript typing or actual React/Three.js component E2E.
