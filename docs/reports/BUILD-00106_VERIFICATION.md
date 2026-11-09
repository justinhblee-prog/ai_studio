# BUILD-00106 Verification Report

## Scope

Photo local-output review/approval, immutable AssetVersion/Provenance/checksum snapshots, append-only review/export audit, metadata-only internal manifest, and PhotoDraftWorkspace review UI.

## Commands and results

| Check | Result | Notes |
|---|---|---|
| `PYTHONPATH=. pytest -q` | PASS — 337 passed | Full backend suite |
| `PYTHONPATH=. python -m compileall -q app scripts tests` | PASS | Backend/scripts/tests compilation |
| `python scripts/validate_source.py` | PASS — 54/54 | Offline UI/source structural checks only |
| `python scripts/audit_openapi_runtime.py` | Completed; exact match false | 13 design paths vs 69 runtime paths |
| `python scripts/audit_openapi_contract.py` | Completed with known drift | 15 design operations, 12 structural drifts, 3 unmatched (credit account, ledger, quote) |
| `npm run typecheck` | NOT VERIFIED | React/Three.js modules and declarations unavailable (`TS2307`) |
| Browser/WebGL/Android E2E | NOT RUN | Browser/device runtime not provisioned |

## Photo output review/export tests

- Review is available only for succeeded local Photo runs with a valid immutable output AssetVersion and `asset.photo_processed` provenance.
- Workspace viewer can read; viewer cannot decide or export. Owner/admin can approve/request changes/reject; owner/admin/editor can export a manifest.
- Request-changes and reject require comments. `changes_requested` can be reviewed again; `approved`/`rejected` are terminal.
- Review events snapshot Asset ID, immutable AssetVersion ID, Provenance ID and checksum.
- Version integrity checks the exact version file path, recorded size and SHA-256; it does not rely on the current Asset version pointer.
- Uploading v2 after approving v1 does not change the v1 approval; manifest remains bound to the reviewed v1.
- Export is blocked until approved and snapshot equality is confirmed. Manifest contains metadata only, includes a canonical SHA-256 and append-only audit event, and excludes binary/publication/commercial rights.
- SQLite triggers reject UPDATE/DELETE against review and export event tables.

## API additions

- `GET /v1/photo-drafts/{draft_id}/runs/{run_id}/review`
- `POST /v1/photo-drafts/{draft_id}/runs/{run_id}/review/approve`
- `POST /v1/photo-drafts/{draft_id}/runs/{run_id}/review/request-changes`
- `POST /v1/photo-drafts/{draft_id}/runs/{run_id}/review/reject`
- `POST /v1/photo-drafts/{draft_id}/runs/{run_id}/export-manifest`

## Boundaries

- Review approval is an internal visual/workflow decision, not copyright, likeness/consent, brand, legal, publication or commercial-use clearance.
- Export is metadata-only; no binary files, public URL or rights grant.
- Underlying ENHANCE/LIGHTING remains deterministic Pillow processing, not generative AI. BACKGROUND/RETOUCH/COMPOSE require a future real AI Photo Engine.
- SQLite/local filesystem only; PostgreSQL, object storage, multi-host and production deployment remain unverified. G0-G5 remain unpassed.
