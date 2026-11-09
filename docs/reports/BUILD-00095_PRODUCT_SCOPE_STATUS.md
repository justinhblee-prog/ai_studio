# BUILD-00095 Product Scope Status

## Implemented and locally tested

- Workspace/RBAC, Project CRUD, Character identity/outfit catalog CRUD.
- Private GLB/GLTF and PNG/JPEG/WebP image asset upload, validation, signed preview, integrity audit, immutable version history and restore-as-new-version.
- AssetRelation types and source/target provenance; `derived_from` cycle prevention under SQLite write serialization.
- Generation Job / Execution / Event / Outbox / Worker / Poll / Output lifecycle at SQLite single-host PoC scope.
- Photo Draft input preparation API/UI with source/mask/reference image validation and append-only draft events.
- Lookbook Draft composition API/UI with multi-product/person images, optional active Project/Character, scene preset and append-only events.
- Bounded pagination for Photo/Lookbook draft lists and event histories.
- Three.js viewer source and offline structural checks.

## Not implemented or not verified

- Actual FASHN live generation and complete Provider-to-Job-to-Output E2E.
- Actual Photo Engine image processing/generation, output persistence and quality evaluation.
- Lookbook SKU/catalog, product variant uniqueness, generated campaign outputs, review/approval and export.
- Video generation, 3D garment simulation, production-grade scene persistence.
- Quote/Pricing and persistent append-only Credit Ledger; accounting policies unresolved.
- PostgreSQL runtime adapter, live PG integration, object storage and multi-host/distributed locking.
- TypeScript typecheck, browser/WebGL runtime, Android E2E and production deployment.
- Full OpenAPI design/runtime alignment; 10/15 matched design operations still drift and 5 design paths are absent.
- QA T-01..T-14 evidence and release gates G0-G5.

## Release decision

BUILD-00095 is an engineering PoC milestone, not a production release. No gate is promoted to PASS. Actual generation remains intentionally unexecuted because Provider credentials, authorized source images, explicit cost approval and rights/retention verification are not available; the user previously deferred live Provider integration. Persistent credits and production data infrastructure remain blocked by unresolved policies and environments.
