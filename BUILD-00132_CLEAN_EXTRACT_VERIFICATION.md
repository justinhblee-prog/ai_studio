# BUILD-00132 Clean Extraction Verification

The release ZIP was extracted into a fresh directory and validated from the extracted copy.

- Structural checks: 107 passed.
- Viewer API contract: 63/63 matched.
- Request body contract: 15 checked, 0 findings.
- Response contract: 51 JSON endpoints / 52 total endpoints, 28 models, 0 missing routes or schemas.
- TypeScript syntax/transpilation: 10 files, 0 errors.
- Viewer script tests: 2 passed.
- Package integrity: 0 findings.
- Backend Python compileall: passed.
- Backend full pytest suite: 359 passed in 15.95s.
- ZIP SHA-256: verified against the adjacent `.sha256` file after packaging.

This does not constitute semantic TypeScript typechecking or React/Three.js component E2E.
