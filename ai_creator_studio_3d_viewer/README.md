# AI CREATOR STUDIO — 3D Viewer + Asset Workspace v0.6

## Included modules

- `Studio3DViewer`: actual Three.js WebGL viewer with GLTFLoader, OrbitControls, camera framing, grid, animation controls, resize handling and resource cleanup.
- `AssetWorkspace`: React workspace panel that uploads GLB/GLTF files, lists owner-scoped model assets, requests short-lived signed preview URLs, displays the selected model in `Studio3DViewer`, deletes assets, and loads/restores verified historical asset versions as new immutable versions.
- `PhotoDraftWorkspace`: React workspace for private PNG/JPEG/WebP source images and non-billable Photo Drafts. It supports deterministic local Pillow processing, exact AssetVersion previews, output review decisions, and metadata-only manifest export. It does not generate images with AI, submit Provider requests, or charge credits.
- `ProductCatalogWorkspace`: React workspace catalog for SKU create/edit/archive, product image references, size/color Product Variant create/edit/archive, and variant-specific image selection/editing.
- `ProjectWorkspace`: React workspace project create/list/edit with active/completed/archived lifecycle states; active Lookbook reference guards are enforced by the backend.
- `LookbookDraftWorkspace`: React campaign workspace that groups catalog Products/Variants, direct product images and person images with optional Project and Character. It supports planning review/approval, attachment of individually approved Photo runs, ordered output assembly, a separate assembly review, and internal-only ZIP/metadata-manifest export after approval. It does not generate campaign images with AI, call Providers, or charge credits.
- `docs/ASSET_API_CONTRACT_v0.1.md`: API/security contract and implementation status.

## Integration

```tsx
import { AssetWorkspace, PhotoDraftWorkspace, LookbookDraftWorkspace, ProductCatalogWorkspace, ProjectWorkspace } from 'ai-creator-studio-3d-viewer';

export function CharacterAssets({ apiBaseUrl, accessToken, workspaceId }) {
  return <AssetWorkspace
    apiBaseUrl={apiBaseUrl}
    accessToken={accessToken}
    workspaceId={workspaceId}
  />;
}

export function PhotoStudio({ apiBaseUrl, accessToken, workspaceId }) {
  return <PhotoDraftWorkspace apiBaseUrl={apiBaseUrl} accessToken={accessToken} workspaceId={workspaceId} />;
}

export function ProductCatalog({ apiBaseUrl, accessToken, workspaceId }) {
  return <ProductCatalogWorkspace apiBaseUrl={apiBaseUrl} accessToken={accessToken} workspaceId={workspaceId} />;
}

export function ProjectManager({ apiBaseUrl, accessToken, workspaceId }) {
  return <ProjectWorkspace apiBaseUrl={apiBaseUrl} accessToken={accessToken} workspaceId={workspaceId} />;
}

export function LookbookStudio({ apiBaseUrl, accessToken, workspaceId }) {
  return <LookbookDraftWorkspace apiBaseUrl={apiBaseUrl} accessToken={accessToken} workspaceId={workspaceId} />;
}
```

The host application must supply a short-lived bearer token and the API base URL. Do not persist access tokens in local storage. Configure backend `APP_CORS_ORIGINS` with exact app origins for cross-origin deployments; same-origin reverse proxy is preferred.

## Dependencies and validation

- React 18+
- Three.js 0.180+
- TypeScript 5.8+

Run `npm install` then `npm run typecheck` in a network-enabled dependency environment. The current execution environment cannot resolve the npm registry and does not contain React/Three.js dependencies or typings, so full semantic TypeScript compilation remains unverified. `python scripts/validate_source.py` performs offline structural checks (75/75 currently pass); it does not prove TypeScript compilation or browser rendering. Version restore is provided by `POST /v1/assets/{asset_id}/versions/{version_id}/restore`; the versions list includes an `is_current` flag. Photo Draft UI uses `POST /v1/assets/images`, `/v1/photo-drafts`, and deterministic `/process-local` operations; Product Catalog UI uses `/v1/products` and `/variants`; Lookbook UI uses `/v1/lookbook-drafts`, output attachment/review routes, and gated internal package-export routes. These are not AI generation interfaces. See the project-level [`FEATURE_SCOPE_STATUS.md`](../docs/FEATURE_SCOPE_STATUS.md) for the current feature matrix and verification boundaries.

## Backend requirements

Use the companion backend included in the same source snapshot (current backend module v0.6). Configure `ASSET_API_TOKENS`, `ASSET_SIGNING_SECRET`, `ASSET_STORAGE_DIR`, `ASSET_DATABASE_PATH`, and (for cross-origin use) `APP_CORS_ORIGINS`. The local private filesystem adapter is PoC-only. Production needs private object storage, managed secrets, workspace membership/RBAC, and a production identity provider.

Create the workspace for the authenticated user with `POST /v1/workspaces` before mounting `AssetWorkspace`. For collaboration, the owner/admin adds other authenticated user IDs with `POST /v1/workspaces/{workspace_id}/members` and an explicit role.

- `LookbookDraftWorkspace`: supports non-billable planning drafts, review/approval, individually approved Photo result attachment, separate output-assembly review, and internal-only ZIP/manifest export after assembly approval. AI campaign generation, Provider dispatch, credit charging, publication, and commercial-rights grants are not included.


## API contract validation

Run `python3 scripts/validate_api_contract.py` (or `npm run validate:api-contract`) to check Viewer fetch paths, HTTP methods, and query parameter names against the committed runtime OpenAPI snapshot. This is source-level validation, not browser E2E or payload-schema validation. See `docs/VIEWER_API_INTEGRATION_AUDIT_BUILD-00114.md`.


## Viewer response contract validation

Run `python3 scripts/validate_viewer_response_contract.py` (or `npm run validate:response-contract`) to check every Viewer `fetch()` endpoint against the committed FastAPI runtime OpenAPI success response schema. The validator expands the known action unions and fails on missing runtime routes, missing JSON success schemas, or unresolved dynamic segments. This is static contract coverage, not runtime payload fixture validation or browser E2E. See `docs/VIEWER_RESPONSE_CONTRACT_AUDIT_BUILD-00117.md`.

## Runtime response coverage

The companion backend now provides `python scripts/verify_viewer_runtime_coverage.py`, which runs the backend integration suite and verifies successful HTTP JSON execution coverage for all Viewer JSON endpoints (47/47 at BUILD-00119). This is stronger than the static OpenAPI audit, but it remains TestClient coverage and does not prove browser execution.


## Offline package integrity validation

Run `python3 scripts/validate_package_integrity.py` (or `npm run validate:package-integrity`) to check npm script targets, relative TS/TSX/CSS imports, declared external dependencies, the public `src/index.ts` exports, and TypeScript source inclusion. This is a packaging/source consistency check; it does not replace `tsc --noEmit`, dependency installation, or browser E2E. The TypeScript syntax checker recursively scans nested `src/` directories. The animation-frame lifecycle controller is covered by `npm run test:animation-frame-controller`; it verifies single-frame ownership, idempotent stop/restart, and render-failure isolation. This helper test does not replace a real React/Three browser E2E.

## Optional browser/WebGL2 environment probe

Install the optional browser-audit dependency with `pip install -r requirements-browser-audit.txt`. With Chromium and Xvfb available, run `xvfb-run -a python3 scripts/probe_browser_runtime.py` (or `npm run probe:browser-runtime` inside the same Xvfb session). The probe compiles and draws a WebGL2 triangle and checks ResizeObserver/requestAnimationFrame. It verifies browser-engine capability only; it does not load or validate the React/Three.js Viewer.
