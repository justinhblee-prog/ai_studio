# BUILD-00173 Verification Report

## Fresh results
- Viewer dependency-free JavaScript: 16 scripts passed; 1 Three.js integration script blocked because `three` is not installed; 0 failures.
- New GLTF parse-error ownership test: 8 assertions passed.
- Viewer Python tests: 7 passed.
- Backend pytest: 367 passed.
- TypeScript syntax/transpile: 10 source files + 14 declaration files parsed; 0 errors.
- API contract: 63/63 calls matched; 0 findings.
- Request contract: 15 JSON-body calls checked; 0 findings.
- Response contract: 50 JSON endpoints documented across 52 routes; 0 missing routes/schemas.
- Package integrity: 0 findings.
- Backend and Viewer Python compileall: passed.
- ZIP CRC test: passed; SHA-256 sidecar verification: passed.

## Explicitly unverified / blocked
- Three.js runtime integration test: blocked by missing `three` package.
- React semantic typecheck: blocked by missing React and `@types/react` dependencies.
- React/Three.js browser E2E and authenticated fixture rendering: not run.
- Real WebGL2 context-loss/restoration, GPU stress, and target-device performance: not run.

## Baseline correction
BUILD-00172's handoff described 8 Viewer Python tests. A fresh enumeration and rerun in BUILD-00173 found 7 `scripts/test_*.py` tests in the delivered tree; all 7 passed. This report uses the freshly verified count.

## Reproduction
Run from `ai_creator_studio_3d_viewer`:

```bash
node scripts/test_report_gltf_parse_error.mjs
node scripts/validate_typescript_syntax.cjs
python3 scripts/validate_package_integrity.py
python3 scripts/validate_api_contract.py
python3 scripts/validate_viewer_request_contract.py
python3 scripts/validate_viewer_response_contract.py
```

The full command outputs are retained in `build173_logs/`.
