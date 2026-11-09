# BUILD-00133 Verification Report

## Viewer and contract checks

- Viewer structural validation: **111/111 PASS**.
- TypeScript syntax/transpilation: **10 files, 0 diagnostics**. This is syntax/transpilation validation, not semantic `tsc --noEmit`.
- Viewer API contract: **63/63 matched**, no missing calls, query mismatches, or unresolved dynamic segments.
- Viewer request contract: **15 JSON request bodies checked, 0 findings**.
- Viewer response contract: **51 JSON endpoints / 52 total endpoints**, 28 models, 0 missing routes, 0 missing schemas, 0 unresolved dynamic segments.
- Viewer Python script tests: **8 passed**.
- Package integrity: **0 findings**.
- Backend Python compileall: **PASS**.
- Backend full pytest suite: **359 passed in 15.55s**.

## Source changes

- Photo Draft uses a monotonically increasing load request sequence across its list and nested Photo-run hydration. A previous reload cannot apply stale images/drafts/runs/source selection after a newer reload starts.
- Project Product Assignment uses independent catalog and assignment request sequences. Assignment responses additionally require the requested project ID to remain the current selection.
- Output Review uses a monotonic request sequence across outputs, nested review histories, and immutable AssetVersion previews.
- Product Catalog's existing load sequence and workspace identity guard were reviewed and retained.
- No backend source, routes, schemas, migrations, dependencies, lockfiles, public component props, provider behavior, or credit behavior changed.

## Scope and limitations

- Structural assertions establish source-level guards only; they do not prove React runtime scheduling behavior.
- Actual React/Three.js browser component E2E remains unverified because trusted React/Three.js packages and typings are unavailable in this environment.
- Semantic `tsc --noEmit` remains blocked by missing React/Three.js dependencies and type declarations. Do not interpret the syntax check as semantic type checking.
- PostgreSQL runtime/multi-host behavior, Android app/device tests, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants, and deployment remain unverified.

## Commands

From `ai_creator_studio_3d_viewer/`:

- `python3 scripts/validate_source.py`
- `node scripts/validate_typescript_syntax.cjs`
- `python3 scripts/validate_api_contract.py`
- `python3 scripts/validate_viewer_request_contract.py`
- `python3 scripts/validate_viewer_response_contract.py`
- `python3 scripts/validate_package_integrity.py`
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`

From `ai_creator_studio_backend_starter/`:

- `python3 -m compileall -q app tests scripts`
- `python3 -m pytest -q`

## Clean extraction

All checks above are repeated against a fresh extraction of the release ZIP. See `BUILD-00133_CLEAN_EXTRACT_VERIFICATION.md`.
