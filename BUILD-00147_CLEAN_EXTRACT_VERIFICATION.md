# BUILD-00147 Clean Extraction Verification

The release ZIP was extracted into a new directory with no dependency installation or source-tree fallback. All checks below were run against the extracted copy.

- Backend pytest: **367 passed**.
- Python compileall: passed.
- Node syntax check for `boundedModelDownload.mjs`: passed.
- Bounded GLTF runtime: **9/9 passed**.
- Bounded GLTF structural: **15/15 passed**.
- Authenticated GLTF structural: **9/9 passed**.
- TypeScript syntax/transpilation: **10 source + 6 declarations, 0 errors**.
- Viewer API contract: **63/63**, 0 missing/mismatched routes.
- Request-body contract: **15 checked, 0 findings**.
- Response contract: **50 JSON / 52 total / 28 models**, 0 missing routes/schemas.
- Package integrity: **0 findings**.

This confirms reproducibility of the listed source-level and runtime-reader tests from the archive. It does not establish React/Three browser rendering, semantic TypeScript, PostgreSQL/Android/production runtime, or deployment readiness.
