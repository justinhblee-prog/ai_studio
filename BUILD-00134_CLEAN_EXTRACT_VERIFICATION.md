# BUILD-00134 Clean Extraction Verification

The release ZIP was extracted into a new directory with no dependency installation or reuse of the source working tree. The following checks were executed against the extracted copy:

- Structural validator: 113 checks passed.
- TypeScript syntax/transpilation: 10 source files + `.d.mts` declaration parse, 0 errors.
- RequestScopeGate behavioral test: 7 assertions passed.
- Viewer API contract: 63/63.
- Request body contract: 15 checked, 0 findings.
- Response contract: 51 JSON endpoints across 52 total endpoints; 28 models; no missing routes/schemas.
- Package integrity: 0 findings.
- Viewer Python test suites: API validator 2 passed, request contract 2 passed, package integrity 4 passed.
- Backend Python compileall: passed.
- Backend full pytest suite: 359 passed in 15.00s.

This verifies the packaged source and offline checks after extraction. It does not substitute for semantic TypeScript type checking, React/Three.js component E2E, PostgreSQL runtime, or production integration.
