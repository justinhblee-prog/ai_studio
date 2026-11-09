# BUILD-00096 Product Scope Status

## Implemented and locally tested

- Workspace/RBAC, Project CRUD, Character identity/outfit catalog CRUD.
- Private GLB/GLTF and PNG/JPEG/WebP image assets, validation, signed preview, integrity audit, immutable versions and restore-as-new-version.
- AssetRelation types, two-sided provenance and `derived_from` cycle prevention.
- Workspace Product/SKU catalog with case-insensitive per-Workspace SKU uniqueness, image associations, update/archive and event history.
- Lookbook Drafts can reference Product catalog IDs and/or direct image assets; active references protect Product, image, Project and Character records from destructive state changes.
- Photo Draft input preparation API/UI with source/mask/reference image validation and append-only events.
- Lookbook Draft composition API/UI with multi-product, person image, Project/Character and scene preset references.
- Bounded pagination for Photo/Lookbook/Product collections and event histories.
- Generation Job / Execution / Event / Outbox / Worker / Poll / Output lifecycle at SQLite single-host PoC scope.
- Three.js viewer and Asset/Photo/Product/Lookbook UI source; offline structural checks only.

## Not implemented or not verified

- Actual FASHN live generation and complete Provider-to-Job-to-Output E2E.
- Actual Photo Engine image processing/generation, output persistence and quality evaluation.
- Lookbook generated campaign outputs, review/approval and export.
- Product variants (size/color/fit), SKU hierarchy, pricing, inventory, barcode, marketplace/PIM sync.
- Video generation, 3D garment simulation, production-grade scene persistence.
- Quote/Pricing and persistent append-only Credit Ledger; accounting policies unresolved.
- PostgreSQL runtime adapter, live PG integration, object storage and multi-host/distributed locking.
- TypeScript typecheck, browser/WebGL runtime, Android E2E and production deployment.
- Full OpenAPI design/runtime alignment; 10/15 matched design operations still drift and 5 design paths are absent.
- QA T-01..T-14 evidence and release gates G0-G5.

## Release decision

BUILD-00096 is an engineering PoC milestone, not a production release. No gate is promoted to PASS. Actual generation remains intentionally unexecuted because Provider credentials, authorized source images, explicit cost approval and rights/retention verification are not available; the user previously deferred live Provider integration. Persistent credits and production data infrastructure remain blocked by unresolved policies and environments.
