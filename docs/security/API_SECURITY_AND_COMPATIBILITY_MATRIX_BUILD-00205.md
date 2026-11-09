# API Security & Compatibility Matrix — BUILD-00205

Date: 2026-11-06  
Status: implemented runtime policy inventory; not a replacement for product/legal approval.

## 1. Authentication model

- API identity is resolved by `app.assets.routes.current_user` from an explicit `Authorization: Bearer <token>` header and the configured token-to-user mapping (`asset_api_tokens`). Missing/unknown tokens fail with HTTP 401.
- Workspace authorization is membership-based. A missing membership is deliberately reported as HTTP 404; an existing membership without the required role is HTTP 403.
- Route handlers are the API authorization boundary. Repository/domain functions accept explicit workspace/actor identifiers and are not independently an end-user authentication system. New routes must authenticate and authorize before invoking them.
- Platform operations are separately gated by `OPS_ADMIN_USER_IDS`; workspace ownership alone does not imply platform-operations access.

## 2. Workspace role matrix

| Capability | Owner | Admin | Editor | Viewer |
|---|---:|---:|---:|---:|
| Read workspace assets, projects, characters, products, drafts, jobs, events and outputs | Yes | Yes | Yes | Yes |
| Upload/update/archive assets, projects, characters, products and ordinary drafts | Yes | Yes | Yes | No |
| Approve/reject generated output and Lookbook review decisions | Yes | Yes | No | No |
| Retry Output→Asset link / reconcile provider submission / retry Poll Task | Yes | Yes | No | No |
| Add workspace members | Yes | Yes | No | No |
| Access platform worker/metrics/alert operations | Only if separately allowlisted in `OPS_ADMIN_USER_IDS` | Same | Same | Same |

Notes:
- Workspace membership management accepts `admin`, `editor`, or `viewer` for newly added members; the API does not permit creating another `owner` through this endpoint.
- `workspace_id` must be applied to resource reads and writes. Resource IDs alone are not sufficient authorization evidence.
- Cross-workspace asset references are rejected by product/character/lookbook validation paths.

## 3. Deliberately public routes

| Route | Public behavior | Rationale / boundary |
|---|---|---|
| `GET /health` | Returns only `{ok, version}` | Liveness probe; does not disclose worker IDs, queue counts, provider mode, or operational topology. |
| `GET /v1/engines/capabilities` | Public capability catalogue | Product discovery metadata; no tenant data. |
| `GET /v1/engines/models` | Public model catalogue and configured indicator | Discovery metadata only; no credentials or provider request data. |
| `GET /v1/assets/{asset_id}/preview` | Short-lived HMAC-signed capability URL | URL is issued only after live workspace membership check; bearer capability is limited to 15 minutes and private/no-store response. Membership revocation does not revoke an already issued asset URL; expiration is the revocation bound. |
| `GET /v1/assets/{asset_id}/versions/{version_id}/preview` | Short-lived HMAC-signed immutable-version capability URL | Issued only after membership and version integrity checks; historical version bytes remain pinned. Membership revocation does not revoke an already issued asset URL; expiration is the revocation bound. |

The signed preview endpoints are the only intentional unauthenticated private-byte routes. They are capability URLs, not anonymous listing or discovery endpoints. For workflows requiring immediate membership re-check, use the authenticated `preview-content` route.

## 4. Authenticated route groups

- `/v1/workspaces/**`: bearer identity plus membership/owner/admin checks.
- `/v1/assets/**` except the two signed preview GETs: bearer identity plus workspace membership; writes require owner/admin/editor.
- `/v1/characters/**`, `/v1/projects/**`, `/v1/photo-drafts/**`, `/v1/lookbook-drafts/**`, `/v1/products/**`, `/v1/project-products/**`: bearer identity plus workspace role checks.
- `/v1/generation-jobs/**`: bearer identity plus workspace membership; destructive/recovery/review operations require owner/admin or editor as specified by route policy.
- `/internal/ops/**`: bearer identity plus platform allowlist for platform-wide worker, metrics, and alert diagnostics; workspace-scoped Poll Task recovery additionally requires workspace owner/admin.

A route-registration regression test walks FastAPI dependency trees and fails if a new route lacks `current_user` unless its exact method/path is in the explicit public allowlist. Internal operations routes are independently asserted to require authentication.

## 5. BUILD-00205 security change

The public `/health` endpoint previously returned Worker health counts, Outbox counts, and Poll Task counts. Those operational details are now private to `/internal/ops/workers` and `/internal/ops/metrics`; public health returns only `ok` and API version. This reduces information disclosure without changing the operational monitoring interfaces.

## 6. API design/runtime compatibility policy

- `docs/api/openapi.runtime.v1.json` is the authoritative generated contract for implemented behavior. `docs/product-baseline/AI_CREATOR_STUDIO_openapi_integrated_draft_v0_2.yaml` remains a target design draft.
- Do not silently alter runtime envelopes, pagination, status codes, operation IDs, auth semantics, or request requirements merely to reduce structural drift. Each compatibility change requires consumer impact review and a deliberate migration/versioning decision.
- Known deferred differences from the earlier reconciliation remain: limit/offset rather than design cursor pagination; optional rather than mandatory `Idempotency-Key`; queued-only cancellation with current Job response; absent credit-account/ledger/quote operations pending billing semantics; runtime-only routes; and generated operation-ID stability.
- No PostgreSQL adapter, billing contract, credit reservation semantics, or publication/commercial-rights permission is implied by this matrix.

## 7. Remaining risks / follow-up

1. Replace configured static bearer-token mapping with a production identity provider, token rotation/revocation, and auditable session lifecycle before public production launch.
2. Decide whether signed asset preview URLs need immediate revocation. If yes, switch clients to authenticated fetch-to-blob or add a revocation-aware capability store; current expiry is at most 15 minutes.
3. Add explicit permission scopes for future marketplace publishing, payments, billing, and organization-level administration; current workspace roles do not encode those product policies.
4. Verify semantic TypeScript/React integration, live PostgreSQL, and actual AI provider execution only when external-test approval and required infrastructure/credentials are available.

## 8. Verification scope

BUILD-00205 adds an API route authentication-surface test and tests that public health exposes no operational counters. These tests inspect registered FastAPI routes and their dependency trees; they do not constitute penetration testing or external identity-provider validation.
