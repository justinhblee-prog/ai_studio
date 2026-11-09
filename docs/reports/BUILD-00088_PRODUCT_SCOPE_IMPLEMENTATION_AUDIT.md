# BUILD-00086 Product Scope ↔ Runtime Implementation Audit

## Basis and method

- Product baseline: `docs/product-baseline/AI_CREATOR_STUDIO_requirements_traceability_matrix_v1_0.md` and `AI_CREATOR_STUDIO_common_data_model_dictionary_v0_1.md`.
- Runtime inspection: FastAPI `app.openapi()`, SQLite table definitions, Backend tests, Viewer source.
- Route comparison: `ai_creator_studio_backend_starter/scripts/audit_openapi_runtime.py` with `/v1` stripped for comparison against the design draft.
- This is a code/source audit, not a production acceptance or Gate approval.

## Requirement coverage

| Requirement | Runtime evidence | Status | Remaining work / boundary |
|---|---|---|---|
| STR-001 Global-first strategy | Conceptual baseline docs | DOCUMENTED ONLY | Country-specific privacy, rights, tax, payments, support and localization not operationally verified. |
| STR-002 B2B paid pilot | No customer/contract/billing workflow | NOT IMPLEMENTED | Customer discovery, pricing, legal, support, refund and paid pilot evidence. |
| STR-003 Asset-first public website | No public marketing website in package | OUT OF CURRENT CODE SCOPE | Requires separate approved website/IA workstream. |
| PRD-001 Organization/Membership/Workspace | Workspace and workspace_members RBAC routes/tables | PARTIAL | No Organization entity or organization-level membership hierarchy. |
| PRD-002 Project/SKU/Asset management | BUILD-00086 adds workspace-scoped Project create/list/read/update; Asset APIs and Character catalog exist | PARTIAL | SKU, ProjectAssetRelation, project-level asset browsing and project-to-job linkage remain absent. |
| PRD-003 Asset ownership/version/derivation | Private workspace Asset metadata and signed preview; Output storage keys | PARTIAL | No immutable AssetVersion/AssetRelation/Provenance domain or original-vs-derived workflow. |
| PRD-004 Upload validation/private storage | Strict single-file GLB/glTF validation, private storage, owner checks | PARTIAL | Original requirement includes image upload; current asset upload only accepts GLB/glTF. No upload-session lifecycle or malware scan. |
| PRD-005 Character Identity Profile | Workspace Character CRUD, identity fields, outfits and asset links | PARTIAL | No immutable profile version history, revision pinning in Job, or profile-to-output provenance. |
| PRD-006 3D Viewer | Three.js GLTF/GLB renderer, OrbitControls, animation controls, AssetWorkspace integration | PARTIAL | No scene save/restore or camera preset persistence; TypeScript build and real browser/WebGL/3-GLB validation not run. |
| PRD-007 Garment Simulation R&D | No garment physics/pattern/body-fit engine | DEFERRED BY PRODUCT BOUNDARY | Must remain a separate R&D gate; Viewer is not simulation. |
| PRD-008 AI Try-on | FASHN adapter, provider registry gate, asynchronous outbox/poll worker, private Output persistence; live smoke harness | PARTIAL / LIVE BLOCKED | No real Provider request/response, cost/latency, output quality, rights/retention proof. Production dispatch intentionally remains blocked. |
| PRD-009 Independent Photo Engine | No 2D post-processing engine or P01–P12 evaluation set | NOT IMPLEMENTED | Separate image-to-image pipeline, quality rubric, cost/rights evidence and APIs required. |
| PRD-010 Lookbook/Campaign | Project record only | NOT IMPLEMENTED | SKU grouping, model/scene/result grouping, review/approval/export workflow absent. |
| PRD-011 Video Pipeline | No temporal generation/frame consistency pipeline | DEFERRED | Separate future pipeline and gate. |
| PRD-012 Marketplace | No listing/purchase/license/entitlement/refund/payout/dispute implementation | DEFERRED | Rights and commerce governance required before any transaction feature. |
| TECH-001 API prefix | Runtime routes use `/v1`; design OpenAPI server URL/prefix is placeholder | PARTIAL | Record ADR and update versioned OpenAPI contract after approval. |
| TECH-002 Generic Job + feature adapters | GenerationJob lifecycle exists for Try-on only | PARTIAL | Photo/Lookbook input schemas and discriminators absent. |
| TECH-003 Photo Job API | No Photo routes | NOT IMPLEMENTED | Requires PhotoInput, quote/create/status/result contract. |
| TECH-004 Job/Execution/Event/Output lifecycle | SQLite tables and repository boundaries exist; events, executions, output and reconciliation paths exist | PARTIAL | Pre-dispatch queued cancellation is implemented in BUILD-00087; in-flight Provider cancellation and full contract alignment remain absent. |
| TECH-005 Output before SUCCEEDED | Atomic Output metadata/Job finalization and immutable attempt files | IMPLEMENTED IN TESTED SQLITE SCOPE | Cross-resource atomicity and distributed storage not guaranteed. |
| TECH-006 Outbox recovery | Durable SQLite Outbox, worker, unknown-outcome quarantine and failure tests | PARTIAL | No external queue publish integration or real process-kill commit/publish test. |
| TECH-007 Provider registry | Provider/model/capability registry and production eligibility flags | PARTIAL | FASHN remains pending live contract/rights verification; no production-ready Provider. |
| TECH-008 Routing policy | MANUAL only; AUTO disabled; no silent fallback | SAFE RESTRICTION IMPLEMENTED | AUTO scoring/fallback needs explicit PO policy and cost ceilings. |
| TECH-009 Credit Ledger | Domain, repository and UoW contracts only | NOT IMPLEMENTED / DECISION BLOCKED | Account scope, precision, expiry/lot, partial capture, refund/adjust and pricing need PO decision. |
| TECH-010 Tenant security | Workspace RBAC, asset ownership checks, private signed preview | PARTIAL | Organization-level isolation and full cross-tenant acceptance evidence absent. |
| TECH-011 Rights/provider governance | Provider registry notes pending evidence | NOT IMPLEMENTED | Provider terms, commercial use, training, region, retention, deletion and input rights review required. |
| TECH-012 Observability | Worker heartbeat, metrics, alerts and operational routes | PARTIAL | Job/provider/cost trace correlation and production alert delivery not validated. |
| TECH-013 Storage/secrets | Local private filesystem, environment-configured secrets | PARTIAL | No S3/object storage, managed Secret Manager/KMS or production retention lifecycle. |
| TECH-014 Deployment architecture | API plus independent workers are runnable locally | PARTIAL | No reproducible deployment, load, backup/restore, scaling or production ops evidence. |
| OPS-001 Review/Approval/Audit | Job events and operations alerts only | NOT IMPLEMENTED | Business review/approval and export gating absent. |
| OPS-002 Usage/Cost | No actual usage/cost ledger | NOT IMPLEMENTED | Real Provider metering and quote-vs-actual reconciliation absent. |
| OPS-003 Unknown outcome/duplicate prevention | Idempotency, outbox quarantine and reconciliation paths | PARTIAL | No provider-side idempotency or client-key lookup guarantee; credit settlement absent. |
| OPS-004 Cancellation | Queued pre-dispatch cancellation endpoint exists (BUILD-00087) | PARTIAL | In-flight Provider cancellation and any credit compensation remain blocked on Provider capability and Credit policy. |
| OPS-005 Original/result comparison | Output API and private assets exist | PARTIAL | AssetVersion/AssetRelation comparison and immutable source linkage absent. |

## Runtime data tables observed

`workspaces`, `workspace_members`, `assets`, `characters`, `character_assets`, `projects`, `generation_jobs`, `generation_executions`, `generation_job_events`, `generation_outputs`, `generation_idempotency`, `generation_outbox`, `generation_poll_tasks`, `generation_worker_heartbeats`, `generation_ops_alerts`, `generation_ops_alert_deliveries`, and `generation_schema_migrations`.

Not observed as implemented tables: Organization, SKU, ProjectAssetRelation, AssetVersion, AssetRelation, Quote, CreditAccount, CreditLedgerEntry, UsageRecord, Review, Approval, License, Entitlement, VideoJob, Marketplace Listing/Purchase/Payout.

## OpenAPI route drift

The design draft has 13 path items. The current FastAPI runtime has 25 path items. After normalizing the runtime `/v1` prefix:

- BUILD-00087 route audit: design-only paths (5): Credit account, Credit ledger, Job executions, plural Job outputs, Quotes. Job cancellation route now exists in both design and runtime inventories.
- Runtime-only paths (17): asset preview URL/preview, engine capabilities/models, singular Job output, reconciliation, health/operations routes, workspaces/members/characters.
- Method gaps (3): runtime adds `GET /assets`, `DELETE /assets/{asset_id}`, and `PUT /projects/{project_id}` beyond the draft.
- `GET /v1/generation-jobs` was added in BUILD-00086; its list is workspace-scoped and paginated.
- BUILD-00088 adds a structural request/response contract audit. It compares 15 matched design operations: 10 show request/response/parameter/operation-ID drift and 5 design operations have no runtime operation. The audit resolves local schema/response references but does not establish semantic or runtime payload conformance. Project create includes the data-model `project_type` extension; Job create uses a Try-on-specific request instead of the generic feature/quote contract; response envelopes and pagination differ.
- Exact route inventory match: `false`. See `BUILD-00088_openapi-runtime-drift.json`.

## Gate status

| Gate | Status | Why it remains open |
|---|---|---|
| G0 | PARTIAL / EVIDENCE PENDING | Source package and local test evidence exist, but no verified Git remote/branch/commit provenance, complete audit pack or deployment inventory. |
| G1 | NOT VERIFIED | Structural source checks only; no 3+ licensed GLB browser run, scene save/restore, responsive/performance or Android evidence. |
| G2 | NOT VERIFIED | Live FASHN request, request ID, result quality, cost/latency, rights and retention evidence absent. |
| G3 | PARTIAL / NOT PASSED | Workspace/Job/Output core tests exist, but Quote/Credit, Project/AssetVersion, in-flight cancellation and full E2E gaps remain. |
| G4 | NOT IMPLEMENTED | Independent Photo Engine and P01–P12 evaluation absent. |
| G5 | NOT VERIFIED | No paid pilot customer, signed terms, billing/refund/support or country readiness evidence. |

## External / PO blockers

1. **Live AI generation cost and access:** FASHN API key, explicit authorization for potentially billable test calls, and model/garment HTTPS URLs for assets the user has rights to use. `scripts/live_fashn_smoke.py` is ready; it remains safely blocked by default. It does not enable production dispatch.
2. **Credit policy decisions:** account ownership scope (Organization vs Workspace), credit precision/unit, expiry/lot behavior, partial capture, refunds and ADJUST rules. Implementing persistent balances without these decisions risks charging or releasing credits incorrectly.
3. **Provider rights:** commercial-use, training, data region, retention/deletion and user-input/output rights must be verified from current terms and accepted by the product owner.
4. **Viewer build/runtime:** npm registry access and React/Three.js dependencies are unavailable in this execution environment; TypeScript and browser/WebGL E2E cannot be completed here.
5. **PostgreSQL:** a reachable PostgreSQL service, driver and isolated test database are required before implementing/enabling a production adapter.

## BUILD-00086 changes

- Recovered the six product-baseline reference documents into the integrated source package.
- Added workspace-scoped Project create/list/read/update API with RBAC and tests. Project deletion, SKU and ProjectAssetRelation remain deliberately absent pending policy.
- Added workspace-scoped, paginated Generation Job listing to close the missing collection read path.
- Added a reproducible OpenAPI/runtime path and method drift audit script plus JSON evidence.
