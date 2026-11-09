# BUILD-00145 Clean Extraction Verification

The release archive was extracted into a new directory and the following checks were rerun from the extracted copy:

- Backend pytest: 367 passed.
- Authenticated GLTF structural assertions: 9/9 passed.
- TypeScript syntax/transpilation: 10 source + 5 declaration files; 0 errors.
- Viewer API contract: 63/63.
- Request body contract: 15 checked / 0 findings.
- Response contract: 50 JSON / 52 endpoints / 28 models / 0 missing.
- Package integrity: 0 findings.
- ZIP CRC integrity: passed.

Actual React/Three.js browser rendering and semantic TypeScript remain unverified; extraction does not change those limitations.
