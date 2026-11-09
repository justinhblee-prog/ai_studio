# BUILD-00213 Verification Report

Date: 2026-11-06

| Check | Result |
|---|---:|
| Backend pytest | PASS — 495 passed, 0 failed |
| Python compileall (`app`, `tests`) | PASS |
| Runtime OpenAPI snapshot check | PASS |
| requirements manifest | PASS — 7 separate entries |
| PostgreSQL factory fail-closed | PASS — 15 repository factories + storage selector |
| Runtime readiness auth | PASS — 401 unauthenticated, 403 non-operator, 200 operator |
| Secret redaction | PASS — credential values absent from response |
| Supabase live app integration | NOT RUN |
| Vercel source-backed Preview | NOT DEPLOYED |
| Real AI provider generation | NOT RUN |

## Test command

```bash
PYTHONPATH=. python -m pytest -q -p no:cacheprovider
python -m compileall -q app tests
PYTHONPATH=. python scripts/export_runtime_openapi.py --check
```

## Interpretation

Local checks validate the code and API contract only. They do not prove Supabase PostgreSQL, Supabase Storage, Vercel Preview, worker deployment, or real AI provider behavior.

## Additional evidence

- `tests/test_postgresql_fail_closed.py`: 16 checks passed.
- Static scan: 106 SQLite-specific references in application Python modules.
- Coverage matrix: `ai_creator_studio_backend_starter/docs/POSTGRESQL_ADAPTER_COVERAGE_MATRIX_BUILD-00213.md`.
