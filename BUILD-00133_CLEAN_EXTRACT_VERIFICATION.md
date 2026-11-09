# BUILD-00133 Clean ZIP Extraction Verification

The release ZIP was freshly extracted to a clean directory. The following checks were re-run against the extracted copy (not the working source tree):

- ZIP SHA-256 verification: **PASS**.
- Structural validation: **111/111 PASS**.
- TypeScript syntax/transpilation: **10 files, 0 errors**.
- Viewer API contract: **63/63 matched**.
- Request contract: **15 JSON bodies checked, 0 findings**.
- Response contract: **51 JSON endpoints / 52 total endpoints; 28 models; 0 missing routes/schemas**.
- Viewer script tests: **8 passed**.
- Package integrity: **0 findings**.
- Python compileall: **PASS**.
- Backend full pytest suite: **359 passed in 14.92s**.

This confirms package reproducibility and the recorded offline checks. It does not establish semantic TypeScript correctness, React/Three.js browser component E2E, PostgreSQL runtime/multi-host behavior, Android, or production integrations; see `BUILD-00133_VERIFICATION.md`.
