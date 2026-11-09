# BUILD-00111 Verification Report

## Scope

Approval-gated private ZIP package of exact Lookbook output AssetVersions, signed download, package integrity/audit and expiry cleanup.

## Commands and results

| Check | Result | Notes |
|---|---|---|
| `PYTHONPATH=. pytest -q` | PASS — 340 passed | Full backend suite |
| `PYTHONPATH=. python -m compileall -q app scripts tests` | PASS | Backend/scripts/tests compilation |
| `python scripts/cleanup_expired_lookbook_exports.py` | PASS — 0 inspected, 0 removed | Dry-run default; audit rows retained |
| `python scripts/validate_source.py` | PASS — 65/65 | Offline UI/source structural checks only |
| `python scripts/audit_openapi_runtime.py` | Completed; exact match false | 13 design paths vs 80 runtime paths |
| `python scripts/audit_openapi_contract.py` | Completed with known drift | 15 design operations, 12 structural drifts, 3 unmatched (credit account, ledger, quote) |
| `npm run typecheck` | NOT VERIFIED | React/Three.js modules and declarations unavailable (`TS2307`) |
| Browser/WebGL/Android E2E | NOT RUN | Browser/device runtime not provisioned |

## Package export tests

- Package export is blocked until the Lookbook plan and output assembly are separately approved.
- Viewer role cannot create a package; workspace viewers can read export history.
- ZIP includes ordered exact-version images and `manifest.json`; manifest declares internal-use-only, no publication/public distribution/commercial rights.
- Each image entry carries page order, AssetVersion ID, checksum, size, Product/Variant SKU and caption.
- Signed download URL rejects tampered and expired signatures.
- Download verifies full package size and SHA-256; tampered package file is rejected.
- Package export history is append-only.
- Limits: 100 pages and 250 MiB total source bytes.

## API additions

- `GET /v1/lookbook-drafts/{draft_id}/outputs/exports`
- `POST /v1/lookbook-drafts/{draft_id}/outputs/package-export`
- `GET /v1/lookbook-drafts/exports/{export_id}/download` (signed URL)

## Retention

- Signed URL: 15 minutes.
- Package file expiry: 24 hours.
- Cleanup script: `scripts/cleanup_expired_lookbook_exports.py` (dry-run default; `--apply` deletes expired files while retaining audit rows).

## Boundaries

- ZIP is private internal-use handoff only; it does not grant copyright, likeness/consent, brand, publication, public distribution or commercial-use rights.
- SQLite/local filesystem only; PostgreSQL, object storage, multi-host and production deployment remain unverified. G0-G5 remain unpassed.
