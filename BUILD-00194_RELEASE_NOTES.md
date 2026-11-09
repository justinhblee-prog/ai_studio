# BUILD-00194 Release Notes

Date: 2026-11-05

## Summary

Hardened SQLite-to-PostgreSQL bundle preflight metadata validation. The importer now rejects malformed manifest counts (including booleans masquerading as integers), missing/blank source database metadata, malformed or duplicate trigger inventories, trigger inventory/schema drift, and duplicate or invalid serial-column declarations. Validation occurs before psycopg is imported or a database connection is opened.

## Implementation

- Validate `table_count` and `row_count` as non-boolean integers with correct bounds/consistency.
- Require a non-empty `source_database` string.
- Validate trigger inventory type, count, identifier shape and uniqueness.
- Extract emitted quoted `CREATE TRIGGER` names from the already checksum-verified schema and compare them to the manifest inventory.
- Validate `serial_columns` entries and reject duplicates.
- Add four adversarial regression tests covering boolean counts, trigger inventory/schema mismatch, duplicate trigger inventory, and duplicate serial columns.

No runtime application API, dependency manifest, lockfile, or live database behavior was changed.

## Verification

- Backend: 52 test files, 384 passed, 0 failed.
- Migration-focused suite: 21 passed.
- Viewer JavaScript: 17 dependency-free scripts, 322 assertions passed.
- Viewer Python: 7 scripts, 87 checks/tests passed.
- Viewer structural source validation: 143 checks passed.
- Viewer API contract: 63/63 calls matched; 52 unique endpoints; no missing or unresolved endpoints.
- Request contract: 15 JSON body calls checked, 0 findings.
- Response contract: 50 JSON success contracts across 52 endpoints and 28 response models; 0 missing routes/schemas.
- Python compileall passed.
- Package integrity validation passed with 0 findings.

## Explicit limitations

- No PostgreSQL server, `psql`, Docker or psycopg 3 is available here. Live import, trigger firing, sequence restoration, rollback and multi-worker concurrency remain unverified.
- Bundle v1 remains unsupported; export fresh v2 bundles.
- PostgreSQL runtime Repository/transaction adapters are not implemented; SQLite remains the supported runtime database.
- React/ReactDOM/Three.js and typings are unavailable. Semantic TypeScript, actual Three.js integration and real React Viewer E2E remain unverified. The dependency-free JS tests are not a substitute.
- Live AI generation was not invoked; it requires explicit cost authorization and valid credentials/authorized input URLs.
