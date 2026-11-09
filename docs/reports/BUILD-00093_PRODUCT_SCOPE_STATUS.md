# BUILD-00093 Product Scope Status

This report distinguishes implemented PoC workflows from complete product capabilities. A CRUD endpoint or draft record is not counted as a complete generation feature.

## Implemented / locally tested

| Area | Current implementation | Boundary |
|---|---|---|
| Workspace/RBAC | SQLite workspace membership and owner/admin/editor/viewer role checks | No external IdP, Organization hierarchy or production IAM |
| Project | Workspace-scoped create/list/read/update | No SKU, deletion or ProjectAssetRelation model |
| Character catalog | Workspace-scoped identity/outfit CRUD and asset associations | No full versioned identity profile or commercial character rights workflow |
| 3D Assets | GLB/GLTF upload, validation, private storage, signed preview, Three.js Viewer source | Browser/WebGL runtime not verified |
| Image Assets | PNG/JPEG/WebP upload, Pillow decode/limits, private storage and signed preview | Original bytes/metadata retained; no external Provider delivery |
| AssetVersion | Immutable image/model versions, SHA-256 integrity, history and restore-as-new-version | SQLite/local filesystem crash atomicity not guaranteed |
| AssetRelation | Workspace-scoped typed relationships | Relation deletion/retention policy unresolved |
| Provenance | Append-only upload/version/relation/delete events | Broader cross-feature audit coverage remains partial |
| Generation core | SQLite Job/Execution/Event/Outbox/Worker/Poll lifecycle, retry/reconciliation and output persistence | SQLite single host only; no PostgreSQL/distributed proof |
| Photo Draft | Source/mask/reference image input validation, operation options, draft lifecycle and audit events | Preparation only; no Photo Engine execution/output |
| Lookbook Draft | Multi-product/person images, optional Project/Character, scene preset, planned output count, draft lifecycle/events | Preparation only; no SKU/catalog, generated campaign output, review/approval/export |
| Operations | Worker health, monitoring/alerts, output crash cleanup and lease protections | Single-host SQLite/POSIX scope only |

## Not implemented or not verified

- Actual FASHN live generation and complete Provider-to-Job-to-Output E2E.
- Independent Photo Engine 2D processing, identity/product preservation QA dataset P01-P12, QA-PH-01..16, cost/time/rights evaluation.
- Lookbook SKU/catalog, multi-product variant model, campaign output generation, review, approval and export.
- Video pipeline, 3D garment simulation, production-grade scene/project persistence.
- Quote/Pricing and persistent append-only Credit Ledger. Accounting policy decisions remain unresolved.
- PostgreSQL runtime adapter, live PG integration tests, object storage and multi-host/distributed lease/locking.
- TypeScript typecheck, browser/WebGL runtime, Android E2E and production deployment.
- Complete OpenAPI design/runtime contract alignment.
- QA T-01..T-14 evidence and release gates G0-G5.

## Release decision

This is an engineering PoC milestone, not a production release. No gate is promoted to PASS. Actual generation, provider/legal/cost verification and production data/security checks remain prerequisites before a commercial launch.
