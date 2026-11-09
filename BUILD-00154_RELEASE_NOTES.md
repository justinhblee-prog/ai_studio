# BUILD-00154 — Failure-Resilient GLTF Resource Disposal

- Made GLTF GPU-resource cleanup best-effort: one resource throwing from `dispose()` no longer aborts cleanup of later resources.
- Added structured diagnostics and counts for attempted/successful disposal, grouped by textures, materials, geometries, and skeletons.
- Isolated scene traversal and nested material-property inspection failures and continued with other scenes/resources.
- Preserved per-call shared-resource deduplication and caller compatibility; typed declaration now exposes the diagnostic result.
- Added 19 new runtime assertions covering disposal failure, continued cleanup, shared-resource deduplication, traversal failure, getter failure, and diagnostic details.
- Backend 367 passed; disposal runtime 33 assertions; authenticated GLTF 15/15; viewer contracts and syntax passed; WebGL2 capability smoke passed.
- No dependencies, API/schema, DB, Provider, credit, publication, rights, production data, or deployment changes.
- Semantic typecheck and actual React/Three browser E2E remain unverified.
