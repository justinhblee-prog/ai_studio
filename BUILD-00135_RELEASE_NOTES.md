# BUILD-00135 Release Notes — Lookbook Archive State Integrity

## Summary

Lookbook draft archival now invalidates and clears the currently open output-assembly context when that same draft is archived. The reset is centralized and reused by the assembly close action and workspace-scope reset.

## Changes

- Added `clearAssemblyState` to invalidate any in-flight output-assembly hydration request.
- Clears the selected assembly draft, approved Photo-run choices, attached immutable outputs, preview URLs, selected Photo run and Product Variant, page-order/caption form state, output manifest, package export and assembly-review state.
- Archiving the currently open assembly draft now invalidates any in-flight planning manifest request and clears the planning manifest; it also clears the dependent assembly state before refreshing the draft list.
- Closing the assembly panel now uses the same complete reset instead of only hiding the panel, preventing stale hidden selection/export state from reappearing.
- Workspace/API/token changes reuse the centralized reset and invalidate in-flight assembly hydration.
- Added three structural checks for archive invalidation, dependent-state clearing and close-action reuse.

## Compatibility and safety

- No backend routes, schemas, database migrations, dependency versions, public component props, Provider calls, credit behavior, publication behavior, or rights grants changed.
- Archival remains non-destructive; immutable source/output history is not deleted.

## Verification

- Structural validation: 116/116 passed.
- RequestScopeGate behavioral test: 7 assertions passed.
- TypeScript syntax/transpilation: 10 source files plus declaration parse, 0 errors (not semantic type checking).
- Viewer API contract: 63/63.
- Request body contract: 15 checked, 0 findings.
- Response contract: 51 JSON endpoints across 52 total endpoints; 28 models; no missing routes/schemas.
- Viewer Python script tests: 2 passed; package integrity: 0 findings.
- Backend Python compileall: passed.
- Backend full pytest suite: 359 passed in 15.26s.
- Clean ZIP extraction verification: see `BUILD-00135_CLEAN_EXTRACT_VERIFICATION.md`.

## Remaining unverified areas

Semantic TypeScript typecheck and actual React/Three.js component E2E remain blocked by unavailable trusted React/Three.js packages and typings. PostgreSQL runtime/multi-host integration, Android, production storage/secrets/RBAC, live Provider/credit operations, publication, rights grants and deployment remain unverified.
