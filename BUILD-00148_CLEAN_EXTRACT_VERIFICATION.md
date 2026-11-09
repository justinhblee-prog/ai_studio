# BUILD-00148 Clean Extraction Verification

The final ZIP was extracted into a separate directory and the following checks were rerun from the extracted copy.

- ZIP CRC/integrity: no errors.
- Backend full pytest: 367 passed.
- Bounded GLTF download runtime: 12/12.
- Bounded GLTF download structural: 15/15.
- Authenticated GLTF loading structural: 9/9.
- RequestScopeGate: 7 assertions.
- KeyedRequestGate: 7 assertions.
- Project lifecycle events: 4 assertions.
- Lookbook signed-link behavior: 12 assertions.
- Lookbook preview recovery: 19/19.
- Viewer API contract: 63/63, no missing calls or query mismatches.
- Request body contract: 15 checked, 0 findings.
- Response contract: 50 JSON endpoints / 52 total / 28 models / 0 missing routes or schemas.
- TypeScript syntax/transpilation: 10 source + 6 declarations, 0 errors (not semantic type checking).
- Package integrity: 0 findings.

All checks above were run against the independently extracted ZIP, not the working source directory.
