# BUILD-00090 Verification Report

## Results

- Backend pytest: **287 passed** (15.33 seconds on the final verbose run).
- Asset API tests: **23 passed**.
- Python `compileall -q app scripts tests`: passed.
- 3D Viewer offline structural validation: **19/19 passed**.
- ZIP archive integrity: verified during final packaging.

## OpenAPI evidence

- Design route inventory: 13 paths.
- Runtime route inventory: 29 paths.
- Exact route match: false; runtime-only and design-only routes remain.
- Schema audit: 15 design operations compared, 10 operations with contract drift, 5 unmatched design operations.
- The design OpenAPI baseline was not silently edited to hide drift.

## Scope / limitations

- Tests exercise FastAPI/SQLite/local filesystem using test fixtures. They do not prove production database durability or multi-host behavior.
- TypeScript build and browser/WebGL/Android end-to-end flow remain unverified.
- PostgreSQL and production object storage remain unavailable/unimplemented.
- Live FASHN generation was not called; no API key or cost authorization was supplied.
- G0-G5 have not been promoted to PASS.
