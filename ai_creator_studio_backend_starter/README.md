# AI CREATOR STUDIO Backend Starter v0.7

FastAPI PoC backend for virtual try-on workflow, authenticated private 3D/image assets, and non-billable Photo/Lookbook draft preparation.

## Run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set unique ASSET_API_TOKENS and ASSET_SIGNING_SECRET values before using asset routes.
uvicorn app.main:app --reload
# In separate terminals, run the durable workers:
python -m app.worker
python -m app.poll_worker
python -m app.output_asset_link_worker
```

## Private 3D asset API

- `POST /v1/assets` — multipart upload (`workspace_id`, `file`); requires `Authorization: Bearer <token>`.
- `GET /v1/assets?workspace_id=<id>` — list assets belonging to the authenticated user and workspace.
- `GET /v1/assets/{asset_id}` — owner-only metadata lookup.
- `POST /v1/assets/{asset_id}/preview-url` — owner-only short-lived signed preview URL.
- `GET /v1/assets/{asset_id}/preview?expires=...&signature=...` — read-only signed capability URL.
- `DELETE /v1/assets/{asset_id}` — owner-only logical metadata deletion and local file removal.

Set `APP_CORS_ORIGINS` to an explicit comma-separated allowlist when the browser app uses a different origin; same-origin reverse proxy deployments may leave it empty. Do not use wildcard origins.

Configure `ASSET_API_TOKENS` as comma-separated `token:user_id` entries and `ASSET_SIGNING_SECRET` as a unique random secret of at least 32 characters. Never commit real secrets. Uploaded files are stored outside the public `/outputs` directory. The default local adapter is for development/PoC only; production should replace it with private S3-compatible object storage and managed secrets.

## Current security boundaries

- Server-side GLB/GLTF 2.0 validation; external buffer/image URIs are blocked.
- Upload size cap; server determines MIME from validated file structure, not the browser-provided MIME.
- Bearer token authentication and owner-scoped metadata operations.
- Preview URLs are HMAC-signed, read-only, short-lived, and `private, no-store`.
- Generation Jobs, Executions, Events, Output metadata, Idempotency, Outbox and Provider Poll Tasks are stored in SQLite.
- Job GET is read-only; Provider status polling and output persistence run in the dedicated `app.poll_worker` process.
- Provider submission and polling are separate worker processes. Submission outcome ambiguity is never automatically replayed.
- Poll GET/output tasks use leases, bounded exponential backoff and a capped standard `Retry-After` response header when present.
- Workspace membership/role records are stored in SQLite and enforced on generation routes.
- SQLite/WAL is a single-host PoC persistence layer; PostgreSQL and multi-instance locking are not yet implemented.

## Tests

```bash
PYTHONPATH=. python -m pytest -q
```

272 backend tests pass in the current verification environment. This does not constitute browser/WebGL or production deployment verification.

## Browser integration

The companion viewer package now includes `AssetWorkspace`, which calls these endpoints and passes the signed preview URL to the Three.js viewer. See the integrated package README for the React usage example. Browser-side integration source exists, but TypeScript compilation and real browser/WebGL rendering remain unverified because npm dependencies could not be installed in this execution environment.

## Workspace API and roles

- `POST /v1/workspaces` — create a workspace; creator becomes `owner`.
- `GET /v1/workspaces` — list workspaces for the authenticated user.
- `POST /v1/workspaces/{workspace_id}/members` — owner/admin adds a member as `admin`, `editor`, or `viewer`.

Asset access is checked against workspace membership. `owner`/`admin`/`editor` may upload and delete; all four roles may list, inspect and request a preview URL. Preview URLs are short-lived signed read-only capabilities. Workspace membership is stored in SQLite. The v0.5-to-v0.6 initialization path bootstraps existing asset owners into workspace membership records.

## Generation workers (BUILD-00102)

Run four processes in deployment: API (`uvicorn app.main:app`), submission/outbox worker (`python -m app.worker`), Provider poll/output worker (`python -m app.poll_worker`), and Output→Asset linker (`python -m app.output_asset_link_worker`). The poll worker claims durable `generation_poll_tasks`; after successful Output finalization, it atomically inserts a durable `generation_output_asset_links` task. The independent linker imports the private image into the Asset store, creates immutable AssetVersion and Provenance rows, and acknowledges the Generation DB outbox only after the Asset DB commit. The API Job GET endpoint never calls the Provider. Polling retry defaults are 2s base, 300s exponential cap, 12 attempts, and 900s maximum accepted `Retry-After`. Expired poll leases are safe to requeue because status polling is GET; submission outbox lease expiry remains `needs_reconciliation` because provider acceptance may be ambiguous.


### Operations monitor (v0.19)

Run the monitor as a fifth independent process beside the API and four workers:

```bash
python -m app.monitor_worker
```

Owner/admin-only diagnostics:
- `GET /internal/ops/workers` — worker heartbeat status
- `GET /internal/ops/metrics` — Prometheus text exposition
- `GET /internal/ops/alerts` — active operational alerts and queue snapshot

Alert checks cover required worker heartbeat loss, stale outbox/poll queues, and tasks awaiting reconciliation. `output_asset_link` is included in the default required worker set. Alerts are persisted and deduplicated by fingerprint. Optional webhook delivery is disabled by default; configure `OPS_ALERT_WEBHOOK_URL` with an HTTPS endpoint and optionally `OPS_ALERT_WEBHOOK_TOKEN`. Delivery retries are bounded. The monitor does not send job payloads, source images, or user identifiers to the webhook.


## Opt-in live FASHN sandbox smoke

The Provider adapter remains production-blocked until contract, rights, cost and retention evidence is approved. To perform a **separate real, potentially billable Provider smoke test** with images you are authorized to use, configure the following environment variables in a private shell (never commit the key):

```bash
export FASHN_API_KEY='…'
export FASHN_LIVE_TEST_CONFIRM_COST=I_UNDERSTAND_PROVIDER_MAY_CHARGE
export FASHN_LIVE_TEST_MODEL_IMAGE_URL='https://…'
export FASHN_LIVE_TEST_GARMENT_IMAGE_URL='https://…'
python scripts/live_fashn_smoke.py
```

The script directly exercises FASHN start/status and downloads/validates the returned image in a temporary directory. It does not create a Generation Job, does not prove commercial rights or retention terms, and does not enable production dispatch. It logs neither API keys nor signed URLs. A timeout may leave a remote generation running; do not blindly resubmit.


## Project and Job listing (BUILD-00086)

- `POST /v1/projects` — create a project using a workspace ID in the request body.
- `GET /v1/projects?workspace_id=...` — list projects in an authorized workspace.
- `GET /v1/projects/{project_id}` — read a project after workspace authorization.
- `PUT /v1/projects/{project_id}` — update project metadata/status. Use `ARCHIVED` rather than deletion; destructive project deletion is not exposed.
- `GET /v1/generation-jobs?workspace_id=...&limit=50&offset=0` — list workspace jobs with bounded pagination.

SKU uniqueness, ProjectAssetRelation semantics, Organization hierarchy, and Project deletion behavior remain unimplemented pending product/data policy. The imported OpenAPI v0.2 draft is a design baseline and is not fully aligned with runtime routes; see `../docs/reports/BUILD-00086_PRODUCT_SCOPE_IMPLEMENTATION_AUDIT.md`.

## Contract drift audit

Install the optional audit dependency and compare the imported OpenAPI draft with FastAPI's runtime route inventory:

```bash
pip install -r requirements-audit.txt
python scripts/audit_openapi_runtime.py --output ../docs/reports/runtime-openapi-drift.json
python scripts/audit_openapi_runtime.py --strict  # non-zero while known drift remains
```

## Asset version history, relations and provenance (BUILD-00090)

- `POST /v1/assets/{asset_id}/versions` accepts a validated GLB/GLTF multipart file, stores an immutable version snapshot, and promotes it as the current asset version.
- `GET /v1/assets/{asset_id}/versions` lists version number, checksum, size, creator and timestamp without exposing private storage keys.
- `POST /v1/assets/{asset_id}/relations` creates a same-workspace relation (`derived_from`, `variant_of`, `uses_texture`, `paired_with`); `GET .../relations` lists incoming/outgoing links.
- `GET /v1/assets/{asset_id}/provenance` returns paginated append-only upload/version/relation/delete events.
- Read APIs allow all workspace roles; version/relation mutations require owner/admin/editor. Asset deletion removes all version files.
- This remains SQLite/local-filesystem PoC functionality. DB/filesystem atomic commit, PostgreSQL, distributed storage, and browser UI for version/relation/provenance are not implemented or verified.

## Image source assets and Photo Engine draft preparation (BUILD-00092)

- `POST /v1/assets/images` — workspace editor uploads one PNG, JPEG, or WebP source image. Pillow verifies the detected format, extension agreement, complete pixel decode, single-frame constraint, byte limit, and bounded dimensions/pixel count. Client MIME is not trusted.
- `GET /v1/assets?workspace_id=<id>&kind=image|model|all` — filter workspace assets by media kind. The 3D AssetWorkspace requests `kind=model` so source photographs are not passed to GLTFLoader.
- Image assets use the same private storage, checksum, integrity audit, immutable version history, and signed preview URL lifecycle. New versions must preserve the asset kind. Historical image versions can be restored as new versions after checksum and image decode verification.
- `POST /v1/photo-drafts` — create a non-billable Photo Engine preparation draft using an active same-workspace image `source_asset_id`; optional mask and reference image IDs are also workspace-scoped. Supported operations: `ENHANCE`, `BACKGROUND`, `LIGHTING`, `RETOUCH`, `COMPOSE`.
- `GET /v1/photo-drafts?workspace_id=<id>` lists active drafts; `GET /{draft_id}?workspace_id=<id>` reads one; `PUT /{draft_id}` updates input; `POST /{draft_id}/archive?workspace_id=<id>` archives without deleting the audit trail; `GET /{draft_id}/events?workspace_id=<id>` reads append-only draft events.
- An active Photo Draft protects its referenced image assets from deletion (HTTP 409). Archive the draft first; the draft and its event history remain retained.

**Important boundary:** Photo Draft is input preparation and validation only. It does not create a Generation Job, Quote, Credit reservation, Provider request, or output image. No AI generation is claimed or simulated. The independent 2D Photo Engine execution path and real image-quality validation remain unimplemented.

## Lookbook campaign preparation (BUILD-00093)

- `POST /v1/lookbook-drafts` — create a non-billable workspace draft grouping one or more product image assets, an optional person image, an optional active Project and Character, a scene preset, and planned output count (1..20).
- `GET /v1/lookbook-drafts?workspace_id=<id>` lists active drafts; `GET /{draft_id}?workspace_id=<id>` reads one; `PUT /{draft_id}` revises it; `POST /{draft_id}/archive?workspace_id=<id>` archives it; `GET /{draft_id}/events?workspace_id=<id>` returns append-only history.
- All product/person references must be active same-workspace image assets. Project must be active and in the workspace; Character must be active and in the workspace.
- Active Lookbook Drafts protect referenced images, Projects, and Characters from deletion/archive transitions (HTTP 409). Archive the draft first to release these active-reference protections while retaining its history.
- `LookbookDraftWorkspace` is the companion React preparation UI.

**Historical BUILD-00093 boundary:** at that build, the Lookbook workflow was limited to composition preparation. The current implementation has since added catalog SKU/Variant selection, planning review/approval, approved Photo-run output attachment, ordered assembly review, and gated internal package/manifest export. AI campaign generation, Provider execution, Quote/Credit, publication, and commercial-rights grants remain out of scope.

### Current Lookbook output workflow (BUILD-00110+)

- Approved Photo Draft runs can be attached to a Lookbook draft as exact immutable AssetVersion references, with optional Product/Variant association, page order and caption.
- Output assembly has a separate snapshot-based review lifecycle: submit, approve or reject. Output attachment is frozen after review starts; manifest/package export is allowed only after assembly approval and integrity verification.
- The package export is a private internal-use ZIP with expiring signed download URL and checksum metadata. It does not authorize publication or commercial use. The metadata manifest remains distinct from the binary package.
- The UI supports planning approval, output attachment, assembly review, exact-version previews, internal package creation and download. It does not generate new campaign images or invoke an AI Provider.

Photo Draft and Lookbook Draft list APIs support bounded pagination (`limit` 1..100, `offset` >=0) and return `total`, `limit`, and `offset`. Event-history APIs support `limit` 1..500 and `offset`. The companion preparation UIs request up to 100 active drafts.

## Product / SKU catalog (BUILD-00096)

- `POST /v1/products` — create a workspace product with a SKU, name, category, description and 1..12 active same-workspace image assets.
- `GET /v1/products?workspace_id=<id>&limit=50&offset=0` — list active products with total counts and bounded pagination; `include_archived=true` includes archived catalog entries.
- `GET /v1/products/{product_id}?workspace_id=<id>` — read a product and ordered image asset references.
- `PUT /v1/products/{product_id}` — update SKU/metadata/images; `POST /{product_id}/archive?workspace_id=<id>` archives non-destructively; `GET /{product_id}/events` reads append-only history.
- SKU uniqueness is case-insensitive within a Workspace. Product image references are active image assets only. Active Products protect their images from deletion; archive the Product before deleting an unused image.
- Lookbook Draft accepts catalog `product_ids` and/or direct `product_asset_ids`. Catalog Products must be active and have active images. Active Lookbook Drafts prevent Product archival until the draft is archived.
- `ProductCatalogWorkspace` manages SKUs/images; `LookbookDraftWorkspace` can select catalog Products and direct image assets.

This is a lightweight workspace catalog for Lookbook planning, not a commerce/PIM integration. Product create/update/archive and Product Variants with option values, independent SKUs, variant-specific image selection/editing and archive lifecycle are implemented; marketplace sync, price/inventory, barcode and multi-organization SKU namespaces are not implemented.

## Viewer runtime JSON response coverage (BUILD-00119)

Run `python scripts/verify_viewer_runtime_coverage.py` from this backend directory. The command executes the complete backend pytest suite, captures successful HTTP JSON responses produced by the integration tests, and compares the observed method/path pairs with all JSON-success endpoints consumed by the Viewer. It fails if any Viewer endpoint has no successful runtime exercise. This is local TestClient integration coverage; it does not replace browser E2E, TypeScript compilation, WebGL device testing, or production infrastructure validation.


## Current implementation scope (BUILD-00122)

The Lookbook workflow has advanced beyond the original BUILD-00093 composition-only draft. The current UI/backend supports planning review, approved Photo output attachment as immutable AssetVersions, ordered assembly, separate snapshot-based assembly review, and integrity-gated internal ZIP/manifest export. Product Variants with unique workspace SKUs and option values are implemented.

The workflow still does not generate new AI campaign images, dispatch a Provider, quote/charge credits, publish content, or grant commercial rights. Lookbook package exports are internal-use-only. See the project-level `docs/FEATURE_SCOPE_STATUS.md` for the current cross-module feature and verification matrix.


## Supabase Auth (BUILD-00226)

For hosted browser sessions, configure `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and the exact frontend origin in `APP_CORS_ORIGINS`. The API validates each bearer access token against the Supabase Auth `/auth/v1/user` endpoint and uses the returned user ID for existing Workspace membership checks. When Supabase Auth is configured, `ASSET_API_TOKENS` is ignored. Static token mapping is retained only for local compatibility when both Supabase settings are absent.

The browser uses only `VITE_SUPABASE_URL` and the project's publishable/anon key. Never expose `SUPABASE_SERVICE_ROLE_KEY` in browser code or any `VITE_` variable.

**Important:** BUILD-00226 does not make the backend production-durable. Runtime repositories still default to SQLite; `DATABASE_BACKEND=postgresql` fails closed until the full PostgreSQL repository and worker integration passes live tests. The Supabase Auth identity bridge does not imply that app records are stored in Supabase PostgreSQL.
