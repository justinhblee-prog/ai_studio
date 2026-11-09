# BUILD-00114 Verification Report

| Check | Result |
|---|---:|
| Viewer source files scanned | 7 |
| Fetch call sites after dynamic expansion | 58 |
| Unique method + path combinations | 48 |
| Path + HTTP method + query-name contract | 58/58 passed |
| Missing path/method | 0 |
| Undeclared query parameter | 0 |
| Unresolved dynamic path segment | 0 |
| Validator regression tests | 2 passed |
| Python compileall (`viewer/scripts`) | passed |
| TypeScript typecheck | NOT VERIFIED — npm dependency installation timed out |
| Browser / React / WebGL / Android E2E | NOT RUN |
| Backend pytest | Not rerun; BUILD-00114 makes no backend code changes |

## Commands

```bash
cd ai_creator_studio_3d_viewer
python3 scripts/validate_api_contract.py
python3 scripts/test_api_contract_validator.py -v
python3 -m compileall -q scripts
```

## Scope caveat

The validator parses Viewer source `fetch()` calls and compares URL path, HTTP method, and query parameter names with the committed BUILD-00113 runtime OpenAPI snapshot. It does not prove payload/response schema compatibility or successful browser execution.
